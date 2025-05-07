CREATE TABLE IF NOT EXISTS orders (
    order_id UUID PRIMARY KEY,
    customer_email VARCHAR(255),
    order_date TIMESTAMP,
    amount NUMERIC(12, 2),
    currency VARCHAR(3)
);
