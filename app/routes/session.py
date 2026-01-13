# app/routes/session.py

import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..db import db_conn

router = APIRouter(tags=["session"])


class SessionCreateIn(BaseModel):
    nick: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Optional player nickname"
    )


class SessionResponse(BaseModel):
    session_id: str
    nick: Optional[str] = None


@router.post("/session", response_model=SessionResponse, status_code=201)
def create_session(payload: SessionCreateIn = SessionCreateIn()):
    session_id = str(uuid.uuid4())

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.session (
                    session_id, nick, created_at, last_activity_at
                )
                VALUES (%s, %s, now(), now())
                """,
                (session_id, payload.nick),
            )
        conn.commit()

    return {
        "session_id": session_id,
        "nick": payload.nick,
    }
