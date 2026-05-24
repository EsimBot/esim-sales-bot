import psycopg
from psycopg.rows import dict_row
import os 
from psycopg_pool import ConnectionPool
from config import DATABASE_URL

# Setup the connection pool
db_pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=5,
    timeout=30.0
)

DB_URL = os.getenv("DATABASE_URL")

def get_connection():
    """Borrow a connection from the pool"""
    return db_pool.connection()

# utils/db.py

def init_db():
    try: 
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. USERS TABLE
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        balance DECIMAL(10, 2) DEFAULT 0.0,
                        payment_topic_id BIGINT,
                        support_topic_id BIGINT,
                        is_activated BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # Patches for existing users
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS balance DECIMAL(10, 2) DEFAULT 0.0;")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS payment_topic_id BIGINT;")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS support_topic_id BIGINT;")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_activated BOOLEAN DEFAULT FALSE;")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE;")

                # 2. ORDERS TABLE
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT REFERENCES users(user_id),
                        order_code TEXT UNIQUE,
                        price NUMERIC(10, 2),
                        region TEXT,
                        duration TEXT,
                        status TEXT DEFAULT 'pending',
                        smdp_address TEXT,
                        activation_code TEXT,
                        qr_code_file_id TEXT,
                        is_renewable BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # Patches for existing users (No Duplicates)
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS price NUMERIC(10, 2);")
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS region TEXT;")
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS duration TEXT;")
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS smdp_address TEXT;")
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS activation_code TEXT;")
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS qr_code_file_id TEXT;")
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS is_renewable BOOLEAN DEFAULT FALSE;")

                # 3. TRANSACTIONS TABLE
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        id SERIAL PRIMARY KEY,
                        order_id VARCHAR(50) UNIQUE NOT NULL,
                        user_id BIGINT NOT NULL,
                        amount NUMERIC(10, 2) NOT NULL,
                        coin_amount VARCHAR(50),
                        currency VARCHAR(10) NOT NULL,
                        status VARCHAR(20) DEFAULT 'pending',
                        invoice_url TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS invoice_url TEXT;")
                cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")

            conn.commit()
        print("✅ Database logic is fully synced and patched.")
    except Exception as e:
        print(f"❌ Database Error: {e}")

# --- ADD THIS NEW FUNCTION BELOW init_db() ---


def get_user_payment_topic(user_id):
    """Retrieves the existing topic ID for a user if it exists."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payment_topic_id FROM users WHERE user_id = %s", (user_id,))
            result = cur.fetchone()
            return result[0] if result else None

def set_user_payment_topic(user_id, topic_id):
    """Saves the created topic ID to the user's record."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET payment_topic_id = %s WHERE user_id = %s", (topic_id, user_id))
        conn.commit()

def get_user_orders(user_id, offset=0, limit=5):
    """Fetches a paginated slice of eSIM orders and the total count."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Get the specific 5 items
            cur.execute(
                """
                SELECT status, created_at::DATE, region, duration, order_code, is_renewable
                FROM orders
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset)
            )
            rows = cur.fetchall()
            
            # Get the total number of orders for the pagination math
            cur.execute("SELECT COUNT(*) FROM orders WHERE user_id = %s", (user_id,))
            total = cur.fetchone()[0]
            
            return rows, total
    
    
def get_user_balance(user_id):
    """Fetches user balance, defaulting to 0.0 if not found."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            result = cur.fetchone()
            # If result is found, return the first column; otherwise, 0.0
            return float(result[0]) if result and result[0] is not None else 0.0 
    
def add_user(user_id: int, username: str):
    """Saves or updates a user in the Railway database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, username, is_blocked)
                VALUES (%s, %s, FALSE)
                ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username, is_blocked = FALSE;
            """, (user_id, username))
        conn.commit()
        
def is_order_id_unique(order_id):
    """Checks the database to ensure an ID hasn't been used yet."""
    # Use 'with' to extract the actual connection from the context manager
    with get_connection() as conn:
        with conn.cursor() as cur:
            # We use str(order_id) to be safe if your DB column is a VARCHAR
            cur.execute("SELECT 1 FROM orders WHERE order_code = %s", (str(order_id),))
            exists = cur.fetchone()
            # If exists is None, the ID is unique (True)
            return exists is None     
        
def create_order_record(order_code, user_id, price, region, duration,is_renewable):
    """Inserts the finalized order with all details into the DB."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # This order MUST match the SQL command above
            cur.execute(
                """
                INSERT INTO orders (order_code, user_id, price, region, duration, is_renewable, status) 
                VALUES (%s, %s, %s, %s, %s, %s,'completed')
                """,
                (str(order_code), user_id, price, region, duration,is_renewable)
            )
        conn.commit()

def deduct_user_balance(user_id, amount):
    """Subtracts the cost from the user's balance."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET balance = balance - %s WHERE user_id = %s",
                (amount, user_id)
            )
        conn.commit()        
        
        
def log_new_transaction(order_id, user_id, amount, coin_amount, currency,invoice_url):
    """Saves a new pending transaction to the ledger."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO transactions (order_id, user_id, amount, coin_amount, currency, status,invoice_url, updated_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, CURRENT_TIMESTAMP)
                """,
                (str(order_id), user_id, amount, str(coin_amount), currency,invoice_url)
            )
        conn.commit()

def get_transaction_history(user_id, limit=5):
    """Fetches the last X transactions for the wallet view."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT created_at::DATE, order_id, status, amount 
                FROM transactions 
                WHERE user_id = %s 
                ORDER BY updated_at DESC 
                LIMIT %s
                """,
                (user_id, limit)
            )
            return cur.fetchall()      
        
def cancel_transaction(order_id):
    """Marks a specific order as canceled in the ledger."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE transactions SET status = 'canceled' WHERE order_id = %s",
                (str(order_id),)
            )
        conn.commit()          
        

def handle_payment_status(order_id, plisio_status):
    """
    Credits user exactly once and returns instructions for alerts.
    Returns: (should_alert, user_id, amount, currency, coin_amount)
    """
    try:
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # 1. Fetch current transaction details
                cur.execute(
                    "SELECT user_id, amount, currency, coin_amount, status FROM transactions WHERE order_id = %s",
                    (str(order_id),)
                )
                row = cur.fetchone()

                if not row: 
                    return False, None, None, None, None # Consistent 5-value return
                
                db_status = row['status']
                user_id = row['user_id']
                amount = float(row['amount'])
                currency = row['currency']
                coin_amount = row['coin_amount']
                
                # 🛡️ THE GHOST FIX: Ensure user exists in the DB before trying to give them money
                cur.execute("""
                    INSERT INTO users (user_id, username, balance) 
                    VALUES (%s, 'Auto_Recovered', 0.00) 
                    ON CONFLICT (user_id) DO NOTHING
                """, (user_id,))

                # 🚀 2. Detect and Credit on Mempool (Instant Credit)
                if plisio_status == 'mempool' and db_status == 'pending':
                    # Add money to user balance
                    cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, user_id))
                    
                    # Update status AND refresh updated_at so it jumps to the top of history
                    cur.execute(
                        """
                        UPDATE transactions 
                        SET status = 'mempool_credited', updated_at = CURRENT_TIMESTAMP 
                        WHERE order_id = %s
                        """, 
                        (str(order_id),)
                    )
                    conn.commit()
                    return True, user_id, amount, currency, coin_amount

                # 🏁 3. Finalize on Completed (Silent if already credited)
                elif plisio_status == 'completed':
                    if db_status == 'mempool_credited':
                        # Already credited! Just finalize status quietly and update timestamp.
                        cur.execute(
                            "UPDATE transactions SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE order_id = %s", 
                            (str(order_id),)
                        )
                        conn.commit()
                        return False, None, None, None, None
                    
                    elif db_status == 'pending':
                        # Missed the mempool ping? Credit them now and update timestamp.
                        cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, user_id))
                        cur.execute(
                            "UPDATE transactions SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE order_id = %s", 
                            (str(order_id),)
                        )
                        cur.execute("UPDATE users SET is_activated = TRUE WHERE user_id = %s", (user_id,))
                        conn.commit()
                        return True, user_id, amount, currency, coin_amount

                return False, None, None, None, None
    except Exception as e:
        print(f"🔥 DB Logic Error: {e}")
        return False, None, None, None, None

def is_user_activated(user_id):
    """Checks if the user has ever completed a deposit."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT is_activated FROM users WHERE user_id = %s", (user_id,))
            result = cur.fetchone()
            return result[0] if result else False    
    
def check_and_get_pending_order(user_id):
    """
    1. Auto-expires anything older than 59 mins.
    2. Returns any active pending order with the exact seconds remaining.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. THE AUTO-CLEANUP (Updates DB before checking)
            cur.execute("""
                UPDATE orders SET status = 'expired' 
                WHERE user_id = %s AND status = 'pending' AND created_at < NOW() - INTERVAL '59 minutes';
            """, (user_id,))
            
            cur.execute("""
                UPDATE transactions SET status = 'expired' 
                WHERE user_id = %s AND status = 'pending' AND created_at < NOW() - INTERVAL '59 minutes';
            """, (user_id,))
            conn.commit()

            # 2. CHECK eSIM ORDERS
            cur.execute("""
                SELECT 'esim' as type, order_code as id, price as amount, 
                       EXTRACT(EPOCH FROM (created_at + INTERVAL '59 minutes' - NOW())) as sec_left 
                FROM orders WHERE user_id = %s AND status = 'pending'
            """, (user_id,))
            esim_pending = cur.fetchone()
            if esim_pending: return esim_pending

            # 3. CHECK WALLET TOP-UPS
            cur.execute("""
                SELECT 'wallet' as type, order_id as id, amount, 
                       EXTRACT(EPOCH FROM (created_at + INTERVAL '59 minutes' - NOW())) as sec_left 
                FROM transactions WHERE user_id = %s AND status = 'pending'
            """, (user_id,))
            wallet_pending = cur.fetchone()
            
            return wallet_pending

def force_cancel_order(order_id, order_type):
    """Triggered when user clicks 'Cancel & Start New'."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if order_type == 'esim':
                cur.execute("UPDATE orders SET status = 'canceled' WHERE order_code = %s", (str(order_id),))
            else:
                cur.execute("UPDATE transactions SET status = 'canceled' WHERE order_id = %s", (str(order_id),))
        conn.commit()  
        
def get_order_by_code(order_code):
    """Fetches the core details of an order to build the Admin Topic summary."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, price, region, duration, status FROM orders WHERE order_code = %s",
                (str(order_code),)
            )
            return cur.fetchone()
        
def expire_old_orders():
    """
    Finds pending orders older than 59 minutes, updates them to 'expired', 
    and returns the list of affected users so the bot can notify them.
    """
    try:
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # The RETURNING clause lets us update and select in one step!
                cur.execute(
                    """
                    UPDATE transactions 
                    SET status = 'expired' 
                    WHERE status = 'pending' 
                    AND created_at < NOW() - INTERVAL '59 minutes'
                    RETURNING order_id, user_id;
                    """
                )
                expired_orders = cur.fetchall()
                conn.commit()
                return expired_orders
    except Exception as e:
        print(f"🔥 DB Expiration Task Error: {e}")
        return []        

def save_delivery_details(order_code, smdp, activation, qr_id):
    """Saves the eSIM data from the Wizard and officially marks it as delivered."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE orders 
                SET smdp_address = %s, 
                    activation_code = %s, 
                    qr_code_file_id = %s, 
                    status = 'delivered'
                WHERE order_code = %s
                """,
                (smdp, activation, qr_id, str(order_code))
            )
        conn.commit()

def get_delivery_details(order_code):
    """Pulls the saved eSIM data when you click 'Edit & Resend'."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT smdp_address, activation_code, qr_code_file_id FROM orders WHERE order_code = %s",
                (str(order_code),)
            )
            return cur.fetchone()    
        
        
def get_support_topic(user_id):
    """Checks if a user already has a dedicated support topic."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT support_topic_id FROM users WHERE user_id = %s", (user_id,))
            result = cur.fetchone()
            return result[0] if result else None

def set_support_topic(user_id, topic_id):
    """Saves the topic ID for a user."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET support_topic_id = %s WHERE user_id = %s", (topic_id, user_id))
        conn.commit()

def get_user_by_topic(topic_id):
    """Finds which user belongs to a specific topic ID (for Admin replies)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM users WHERE support_topic_id = %s", (topic_id,))
            result = cur.fetchone()
            return result[0] if result else None         
        
def get_admin_stats():
    """Fetches global statistics for the admin dashboard."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users WHERE is_blocked = FALSE")
            total_users = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM users WHERE is_blocked = TRUE")
            blocked_users = cur.fetchone()[0]
            
            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE status IN ('completed', 'mempool_credited')")
            total_revenue = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'delivered'")
            active_esims = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'expired'")
            expired_esims = cur.fetchone()[0]
            
            return total_users, total_revenue, active_esims, expired_esims, blocked_users

def check_user_exists(user_id):
    """Verifies if a user ID is actually in the database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
            return cur.fetchone() is not None

def get_all_user_ids():
    """Fetches every registered user ID for global broadcasts."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM users WHERE is_blocked = FALSE")
            return [row[0] for row in cur.fetchall()]   
        
def mark_user_blocked(user_id):
    """Flags a user as blocked if Telegram rejects a message to them."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET is_blocked = TRUE WHERE user_id = %s", (user_id,))
        conn.commit()          

def close_db():
    """Closes the connection pool gracefully."""
    if db_pool:
        db_pool.close()
        print("🔌 Database connection pool closed.")        