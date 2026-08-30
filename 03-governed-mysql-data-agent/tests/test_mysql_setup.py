import importlib.util
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETUP_PATH = PROJECT_ROOT / "scripts" / "setup_mysql.py"


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.closed = False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def executemany(self, sql, params):
        self.calls.append((sql, params))

    def fetchall(self):
        return [
            ("GRANT USAGE ON *.* TO `data_agent_ro`@`%`",),
            ("GRANT SELECT ON `data_agent`.* TO `data_agent_ro`@`%`",),
        ]

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class FakeConnector:
    def __init__(self):
        self.connection = FakeConnection()
        self.kwargs = None

    def connect(self, **kwargs):
        self.kwargs = kwargs
        return self.connection


def _load_setup_module():
    spec = importlib.util.spec_from_file_location("mysql_setup_script", SETUP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_setup_revokes_everything_before_granting_only_select():
    module = _load_setup_module()
    connector = FakeConnector()
    environment = {
        "MYSQL_HOST": "mysql.test",
        "MYSQL_PORT": "3306",
        "MYSQL_DATABASE": "data_agent",
        "MYSQL_ADMIN_USER": "setup_admin",
        "MYSQL_ADMIN_PASSWORD": "admin-test-only",
        "MYSQL_AGENT_USER": "data_agent_ro",
        "MYSQL_AGENT_PASSWORD": "agent-test-only",
        "MYSQL_AGENT_HOST_PATTERN": "%",
    }

    with patch.dict(module.os.environ, environment, clear=True):
        module._connector = lambda: connector
        grants = module.setup()

    statements = [sql for sql, _ in connector.connection.cursor_instance.calls]
    revoke_index = next(
        index for index, sql in enumerate(statements) if sql.startswith("REVOKE ALL")
    )
    grant_index = next(
        index for index, sql in enumerate(statements) if sql.startswith("GRANT SELECT")
    )

    assert revoke_index < grant_index
    assert statements[grant_index] == (
        "GRANT SELECT ON `data_agent`.* TO 'data_agent_ro'@'%'"
    )
    assert not any(
        sql.startswith(("GRANT INSERT", "GRANT UPDATE", "GRANT DELETE"))
        for sql in statements
    )
    assert grants[-1].startswith("GRANT SELECT ON")
    assert connector.connection.committed is True
    assert connector.connection.cursor_instance.closed is True
    assert connector.connection.closed is True
