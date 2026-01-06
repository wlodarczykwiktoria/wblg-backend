from typing import Optional
from fastapi import APIRouter, Header, HTTPException

from ..db import db_conn, touch_session

router = APIRouter(tags=["books"])


@router.get("/books")
def list_books(
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-Id"),
):
    """
    Zwraca listę książek w formacie zgodnym z frontendowym interfejsem Book:
    id, title, author, year, genre, chapters, completedChapters

    Jeśli podasz X-Session-Id:
    - liczymy completedChapters dla tej sesji
    - robimy touch last_activity_at
    Jeśli nie podasz:
    - completedChapters = 0
    """
    with db_conn() as conn:
        if x_session_id:
            touch_session(conn, x_session_id)

        with conn.cursor() as cur:
            if x_session_id:
                cur.execute(
                    """
                    SELECT
                      b.book_id AS id,
                      b.title,
                      COALESCE(b.author, '') AS author,
                      COALESCE(b.year, 0) AS year,
                      COALESCE(g.name, '') AS genre,
                      COUNT(DISTINCT e.extract_id)::int AS chapters,
                      COUNT(DISTINCT gr.extract_id)::int AS "completedChapters"
                    FROM book b
                    LEFT JOIN genre g ON g.genre_id = b.genre_id
                    LEFT JOIN extract e ON e.book_id = b.book_id
                    LEFT JOIN game_result gr
                      ON gr.book_id = b.book_id
                     AND gr.session_id = %s
                     AND gr.extract_id = e.extract_id
                    GROUP BY b.book_id, b.title, b.author, b.year, g.name
                    ORDER BY b.book_id;
                    """,
                    (x_session_id,),
                )
            else:
                # Bez sesji: completedChapters = 0
                cur.execute(
                    """
                    SELECT
                      b.book_id AS id,
                      b.title,
                      COALESCE(b.author, '') AS author,
                      COALESCE(b.year, 0) AS year,
                      COALESCE(g.name, '') AS genre,
                      COUNT(DISTINCT e.extract_id)::int AS chapters,
                      0::int AS "completedChapters"
                    FROM book b
                    LEFT JOIN genre g ON g.genre_id = b.genre_id
                    LEFT JOIN extract e ON e.book_id = b.book_id
                    GROUP BY b.book_id, b.title, b.author, b.year, g.name
                    ORDER BY b.book_id;
                    """
                )

            rows = cur.fetchall()

    # rows -> list dictów
    return [
        {
            "id": r[0],
            "title": r[1],
            "author": r[2],
            "year": r[3],
            "genre": r[4],
            "chapters": r[5],
            "completedChapters": r[6],
        }
        for r in rows
    ]
