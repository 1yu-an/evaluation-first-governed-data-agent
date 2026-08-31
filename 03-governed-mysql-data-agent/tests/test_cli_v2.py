import json
from unittest.mock import patch

from src.cli import main
from src.demo import initialize_expenses
from src.executor import MySQLConfig, MySQLExecutor
from src.profile import load_profile


def test_validate_profile_command_is_offline_and_actionable(capsys):
    exit_code = main(
        ["validate-profile", "--profile", "profiles/expenses.json"]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result == {
        "status": "valid",
        "profile_id": "expenses",
        "required_schema": {"expenses": ["amount", "category", "spent_on"]},
        "mysql_schema_checked": False,
    }


def test_explain_command_does_not_require_a_database(capsys):
    exit_code = main(
        [
            "explain",
            "--profile",
            "profiles/expenses.json",
            "total expenses for groceries",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result["profile_id"] == "expenses"
    assert result["executed"] is False
    assert result["params"] == ["food"]
    assert result["sql"].endswith("WHERE category=?")


def test_invalid_profile_has_nonzero_exit_and_no_traceback(tmp_path, capsys):
    profile = tmp_path / "invalid.json"
    profile.write_text("{}", encoding="utf-8")

    exit_code = main(["validate-profile", "--profile", str(profile)])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert result["status"] == "error"
    assert result["reason_code"] == "profile_validation_failed"
    assert "required field is missing" in result["reason"]
    assert "validate-profile again" in result["hint"]
    assert result["evidence"] == {}


def test_ask_command_returns_concise_contract_without_sql(
    tmp_path, capsys, monkeypatch
):
    database = initialize_expenses(tmp_path / "expenses.db")
    monkeypatch.setenv("DATA_AGENT_EXECUTOR", "sqlite")

    exit_code = main(
        [
            "ask",
            "--profile",
            "profiles/expenses.json",
            "--db-path",
            str(database),
            "total expenses for groceries",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result == {
        "status": "success",
        "profile_id": "expenses",
        "metric": "total_expenses",
        "filters": {"category": "food"},
        "value": 47.5,
        "verified": True,
        "evidence": {"row_count": 1, "result_key": "total_expenses"},
    }
    assert "sql" not in result


def test_ask_safe_failures_have_stable_reason_codes(capsys, monkeypatch):
    monkeypatch.setenv("DATA_AGENT_EXECUTOR", "sqlite")
    cases = (
        ("largest merchant", "unknown_metric"),
        ("total expenses and average expense", "ambiguous_metric"),
        ("total expenses for the north region", "unsupported_filter"),
        ("total expenses for category business", "unsupported_filter"),
    )

    for question, reason_code in cases:
        exit_code = main(
            [
                "ask",
                "--profile",
                "profiles/expenses.json",
                question,
            ]
        )
        result = json.loads(capsys.readouterr().out)

        assert exit_code == 1
        assert result["status"] == "safe_failure"
        assert result["reason_code"] == reason_code
        assert result["evidence"] == {}


def test_bad_database_credentials_are_categorized_and_redacted(capsys):
    redaction_target = "-".join(("v22", "cli", "test", "secret"))

    class AuthenticationError(Exception):
        errno = 1045

    class FailingConnector:
        @staticmethod
        def connect(**kwargs):
            raise AuthenticationError(f"Access denied with password {redaction_target}")

    executor = MySQLExecutor(
        MySQLConfig(
            host="db.test",
            port=3306,
            database="data_agent",
            user="reader",
            password=redaction_target,
        ),
        connector_module=FailingConnector(),
    )

    with patch("src.cli.executor_from_env", return_value=executor):
        exit_code = main(
            [
                "validate-profile",
                "--profile",
                "profiles/expenses.json",
                "--check-mysql-schema",
            ]
        )
    output = capsys.readouterr().out
    result = json.loads(output)

    assert exit_code == 2
    assert result["status"] == "error"
    assert result["reason_code"] == "database_authentication_failed"
    assert "MYSQL_AGENT_USER" in result["hint"]
    assert "v22-cli-test-secret" not in output


def test_root_help_lists_commands_without_loading_an_executor(capsys):
    with patch("src.cli.executor_from_env") as executor_factory:
        exit_code = main(["--help"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "ask" in output
    assert "explain" in output
    assert "init-profile" in output
    assert "validate-profile" in output
    assert "DATA_AGENT_*" in output
    executor_factory.assert_not_called()


def test_environment_profile_and_db_path_override_defaults(
    tmp_path, capsys, monkeypatch
):
    database = initialize_expenses(tmp_path / "from-environment.db")
    monkeypatch.setenv("DATA_AGENT_EXECUTOR", "sqlite")
    monkeypatch.setenv("DATA_AGENT_PROFILE", "profiles/expenses.json")
    monkeypatch.setenv("DATA_AGENT_DB_PATH", str(database))

    exit_code = main(["ask", "total expenses"])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result["profile_id"] == "expenses"
    assert result["value"] == 977.5


def test_cli_profile_and_db_path_override_environment(
    tmp_path, capsys, monkeypatch
):
    database = initialize_expenses(tmp_path / "from-cli.db")
    monkeypatch.setenv("DATA_AGENT_EXECUTOR", "sqlite")
    monkeypatch.setenv("DATA_AGENT_PROFILE", "profiles/demo.json")
    monkeypatch.setenv("DATA_AGENT_DB_PATH", str(tmp_path / "wrong.db"))

    exit_code = main(
        [
            "ask",
            "--profile",
            "profiles/expenses.json",
            "--db-path",
            str(database),
            "how many expenses",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result["profile_id"] == "expenses"
    assert result["value"] == 6


def test_missing_mysql_configuration_has_stable_actionable_error(
    capsys, monkeypatch
):
    monkeypatch.setenv("DATA_AGENT_EXECUTOR", "mysql")
    for name in (
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_DATABASE",
        "MYSQL_AGENT_USER",
        "MYSQL_AGENT_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)

    exit_code = main(
        [
            "validate-profile",
            "--profile",
            "profiles/expenses.json",
            "--check-mysql-schema",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert result["status"] == "error"
    assert result["reason_code"] == "database_configuration_missing"
    assert "MYSQL_*" in result["hint"]


def test_init_profile_creates_valid_template_without_database_access(
    tmp_path, capsys
):
    target = tmp_path / "my_profile.json"

    with patch("src.cli.executor_from_env") as executor_factory:
        exit_code = main(["init-profile", str(target)])
    result = json.loads(capsys.readouterr().out)
    profile = load_profile(target)

    assert exit_code == 0
    assert result["status"] == "created"
    assert result["profile_id"] == "my_profile"
    assert profile.profile_id == "my_profile"
    assert set(profile.metric_catalog) == {"row_count"}
    assert "sql" not in target.read_text(encoding="utf-8").lower()
    executor_factory.assert_not_called()


def test_init_profile_refuses_overwrite_and_preserves_existing_file(
    tmp_path, capsys
):
    target = tmp_path / "existing.json"
    target.write_text("user-owned-content", encoding="utf-8")

    exit_code = main(["init-profile", str(target)])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert result["status"] == "error"
    assert result["reason_code"] == "profile_target_exists"
    assert "refusing to overwrite" in result["reason"]
    assert target.read_text(encoding="utf-8") == "user-owned-content"


def test_init_profile_invalid_filename_has_actionable_override(capsys, tmp_path):
    target = tmp_path / "bad-profile.json"

    exit_code = main(["init-profile", str(target)])
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert result["reason_code"] == "invalid_profile_id"
    assert "--profile-id" in result["hint"]
    assert not target.exists()


def test_personal_user_smoke_flow_from_initialize_to_verified_answer(
    tmp_path, capsys, monkeypatch
):
    database = initialize_expenses(tmp_path / "daily-expenses.db")
    monkeypatch.setenv("DATA_AGENT_EXECUTOR", "sqlite")
    monkeypatch.setenv("DATA_AGENT_PROFILE", "profiles/expenses.json")
    monkeypatch.setenv("DATA_AGENT_DB_PATH", str(database))

    assert main(["validate-profile"]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["status"] == "valid"

    assert main(["explain", "average expense for transport"]) == 0
    explained = json.loads(capsys.readouterr().out)
    assert explained["executed"] is False
    assert explained["params"] == ["transport"]

    assert main(["ask", "total expenses for groceries"]) == 0
    answered = json.loads(capsys.readouterr().out)
    assert answered["status"] == "success"
    assert answered["metric"] == "total_expenses"
    assert answered["filters"] == {"category": "food"}
    assert answered["value"] == 47.5
    assert answered["verified"] is True
