from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..db import db_conn, touch_session

router = APIRouter(tags=["results"])

class GameResultIn(BaseModel):
    book_id: int
    extract_id: int
    puzzle_type: str = Field(min_length=1)
    score: int = 0
    duration_sec: int = 0
    played_at: Optional[datetime] = None

@router.post("/results")
def save_result(
    payload: GameResultIn,
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-Id"),
):
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-Id header")

    played_at = payload.played_at or datetime.now(timezone.utc)

    with db_conn() as conn:
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
            result_id = cur.fetchone()[0]

        conn.commit()

    return {"ok": True, "result_id": result_id}
