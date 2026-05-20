CREATE TYPE user_role AS ENUM ('admin', 'student');
CREATE TYPE user_status AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE attempt_status AS ENUM ('correct', 'incorrect', 'skipped');
CREATE TYPE roadmap_phase AS ENUM ('A', 'A1', 'HINT', 'EXPLAIN', 'RETEST');

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'student',
    status user_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE classes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    created_by INTEGER REFERENCES users(id)
);

CREATE TABLE groups (
    id SERIAL PRIMARY KEY,
    class_id INTEGER REFERENCES classes(id),
    name VARCHAR(120) NOT NULL
);

CREATE TABLE student_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    full_name VARCHAR(255) NOT NULL,
    university_group VARCHAR(10) NOT NULL,
    class_id INTEGER REFERENCES classes(id),
    group_id INTEGER REFERENCES groups(id),
    avatar_url VARCHAR(500)
);

CREATE TABLE pdfs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    uploaded_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE pdf_chunks (
    id SERIAL PRIMARY KEY,
    pdf_id INTEGER REFERENCES pdfs(id),
    chapter VARCHAR(120),
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content_text TEXT NOT NULL
);

CREATE TABLE roadmaps (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    pdf_id INTEGER REFERENCES pdfs(id),
    page_start INTEGER,
    page_end INTEGER,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE roadmap_items (
    id SERIAL PRIMARY KEY,
    roadmap_id INTEGER REFERENCES roadmaps(id),
    topic VARCHAR(255) NOT NULL,
    question_type VARCHAR(120) NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    sequence_index INTEGER NOT NULL,
    metadata JSONB
);

CREATE TABLE roadmap_assignments (
    id SERIAL PRIMARY KEY,
    roadmap_id INTEGER REFERENCES roadmaps(id),
    target_type VARCHAR(20) NOT NULL,
    target_id INTEGER NOT NULL,
    assigned_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE roadmap_attempts (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES users(id),
    roadmap_item_id INTEGER REFERENCES roadmap_items(id),
    attempt_no INTEGER NOT NULL,
    status attempt_status NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE ai_questions (
    id SERIAL PRIMARY KEY,
    roadmap_item_id INTEGER REFERENCES roadmap_items(id),
    student_id INTEGER REFERENCES users(id),
    type_label VARCHAR(120) NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    question_text TEXT NOT NULL,
    choices JSONB,
    answer_key JSONB,
    explanation TEXT,
    hint TEXT,
    source VARCHAR(20) NOT NULL DEFAULT 'groq',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE roadmap_state (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES users(id),
    roadmap_item_id INTEGER REFERENCES roadmap_items(id),
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    phase roadmap_phase NOT NULL DEFAULT 'A',
    last_question_id INTEGER REFERENCES ai_questions(id),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE practice_exams (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    uploaded_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE practice_exam_attempts (
    id SERIAL PRIMARY KEY,
    practice_exam_id INTEGER REFERENCES practice_exams(id),
    student_id INTEGER REFERENCES users(id),
    score INTEGER NOT NULL,
    submitted_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE lesson_links (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    url VARCHAR(1000) NOT NULL,
    class_id INTEGER REFERENCES classes(id),
    group_id INTEGER REFERENCES groups(id),
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE monthly_exam_grades (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES users(id),
    exam_date TIMESTAMP NOT NULL,
    grade INTEGER NOT NULL,
    uploaded_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
