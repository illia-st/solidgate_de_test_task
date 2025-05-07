# Data engineer test task

## Overview

This project implements a test task using **Apache Airflow 2.6.2** to generate and process orders with currency conversion to Euro.

### Key Components:
- **2 DAGs**
- **Class for interacting with OpenExchangeRates API**
- **PostgreSQL databases**
- **Docker-based deployment**
- **Environment variable configuration via `.env`**

---

## Environment

- Uses **Airflow 2.6.2**
- Required dependencies are listed in `requirements.txt`
- A custom Dockerfile `DockerFile_AirFlow` is used to extend Airflow with additional packages
- Dependencies from `requirements.txt` are automatically installed inside the Airflow container

---

## DAGs

### 1. `generate_orders`
- Runs **every 10 minutes**
- Generates **5000 random orders**
- Inserts the data into the `orders` table in **postgres-1** database

### 2. `sync_orders_to_eur`
- Runs **hourly**
- Syncs unprocessed orders
- Converts the order prices to **EUR** using the latest exchange rates from the OpenExchangeRates API
- Inserts the data into the `orders_eur` table in **postgres-2** database

---

## `orders` Table Schema

```sql
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

CREATE INDEX idx_orders_retriable
ON orders (processed, failed)
WHERE processed = false AND failed = false;
```

- processing_attempts — number of processing attempts for an order
- processed — indicates if the order was successfully processed
- failed — indicates that the order exceeded retry limits and won’t be processed anymore

## `orders_eur` Table Schema
```sql
CREATE TABLE IF NOT EXISTS orders_eur (
    order_id UUID PRIMARY KEY,
    customer_email VARCHAR(255),
    order_date TIMESTAMP,
    amount_eur NUMERIC(12, 2),
    original_currency VARCHAR(3)
);
```

## Environment Variable:
- MAX_PROCESSING_ATTEMPS — defined in .env, sets the maximum allowed number of processing attempts
- OXR_APP_ID - OpenExchangeRatesAPI app key

- ORDERS_DB_HOST
- ORDERS_DB_NAME
- ORDERS_DB_USER
- ORDERS_DB_PASS

- ORDERS_DB_EUR_HOST
- ORDERS_DB_EUR_NAME
- ORDERS_DB_EUR_USER
- ORDERS_DB_EUR_PASS

**NOTE**: I have left in `.env.example` varaible values for testing

## Why Retry Limits Were Implemented
Prevent DAG Overload — to avoid long-running DAGs overlapping and competing for resources

Handle Permanent Failures — if an order fails repeatedly, it's likely due to a persistent issue that requires manual intervention

### Example:
During order generation, random currencies were selected from the `/currencies.json` endpoint. However, the `/latest.json` endpoint didn’t always return a full list of exchange rates, resulting in conversion failures. Such orders are marked as failed.



## API Integration
A dedicated Python class was implemented to interact with the OpenExchangeRates API, supporting:
- Fetching available currencies
- Fetching latest exchange rates (base: EUR)

## Running the Project
1. Configure the .env file
2. Start services using Docker Compose:

```bash
docker compose up
```
Make sure the DAGs are enabled in the Airflow UI


## Author

**Illia Stetsenko**  
[illia.stetsenko.work@gmail.com](mailto:illia.stetsenko.work@gmail.com)