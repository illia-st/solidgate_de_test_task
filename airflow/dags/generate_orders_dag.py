from airflow import DAG
from airflow.operators.python import PythonOperator

from datetime import timedelta
import pendulum
import os
import sys

import uuid
import random
from datetime import datetime, timedelta
import psycopg2

from scripts.open_exchange_api import OpenExchangeRatesAPI
import logging

logger = logging.getLogger(__name__)
logger.info("This is a log message")

APP_KEY_OPEN_EXCHANGE_API = "5183c2a0f5c64b41a3363bf184ef6db9"

INSERT_QUERY = (
    "INSERT INTO orders (order_id, customer_email, order_date, amount, currency) "
    "VALUES (%s, %s, %s, %s, %s)"
)


def generate_orders_to_db(count=5000):
    """Generate `count` random orders and insert into the source database (Postgres-1)."""
    currencies = OpenExchangeRatesAPI(app_id=APP_KEY_OPEN_EXCHANGE_API).get_latest_rates(base="EUR")
    currencies_codes = list(currencies.get('rates').keys())
    currencies_codes_max_index = len(currencies_codes) - 1

    # Database connection parameters from environment
    db_host = os.environ.get('DB1_HOST', 'postgres1')
    db_name = os.environ.get('DB1_NAME', 'orders_db')
    db_user = os.environ.get('DB1_USER', 'postgres')
    db_pass = os.environ.get('DB_PASS', 'postgres')
    
    conn = psycopg2.connect(host=db_host, user=db_user, password=db_pass)
    cur = conn.cursor()
    now = datetime.now()
    orders = []

    for _ in range(count):
        index = random.randint(0, currencies_codes_max_index)
        # get currency code out of the API 
        currency_code = currencies_codes[index]
        # generate guid order id
        order_id = str(uuid.uuid4())
        # Generate random email
        customer_email = f"user{random.randint(1, 100000)}@example.com"
        # Random date within last 7 days
        random_offset = random.random() * 7 * 24 * 60 * 60  # seconds in 7 days
        order_date = now - timedelta(seconds=random_offset)
        # Random amount up to 1000, with 2 decimal places
        amount = round(random.uniform(1, 1000), 2)
        orders.append((order_id, customer_email, order_date, amount, currency_code))
    # Insert into orders table
    cur.executemany(INSERT_QUERY, orders)
    conn.commit()

    logger.info("Inserted %d new orders into source database.", len(orders))

    cur.close()
    conn.close()

generate_orders_to_db(10)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 0,
}

with DAG(
    dag_id='generate_orders',
    default_args=default_args,
    schedule='*/1 * * * *',
    start_date=pendulum.datetime(2025, 5, 1, tz="UTC"),
    catchup=False
) as dag:
    generate_task = PythonOperator(
        task_id='generate_orders_task',
        python_callable=generate_orders_to_db,
        op_args=[10]
    )
