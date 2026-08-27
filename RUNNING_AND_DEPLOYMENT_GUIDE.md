# AI Job Application Autopilot — Running & Deployment Guide (Supabase + Vercel)

This guide covers:
1. **Supabase Database Setup** (Free Cloud PostgreSQL 16)
2. **Local Development Setup** (Running FastAPI backend + React frontend connected to Supabase)
3. **Production Deployment on Vercel** (Frontend on Vercel + Backend on Railway/Render + Supabase PostgreSQL)

---

## Part 1: Supabase Database Setup

Supabase provides managed PostgreSQL 16 with a visual dashboard, automatic backups, and generous free limits.

```
┌─────────────────────────────────────────────────────────────┐
│                    SUPABASE POSTGRESQL 16                   │
│                                                             │
│  • Visual Table Editor (View resumes, jobs, applications)   │
│  • JSONB support for LangGraph traces & Apollo data         │
│  • Single async connection string for dev & production      │
└─────────────────────────────────────────────────────────────┘
```

### Step 1: Create your Free Supabase Database
1. Go to [https://supabase.com/](https://supabase.com/) and click **Sign Up** / **Sign In**.
2. Click **"New Project"**.
3. Choose your project settings:
   - **Name**: `job-autopilot`
   - **Database Password**: Set a strong password (save this password).
   - **Region**: Select the region closest to you (e.g. `US East`, `EU West`, `Asia South`).
4. Click **Create new project**.

### Step 2: Copy your Connection String
1. In your Supabase dashboard, go to: **Project Settings** (gear icon) > **Database** > scroll down to **Connection String**.
2. Select the **URI** tab.
3. Select **"Connection pooling"** (Transaction mode or Session mode).
4. Copy the connection string. It will look like:
   ```text
   postgresql://postgres.your-project-ref:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```
   *(Or direct: `postgresql://postgres:[YOUR-PASSWORD]@db.your-project-ref.supabase.co:5432/postgres`)*

5. **Convert the prefix to async SQLAlchemy format** (`postgresql+asyncpg://`):
   ```ini
   DATABASE_URL=postgresql+asyncpg://postgres.your-project-ref:your_password@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```

6. Paste this `DATABASE_URL` into your `.env` file in the project root.

---

## Part 2: Local Development Setup

### 1. Prerequisites
- **Python**: `3.11` or `3.12`
- **Node.js**: `v20+` or `v22+` & `npm`
- **Ollama** (Optional, for local LLMs like `minimax-m3:cloud`): [ollama.com](https://ollama.com/)

---

### 2. Backend Setup (FastAPI & LangGraph)

1. **Open a terminal in the project root directory**:
   ```powershell
   cd "c:\Users\Capricon\Desktop\resume project"
   ```

2. **Activate virtual environment** (or create one):
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

4. **Run database migrations against Supabase**:
   ```powershell
   alembic upgrade head
   ```
   *This will instantly create all tables (`users`, `resumes`, `jobs`, `applications`, `agent_runs`) directly in your Supabase project! You can immediately see the new tables in your Supabase web dashboard under the **Table Editor** tab.*

5. **Start the FastAPI Backend Server**:
   ```powershell
   uvicorn app.main:app --reload --port 8000
   ```
   - Backend API: **`http://localhost:8000`**
   - Interactive API Swagger Docs: **`http://localhost:8000/docs`**

---

### 3. Frontend Setup (React + TypeScript + Tailwind)

1. **Open a second terminal window** and navigate to `frontend/`:
   ```powershell
   cd "c:\Users\Capricon\Desktop\resume project\frontend"
   ```

2. **Install frontend dependencies**:
   ```powershell
   npm install
   ```

3. **Start the Vite development server**:
   ```powershell
   npm run dev
   ```
   - Frontend UI: **`http://localhost:5173`**

4. **Testing in Your Browser**:
   - Open `http://localhost:5173` in your browser.
   - Click **"Development Quick-Access"** (or use Google Sign-in).
   - Upload a resume (`.pdf` or `.docx`).
   - Inspect the extracted text in the **Extracted Resume Text** debug card.
   - Click **"Discover New Jobs"** or **"Tailor & Apply"** to trigger the LangGraph pipeline.

---

### 4. Running Tests & Evaluations

- **Run all 42 automated tests**:
  ```powershell
  python -m pytest tests/ -v
  ```
- **Run LangSmith Evaluation Suite**:
  ```powershell
  python -m pytest -m eval -v -s
  ```
- **Verify Frontend Production Build**:
  ```powershell
  cd frontend
  npm run build
  ```

---

## Part 3: Production Deployment Guide

```
┌─────────────────────────────────────────────────────────────┐
│                    VERCEL (Frontend)                        │
│             https://autopilot-app.vercel.app                │
└──────────────────────────────┬──────────────────────────────┘
                               │ API Calls (CORS + Cookies)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               RAILWAY / RENDER (Backend API)                │
│             https://api-autopilot.up.railway.app            │
│         (FastAPI + LangGraph Pipeline + APScheduler)        │
└──────────────────────────────┬──────────────────────────────┘
                               │ Async SQLAlchemy
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               SUPABASE (Managed PostgreSQL 16)              │
│       db.your-project-ref.supabase.co:5432/postgres         │
└─────────────────────────────────────────────────────────────┘
```

---

### Step 1: Deploy the Backend API (Railway or Render)

1. **Push your code to a GitHub repository**:
   ```powershell
   git init
   git add .
   git commit -m "Deploy AI Job Application Autopilot"
   git remote add origin https://github.com/your-username/job-application-autopilot.git
   git push -u origin main
   ```

2. **Deploy on Railway** (or Render):
   - Go to [railway.app](https://railway.app/) > **New Project** > **Deploy from GitHub repo**.
   - Select your repository.
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

3. **Set Environment Variables on Railway**:
   Add the following variables:
   - `DATABASE_URL`: `postgresql+asyncpg://postgres.your-ref:your_password@aws-0-us-east-1.pooler.supabase.com:6543/postgres`
   - `GOOGLE_CLIENT_ID`: `your-google-client-id.apps.googleusercontent.com`
   - `GOOGLE_CLIENT_SECRET`: `your-google-client-secret`
   - `GOOGLE_REDIRECT_URI`: `https://api-your-backend.up.railway.app/auth/google/callback`
   - `LLM_PROVIDER`: `groq` or `gemini`
   - `GROQ_API_KEY` or `GEMINI_API_KEY`: *(Your API Key)*
   - `LANGCHAIN_TRACING_V2`: `true`
   - `LANGCHAIN_API_KEY`: *(Your LangSmith Key)*
   - `LANGCHAIN_PROJECT`: `job-application-autopilot`
   - `SESSION_SECRET_KEY`: `3MP_R6rAgwOze9wECzXTFx8JMcWYI5zNmcw3pxc6cw0`
   - `TOKEN_ENCRYPTION_KEY`: `95fnoEeSufCkEXtzZiynk_O2tWQXgcwYXJD3cHPh74o=`
   - `SCHEDULER_ENABLED`: `true`

4. **Run Migrations on Production**:
   In the Railway terminal or via Railway CLI, run:
   ```powershell
   alembic upgrade head
   ```

---

### Step 2: Deploy the Frontend on Vercel

1. Go to [Vercel.com](https://vercel.com/) and sign in with GitHub.
2. Click **"Add New Project"** and select your GitHub repository.
3. Configure the build settings:
   - **Framework Preset**: `Vite`
   - **Root Directory**: Click *Edit* and select **`frontend`**
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. Add the Environment Variable:
   - **Name**: `VITE_API_URL`
   - **Value**: `https://api-your-backend.up.railway.app`
5. Click **Deploy**.
6. Vercel will build and assign your live production URL: `https://autopilot-app.vercel.app`.

---

### Step 3: Configure Google OAuth for Production Domains

1. Go to [Google Cloud Console](https://console.cloud.google.com/) > **APIs & Services** > **Credentials**.
2. Click on your **OAuth 2.0 Client ID**.
3. Under **Authorized JavaScript Origins**, add:
   - `https://autopilot-app.vercel.app`
4. Under **Authorized Redirect URIs**, add:
   - `https://api-your-backend.up.railway.app/auth/google/callback`
5. Save changes.

---

### Step 4: Verification
1. Visit `https://autopilot-app.vercel.app`.
2. Sign in with Google (grants Gmail & Drive permissions).
3. Upload your resume and let the autopilot find and apply for jobs!
4. View all stored records live in your **Supabase Table Editor**.
