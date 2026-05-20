# Demo_Day-project

## Curricula AI frontend

The frontend is a static browser app in `frontend/`.

1. Install backend dependencies:

   ```powershell
   cd backend
   ..\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Start the FastAPI backend:

   ```powershell
   ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```

   The API will run at `http://127.0.0.1:8000`.

3. Open a frontend page in your browser:

   - `frontend/teacher-login.html`
   - `frontend/student-login.html`
   - `frontend/register.html`
   - `frontend/admin.html`
   - `frontend/student.html`

Teacher login defaults:

```text
Email: teacher@curricula.ai
Password: Teacher@12345
```

The backend uses local SQLite by default for development, so teacher login works without manual database setup. For production/PostgreSQL, copy `backend/.env.example` to `backend/.env` and set `DATABASE_URL`, `GROQ_API_KEY`, `JWT_SECRET_KEY`, `TEACHER_EMAIL`, and `TEACHER_PASSWORD`.

The teacher workspace includes approvals, class/group management, PDF uploads, Groq roadmap generation, assignments, practice exam uploads, and progress analytics. The student workspace includes assigned roadmaps, adaptive question flow, private practice exam submission, downloads, and profile details.
