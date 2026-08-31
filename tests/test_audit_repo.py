import json
from pathlib import Path
import subprocess

import pytest

from scripts.audit_repo import (
    AuditReport,
    Finding,
    Severity,
    audit_repository,
    exit_code,
    main,
    render_json,
)


PROJECT_TESTS = {
    "00-agent-eval-harness": ("tests/test_eval.py", ""),
    "01-agent-control-plane": ("src/test/java/example/ControlTest.java", "class ControlTest {}\n"),
    "02-verified-browser-ops-agent": ("tests/test_agent.py", ""),
    "03-governed-mysql-data-agent": ("tests/test_agent.py", ""),
    "04-java-migration-agent": ("tests/test_planner.py", ""),
    "05-evidence-deep-research-agent": ("tests/test_research.py", ""),
    "06-a2a-spring-boot-starter": ("src/test/java/example/TaskTest.java", "class TaskTest {}\n"),
}


def _write(root: Path, relative: str, content: str | bytes = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )


def _stage(root: Path, *paths: str, force: bool = False) -> None:
    args = ["add"]
    if force:
        args.append("-f")
    args.extend(paths)
    _git(root, *args)


@pytest.fixture
def clean_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "audit@example.invalid")
    _git(tmp_path, "config", "user.name", "Audit Test")

    _write(
        tmp_path,
        ".gitignore",
        "__pycache__/\n.pytest_cache/\ntarget/\n*.pyc\n.env\n",
    )
    _write(tmp_path, "README.md", "# Clean repository\n")
    _write(tmp_path, "CURRENT_STATE.md", "# Current state\n")
    _write(
        tmp_path,
        "requirements-dev.txt",
        "-r 03-governed-mysql-data-agent/requirements.txt\npytest==9.1.1\n",
    )
    _write(
        tmp_path,
        "03-governed-mysql-data-agent/requirements.txt",
        "sqlglot==30.13.0\nmysql-connector-python==9.7.0\n",
    )

    for project, (test_path, content) in PROJECT_TESTS.items():
        _write(tmp_path, f"{project}/{test_path}", content)

    pom = (
        "<project><properties><java.version>21</java.version></properties>"
        "<dependencies><dependency><groupId>example</groupId>"
        "<artifactId>demo</artifactId></dependency></dependencies></project>"
    )
    _write(tmp_path, "01-agent-control-plane/pom.xml", pom)
    _write(tmp_path, "06-a2a-spring-boot-starter/pom.xml", pom)
    _write(tmp_path, "scripts/validate_all.py", "")
    _write(
        tmp_path,
        "scripts/acceptance_gate.py",
        """
def build_checks(root):
    return [
        Check('validation', (python, 'scripts/validate_all.py'), root),
        Check('gate tests', (python, '-m', 'pytest', '-q', 'tests/test_acceptance_gate.py'), root),
        Check('python tests', (python, '-m', 'pytest', '-q'), root / '00-agent-eval-harness'),
        Check('benchmark', (python, '-m', 'benchmark', '--gate', 'config/03_regression_gate.json'), root / '00-agent-eval-harness'),
    ]
""".lstrip(),
    )
    _write(tmp_path, "tests/test_acceptance_gate.py", "")
    _write(tmp_path, "00-agent-eval-harness/config/03_regression_gate.json", "{}\n")
    _write(
        tmp_path,
        ".github/workflows/ci.yml",
        "steps:\n  - name: Audit\n    run: python scripts/acceptance_gate.py\n",
    )
    _stage(tmp_path, ".")
    return tmp_path


def _findings(report: AuditReport, check_id: str) -> list[Finding]:
    return [finding for finding in report.findings if finding.check_id == check_id]


def test_clean_repository_fixture_passes(clean_repo: Path):
    report = audit_repository(clean_repo)

    assert report.status == "PASS"
    assert report.findings == ()


def test_tracked_large_file_is_reported(clean_repo: Path):
    _write(clean_repo, "assets/large.bin", b"x" * (1024 * 1024))
    _stage(clean_repo, "assets/large.bin")

    report = audit_repository(clean_repo)

    finding = _findings(report, "LARGE001")[0]
    assert finding.path == "assets/large.bin"
    assert finding.severity is Severity.INFO
    assert "1048576 bytes" in finding.evidence


def test_debt_marker_reports_path_line_and_marker(clean_repo: Path):
    _write(clean_repo, "src/app.py", "value = 1\n# TODO: replace prototype\n")
    _stage(clean_repo, "src/app.py")

    report = audit_repository(clean_repo)

    finding = _findings(report, "DEBT001")[0]
    assert finding.path == "src/app.py"
    assert finding.line == 2
    assert "TODO marker" in finding.evidence


def test_missing_readme_local_link_is_reported(clean_repo: Path):
    _write(clean_repo, "README.md", "[missing](docs/missing.md)\n")
    _stage(clean_repo, "README.md")

    report = audit_repository(clean_repo)

    finding = _findings(report, "DOC002")[0]
    assert finding.path == "README.md"
    assert finding.line == 1
    assert "docs/missing.md" in finding.evidence


def test_tracked_dotenv_is_high(clean_repo: Path):
    _write(clean_repo, ".env", "PASSWORD=example\n")
    _stage(clean_repo, ".env", force=True)

    report = audit_repository(clean_repo)

    finding = _findings(report, "SEC001")[0]
    assert finding.severity is Severity.HIGH
    assert report.status == "FAIL"


def test_private_key_detection_redacts_material(clean_repo: Path):
    header = "-----BEGIN " + "PRIVATE KEY-----"
    secret_material = "never-print-this-private-material"
    _write(clean_repo, "config/data.txt", f"{header}\n{secret_material}\n")
    _stage(clean_repo, "config/data.txt")

    report = audit_repository(clean_repo)
    finding = _findings(report, "SEC004")[0]
    serialized = render_json(report)

    assert finding.severity is Severity.HIGH
    assert "redacted" in finding.evidence
    assert secret_material not in serialized


def test_dynamic_secret_assignments_are_not_reported(clean_repo: Path):
    _write(
        clean_repo,
        "src/config.py",
        "password = config.password\napi_key = read_environment('API_KEY')\n",
    )
    _stage(clean_repo, "src/config.py")

    report = audit_repository(clean_repo)

    assert _findings(report, "SEC007") == []


def test_literal_secret_assignment_is_redacted(clean_repo: Path):
    secret_value = "a-real-looking-value-123"
    _write(clean_repo, "src/config.py", f"api_key = '{secret_value}'\n")
    _stage(clean_repo, "src/config.py")

    report = audit_repository(clean_repo)
    finding = _findings(report, "SEC007")[0]

    assert finding.severity is Severity.HIGH
    assert secret_value not in render_json(report)


def test_warning_result_returns_exit_zero():
    report = AuditReport(
        (
            Finding(
                "TEST001",
                "debt_markers",
                Severity.WARNING,
                "src/app.py",
                "advisory evidence",
                "review it",
            ),
        )
    )

    assert report.status == "WARN"
    assert exit_code(report) == 0


def test_high_result_returns_exit_one():
    report = AuditReport(
        (
            Finding(
                "TEST002",
                "secret_risk",
                Severity.HIGH,
                ".env",
                "high-confidence evidence",
                "rotate it",
            ),
        )
    )

    assert report.status == "FAIL"
    assert exit_code(report) == 1


def test_json_output_is_valid_and_contains_required_fields(clean_repo: Path, capsys):
    result = main(["--json"], root=clean_repo)

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == 0
    assert captured.err == ""
    assert payload["status"] == "PASS"
    assert payload["summary"] == {"high": 0, "info": 0, "warning": 0}
    assert isinstance(payload["findings"], list)


def test_ignored_and_untracked_artifacts_do_not_produce_findings(clean_repo: Path):
    _write(clean_repo, "target/generated.class", b"compiled")
    _write(clean_repo, ".env", "PASSWORD=not-a-real-secret\n")
    _write(clean_repo, "notes.untracked", "TODO: local note\n")

    report = audit_repository(clean_repo)

    assert report.status == "PASS"
    assert report.findings == ()


def test_test_fixture_marker_string_is_not_reported(clean_repo: Path):
    _write(clean_repo, "tests/fixtures/debt.txt", "TODO: expected fixture value\n")
    _stage(clean_repo, "tests/fixtures/debt.txt")

    report = audit_repository(clean_repo)

    assert _findings(report, "DEBT001") == []


def test_obvious_undeclared_import_is_reported(clean_repo: Path):
    _write(clean_repo, "src/app.py", "import requests\n")
    _stage(clean_repo, "src/app.py")

    report = audit_repository(clean_repo)

    finding = _findings(report, "PYDEP005")[0]
    assert finding.path == "src/app.py"
    assert "requests" in finding.evidence


def test_java_version_mismatch_is_reported_without_scanning_fixture_pom(clean_repo: Path):
    _write(
        clean_repo,
        "01-agent-control-plane/pom.xml",
        "<project><properties><java.version>17</java.version></properties></project>",
    )
    _write(
        clean_repo,
        "04-java-migration-agent/fixtures/legacy-app/pom.xml",
        "<project><properties><java.version>8</java.version></properties></project>",
    )
    _stage(clean_repo, "01-agent-control-plane/pom.xml", "04-java-migration-agent/fixtures/legacy-app/pom.xml")

    report = audit_repository(clean_repo)

    mismatches = _findings(report, "JAVA003")
    assert len(mismatches) == 1
    assert mismatches[0].path == "01-agent-control-plane/pom.xml"


def test_default_run_does_not_write_report_file(clean_repo: Path, capsys):
    before = {path.relative_to(clean_repo) for path in clean_repo.rglob("*")}

    result = main([], root=clean_repo)
    after = {path.relative_to(clean_repo) for path in clean_repo.rglob("*")}

    assert result == 0
    assert "AUDIT RESULT: PASS" in capsys.readouterr().out
    assert after == before

def test_pyproject_conflict_with_requirements_is_reported(clean_repo: Path):
    _write(
        clean_repo,
        "pyproject.toml",
        '[project]\ndependencies = ["sqlglot==31.0.0"]\n',
    )
    _stage(clean_repo, "pyproject.toml")

    report = audit_repository(clean_repo)

    finding = _findings(report, "PYDEP003")[0]
    assert "sqlglot" in finding.evidence
