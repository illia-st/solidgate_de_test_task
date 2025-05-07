-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    order_id UUID PRIMARY KEY,
    customer_email VARCHAR(255),
    order_date TIMESTAMP,
    amount NUMERIC(12, 2),
    currency VARCHAR(3),
    processing_attempts smallint DEFAULT 0,
    processed BOOLEAN DEFAULT FALSE,
    failed BOOLEAN DEFAULT FALSE
);

-- Create Partial index on processed attribute bcause we will search records using it
CREATE INDEX idx_orders_retriable
ON orders (processed, failed)
WHERE processed = false AND failed = false;