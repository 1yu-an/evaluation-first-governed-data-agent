import json

from src.cli import main
from src.demo import initialize_expenses


def test_validate_profile_command_is_offline_and_actionable(capsys):
    exit_code = main(
        ["validate-profile", "--profile", "profiles/expenses.json"]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result == {
        "status": "valid",
        "profile_id": "expenses",
        "required_schema": {"expenses": ["amount", "category"]},
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
    assert result["status"] == "ERROR"
    assert "required field is missing" in result["reason"]
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
