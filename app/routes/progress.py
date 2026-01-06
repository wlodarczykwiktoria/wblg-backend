from typing import Optional, List, Dict
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..db import db_conn, touch_session

router = APIRouter(tags=["books"])


class ResultOut(BaseModel):
    result_id: int
    puzzle_type: str
    score: int
    duration_sec: int


class ChapterOut(BaseModel):
    extract_id: int
    extract_no: int
    extract_title: Optional[str] = None
    completed: bool
    result: Optional[ResultOut] = None


class BookOut(BaseModel):
    book_id: int
    title: str
    author: Optional[str] = None
    genre: Optional[str] = None


class StatsOut(BaseModel):
    total_chapters: int
    completed_chapters: int


class BookSummaryOut(BaseModel):
    book: BookOut
    stats: StatsOut
    chapters: List[ChapterOut]


@router.get("/books/{book_id}/summary", response_model=BookSummaryOut)
def get_book_summary(
    book_id: int,
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-Id"),
):
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-Id header")

    with db_conn() as conn:
        touch_session(conn, x_session_id)

        # 1) book + genre
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.book_id, b.title, b.author, g.name
                FROM book b
                LEFT JOIN genre g ON g.genre_id = b.genre_id
                WHERE b.book_id = %s
                """,
                (book_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Book not found")

            book = BookOut(
                book_id=row[0],
                title=row[1],
                author=row[2],
                genre=row[3],
            )

        # 2) chapters (extracts)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT extract_id, extract_no, extract_title
                FROM extract
                WHERE book_id = %s
                ORDER BY extract_no
                """,
                (book_id,),
            )
            extracts = cur.fetchall()

        # 3) latest results per extract for this session+book
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (extract_id)
                    result_id, extract_id, puzzle_type, score, duration_sec
                FROM game_result
                WHERE session_id = %s AND book_id = %s
                ORDER BY extract_id, played_at DESC, result_id DESC
                """,
                (x_session_id, book_id),
            )
            results_rows = cur.fetchall()

    results_by_extract: Dict[int, ResultOut] = {
        r[1]: ResultOut(
            result_id=r[0],
            puzzle_type=r[2],
            score=r[3],
            duration_sec=r[4],
        )
        for r in results_rows
    }

    chapters: List[ChapterOut] = []
    completed = 0

    for extract_id, extract_no, extract_title in extracts:
        res = results_by_extract.get(extract_id)
        is_completed = res is not None
        if is_completed:
            completed += 1

        chapters.append(
            ChapterOut(
                extract_id=extract_id,
                extract_no=extract_no,
                extract_title=extract_title,
                completed=is_completed,
                result=res,
            )
        )

    return BookSummaryOut(
        book=book,
        stats=StatsOut(total_chapters=len(chapters), completed_chapters=completed),
        chapters=chapters,
    )
