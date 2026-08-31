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

EXPENSES_SQL = """
DROP TABLE IF EXISTS expenses;
CREATE TABLE expenses(
    id INTEGER PRIMARY KEY,
    spent_on TEXT NOT NULL,
    category TEXT NOT NULL,
    merchant TEXT NOT NULL,
    amount REAL NOT NULL,
    note TEXT
);
INSERT INTO expenses VALUES
    (1,'2026-08-01','food','Cafe',12.50,'breakfast'),
    (2,'2026-08-03','food','Market',30.00,'groceries'),
    (3,'2026-08-05','transport','Metro',8.00,'commute'),
    (4,'2026-08-09','transport','Taxi',22.00,'late ride'),
    (5,'2026-08-10','housing','Landlord',900.00,'rent'),
    (6,'2026-08-12','food','Bakery',5.00,'snack');
"""


def initialize_demo(db_path: str | Path) -> Path:
    """Create the deterministic demo database used by the CLI and integration."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(DEMO_SQL)
    return path


def initialize_expenses(db_path: str | Path) -> Path:
    """Create the deterministic non-demo personal expenses example."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(EXPENSES_SQL)
    return path
