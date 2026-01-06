import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import db_conn

router = APIRouter(tags=["session"])

class SessionResponse(BaseModel):
    session_id: str

@router.post("/session", response_model=SessionResponse)
def create_session():
    session_id = str(uuid.uuid4())
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO session (session_id, created_at, last_activity_at)
                VALUES (%s, now(), now())
                """,
                (session_id,),
            )
        conn.commit()
    return {"session_id": session_id}
