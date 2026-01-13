# app/routes/results.py

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from ..db import db_conn, touch_session

router = APIRouter(tags=["results"])


class ResultsSummaryOut(BaseModel):
    book_id: int
    chapters_completed: int
    avg_accuracy: float
    avg_duration_sec: float
    most_played_puzzle_type: Optional[str] = None


@router.get("/results/summary", response_model=ResultsSummaryOut)
def results_summary(
    book_id: int = Query(..., ge=1),
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-Id"),
):
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-Id header")

    with db_conn() as conn:
        touch_session(conn, x_session_id)

        with conn.cursor() as cur:
            cur.execute(
                """
                WITH base AS (
                  SELECT
                    extract_id,
                    puzzle_type,
                    duration_sec,
                    accuracy
                  FROM public.game_result
                  WHERE session_id = %s AND book_id = %s
                ),
                mode_type AS (
                  SELECT puzzle_type
                  FROM base
                  GROUP BY puzzle_type
                  ORDER BY COUNT(*) DESC, puzzle_type ASC
                  LIMIT 1
                )
                SELECT
                  %s::bigint AS book_id,
                  COALESCE(COUNT(DISTINCT base.extract_id), 0) AS chapters_completed,
                  COALESCE(AVG(base.accuracy), 0)::float8 AS avg_accuracy,
                  COALESCE(AVG(base.duration_sec), 0)::float8 AS avg_duration_sec,
                  (SELECT puzzle_type FROM mode_type) AS most_played_puzzle_type
                FROM base
                """,
                (x_session_id, book_id, book_id),
            )

            row = cur.fetchone()
            if row is None:
                # praktycznie nie powinno się zdarzyć, ale zostawiamy bezpiecznik
                raise HTTPException(status_code=500, detail="Failed to compute summary")

    return {
        "book_id": int(row[0]),
        "chapters_completed": int(row[1]),
        "avg_accuracy": float(row[2]),
        "avg_duration_sec": float(row[3]),
        "most_played_puzzle_type": row[4],
    }
