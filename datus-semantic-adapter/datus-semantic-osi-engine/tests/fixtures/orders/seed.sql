-- Seed data for the orders.yaml fixture model. Hand-sized so every expected
-- result in the oracle tests is verifiable by eye:
--   revenue: completed=350 cancelled=100 total=450
--   by month: 2024-01=150 2024-02=230 2024-03=70
--   order_count=6, unique_customers=3, avg_order_value=75.0
--   total_margin = 450 - (20+10+60) = 360
CREATE TABLE orders (
    order_id INTEGER,
    customer_id INTEGER,
    product_id INTEGER,
    order_date DATE,
    status VARCHAR,
    amount DOUBLE
);
INSERT INTO orders VALUES
    (1, 1, 10, DATE '2024-01-05', 'completed', 100),
    (2, 1, 11, DATE '2024-01-20', 'completed', 50),
    (3, 2, 10, DATE '2024-02-10', 'completed', 80),
    (4, 2, 11, DATE '2024-02-15', 'cancelled', 30),
    (5, 3, 12, DATE '2024-02-20', 'completed', 120),
    (6, 1, 12, DATE '2024-03-01', 'cancelled', 70);

CREATE TABLE customers (
    customer_id INTEGER,
    region VARCHAR,
    signup_date DATE
);
INSERT INTO customers VALUES
    (1, 'east', DATE '2023-12-01'),
    (2, 'west', DATE '2023-11-15'),
    (3, 'east', DATE '2024-01-10');

CREATE TABLE products (
    product_id INTEGER,
    category VARCHAR,
    unit_cost DOUBLE
);
INSERT INTO products VALUES
    (10, 'books', 20),
    (11, 'toys', 10),
    (12, 'books', 60);
