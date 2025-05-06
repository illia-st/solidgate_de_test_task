CREATE TABLE IF NOT EXISTS orders_eur (
    order_id UUID PRIMARY KEY,
    customer_email VARCHAR(255),
    order_date TIMESTAMP,
    amount_eur NUMERIC(12, 2),
    original_currency VARCHAR(3)
);
