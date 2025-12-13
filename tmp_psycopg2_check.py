import psycopg2

try:
    conn = psycopg2.connect(
        "postgresql://app_user:npg_IGZ4D2rHNndq@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
    )
    cur = conn.cursor()
    cur.execute("SELECT current_user;")
    result = cur.fetchone()
    print(f"? psycopg2 SUCCESS: {result}")
    conn.close()
except Exception as e:
    print(f"? psycopg2 FAILED: {type(e).__name__}: {e}")
