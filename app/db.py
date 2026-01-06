import psycopg
from fastapi import HTTPException
from .settings import DATABASE_URL

def db_conn() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)

def touch_session(conn: psycopg.Connection, session_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE session
            SET last_activity_at = now()
            WHERE session_id = %s
            """,
            (session_id,),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Unknown session_id")
