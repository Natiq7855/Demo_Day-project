from fastapi import FastAPI

from app.routers import admin, auth, practice_exams, roadmaps, users

app = FastAPI(title="Curricula AI API")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(roadmaps.router, prefix="/roadmaps", tags=["roadmaps"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(practice_exams.router, prefix="/practice-exams", tags=["practice-exams"])
