from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.routers import admin, auth, practice_exams, roadmaps, users

app = FastAPI(title="Curricula AI API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
    ],
    allow_origin_regex=r"http://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
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
        with engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(practice_exams)"))
            }
            if "answer_key" not in columns:
                connection.execute(text("ALTER TABLE practice_exams ADD COLUMN answer_key TEXT"))
                connection.commit()
            attempt_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(practice_exam_attempts)"))
            }
            if "answers" not in attempt_columns:
                connection.execute(text("ALTER TABLE practice_exam_attempts ADD COLUMN answers TEXT"))
            if "correct_count" not in attempt_columns:
                connection.execute(text("ALTER TABLE practice_exam_attempts ADD COLUMN correct_count INTEGER"))
            if "total_questions" not in attempt_columns:
                connection.execute(text("ALTER TABLE practice_exam_attempts ADD COLUMN total_questions INTEGER"))
            source_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(roadmap_source_pdfs)"))
            }
            if "page_start" not in source_columns:
                connection.execute(text("ALTER TABLE roadmap_source_pdfs ADD COLUMN page_start INTEGER"))
            if "page_end" not in source_columns:
                connection.execute(text("ALTER TABLE roadmap_source_pdfs ADD COLUMN page_end INTEGER"))

            item_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(roadmap_items)"))
            }
            if "mini_roadmap_id" not in item_columns:
                connection.execute(text("ALTER TABLE roadmap_items ADD COLUMN mini_roadmap_id INTEGER"))
            if "order_in_mini" not in item_columns:
                connection.execute(text("ALTER TABLE roadmap_items ADD COLUMN order_in_mini INTEGER"))
            if "question_text" not in item_columns:
                connection.execute(text("ALTER TABLE roadmap_items ADD COLUMN question_text TEXT"))
            if "media_type" not in item_columns:
                connection.execute(text("ALTER TABLE roadmap_items ADD COLUMN media_type TEXT"))
            if "media_path" not in item_columns:
                connection.execute(text("ALTER TABLE roadmap_items ADD COLUMN media_path TEXT"))
            if "choices" not in item_columns:
                connection.execute(text("ALTER TABLE roadmap_items ADD COLUMN choices TEXT"))
            if "answer_key" not in item_columns:
                connection.execute(text("ALTER TABLE roadmap_items ADD COLUMN answer_key TEXT"))

            mini_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(roadmap_minis)"))
            }
            if "title" not in mini_columns:
                connection.execute(text("ALTER TABLE roadmap_minis ADD COLUMN title TEXT"))

            attempt_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(roadmap_attempts)"))
            }
            if "mini_roadmap_id" not in attempt_columns:
                connection.execute(text("ALTER TABLE roadmap_attempts ADD COLUMN mini_roadmap_id INTEGER"))

            state_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(roadmap_state)"))
            }
            if "mini_roadmap_id" not in state_columns:
                connection.execute(text("ALTER TABLE roadmap_state ADD COLUMN mini_roadmap_id INTEGER"))
            if "step_index" not in state_columns:
                connection.execute(text("ALTER TABLE roadmap_state ADD COLUMN step_index INTEGER"))

            connection.commit()


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(roadmaps.router, prefix="/roadmaps", tags=["roadmaps"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(practice_exams.router, prefix="/practice-exams", tags=["practice-exams"])
