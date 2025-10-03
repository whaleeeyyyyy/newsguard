import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2 import sql

# --- Configuration ---
DB_HOST = 'localhost'
DB_PORT = '5432'
ROOT_USER = 'postgres'  # Your superuser
ROOT_PASSWORD = 'BreadSQL020227!'  # <-- REPLACE

# --- New Database and User Details ---
APP_DB_NAME = 'newsguard_db'
APP_USER = 'newsguard_user'
APP_PASSWORD = 'newsguard_password123'  # <-- REPLACE with a secure password

def create_database(db_name, user, password):
    """Creates a PostgreSQL DB and user for NewsGuard project."""
    try:
        conn = psycopg2.connect(
            dbname='postgres',
            user=ROOT_USER,
            password=ROOT_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        print("✅ Connected to PostgreSQL server successfully.")

    except psycopg2.OperationalError as e:
        print(f"❌ Could not connect to PostgreSQL server: {e}")
        return

    # Create user
    try:
        cur.execute(
            sql.SQL("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = %s) THEN
                    CREATE USER {} WITH PASSWORD %s;
                END IF;
            END
            $$;
            """).format(sql.Identifier(user)),
            (user, password)
        )
        print(f"✅ User '{user}' created or already exists.")

    except Exception as e:
        print(f"❌ Error creating user: {e}")
        cur.close()
        conn.close()
        return

    # Create database
    try:
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s;", (db_name,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(
                sql.SQL("CREATE DATABASE {} OWNER {};").format(
                    sql.Identifier(db_name),
                    sql.Identifier(user)
                )
            )
            print(f"✅ Database '{db_name}' created successfully.")
        else:
            print(f"✅ Database '{db_name}' already exists.")

    except Exception as e:
        print(f"❌ Error creating database: {e}")

    cur.close()
    conn.close()

    print("\n🎉 NewsGuard DB setup complete!")
    print(f"Connect in pgAdmin or SQLAlchemy with:")
    print(f"  Host: {DB_HOST}")
    print(f"  Port: {DB_PORT}")
    print(f"  DB Name: {APP_DB_NAME}")
    print(f"  User: {APP_USER}")
    print(f"  Password: {APP_PASSWORD}")

if __name__ == "__main__":
    create_database(APP_DB_NAME, APP_USER, APP_PASSWORD)
