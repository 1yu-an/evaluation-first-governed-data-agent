CREATE DATABASE IF NOT EXISTS data_agent;
USE data_agent;

CREATE TABLE IF NOT EXISTS orders(
    id BIGINT PRIMARY KEY,
    status VARCHAR(32) NOT NULL,
    total DECIMAL(12,2) NOT NULL,
    region VARCHAR(32) NOT NULL
);
CREATE TABLE IF NOT EXISTS payments(
    id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    status VARCHAR(32) NOT NULL,
    amount DECIMAL(12,2) NOT NULL
);
CREATE TABLE IF NOT EXISTS refunds(
    id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    status VARCHAR(32) NOT NULL,
    amount DECIMAL(12,2) NOT NULL
);
CREATE TABLE IF NOT EXISTS expenses(
    id BIGINT PRIMARY KEY,
    spent_on DATE NOT NULL,
    category VARCHAR(40) NOT NULL,
    merchant VARCHAR(100) NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    note VARCHAR(255) NULL
);

INSERT INTO orders(id,status,total,region) VALUES
    (1,'completed',120.00,'east'),
    (2,'completed',80.00,'west'),
    (3,'pending',50.00,'east')
ON DUPLICATE KEY UPDATE
    status=VALUES(status), total=VALUES(total), region=VALUES(region);

INSERT INTO payments(id,order_id,status,amount) VALUES
    (1,1,'completed',120.00),
    (2,2,'completed',80.00)
ON DUPLICATE KEY UPDATE
    order_id=VALUES(order_id), status=VALUES(status), amount=VALUES(amount);

INSERT INTO refunds(id,order_id,status,amount) VALUES
    (1,1,'completed',20.00)
ON DUPLICATE KEY UPDATE
    order_id=VALUES(order_id), status=VALUES(status), amount=VALUES(amount);

INSERT INTO expenses(id,spent_on,category,merchant,amount,note) VALUES
    (1,'2026-08-01','food','Cafe',12.50,'breakfast'),
    (2,'2026-08-03','food','Market',30.00,'groceries'),
    (3,'2026-08-05','transport','Metro',8.00,'commute'),
    (4,'2026-08-09','transport','Taxi',22.00,'late ride'),
    (5,'2026-08-10','housing','Landlord',900.00,'rent'),
    (6,'2026-08-12','food','Bakery',5.00,'snack')
ON DUPLICATE KEY UPDATE
    spent_on=VALUES(spent_on), category=VALUES(category),
    merchant=VALUES(merchant), amount=VALUES(amount), note=VALUES(note);

-- The runtime user is deliberately not created here because its password must
-- come from the environment. Run scripts/setup_mysql.py with admin credentials.
