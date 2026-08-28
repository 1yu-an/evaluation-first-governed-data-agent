import sqlite3
from contextlib import closing
from pathlib import Path


DEMO_SQL = """
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS refunds;
CREATE TABLE orders(id INTEGER PRIMARY KEY,status TEXT,total REAL,region TEXT);
CREATE TABLE payments(id INTEGER PRIMARY KEY,order_id INTEGER,status TEXT,amount REAL);
CREATE TABLE refunds(id INTEGER PRIMARY KEY,order_id INTEGER,status TEXT,amount REAL);
INSERT INTO orders VALUES
    (1,'completed',120,'east'),
    (2,'completed',80,'west'),
    (3,'pending',50,'east');
INSERT INTO payments VALUES
    (1,1,'completed',120),
    (2,2,'completed',80);
INSERT INTO refunds VALUES(1,1,'completed',20);
"""


def initialize_demo(db_path: str | Path) -> Path:
    """Create the deterministic demo database used by the CLI and integration."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(DEMO_SQL)
    return path
