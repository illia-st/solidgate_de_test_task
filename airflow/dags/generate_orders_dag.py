from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

from datetime import timedelta
import os

import uuid
import random
from datetime import datetime, timedelta
import psycopg2

from scripts.open_exchange_api import OpenExchangeRatesAPI
import logging


logger = logging.getLogger(__name__)

APP_KEY_OPEN_EXCHANGE_API = os.environ.get("OXR_APP_ID")

INSERT_QUERY = (
    "INSERT INTO orders (order_id, customer_email, order_date, amount, currency) "
    "VALUES (%s, %s, %s, %s, %s)"
)


def generate_orders_to_db(count=5000):
    """Generate `count` random orders and insert into the source database (Postgres-1)."""
    try:
        currencies = OpenExchangeRatesAPI(app_id=APP_KEY_OPEN_EXCHANGE_API).get_currencies()
    except Exception as e:
        logger.error("Failed to fetch currencies from OpenExchangeRates: %s", e)
        return

    currencies_codes = list(currencies.items())
    if not currencies_codes:
        logger.warning("Currency list is empty — skipping generation.")
        return

    currencies_codes_max_index = len(currencies_codes) - 1

    db_host = os.environ.get('ORDERS_DB_HOST', '')
    db_name = os.environ.get('ORDERS_DB_NAME', '')
    db_user = os.environ.get('ORDERS_DB_USER', '')
    db_pass = os.environ.get('ORDERS_DB_PASS', '')

    conn = None
    cur = None
    try:
        conn = psycopg2.connect(
            host=db_host,
            dbname=db_name,
            user=db_user,
            password=db_pass
        )
        cur = conn.cursor()

        now = datetime.now()
        orders = []

        for _ in range(count):
            index = random.randint(0, currencies_codes_max_index)
            currency_code, _ = currencies_codes[index]
            order_id = str(uuid.uuid4())
            customer_email = f"user{random.randint(1, 100000)}@example.com"
            random_offset = random.random() * 7 * 24 * 60 * 60
            order_date = now - timedelta(seconds=random_offset)
            amount = round(random.uniform(1, 1000), 2)
            orders.append((order_id, customer_email, order_date, amount, currency_code))

        try:
            cur.executemany(INSERT_QUERY, orders)
            conn.commit()
            logger.info("Inserted %d new orders into source database.", len(orders))
        except Exception as insert_err:
            conn.rollback()
            logger.error("Failed to insert orders into DB: %s", insert_err)

    except Exception as db_err:
        logger.error("Database connection or cursor error: %s", db_err)

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


with DAG(
    dag_id='generate_orders',
    schedule='*/10 * * * *',
    start_date=days_ago(1),
    catchup=False
) as dag:
    generate_task = PythonOperator(
        task_id='generate_orders_task',
        python_callable=generate_orders_to_db,
        op_args=[5000]
    )
