import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient

from src.agent import DataAgent
from src.demo import initialize_demo
from src.web import DEMO_META_PATH, MAX_QUESTION_LENGTH, create_app


def _client_for(db_path: Path) -> TestClient:
    agent = DataAgent(db_path)
    return TestClient(create_app(agent_provider=lambda: agent, db_path=db_path))


def test_web_app_imports_and_serves_local_page():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Governed MySQL Data Agent" in response.text
    assert "https://" not in response.text


def test_health_endpoint_reports_ready_sqlite_demo():
    with tempfile.TemporaryDirectory() as directory:
        db_path = initialize_demo(Path(directory) / "demo.db")
        response = _client_for(db_path).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "executor": "sqlite",
        "demo_ready": True,
    }


def test_successful_query_uses_real_agent_result():
    with tempfile.TemporaryDirectory() as directory:
        db_path = initialize_demo(Path(directory) / "demo.db")
        response = _client_for(db_path).post(
            "/api/query", json={"question": "highest completed order total"}
        )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "OK"
    assert result["evidence"] == {"max_completed_order_total": 120.0}
    assert result["verified"] is True


def test_ambiguous_query_stops_after_resolver():
    response = TestClient(create_app()).post(
        "/api/query", json={"question": "turnover"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "NEED_CLARIFICATION"
    assert response.json()["trace"] == ["resolve_metric"]


def test_empty_and_oversized_questions_are_rejected():
    client = TestClient(create_app())

    assert client.post("/api/query", json={"question": "   "}).status_code == 422
    assert client.post(
        "/api/query", json={"question": "x" * (MAX_QUESTION_LENGTH + 1)}
    ).status_code == 422


def test_web_adapter_delegates_to_data_agent_without_reimplementation():
    expected = {"status": "NEED_CLARIFICATION", "trace": ["resolve_metric"]}
    agent = Mock(spec=DataAgent)
    agent.answer.return_value = expected
    client = TestClient(create_app(agent_provider=lambda: agent))

    response = client.post("/api/query", json={"question": "  exact question  "})

    agent.answer.assert_called_once_with("exact question")
    assert response.json() == expected


def test_api_trace_matches_direct_data_agent_result():
    with tempfile.TemporaryDirectory() as directory:
        db_path = initialize_demo(Path(directory) / "demo.db")
        agent = DataAgent(db_path)
        direct = agent.answer("revenue for the east region")
        response = TestClient(
            create_app(agent_provider=lambda: agent, db_path=db_path)
        ).post("/api/query", json={"question": "revenue for the east region"})

    assert response.json()["trace"] == direct["trace"]
    assert response.json()["semantic_plan"] == direct["semantic_plan"]
    assert response.json()["sql"] == direct["sql"]
    assert response.json()["params"] == direct["params"]


def test_web_layer_has_no_arbitrary_sql_endpoint():
    app = create_app()
    paths = {route.path for route in app.routes}

    assert paths == {"/", "/api/health", "/api/demo-meta", "/api/query", "/static"}
    assert TestClient(app).post("/api/sql", json={"sql": "SELECT 1"}).status_code == 404


def test_internal_error_is_logged_but_not_leaked_to_browser():
    def broken_provider():
        raise RuntimeError("sensitive internal detail")

    response = TestClient(create_app(agent_provider=broken_provider)).post(
        "/api/query", json={"question": "revenue"}
    )

    assert response.status_code == 500
    assert response.json()["status"] == "ERROR"
    assert "sensitive internal detail" not in response.text


def test_demo_metadata_matches_canonical_repository_facts():
    meta = json.loads(DEMO_META_PATH.read_text(encoding="utf-8"))
    root = DEMO_META_PATH.parents[2]
    project_readme = (root / "03-governed-mysql-data-agent" / "README.md").read_text(
        encoding="utf-8"
    )
    cases = json.loads(
        (root / "00-agent-eval-harness" / "cases" / "03_integration_cases.json").read_text(
            encoding="utf-8"
        )
    )
    benchmark = meta["benchmark"]

    assert len(cases) == benchmark["total"] == 56
    assert f"Fixed Benchmark: {benchmark['passed']} / {benchmark['total']} success" in project_readme
    for key in ("SAFE_FAILURE", "FALSE_SUCCESS", "UNSAFE_ALLOW", "OVER_BLOCK"):
        assert f"{key} = {benchmark[key]}" in project_readme
