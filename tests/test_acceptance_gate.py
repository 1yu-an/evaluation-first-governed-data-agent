from pathlib import Path

from scripts.acceptance_gate import (
    FAIL,
    MISSING_TOOL,
    Check,
    build_checks,
    execute_checks,
    print_summary,
    run_acceptance,
)


def _check(name: str, *required_tools: str) -> Check:
    return Check(name, ("fake-command",), Path.cwd(), required_tools)


def test_all_commands_succeed_means_overall_pass(capsys):
    exit_code = run_acceptance(
        [_check("validation"), _check("tests")],
        command_runner=lambda check: 0,
    )

    assert exit_code == 0
    assert "FINAL RESULT: PASS" in capsys.readouterr().out


def test_any_command_failure_means_overall_fail(capsys):
    exit_codes = {"validation": 0, "tests": 7}

    exit_code = run_acceptance(
        [_check("validation"), _check("tests")],
        command_runner=lambda check: exit_codes[check.name],
    )

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "tests       FAIL (exit code 7)" in output
    assert "FINAL RESULT: FAIL" in output


def test_missing_tool_is_not_reported_as_pass():
    runner_called = False

    def runner(check):
        nonlocal runner_called
        runner_called = True
        return 0

    results = execute_checks(
        [_check("01 Java tests", "java", "mvn")],
        command_runner=runner,
        tool_finder=lambda tool: None if tool == "mvn" else f"/tools/{tool}",
    )

    assert results[0].name == "01 Java tests"
    assert results[0].status == MISSING_TOOL
    assert results[0].detail == "missing required tool(s): mvn"
    assert runner_called is False


def test_benchmark_failure_fails_gate():
    checks = [_check("03 Python tests"), _check("03 Benchmark Gate")]

    exit_code = run_acceptance(
        checks,
        command_runner=lambda check: 1 if "Benchmark" in check.name else 0,
    )

    assert exit_code == 1


def test_command_start_error_fails_closed():
    def unavailable(check):
        raise FileNotFoundError("not installed")

    results = execute_checks([_check("tests")], command_runner=unavailable)

    assert results[0].status == FAIL
    assert "command could not start" in results[0].detail


def test_summary_prints_each_terminal_status_and_final_failure(capsys):
    results = execute_checks(
        [_check("pass"), _check("fail"), _check("missing", "mvn")],
        command_runner=lambda check: 0 if check.name == "pass" else 2,
        tool_finder=lambda tool: None,
    )
    print_summary(results)

    output = capsys.readouterr().out
    assert "pass     PASS" in output
    assert "fail     FAIL (exit code 2)" in output
    assert "missing  MISSING_TOOL" in output
    assert "FINAL RESULT: FAIL" in output


def test_mysql_suite_is_only_added_by_explicit_option(tmp_path):
    default_checks = build_checks(root=tmp_path)
    mysql_checks = build_checks(with_mysql=True, root=tmp_path)

    assert all(check.name != "03 MySQL integration" for check in default_checks)
    assert mysql_checks[-1].name == "03 MySQL integration"
    assert mysql_checks[-1].env == {"RUN_MYSQL_INTEGRATION": "1"}


def test_build_checks_includes_repository_audit_and_its_tests(tmp_path):
    checks = {check.name: check for check in build_checks(root=tmp_path)}

    assert checks["Repository audit tests"].command[-1] == (
        "tests/test_audit_repo.py"
    )
    assert checks["Repository audit"].command[-1] == "scripts/audit_repo.py"


def test_build_checks_uses_resolved_maven_executable(monkeypatch, tmp_path):
    resolved_maven = str(tmp_path / "apache-maven" / "bin" / "mvn.cmd")
    monkeypatch.setattr(
        "scripts.acceptance_gate.shutil.which",
        lambda tool: resolved_maven if tool == "mvn" else f"/tools/{tool}",
    )

    java_checks = [
        check for check in build_checks(root=tmp_path) if "Java tests" in check.name
    ]

    assert len(java_checks) == 2
    assert all(check.command[0] == resolved_maven for check in java_checks)
