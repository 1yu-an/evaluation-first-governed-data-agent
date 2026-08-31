CREATE TABLE IF NOT EXISTS expenses(
    id BIGINT PRIMARY KEY,
    spent_on DATE NOT NULL,
    category VARCHAR(40) NOT NULL,
    merchant VARCHAR(100) NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    note VARCHAR(255) NULL
);

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
