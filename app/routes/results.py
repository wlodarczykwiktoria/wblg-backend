# app/routes/results.py

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field, confloat, conint

from ..db import db_conn, touch_session

router = APIRouter(tags=["results"])


# =========================
# MODELE
# =========================

class GameResultIn(BaseModel):
    book_id: int
    extract_no: int  # numer extractu w obrębie książki (1,2,3...)

    puzzle_type: str = Field(min_length=1)
    score: int = 0
    duration_sec: int = 0

    mistakes: conint(ge=0) = 0
    accuracy: confloat(ge=0.0, le=1.0) = 1.0

    played_at: Optional[datetime] = None


class ResultsSummaryOut(BaseModel):
    book_id: int
    chapters_completed: int
    avg_accuracy: float
    avg_duration_sec: float
    most_played_puzzle_type: Optional[str] = None


# =========================
# POST /results
# =========================

@router.post("/results")
def save_result(
    payload: GameResultIn,
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-Id"),
):
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-Id header")

    played_at = payload.played_at or datetime.now(timezone.utc)

    with db_conn() as conn:
        # sprawdź / odśwież sesję
        touch_session(conn, x_session_id)

        with conn.cursor() as cur:
            # 1) mapowanie extract_no -> extract_id w ramach book_id
            cur.execute(
                """
                SELECT extract_id
                FROM public.extract
                WHERE book_id = %s AND extract_no = %s
                """,
                (payload.book_id, payload.extract_no),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid extract_no for this book_id",
                )

            extract_id = row[0]

            # 2) zapis wyniku gry
            cur.execute(
                """
                INSERT INTO public.game_result (
                    session_id, book_id, extract_id,
                    puzzle_type, score, duration_sec,
                    mistakes, accuracy,
                    played_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING result_id
                """,
                (
                    x_session_id,
                    payload.book_id,
                    extract_id,
                    payload.puzzle_type,
                    payload.score,
                    payload.duration_sec,
                    payload.mistakes,
                    payload.accuracy,
                    played_at,
                ),
            )

            result_id = cur.fetchone()[0]

        conn.commit()

    return {
        "ok": True,
        "result_id": result_id,
        "book_id": payload.book_id,
        "extract_no": payload.extract_no,
    }


# =========================
# GET /results/summary
# =========================

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
                    WHERE session_id = %s
                      AND book_id = %s
                ),
                most_played AS (
                    SELECT puzzle_type
                    FROM base
                    GROUP BY puzzle_type
                    ORDER BY COUNT(*) DESC, puzzle_type ASC
                    LIMIT 1
                )
                SELECT
                    %s::bigint AS book_id,
                    COALESCE(COUNT(DISTINCT extract_id), 0) AS chapters_completed,
                    COALESCE(AVG(accuracy), 0)::float8 AS avg_accuracy,
                    COALESCE(AVG(duration_sec), 0)::float8 AS avg_duration_sec,
                    (SELECT puzzle_type FROM most_played) AS most_played_puzzle_type
                FROM base
                """,
                (x_session_id, book_id, book_id),
            )

            row = cur.fetchone()

    return {
        "book_id": int(row[0]),
        "chapters_completed": int(row[1]),
        "avg_accuracy": float(row[2]),
        "avg_duration_sec": float(row[3]),
        "most_played_puzzle_type": row[4],
    }
