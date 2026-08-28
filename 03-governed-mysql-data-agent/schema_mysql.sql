CREATE DATABASE IF NOT EXISTS data_agent;
USE data_agent;
CREATE TABLE orders(id BIGINT PRIMARY KEY,status VARCHAR(32),total DECIMAL(12,2),region VARCHAR(32));
CREATE TABLE payments(id BIGINT PRIMARY KEY,order_id BIGINT,status VARCHAR(32),amount DECIMAL(12,2));
CREATE TABLE refunds(id BIGINT PRIMARY KEY,order_id BIGINT,status VARCHAR(32),amount DECIMAL(12,2));
-- Production / 生产环境：为 Agent 创建只读账号，并限制到允许的 schema/table。
