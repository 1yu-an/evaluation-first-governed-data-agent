import sqlite3
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"demo.db"
with sqlite3.connect(p) as c:
 c.executescript("""
 DROP TABLE IF EXISTS orders; DROP TABLE IF EXISTS payments; DROP TABLE IF EXISTS refunds;
 CREATE TABLE orders(id INTEGER PRIMARY KEY,status TEXT,total REAL,region TEXT);
 CREATE TABLE payments(id INTEGER PRIMARY KEY,order_id INTEGER,status TEXT,amount REAL);
 CREATE TABLE refunds(id INTEGER PRIMARY KEY,order_id INTEGER,status TEXT,amount REAL);
 INSERT INTO orders VALUES(1,'completed',120,'east'),(2,'completed',80,'west'),(3,'pending',50,'east');
 INSERT INTO payments VALUES(1,1,'completed',120),(2,2,'completed',80);
 INSERT INTO refunds VALUES(1,1,'completed',20);
 """)
print(p)
