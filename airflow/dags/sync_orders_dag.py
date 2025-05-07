from airflow import DAG
from airflow.operators.python import PythonOperator

import pendulum

import os
import psycopg2
from psycopg2.extensions import cursor as PgCursor

from scripts.open_exchange_api import OpenExchangeRatesAPI
from dataclasses import dataclass
from typing import List
from decimal import Decimal
from datetime import datetime

import logging
logger = logging.getLogger(__name__)

@dataclass
class Order:
    order_id: int
    customer_email: str
    order_date: datetime
    amount: Decimal
    currency: str

GET_UNPROCESSED_ORDERS_QUERY = "SELECT ORDER_ID, CUSTOMER_EMAIL, ORDER_DATE, AMOUNT, CURRENCY FROM ORDERS WHERE NOT PROCESSED"
INSERT_PROCESSED_ORDERS_QUERY = (
    "INSERT INTO orders_eur (order_id, customer_email, order_date, amount_eur, original_currency) "
    "VALUES (%s, %s, %s, %s, %s)"
)
MARK_ORDERS_AS_PROCESSED = "UPDATE orders SET processed = TRUE WHERE NOT processed"

APP_KEY_OPEN_EXCHANGE_API = "5183c2a0f5c64b41a3363bf184ef6db9"

def get_unprocessed_orders(cursor: PgCursor) -> List[Order]:
    cursor.execute(GET_UNPROCESSED_ORDERS_QUERY)
    return cursor.fetchall()

def create_connections():
    src_conn = psycopg2.connect(
        host=os.environ.get('DB1_HOST', 'postgres1'),
        # dbname=os.environ.get('DB1_NAME', 'orders_db'),
        user=os.environ.get('DB1_USER', 'postgres'),
        password=os.environ.get('DB1_PASS', 'postgres')
    )
    dest_conn = psycopg2.connect(
        host=os.environ.get('DB2_HOST', 'postgres2'),
        # dbname=os.environ.get('DB2_NAME', 'orders_eur_db'),
        user=os.environ.get('DB2_USER', 'postgres'),
        password=os.environ.get('DB2_PASS', 'postgres')
    )
    return src_conn, dest_conn

def convert_to_eur(amount: Decimal, currency: str, rates: dict) -> Decimal:
    if currency == 'EUR':
        return amount
    rate = rates.get(currency)
    if not rate:
        raise ValueError(f"No exchange rate found for {currency}")
    return amount / Decimal(rate)

def sync_orders_to_eur():
    """Extract new orders from source, convert amounts to EUR, and load into target database."""
    eur_rates = OpenExchangeRatesAPI(app_id=APP_KEY_OPEN_EXCHANGE_API).get_latest_rates(base="EUR").get("rates")

    src_conn, dest_conn = create_connections()

    src_cur = src_conn.cursor()
    dst_cur = dest_conn.cursor()

    unprocessed_orders = get_unprocessed_orders(src_cur)
    if len(unprocessed_orders) == 0:
        src_cur.close()
        dst_cur.close()
        src_conn.close()
        dest_conn.close()
        return

    new_orders: List[Order] = []
    for order_id, customer_email, order_date, amount, currency in unprocessed_orders:
        eur_amount = convert_to_eur(amount, currency, rates=eur_rates)
        new_orders.append(Order(order_id, customer_email, order_date, eur_amount, currency))

    dst_cur.executemany(INSERT_PROCESSED_ORDERS_QUERY, [
        (order.order_id, order.customer_email, order.order_date, order.amount, order.currency)
        for order in new_orders
    ])

    src_cur.execute(MARK_ORDERS_AS_PROCESSED)
    dest_conn.commit()
    src_conn.commit()

    logger.info("Transferred %d orders into source database into destination.", len(new_orders))

    if len(new_orders) > 0:
        print("Synced %d new orders to EUR database.", len(new_orders))
    else:
        print("No new orders to sync.")

    src_cur.close()
    dst_cur.close()
    src_conn.close()
    dest_conn.close()

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 0,
}

with DAG(
    dag_id='convert_orders_to_eur',
    default_args=default_args,
    schedule='*/2 * * * *',
    start_date=pendulum.datetime(2025, 5, 1, tz="UTC"),
    catchup=False
) as dag:
    sync_orders_to_eur_task = PythonOperator(
        task_id='sync_orders_to_eur',
        python_callable=sync_orders_to_eur,
    )
