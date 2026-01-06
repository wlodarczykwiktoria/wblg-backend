from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .settings import ALLOWED_ORIGINS
from .routes.session import router as session_router
from .routes.results import router as results_router
from .routes.progress import router as progress_router
from .routes.books import router as books_router

app = FastAPI(title="WBLG Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(session_router)
app.include_router(results_router)
app.include_router(progress_router)
app.include_router(books_router)
