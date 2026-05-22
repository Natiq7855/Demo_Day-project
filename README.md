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

   The API will run at `http://127.0.0.1:8000` and also serves the frontend from the same origin.

3. Configure environment files:

   - Copy `backend/.env.example` to `backend/.env` and set `GEMINI_API_KEY` (required for roadmap generation).
   - Copy `frontend/config.example.js` to `frontend/config.js` if you need a non-default API URL.

4. Open the app in your browser:

   - `http://127.0.0.1:8000/teacher-login.html` (recommended)
   - or open the HTML files under `frontend/` directly

Teacher login defaults:

```text
Email: teacher@curricula.ai
Password: Teacher@12345
```

The backend uses local SQLite by default for development, so teacher login works without manual database setup. PDF uploads must be text-based (not scanned images). For production/PostgreSQL, set `DATABASE_URL` in `backend/.env` along with `GEMINI_API_KEY`, `JWT_SECRET_KEY`, `TEACHER_EMAIL`, and `TEACHER_PASSWORD`.

The teacher workspace includes approvals, class/group management, PDF uploads, Gemini-powered roadmap generation, assignments, practice exam uploads, and progress analytics. The student workspace includes assigned roadmaps, adaptive question flow, private practice exam submission, downloads, and profile details.
