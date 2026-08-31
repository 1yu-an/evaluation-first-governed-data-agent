#!/usr/bin/env python3
"""Deterministic, read-only repository audit.

The audit reports static repository facts. It deliberately does not run tests,
build projects, benchmark behavior, update dependencies, or modify source files.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import asdict, dataclass
from enum import Enum
import json
import tomllib
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Iterable, Sequence
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 * 1024


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"


@dataclass(frozen=True)
class Finding:
    check_id: str
    category: str
    severity: Severity
    path: str
    evidence: str
    recommendation: str
    line: int | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


@dataclass(frozen=True)
class ProjectSpec:
    path: str
    test_path: str
    test_glob: str


@dataclass(frozen=True)
class AuditConfig:
    info_file_bytes: int = MIB
    warning_file_bytes: int = 5 * MIB
    high_file_bytes: int = 20 * MIB
    required_docs: tuple[str, ...] = ("README.md", "CURRENT_STATE.md")
    python_dependency_files: tuple[str, ...] = (
        "requirements-dev.txt",
        "03-governed-mysql-data-agent/requirements.txt",
    )
    java_projects: tuple[str, ...] = (
        "01-agent-control-plane",
        "06-a2a-spring-boot-starter",
    )
    projects: tuple[ProjectSpec, ...] = (
        ProjectSpec("00-agent-eval-harness", "tests", "test_*.py"),
        ProjectSpec("01-agent-control-plane", "src/test", "*Test.java"),
        ProjectSpec("02-verified-browser-ops-agent", "tests", "test_*.py"),
        ProjectSpec("03-governed-mysql-data-agent", "tests", "test_*.py"),
        ProjectSpec("04-java-migration-agent", "tests", "test_*.py"),
        ProjectSpec("05-evidence-deep-research-agent", "tests", "test_*.py"),
        ProjectSpec("06-a2a-spring-boot-starter", "src/test", "*Test.java"),
    )


CATEGORY_ORDER = (
    ("git_hygiene", "Git hygiene"),
    ("large_files", "Large tracked files"),
    ("debt_markers", "Technical-debt markers"),
    ("secret_risk", "Secret risk"),
    ("dependencies", "Dependency hygiene"),
    ("documentation", "Documentation hygiene"),
    ("structure", "Project / test structure"),
)

CACHE_BUILD_DIRS = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "venv",
        "node_modules",
        "build",
        "dist",
        "coverage",
        "htmlcov",
        "target",
    }
)
GENERATED_FILE_NAMES = frozenset({".ds_store", "thumbs.db", "desktop.ini"})
GENERATED_SUFFIXES = frozenset(
    {
        ".pyc",
        ".pyo",
        ".class",
        ".swp",
        ".swo",
        ".tmp",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".log",
        ".bak",
    }
)
SOURCE_DOC_SUFFIXES = frozenset(
    {
        ".py",
        ".java",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".go",
        ".rs",
        ".c",
        ".h",
        ".cpp",
        ".cs",
        ".sql",
        ".sh",
        ".ps1",
        ".md",
        ".rst",
        ".adoc",
        ".txt",
        ".toml",
        ".yml",
        ".yaml",
    }
)
TEST_DATA_PARTS = frozenset({"test", "tests", "fixtures", "cases", "evals"})
TEMPLATE_ENV_NAMES = frozenset({".env.example", ".env.sample", ".env.template"})
PRIVATE_KEY_NAMES = frozenset({"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"})
CREDENTIAL_FILE_NAMES = frozenset(
    {
        "credentials.json",
        "credential.json",
        "secrets.json",
        "secret.json",
        "service-account.json",
        "service_account.json",
    }
)
PRIVATE_KEY_SUFFIXES = frozenset({".key", ".p12", ".pfx"})

MARKER_NAMES = ("TO" + "DO", "FIX" + "ME", "HA" + "CK", "X" + "XX")
MARKER_RE = re.compile(r"\b(" + "|".join(MARKER_NAMES) + r")\b", re.IGNORECASE)
PRIVATE_KEY_HEADER_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
)
AWS_ACCESS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
GITHUB_TOKEN_RE = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)^\s*(password|passwd|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)\b"
    r"\s*(?:=|:)\s*(?P<quote>[\"'])(?P<value>[^\"'\r\n]+)(?P=quote)"
)
UNQUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)^\s*(password|passwd|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)\b"
    r"\s*(?:=|:)\s*(?P<value>[^\s,#;]{12,})"
)
UNQUOTED_SECRET_SUFFIXES = frozenset({".env", ".ini", ".cfg", ".conf", ".toml", ".yml", ".yaml"})
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
PYTHON_SCRIPT_RE = re.compile(
    r"\bpython(?:3(?:\.\d+)?)?\s+(?!-m\b)[\"']?([^\"'\s`]+\.py)",
    re.IGNORECASE,
)
REQUIREMENT_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*(.*)$")

IMPORT_TO_DISTRIBUTION = {"mysql": "mysql-connector-python"}


class AuditError(RuntimeError):
    """The repository could not be audited reliably."""


@dataclass(frozen=True)
class AuditReport:
    findings: tuple[Finding, ...]

    @property
    def status(self) -> str:
        if any(item.severity is Severity.HIGH for item in self.findings):
            return "FAIL"
        if any(item.severity is Severity.WARNING for item in self.findings):
            return "WARN"
        return "PASS"

    @property
    def summary(self) -> dict[str, int]:
        return {
            "high": sum(item.severity is Severity.HIGH for item in self.findings),
            "warning": sum(item.severity is Severity.WARNING for item in self.findings),
            "info": sum(item.severity is Severity.INFO for item in self.findings),
        }

    def to_dict(self) -> dict[str, object]:
        checks = []
        for category, label in CATEGORY_ORDER:
            category_findings = [item for item in self.findings if item.category == category]
            checks.append(
                {
                    "id": category,
                    "name": label,
                    "status": _category_status(category_findings),
                    "finding_count": len(category_findings),
                }
            )
        return {
            "status": self.status,
            "summary": self.summary,
            "checks": checks,
            "findings": [item.to_dict() for item in self.findings],
        }


def _category_status(findings: Sequence[Finding]) -> str:
    if any(item.severity is Severity.HIGH for item in findings):
        return "FAIL"
    if any(item.severity is Severity.WARNING for item in findings):
        return "WARN"
    if findings:
        return "INFO"
    return "PASS"


def _sort_findings(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    severity_order = {Severity.HIGH: 0, Severity.WARNING: 1, Severity.INFO: 2}
    category_order = {category: index for index, (category, _) in enumerate(CATEGORY_ORDER)}
    return tuple(
        sorted(
            findings,
            key=lambda item: (
                category_order.get(item.category, len(category_order)),
                severity_order[item.severity],
                item.path.casefold(),
                item.line or 0,
                item.check_id,
            ),
        )
    )


def git_tracked_files(root: Path) -> tuple[str, ...]:
    """Return tracked file paths exactly as Git records them, including Unicode."""

    try:
        completed = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise AuditError(f"git could not start: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise AuditError(f"git ls-files failed: {detail or f'exit {completed.returncode}'}")
    return tuple(
        sorted(
            (
                chunk.decode("utf-8", errors="surrogateescape").replace("\\", "/")
                for chunk in completed.stdout.split(b"\0")
                if chunk
            ),
            key=str.casefold,
        )
    )


def _absolute(root: Path, tracked_path: str) -> Path:
    return root.joinpath(*PurePosixPath(tracked_path).parts)


def _read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def audit_git_hygiene(tracked: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    for tracked_path in tracked:
        pure = PurePosixPath(tracked_path)
        parts = {part.casefold() for part in pure.parts}
        name = pure.name.casefold()
        suffix = pure.suffix.casefold()
        if parts & CACHE_BUILD_DIRS or name in GENERATED_FILE_NAMES or suffix in GENERATED_SUFFIXES:
            findings.append(
                Finding(
                    "GIT001",
                    "git_hygiene",
                    Severity.WARNING,
                    tracked_path,
                    "A common cache, build output, or generated artifact is tracked by Git.",
                    "Remove the generated artifact from version control and keep an appropriate ignore rule.",
                )
            )
        elif ".idea" in parts:
            findings.append(
                Finding(
                    "GIT002",
                    "git_hygiene",
                    Severity.WARNING,
                    tracked_path,
                    "An IntelliJ project metadata file is tracked by Git.",
                    "Confirm it is intentionally shared; otherwise untrack the IDE metadata.",
                )
            )
        elif ".vscode" in parts:
            findings.append(
                Finding(
                    "GIT003",
                    "git_hygiene",
                    Severity.INFO,
                    tracked_path,
                    "A VS Code workspace file is tracked; this can be intentional for shared settings.",
                    "Keep it only when the workspace setting is intentionally shared and contains no local paths.",
                )
            )
        elif name.endswith("~"):
            findings.append(
                Finding(
                    "GIT004",
                    "git_hygiene",
                    Severity.WARNING,
                    tracked_path,
                    "A common editor backup file is tracked by Git.",
                    "Untrack the temporary backup and add a narrow ignore rule if needed.",
                )
            )
    return findings


def audit_large_files(
    root: Path,
    tracked: Sequence[str],
    config: AuditConfig,
) -> list[Finding]:
    findings: list[Finding] = []
    for tracked_path in tracked:
        path = _absolute(root, tracked_path)
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size < config.info_file_bytes:
            continue
        if size >= config.high_file_bytes:
            severity = Severity.HIGH
            threshold = config.high_file_bytes
        elif size >= config.warning_file_bytes:
            severity = Severity.WARNING
            threshold = config.warning_file_bytes
        else:
            severity = Severity.INFO
            threshold = config.info_file_bytes
        findings.append(
            Finding(
                "LARGE001",
                "large_files",
                severity,
                tracked_path,
                f"Tracked file size is {size} bytes ({size / MIB:.2f} MiB); threshold is {threshold} bytes.",
                "Confirm the file belongs in Git; use an artifact store or Git LFS when ordinary Git is unsuitable.",
            )
        )
    return findings


def _is_test_data_path(path: PurePosixPath) -> bool:
    lowered = {part.casefold() for part in path.parts}
    return bool(lowered & TEST_DATA_PARTS) or path.name.casefold().startswith("test_")


def audit_debt_markers(root: Path, tracked: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    for tracked_path in tracked:
        pure = PurePosixPath(tracked_path)
        if pure.suffix.casefold() not in SOURCE_DOC_SUFFIXES or _is_test_data_path(pure):
            continue
        text = _read_text(_absolute(root, tracked_path))
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = MARKER_RE.search(line)
            if not match:
                continue
            marker = match.group(1).upper()
            excerpt = " ".join(line.strip().split())[:180]
            findings.append(
                Finding(
                    "DEBT001",
                    "debt_markers",
                    Severity.WARNING,
                    tracked_path,
                    f"{marker} marker: {excerpt}",
                    "Resolve the marker or link it to a maintained issue with enough context for ownership.",
                    line_number,
                )
            )
    return findings


def _placeholder_secret(value: str) -> bool:
    lowered = value.casefold()
    placeholders = (
        "example",
        "sample",
        "dummy",
        "fake",
        "placeholder",
        "changeme",
        "replace",
        "change-me",
        "not-set",
        "not_set",
        "your_",
        "your-",
    )
    return (
        len(value) < 12
        or any(token in lowered for token in placeholders)
        or value.startswith("${")
        or (value.startswith("<") and value.endswith(">"))
    )


def audit_secret_risks(root: Path, tracked: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    for tracked_path in tracked:
        pure = PurePosixPath(tracked_path)
        name = pure.name.casefold()
        suffix = pure.suffix.casefold()
        if name == ".env" or (name.startswith(".env.") and name not in TEMPLATE_ENV_NAMES):
            findings.append(
                Finding(
                    "SEC001",
                    "secret_risk",
                    Severity.HIGH,
                    tracked_path,
                    "A runtime environment file is tracked by Git.",
                    "Remove it from Git history, rotate exposed credentials, and keep only a redacted template.",
                )
            )
        if name in PRIVATE_KEY_NAMES or suffix in PRIVATE_KEY_SUFFIXES:
            findings.append(
                Finding(
                    "SEC002",
                    "secret_risk",
                    Severity.HIGH,
                    tracked_path,
                    "A private-key-like filename is tracked by Git.",
                    "Verify the file immediately; remove it from history and rotate the key if it is private material.",
                )
            )
        elif name in CREDENTIAL_FILE_NAMES:
            findings.append(
                Finding(
                    "SEC003",
                    "secret_risk",
                    Severity.WARNING,
                    tracked_path,
                    "A credential-like filename is tracked; filename alone does not prove a secret is present.",
                    "Confirm the file contains only safe templates or remove and rotate any real credentials.",
                )
            )

        text = _read_text(_absolute(root, tracked_path))
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if PRIVATE_KEY_HEADER_RE.search(line):
                findings.append(
                    Finding(
                        "SEC004",
                        "secret_risk",
                        Severity.HIGH,
                        tracked_path,
                        "A PEM private-key header was detected; key material is redacted.",
                        "Remove the key from Git history and rotate the corresponding credential.",
                        line_number,
                    )
                )
            if AWS_ACCESS_KEY_RE.search(line):
                findings.append(
                    Finding(
                        "SEC005",
                        "secret_risk",
                        Severity.HIGH,
                        tracked_path,
                        "An AWS access-key-shaped value was detected and redacted.",
                        "Revoke or rotate the credential and remove it from Git history.",
                        line_number,
                    )
                )
            if GITHUB_TOKEN_RE.search(line):
                findings.append(
                    Finding(
                        "SEC006",
                        "secret_risk",
                        Severity.HIGH,
                        tracked_path,
                        "A GitHub-token-shaped value was detected and redacted.",
                        "Revoke the token and remove it from Git history.",
                        line_number,
                    )
                )
            assignment = SECRET_ASSIGNMENT_RE.search(line)
            if assignment is None and (
                (name.startswith(".env") and name not in TEMPLATE_ENV_NAMES)
                or suffix in UNQUOTED_SECRET_SUFFIXES
            ):
                assignment = UNQUOTED_SECRET_ASSIGNMENT_RE.search(line)
            if assignment and not _placeholder_secret(assignment.group("value")):
                variable = assignment.group(1)
                value = assignment.group("value")
                findings.append(
                    Finding(
                        "SEC007",
                        "secret_risk",
                        Severity.HIGH,
                        tracked_path,
                        f"High-confidence hard-coded {variable} assignment detected; value redacted ({len(value)} characters).",
                        "Move the secret to an approved runtime secret source and rotate it if it was exposed.",
                        line_number,
                    )
                )
    return findings


@dataclass(frozen=True)
class RequirementRecord:
    name: str
    specifier: str
    path: str
    line: int


def _normalize_distribution(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).casefold()


def _parse_requirements(
    root: Path,
    relative_path: str,
    seen: set[str],
    findings: list[Finding],
) -> list[RequirementRecord]:
    normalized_path = PurePosixPath(relative_path).as_posix()
    if normalized_path in seen:
        return []
    seen.add(normalized_path)
    path = _absolute(root, normalized_path)
    text = _read_text(path)
    if text is None:
        return []
    records: list[RequirementRecord] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith(("-r ", "--requirement ")):
            include_name = line.split(maxsplit=1)[1].strip()
            include_path = (PurePosixPath(normalized_path).parent / include_name).as_posix()
            if not _absolute(root, include_path).is_file():
                findings.append(
                    Finding(
                        "PYDEP002",
                        "dependencies",
                        Severity.WARNING,
                        normalized_path,
                        f"Requirement include does not exist: {include_path}",
                        "Correct the include path or add the declared dependency file.",
                        line_number,
                    )
                )
            else:
                records.extend(_parse_requirements(root, include_path, seen, findings))
            continue
        if line.startswith("-"):
            continue
        requirement = line.split(";", 1)[0].strip()
        match = REQUIREMENT_RE.match(requirement)
        if not match:
            continue
        records.append(
            RequirementRecord(
                _normalize_distribution(match.group(1)),
                match.group(2).strip(),
                normalized_path,
                line_number,
            )
        )
    return records

def _requirement_record(text: str, path: str, line: int = 1) -> RequirementRecord | None:
    requirement = text.split(";", 1)[0].strip()
    match = REQUIREMENT_RE.match(requirement)
    if not match:
        return None
    return RequirementRecord(
        _normalize_distribution(match.group(1)),
        match.group(2).strip(),
        path,
        line,
    )


def _parse_pyproject(root: Path, relative_path: str, findings: list[Finding]) -> list[RequirementRecord]:
    path = _absolute(root, relative_path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        findings.append(
            Finding(
                "PYDEP006",
                "dependencies",
                Severity.WARNING,
                relative_path,
                f"pyproject.toml could not be parsed: {type(exc).__name__}",
                "Repair the TOML dependency declaration.",
            )
        )
        return []

    raw_requirements: list[str] = []
    project = data.get("project", {})
    if isinstance(project, dict):
        dependencies = project.get("dependencies", [])
        if isinstance(dependencies, list):
            raw_requirements.extend(item for item in dependencies if isinstance(item, str))
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    raw_requirements.extend(item for item in group if isinstance(item, str))

    tool = data.get("tool", {})
    poetry = tool.get("poetry", {}) if isinstance(tool, dict) else {}
    poetry_dependencies = poetry.get("dependencies", {}) if isinstance(poetry, dict) else {}
    if isinstance(poetry_dependencies, dict):
        for name, value in poetry_dependencies.items():
            if name.casefold() == "python":
                continue
            specifier = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
            raw_requirements.append(f"{name}{specifier}")

    records: list[RequirementRecord] = []
    for requirement in raw_requirements:
        record = _requirement_record(requirement, relative_path)
        if record is not None:
            records.append(record)
    return records



def _local_import_names(tracked: Sequence[str]) -> set[str]:
    names = {"src", "scripts", "tests"}
    for tracked_path in tracked:
        pure = PurePosixPath(tracked_path)
        if pure.name == "__init__.py" and len(pure.parts) >= 2:
            names.add(pure.parent.name)
        elif len(pure.parts) == 1 and pure.suffix == ".py":
            names.add(pure.stem)
    return names


def _third_party_imports(root: Path, tracked: Sequence[str]) -> dict[str, tuple[str, int]]:
    imports: dict[str, tuple[str, int]] = {}
    local_names = _local_import_names(tracked)
    stdlib = getattr(sys, "stdlib_module_names", frozenset())
    for tracked_path in tracked:
        pure = PurePosixPath(tracked_path)
        if pure.suffix.casefold() != ".py":
            continue
        text = _read_text(_absolute(root, tracked_path))
        if text is None:
            continue
        try:
            tree = ast.parse(text, filename=tracked_path)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            candidates: list[str] = []
            if isinstance(node, ast.Import):
                candidates = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                candidates = [node.module.split(".", 1)[0]]
            for module in candidates:
                if module in stdlib or module in local_names or module.startswith("_"):
                    continue
                imports.setdefault(module, (tracked_path, getattr(node, "lineno", 1)))
    return imports


def _xml_text_by_local_name(root: ET.Element, local_name: str) -> str | None:
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == local_name and element.text:
            return element.text.strip()
    return None


def _java_dependency_findings(root: Path, projects: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    for project in projects:
        relative = f"{project}/pom.xml"
        path = _absolute(root, relative)
        if not path.is_file():
            findings.append(
                Finding(
                    "JAVA001",
                    "dependencies",
                    Severity.WARNING,
                    relative,
                    "Required Maven dependency declaration is missing.",
                    "Restore pom.xml for the Java project.",
                )
            )
            continue
        try:
            xml_root = ET.fromstring(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ET.ParseError) as exc:
            findings.append(
                Finding(
                    "JAVA002",
                    "dependencies",
                    Severity.WARNING,
                    relative,
                    f"pom.xml could not be parsed: {type(exc).__name__}",
                    "Repair the Maven XML declaration.",
                )
            )
            continue
        java_version = _xml_text_by_local_name(xml_root, "java.version")
        if java_version != "21":
            findings.append(
                Finding(
                    "JAVA003",
                    "dependencies",
                    Severity.WARNING,
                    relative,
                    f"java.version is {java_version!r}; repository requirement is '21'.",
                    "Align the Java project declaration with Java 21 after reviewing compatibility.",
                )
            )
        seen_dependencies: set[tuple[str, str]] = set()
        for element in xml_root.iter():
            if element.tag.rsplit("}", 1)[-1] != "dependency":
                continue
            group = _xml_text_by_local_name(element, "groupId")
            artifact = _xml_text_by_local_name(element, "artifactId")
            if not group or not artifact:
                findings.append(
                    Finding(
                        "JAVA004",
                        "dependencies",
                        Severity.WARNING,
                        relative,
                        "A Maven dependency is missing groupId or artifactId.",
                        "Complete or remove the malformed dependency declaration.",
                    )
                )
                continue
            coordinate = (group, artifact)
            if coordinate in seen_dependencies:
                findings.append(
                    Finding(
                        "JAVA005",
                        "dependencies",
                        Severity.WARNING,
                        relative,
                        f"Duplicate Maven dependency declaration: {group}:{artifact}",
                        "Keep one authoritative dependency declaration.",
                    )
                )
            seen_dependencies.add(coordinate)
    return findings


def audit_dependencies(
    root: Path,
    tracked: Sequence[str],
    config: AuditConfig,
) -> list[Finding]:
    findings: list[Finding] = []
    records: list[RequirementRecord] = []
    seen_requirement_files: set[str] = set()
    dependency_files = set(config.python_dependency_files)
    dependency_files.update(
        tracked_path
        for tracked_path in tracked
        if PurePosixPath(tracked_path).name.casefold().startswith("requirements")
        and PurePosixPath(tracked_path).suffix.casefold() == ".txt"
    )
    for dependency_file in sorted(dependency_files):
        if not _absolute(root, dependency_file).is_file():
            findings.append(
                Finding(
                    "PYDEP001",
                    "dependencies",
                    Severity.WARNING,
                    dependency_file,
                    "Expected Python dependency declaration is missing.",
                    "Restore the dependency file or update the audit configuration deliberately.",
                )
            )
            continue
        records.extend(
            _parse_requirements(root, dependency_file, seen_requirement_files, findings)
        )

    for pyproject in sorted(
        tracked_path
        for tracked_path in tracked
        if PurePosixPath(tracked_path).name.casefold() == "pyproject.toml"
    ):
        records.extend(_parse_pyproject(root, pyproject, findings))

    by_name: dict[str, list[RequirementRecord]] = {}
    for record in records:
        by_name.setdefault(record.name, []).append(record)
    for name, declarations in sorted(by_name.items()):
        specifiers = {item.specifier for item in declarations}
        locations = {(item.path, item.line) for item in declarations}
        if len(specifiers) > 1:
            detail = ", ".join(
                f"{item.path}:{item.line}={item.specifier or '<unversioned>'}"
                for item in declarations
            )
            findings.append(
                Finding(
                    "PYDEP003",
                    "dependencies",
                    Severity.WARNING,
                    declarations[0].path,
                    f"Conflicting declarations for {name}: {detail}",
                    "Choose one compatible, authoritative requirement declaration.",
                    declarations[0].line,
                )
            )
        elif len(locations) > 1:
            findings.append(
                Finding(
                    "PYDEP004",
                    "dependencies",
                    Severity.INFO,
                    declarations[0].path,
                    f"The same direct requirement for {name} is declared in multiple files.",
                    "Prefer one authoritative declaration and include it where practical.",
                    declarations[0].line,
                )
            )

    declared = set(by_name)
    for module, (path, line) in sorted(_third_party_imports(root, tracked).items()):
        distribution = _normalize_distribution(IMPORT_TO_DISTRIBUTION.get(module, module))
        if distribution in declared:
            continue
        findings.append(
            Finding(
                "PYDEP005",
                "dependencies",
                Severity.WARNING,
                path,
                f"Third-party import {module!r} has no matching declared Python dependency.",
                "Declare the distribution in an existing dependency file after confirming the import is required.",
                line,
            )
        )

    findings.extend(_java_dependency_findings(root, config.java_projects))
    return findings


def _markdown_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    target = unquote(target)
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or target.startswith(("#", "//")):
        return None
    path = parsed.path
    if not path:
        return None
    return path.replace("\\", "/")


def _markdown_link_findings(root: Path, tracked: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    for tracked_path in tracked:
        pure = PurePosixPath(tracked_path)
        if pure.suffix.casefold() != ".md":
            continue
        text = _read_text(_absolute(root, tracked_path))
        if text is None:
            continue
        in_fence = False
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in MARKDOWN_LINK_RE.finditer(line):
                target = _markdown_target(match.group(1))
                if target is None:
                    continue
                resolved = _absolute(root, (pure.parent / target).as_posix())
                if resolved.exists():
                    continue
                findings.append(
                    Finding(
                        "DOC002",
                        "documentation",
                        Severity.WARNING,
                        tracked_path,
                        f"Markdown local link target does not exist: {target}",
                        "Correct or remove the stale local link.",
                        line_number,
                    )
                )
    return findings


def _script_reference_findings(root: Path, tracked: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    candidates = [
        tracked_path
        for tracked_path in tracked
        if PurePosixPath(tracked_path).name.casefold() == "readme.md"
        or (
            tracked_path.startswith(".github/workflows/")
            and PurePosixPath(tracked_path).suffix.casefold() in {".yml", ".yaml"}
        )
    ]
    for tracked_path in candidates:
        pure = PurePosixPath(tracked_path)
        text = _read_text(_absolute(root, tracked_path))
        if text is None:
            continue
        workflow = tracked_path.startswith(".github/workflows/")
        working_directory = PurePosixPath(".")
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if workflow and stripped.startswith("- name:"):
                working_directory = PurePosixPath(".")
            elif workflow and stripped.startswith("working-directory:"):
                working_directory = PurePosixPath(stripped.split(":", 1)[1].strip())
            for match in PYTHON_SCRIPT_RE.finditer(line):
                script = match.group(1).replace("\\", "/")
                base = working_directory if workflow else pure.parent
                relative = (base / script).as_posix()
                if _absolute(root, relative).is_file():
                    continue
                findings.append(
                    Finding(
                        "DOC003",
                        "documentation",
                        Severity.WARNING,
                        tracked_path,
                        f"Referenced Python script does not exist: {relative}",
                        "Correct the command so it references an existing repository script.",
                        line_number,
                    )
                )
    return findings


def audit_documentation(
    root: Path,
    tracked: Sequence[str],
    config: AuditConfig,
) -> list[Finding]:
    findings: list[Finding] = []
    for required in config.required_docs:
        if _absolute(root, required).is_file():
            continue
        findings.append(
            Finding(
                "DOC001",
                "documentation",
                Severity.WARNING,
                required,
                "Required root documentation file is missing.",
                "Restore the factual repository documentation entry point.",
            )
        )
    findings.extend(_markdown_link_findings(root, tracked))
    findings.extend(_script_reference_findings(root, tracked))
    return findings


def _path_from_root_expression(node: ast.AST) -> PurePosixPath | None:
    if isinstance(node, ast.Name) and node.id == "root":
        return PurePosixPath(".")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _path_from_root_expression(node.left)
        if left is not None and isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
            return left / node.right.value
    return None


def _acceptance_target_findings(root: Path) -> list[Finding]:
    relative = "scripts/acceptance_gate.py"
    path = _absolute(root, relative)
    if not path.is_file():
        return [
            Finding(
                "STRUCT003",
                "structure",
                Severity.WARNING,
                relative,
                "Acceptance Gate entry point is missing.",
                "Restore the existing acceptance entry point.",
            )
        ]
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    except (OSError, UnicodeError, SyntaxError) as exc:
        return [
            Finding(
                "STRUCT004",
                "structure",
                Severity.WARNING,
                relative,
                f"Acceptance Gate references could not be inspected: {type(exc).__name__}",
                "Repair the entry point so its static targets can be audited.",
            )
        ]
    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = node.func.id if isinstance(node.func, ast.Name) else ""
        if function_name != "Check" or len(node.args) < 2:
            continue
        cwd = PurePosixPath(".")
        if len(node.args) >= 3:
            cwd = _path_from_root_expression(node.args[2]) or cwd
        for keyword in node.keywords:
            if keyword.arg == "cwd":
                cwd = _path_from_root_expression(keyword.value) or cwd
        if not _absolute(root, cwd.as_posix()).is_dir():
            key = ("cwd", cwd.as_posix())
            if key not in seen:
                seen.add(key)
                findings.append(
                    Finding(
                        "STRUCT005",
                        "structure",
                        Severity.WARNING,
                        relative,
                        f"Acceptance Gate working directory does not exist: {cwd.as_posix()}",
                        "Restore the referenced project directory or update the gate deliberately.",
                        getattr(node, "lineno", None),
                    )
                )
        for command_node in ast.walk(node.args[1]):
            if not isinstance(command_node, ast.Constant) or not isinstance(command_node.value, str):
                continue
            target = command_node.value.replace("\\", "/")
            if not target.endswith((".py", ".json")):
                continue
            resolved = (cwd / target).as_posix()
            if _absolute(root, resolved).is_file():
                continue
            key = ("target", resolved)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                Finding(
                    "STRUCT006",
                    "structure",
                    Severity.WARNING,
                    relative,
                    f"Acceptance Gate target does not exist: {resolved}",
                    "Restore the referenced validator, test, or benchmark configuration.",
                    getattr(node, "lineno", None),
                )
            )
    return findings


def audit_structure(root: Path, config: AuditConfig) -> list[Finding]:
    findings: list[Finding] = []
    for project in config.projects:
        project_path = _absolute(root, project.path)
        if not project_path.is_dir():
            findings.append(
                Finding(
                    "STRUCT001",
                    "structure",
                    Severity.WARNING,
                    project.path,
                    "Expected project directory is missing.",
                    "Restore the project directory or update the declared repository scope.",
                )
            )
            continue
        test_relative = (PurePosixPath(project.path) / project.test_path).as_posix()
        test_path = _absolute(root, test_relative)
        test_files = tuple(test_path.rglob(project.test_glob)) if test_path.is_dir() else ()
        if not test_files:
            findings.append(
                Finding(
                    "STRUCT002",
                    "structure",
                    Severity.WARNING,
                    test_relative,
                    f"No expected test files match {project.test_glob!r}.",
                    "Restore the project's expected test target.",
                )
            )
    findings.extend(_acceptance_target_findings(root))
    workflow = _absolute(root, ".github/workflows/ci.yml")
    if not workflow.is_file():
        findings.append(
            Finding(
                "STRUCT007",
                "structure",
                Severity.WARNING,
                ".github/workflows/ci.yml",
                "The CI workflow referenced by repository policy is missing.",
                "Restore the CI workflow entry point.",
            )
        )
    return findings


def audit_repository(root: Path = ROOT, config: AuditConfig = AuditConfig()) -> AuditReport:
    root = root.resolve()
    tracked = git_tracked_files(root)
    findings: list[Finding] = []
    findings.extend(audit_git_hygiene(tracked))
    findings.extend(audit_large_files(root, tracked, config))
    findings.extend(audit_debt_markers(root, tracked))
    findings.extend(audit_secret_risks(root, tracked))
    findings.extend(audit_dependencies(root, tracked, config))
    findings.extend(audit_documentation(root, tracked, config))
    findings.extend(audit_structure(root, config))
    return AuditReport(_sort_findings(findings))


def _display_path(finding: Finding) -> str:
    return f"{finding.path}:{finding.line}" if finding.line else finding.path


def render_text(report: AuditReport) -> str:
    lines = ["Repository Audit v1", ""]
    for category, label in CATEGORY_ORDER:
        findings = [item for item in report.findings if item.category == category]
        status = _category_status(findings)
        lines.append(f"[{status}] {label}")
        for finding in findings:
            lines.append(
                f"       - {_display_path(finding)} | {finding.severity.value} | "
                f"{finding.check_id} | {finding.evidence}"
            )
            lines.append(f"         Recommendation: {finding.recommendation}")
        lines.append("")
    summary = report.summary
    lines.extend(
        [
            "Summary",
            "-------",
            f"HIGH: {summary['high']}",
            f"WARNING: {summary['warning']}",
            f"INFO: {summary['info']}",
            "",
            f"AUDIT RESULT: {report.status}",
        ]
    )
    return "\n".join(lines)


def render_json(report: AuditReport) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)


def exit_code(report: AuditReport) -> int:
    return 1 if report.status == "FAIL" else 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the deterministic Repository Audit v1")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit only machine-readable JSON to stdout",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write the JSON report to this explicit path; no file is written by default",
    )
    return parser.parse_args(argv)


def _error_report(detail: str) -> AuditReport:
    finding = Finding(
        "AUDIT001",
        "git_hygiene",
        Severity.HIGH,
        ".",
        detail,
        "Run the audit inside an accessible Git worktree and resolve the reported Git error.",
    )
    return AuditReport((finding,))


def main(argv: Sequence[str] | None = None, root: Path = ROOT) -> int:
    args = parse_args(argv)
    try:
        report = audit_repository(root)
    except AuditError as exc:
        report = _error_report(str(exc))

    json_text = render_json(report)
    if args.output:
        output_path = args.output if args.output.is_absolute() else root / args.output
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json_text + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"audit report could not be written: {exc}", file=sys.stderr)
            return 1

    print(json_text if args.json else render_text(report))
    return exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
