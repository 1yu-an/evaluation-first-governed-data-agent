import os
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.executor import ExecutionError


IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")
HOST_PATTERN = re.compile(r"^[A-Za-z0-9_.:%-]+$")


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ExecutionError(f"missing required environment variable: {name}")
    return value


def _validated(value: str, name: str, pattern: re.Pattern) -> str:
    if not pattern.fullmatch(value):
        raise ExecutionError(f"invalid {name}: only safe identifier characters are allowed")
    return value


def _connector():
    try:
        import mysql.connector
    except ImportError as error:
        raise ExecutionError(
            "mysql-connector-python is required; install requirements.txt"
        ) from error
    return mysql.connector


def setup() -> list[str]:
    host = _required("MYSQL_HOST")
    port_text = _required("MYSQL_PORT")
    try:
        port = int(port_text)
    except ValueError as error:
        raise ExecutionError("MYSQL_PORT must be an integer") from error
    database = _validated(
        _required("MYSQL_DATABASE"), "MYSQL_DATABASE", IDENTIFIER
    )
    admin_user = _required("MYSQL_ADMIN_USER")
    admin_password = _required("MYSQL_ADMIN_PASSWORD")
    agent_user = _validated(
        _required("MYSQL_AGENT_USER"), "MYSQL_AGENT_USER", IDENTIFIER
    )
    if agent_user.lower() == "root" or agent_user == admin_user:
        raise ExecutionError(
            "MYSQL_AGENT_USER must be distinct from the admin/root account"
        )
    agent_password = _required("MYSQL_AGENT_PASSWORD")
    agent_host = _validated(
        _required("MYSQL_AGENT_HOST_PATTERN"),
        "MYSQL_AGENT_HOST_PATTERN",
        HOST_PATTERN,
    )

    connector = _connector()
    connection = connector.connect(
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
    )
    cursor = connection.cursor()
    account = f"'{agent_user}'@'{agent_host}'"
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
        cursor.execute(f"USE `{database}`")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS orders("
            "id BIGINT PRIMARY KEY,status VARCHAR(32) NOT NULL,"
            "total DECIMAL(12,2) NOT NULL,region VARCHAR(32) NOT NULL)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS payments("
            "id BIGINT PRIMARY KEY,order_id BIGINT NOT NULL,"
            "status VARCHAR(32) NOT NULL,amount DECIMAL(12,2) NOT NULL)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS refunds("
            "id BIGINT PRIMARY KEY,order_id BIGINT NOT NULL,"
            "status VARCHAR(32) NOT NULL,amount DECIMAL(12,2) NOT NULL)"
        )
        cursor.executemany(
            "INSERT INTO orders(id,status,total,region) VALUES(%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE status=VALUES(status),"
            "total=VALUES(total),region=VALUES(region)",
            [
                (1, "completed", 120, "east"),
                (2, "completed", 80, "west"),
                (3, "pending", 50, "east"),
            ],
        )
        cursor.executemany(
            "INSERT INTO payments(id,order_id,status,amount) VALUES(%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE order_id=VALUES(order_id),"
            "status=VALUES(status),amount=VALUES(amount)",
            [
                (1, 1, "completed", 120),
                (2, 2, "completed", 80),
            ],
        )
        cursor.execute(
            "INSERT INTO refunds(id,order_id,status,amount) VALUES(%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE order_id=VALUES(order_id),"
            "status=VALUES(status),amount=VALUES(amount)",
            (1, 1, "completed", 20),
        )
        cursor.execute(
            f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY %s",
            (agent_password,),
        )
        cursor.execute(
            f"ALTER USER {account} IDENTIFIED BY %s",
            (agent_password,),
        )
        cursor.execute(f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM {account}")
        cursor.execute(f"GRANT SELECT ON `{database}`.* TO {account}")
        connection.commit()
        cursor.execute(f"SHOW GRANTS FOR {account}")
        return [str(row[0]) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    try:
        grants = setup()
    except ExecutionError as error:
        raise SystemExit(f"MySQL setup failed: {error}") from error
    print("MySQL demo schema, seed data, and read-only account are ready.")
    print("Effective agent grants:")
    for grant in grants:
        print(f"- {grant}")
