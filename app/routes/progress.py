from typing import Optional
from fastapi import APIRouter, Header, HTTPException
from ..db import db_conn

router = APIRouter(tags=["progress"])

@router.get("/progress")
def get_progress(
    book_id: int,
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-Id"),
):
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-Id header")

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH done AS (
                  SELECT DISTINCT gr.extract_id
                  FROM game_result gr
                  WHERE gr.session_id = %s
                    AND gr.book_id = %s
                ),
                stats AS (
                  SELECT
                    COALESCE(MAX(e.extract_no), 0)::int AS max_extract_no,
                    COUNT(*)::int AS completed_extracts
                  FROM done
                  JOIN extract e ON e.extract_id = done.extract_id
                ),
                total AS (
                  SELECT COUNT(*)::int AS total_extracts
                  FROM extract
                  WHERE book_id = %s
                )
                SELECT
                  stats.max_extract_no,
                  stats.completed_extracts,
                  total.total_extracts,
                  CASE
                    WHEN total.total_extracts = 0 THEN 0
                    ELSE ROUND((stats.completed_extracts::numeric / total.total_extracts) * 100, 2)
                  END AS progress_percent
                FROM stats, total;
                """,
                (x_session_id, book_id, book_id),
            )
            row = cur.fetchone()

    return {
        "book_id": book_id,
        "max_extract_no": row[0],
        "completed_extracts": row[1],
        "total_extracts": row[2],
        "progress_percent": float(row[3]),
    }
