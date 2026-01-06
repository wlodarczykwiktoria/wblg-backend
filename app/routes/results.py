from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import db_conn, touch_session

router = APIRouter(tags=["results"])


# ---------- MODELE ----------

class GameResultIn(BaseModel):
    book_id: int
    extract_id: int
    puzzle_type: str = Field(min_length=1)
    score: int = 0
    duration_sec: int = 0
    played_at: Optional[datetime] = None


class GameResultOut(BaseModel):
    result_id: int
    book_id: int
    extract_id: int
    puzzle_type: str
    score: int
    duration_sec: int
    played_at: datetime


# ---------- ENDPOINTY ----------

@router.post("/results")
def save_result(
    payload: GameResultIn,
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-Id"),
):
    """
    Zapisuje wynik gry do tabeli game_result.
    Session id jest przekazywane w headerze X-Session-Id.
    """
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-Id header")

    played_at = payload.played_at or datetime.now(timezone.utc)

    with db_conn() as conn:
        # opcjonalnie: zaktualizuj last_activity_at
        touch_session(conn, x_session_id)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO game_result (
                    session_id, book_id, extract_id,
                    puzzle_type, score, duration_sec, played_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING result_id
                """,
                (
                    x_session_id,
                    payload.book_id,
                    payload.extract_id,
                    payload.puzzle_type,
                    payload.score,
                    payload.duration_sec,
                    played_at,
                ),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=500, detail="Failed to insert result")
            result_id = row[0]

        conn.commit()

    return {"ok": True, "result_id": result_id}


@router.get("/results/latest", response_model=List[GameResultOut])
def get_latest_results(
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-Id"),
    book_id: Optional[int] = Query(default=None),
):
    """
    Zwraca tylko NAJŚWIEŻSZY wynik dla każdej pary (book_id, extract_id)
    w ramach danej sesji (X-Session-Id).

    Jeśli podasz book_id, zwróci latest wyniki tylko dla tej książki.
    """
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-Id header")

    # Postgres: DISTINCT ON wybiera pierwszy rekord dla grupy, więc
    # ORDER BY musi mieć najpierw te same kolumny co DISTINCT ON, a potem sortowanie "najnowszy".
    if book_id is None:
        sql = """
            SELECT DISTINCT ON (book_id, extract_id)
                result_id, book_id, extract_id, puzzle_type, score, duration_sec, played_at
            FROM game_result
            WHERE session_id = %s
            ORDER BY book_id, extract_id, played_at DESC, result_id DESC
        """
        params = (x_session_id,)
    else:
        sql = """
            SELECT DISTINCT ON (book_id, extract_id)
                result_id, book_id, extract_id, puzzle_type, score, duration_sec, played_at
            FROM game_result
            WHERE session_id = %s AND book_id = %s
            ORDER BY book_id, extract_id, played_at DESC, result_id DESC
        """
        params = (x_session_id, book_id)

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        GameResultOut(
            result_id=r[0],
            book_id=r[1],
            extract_id=r[2],
            puzzle_type=r[3],
            score=r[4],
            duration_sec=r[5],
            played_at=r[6],
        )
        for r in rows
    ]
