from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

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
    processing_attempts: int

GET_UNPROCESSED_ORDERS_QUERY = (
    "SELECT order_id, customer_email, order_date, amount, currency, processing_attempts "
    "FROM orders WHERE not processed AND not failed"
)

INSERT_PROCESSED_ORDERS_QUERY = (
    "INSERT INTO orders_eur (order_id, customer_email, order_date, amount_eur, original_currency) "
    "VALUES (%s, %s, %s, %s, %s)"
)

MARK_ORDERS_AS_PROCESSED = "UPDATE orders SET processed = TRUE WHERE order_id IN %s"

MARK_ORDER_AS_FAILED = "UPDATE orders SET failed = TRUE WHERE order_id = %s"

INCREMENT_PROCESSING_ATTEMPT = (
    "UPDATE orders SET processing_attempts = processing_attempts + 1 WHERE order_id = %s"
)

APP_KEY_OPEN_EXCHANGE_API = os.environ.get("OXR_APP_ID")

MAX_PROCESSING_ATTEMPS = os.environ.get("MAX_PROCESSING_ATTEMPS")

def get_unprocessed_orders(cursor: PgCursor) -> List[Order]:
    cursor.execute(GET_UNPROCESSED_ORDERS_QUERY)
    return cursor.fetchall()

def create_connections():
    src_conn = psycopg2.connect(
        host=os.environ.get('ORDERS_DB_HOST', ''),
        dbname=os.environ.get('ORDERS_DB_NAME', ''),
        user=os.environ.get('ORDERS_DB_USER', ''),
        password=os.environ.get('ORDERS_DB_PASS', '')
    )
    dest_conn = psycopg2.connect(
        host=os.environ.get('ORDERS_DB_EUR_HOST', ''),
        dbname=os.environ.get('ORDERS_DB_EUR_NAME', ''),
        user=os.environ.get('ORDERS_DB_EUR_USER', ''),
        password=os.environ.get('ORDERS_DB_EUR_PASS', '')
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
    try:
        logger.info("Starting sync process...")
        # 1. API виклик
        try:
            eur_rates = OpenExchangeRatesAPI(app_id=APP_KEY_OPEN_EXCHANGE_API).get_latest_rates(base="EUR").get("rates")
        except Exception as e:
            logger.error("Failed to fetch exchange rates: %s", e)
            raise

        # 2. Підключення до баз
        try:
            src_conn, dest_conn = create_connections()
            src_cur = src_conn.cursor()
            dst_cur = dest_conn.cursor()
        except Exception as e:
            logger.error("Failed to connect to databases: %s", e)
            raise

        try:
            # 3. Читання необроблених
            unprocessed_orders = get_unprocessed_orders(src_cur)
            if not unprocessed_orders:
                logger.info("No unprocessed orders found.")
                return

            # 4. Конвертація та додавання
            new_orders: List[Order] = []
            for order_id, customer_email, order_date, amount, currency, processing_attempts in unprocessed_orders:
                try:
                    eur_amount = convert_to_eur(amount, currency, rates=eur_rates)
                except ValueError as conv_err:
                    logger.warning("Skipping order %s due to conversion error: %s", order_id, conv_err)

                    src_cur.execute(INCREMENT_PROCESSING_ATTEMPT, order_id)
                    # Mark as failed if limit reached
                    if processing_attempts + 1 >= MAX_PROCESSING_ATTEMPS:
                        src_cur.execute(MARK_ORDER_AS_FAILED, order_id)
                    continue

                new_orders.append(Order(order_id, customer_email, order_date, eur_amount, currency, 0))

            if new_orders:
                dst_cur.executemany(INSERT_PROCESSED_ORDERS_QUERY, [
                    (order.order_id, order.customer_email, order.order_date, order.amount, order.currency)
                    for order in new_orders
                ])
                order_ids = tuple(order.order_id for order in new_orders)
                src_cur.execute(MARK_ORDERS_AS_PROCESSED, (order_ids,))
                dest_conn.commit()
                src_conn.commit()
                logger.info("Synced %d orders to EUR DB", len(new_orders))
            else:
                logger.info("No orders to insert after conversion.")

        except Exception as e:
            logger.error("Sync process failed during data processing: %s", e)
            src_conn.rollback()
            dest_conn.rollback()
            raise

    except Exception as e:
        logger.exception("Sync DAG failed with error: %s", e)

    finally:
        try:
            src_cur.close()
            dst_cur.close()
            src_conn.close()
            dest_conn.close()
        except Exception:
            pass  # Ігноруємо, якщо щось уже закрите


with DAG(
    dag_id='convert_orders_to_eur',
    schedule='@hourly',
    start_date=days_ago(1),
    catchup=False
) as dag:
    sync_orders_to_eur_task = PythonOperator(
        task_id='sync_orders_to_eur',
        python_callable=sync_orders_to_eur,
    )
