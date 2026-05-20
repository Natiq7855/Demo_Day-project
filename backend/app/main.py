from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.routers import admin, auth, practice_exams, roadmaps, users

app = FastAPI(title="Curricula AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Curricula AI API"}


@app.on_event("startup")
def prepare_dev_database():
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(roadmaps.router, prefix="/roadmaps", tags=["roadmaps"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(practice_exams.router, prefix="/practice-exams", tags=["practice-exams"])
