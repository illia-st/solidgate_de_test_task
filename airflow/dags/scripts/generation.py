import os
import uuid
import random
from datetime import datetime, timedelta
import psycopg2

def generate_orders_to_db(count=5000):
    """Generate `count` random orders and insert into the source database (Postgres-1)."""
    # Database connection parameters from environment
    db_host = os.environ.get('DB1_HOST', 'localhost')
    db_name = os.environ.get('DB1_NAME', 'orders_db')
    db_user = os.environ.get('DB1_USER', 'postgres')
    db_pass = os.environ.get('DB1_PASS', 'postgres')
    
    conn = psycopg2.connect(host=db_host, user=db_user, password=db_pass, port=5440)
    cur = conn.cursor()
    now = datetime.now()
    orders = []
    for _ in range(count):
        order_id = str(uuid.uuid4())
        # Generate random email
        customer_email = f"user{random.randint(1, 100000)}@example.com"
        # Random date within last 7 days
        random_offset = random.random() * 7 * 24 * 60 * 60  # seconds in 7 days
        order_date = now - timedelta(seconds=random_offset)
        # Random amount up to 1000, with 2 decimal places
        amount = round(random.uniform(1, 1000), 2)
        # Random currency (some common currencies including EUR, but could be others)
        currency = random.choice(['USD', 'EUR', 'GBP', 'UAH'])
        orders.append((order_id, customer_email, order_date, amount, currency))
    # Insert into orders table
    insert_query = "INSERT INTO orders (order_id, customer_email, order_date, amount, currency) VALUES (%s, %s, %s, %s, %s)"
    cur.executemany(insert_query, orders)
    conn.commit()
    print(f"Inserted {len(orders)} new orders into source database.")
    cur.close()
    conn.close()

generate_orders_to_db(10)
