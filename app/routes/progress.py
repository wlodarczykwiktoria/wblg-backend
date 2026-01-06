from typing import Optional, List, Dict
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..db import db_conn, touch_session

router = APIRouter(tags=["progress"])


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


@router.get("/progress/summary", response_model=List[BookSummaryOut])
def get_all_books_summary(
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-Id"),
):
    """
    Zwraca WSZYSTKIE książki + ich chaptery (extracty) + najnowszy wynik
    dla każdej pary (book_id, extract_id) w ramach danej sesji.
    completed = zagrał choć raz (czyli wynik istnieje).
    """
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-Id header")

    with db_conn() as conn:
        touch_session(conn, x_session_id)

        # 1) wszystkie książki + genre
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.book_id, b.title, b.author, g.name
                FROM book b
                LEFT JOIN genre g ON g.genre_id = b.genre_id
                ORDER BY b.title
                """
            )
            book_rows = cur.fetchall()

        # 2) wszystkie extracty (chaptery) dla wszystkich książek
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.book_id, e.extract_id, e.extract_no, e.extract_title
                FROM extract e
                ORDER BY e.book_id, e.extract_no
                """
            )
            extract_rows = cur.fetchall()

        # 3) najnowszy wynik per (book_id, extract_id) dla tej sesji
        # Postgres DISTINCT ON pozwala wybrać latest per grupa
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (gr.book_id, gr.extract_id)
                    gr.book_id,
                    gr.extract_id,
                    gr.result_id,
                    gr.puzzle_type,
                    gr.score,
                    gr.duration_sec
                FROM game_result gr
                WHERE gr.session_id = %s
                ORDER BY gr.book_id, gr.extract_id, gr.played_at DESC, gr.result_id DESC
                """,
                (x_session_id,),
            )
            result_rows = cur.fetchall()

    # map: book_id -> BookOut
    books: Dict[int, BookOut] = {
        r[0]: BookOut(book_id=r[0], title=r[1], author=r[2], genre=r[3])
        for r in book_rows
    }

    # map: (book_id, extract_id) -> ResultOut
    results_by_key: Dict[tuple[int, int], ResultOut] = {
        (r[0], r[1]): ResultOut(
            result_id=r[2],
            puzzle_type=r[3],
            score=r[4],
            duration_sec=r[5],
        )
        for r in result_rows
    }

    # map: book_id -> list[ChapterOut]
    chapters_by_book: Dict[int, List[ChapterOut]] = {bid: [] for bid in books.keys()}
    completed_count: Dict[int, int] = {bid: 0 for bid in books.keys()}
    total_count: Dict[int, int] = {bid: 0 for bid in books.keys()}

    for book_id, extract_id, extract_no, extract_title in extract_rows:
        # jeśli w bazie są extracty do książek, których nie ma w tabeli book, pomijamy
        if book_id not in books:
            continue

        res = results_by_key.get((book_id, extract_id))
        is_completed = res is not None

        total_count[book_id] += 1
        if is_completed:
            completed_count[book_id] += 1

        chapters_by_book[book_id].append(
            ChapterOut(
                extract_id=extract_id,
                extract_no=extract_no,
                extract_title=extract_title,
                completed=is_completed,
                result=res,
            )
        )

    # składamy listę BookSummaryOut w tej samej kolejności co books (ORDER BY title)
    summaries: List[BookSummaryOut] = []
    for b in book_rows:
        bid = b[0]
        summaries.append(
            BookSummaryOut(
                book=books[bid],
                stats=StatsOut(
                    total_chapters=total_count.get(bid, 0),
                    completed_chapters=completed_count.get(bid, 0),
                ),
                chapters=chapters_by_book.get(bid, []),
            )
        )

    return summaries
