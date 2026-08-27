# Google Sign-In and Deployment Guide

This guide explains how to make the app public so anyone can sign in with Google.
It assumes the frontend is on Netlify, the FastAPI backend is on Render, and the
database stays on Supabase.

## What lives where

1. `Netlify` hosts the React frontend.
2. `Render` hosts the FastAPI backend.
3. `Supabase` hosts the PostgreSQL database.
4. `Google Cloud Console` controls the Google sign-in setup only.

## Very important before you start

1. Your current backend is **not** fully running on Netlify.
2. Your FastAPI backend should run on **Render**, not Cloud Run.
3. Your database does **not** move. Keep using Supabase.
4. Your backend must know the Netlify frontend URL.
5. Your Google OAuth callback must point to the Render backend URL, not localhost.

---

## Step 1. Create the Google Cloud project for OAuth

1. Open Google Cloud Console.
2. Create or select a project.
3. You do not need Cloud Run for this setup because Render hosts the backend.

## Step 2. Enable the required Google services

1. In Google Cloud Console, enable the OAuth consent screen / Google Auth Platform.
2. If you use Gmail or Drive features, keep those APIs available too.

## Step 3. Deploy the FastAPI backend to Render

1. Open your Render dashboard.
2. Click **New**.
3. Choose **Web Service**.
4. Connect your GitHub repository.
5. Select the repo that contains this project.
6. Set the service type to a Python web service or Docker web service.
7. Set the health check path to `/health` instead of `/` if Render lets you configure it.

### If you use the Dockerfile

1. Use the `Dockerfile` in the repo root.
2. Let Render build the image from that file.
3. Start the app with:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### If you use Render's Python settings instead

1. Set the build command to:

```text
pip install -r requirements.txt
```

2. Set the start command to:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Backend environment variables for Render

Add these in the Render service settings. The app will fail to start if the
required keys are missing.

Required for startup:

1. `DATABASE_URL`
2. `GOOGLE_CLIENT_ID`
3. `GOOGLE_CLIENT_SECRET`
4. `LANGCHAIN_API_KEY`
5. `APIFY_API_TOKEN`
6. `APOLLO_API_KEY`
7. `PDFCO_API_KEY`
8. `SESSION_SECRET_KEY`
9. `TOKEN_ENCRYPTION_KEY`

Recommended to set explicitly:

1. `GOOGLE_REDIRECT_URI`
2. `LLM_PROVIDER`
3. `GROQ_API_KEY` or `GEMINI_API_KEY` or the LLM key you use
4. `LANGCHAIN_TRACING_V2`
5. `LANGCHAIN_PROJECT`
6. `APIFY_ACTOR_ID`
7. `MAX_AUTO_SENDS_PER_DAY`
8. `REVIEW_LOOP_MAX_ATTEMPTS`
9. `SCHEDULER_ENABLED`
10. `SCHEDULER_INTERVAL_HOURS`

### The important backend URL values

1. After deployment, Render gives you a public backend URL.
2. Your Google callback must look like this:

```text
https://voxyl-resume.onrender.com/auth/google/callback
```

3. Put that exact URL into `GOOGLE_REDIRECT_URI`.
4. Put the same exact URL in Google Cloud Console as an authorized redirect URI.

### If Render crashes on startup

1. Check the deploy logs for `ValidationError for Settings`.
2. That means one or more required env vars are still missing.
3. Add the missing keys in Render, redeploy, and the app should boot.

---

## Step 4. Update Google Cloud Console for public login

### 4.1 Open the OAuth consent screen

1. Go to Google Cloud Console.
2. Open **Google Auth Platform** or **OAuth consent screen**.
3. Set the app type to **External**.
4. Fill in:
   - App name
   - Support email
   - Developer contact email

### 4.2 Publish the app

1. Change publishing status to **In production** or **Published**.
2. Do not leave it in testing if you want everyone to sign in.
3. If it stays in testing, only test users can use it.

### 4.3 Add the OAuth client

1. Go to **Credentials**.
2. Create an OAuth client ID.
3. Choose **Web application**.
4. Add this redirect URI exactly:

```text
https://YOUR-BACKEND-URL/auth/google/callback
```

5. Save the client ID and secret.

### 4.4 Watch out for sensitive scopes

1. Your app currently requests Google login plus Gmail and Drive scopes.
2. Gmail and Drive scopes are sensitive.
3. If Google blocks public use, that is usually because of those scopes.
4. If you want the fastest path for public testing, use only:
   - `openid`
   - `email`
   - `profile`
5. If you keep Gmail and Drive scopes, Google may require verification before full public access.

---

## Step 5. Deploy the frontend to Netlify

1. Open Netlify.
2. Connect your GitHub repo.
3. Set the base directory to `frontend`.
4. Set the build command to:

```text
npm run build
```

5. Set the publish directory to:

```text
dist
```

6. Add this environment variable in Netlify:

```text
VITE_API_URL=https://voxyl-resume.onrender.com
```

7. Redeploy the site.

### What `VITE_API_URL` does

1. The frontend uses `VITE_API_URL` to know where the backend lives.
2. Without it, the frontend talks to localhost.
3. On Netlify, localhost will not work for real users.

---

## Step 6. Fix the backend for production

Your backend currently has a few localhost-only values that must be updated for production.

### 6.1 Change the frontend redirect after Google login

1. In `app/api/auth.py`, the callback currently redirects to localhost.
2. Change it so it redirects to your Netlify site.

Use this idea:

```text
https://voxyl-resume.netlify.app/
```

3. A better long-term fix is to store the frontend URL in config or an environment variable.

### 6.2 Update CORS

1. In `app/main.py`, add your Netlify site to `allow_origins`.
2. Keep localhost origins for development.
3. Add:

```text
https://voxyl-resume.netlify.app
```

### 6.3 Update cookies for cross-site login

1. The frontend and backend are on different domains.
2. That means the session cookie must be allowed across sites.
3. In production, use:
   - `same_site="none"`
   - `https_only=True`

4. If you leave the cookie settings as local-only values, Google login can appear to work and then fail after redirect.

### 6.4 Render and the background scheduler

1. Your backend starts a scheduler in `app.main`.
2. Render web services can sleep if you use a free plan.
3. If the scheduler must always run, you may need a paid instance or a separate background worker.
4. If the scheduler is not critical, you can disable it with `SCHEDULER_ENABLED=false`.

---

## Step 7. Keep Supabase as the database

1. Do not move the database away from Supabase unless you want to.
2. The backend reads the database using `DATABASE_URL`.
3. Render will connect directly to Supabase.
4. Netlify does not talk to the database directly.

### Database setup checklist

1. Make sure `DATABASE_URL` is the Supabase connection string.
2. Prefer the Supabase pooler URL on Render, for example:

```text
postgresql+asyncpg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

3. Avoid the direct `db.<project-ref>.supabase.co` host on Render if you hit network errors.
4. Make sure the backend can reach the database from Render.
5. Keep migrations available.
6. Run migrations once on the production database if needed.

### If you see `Network is unreachable`

1. Check whether `DATABASE_URL` points to the direct Supabase host instead of the pooler host.
2. If it does, switch to the pooler connection string in Render and redeploy.
3. If the URL is already the pooler URL, verify the password and region, then retry after redeploy.
4. A `404` on `/` is normal here because the app exposes `/health` rather than a homepage route.

---

## Step 8. Test the full login flow

1. Open the Netlify website.
2. Click **Sign in with Google**.
3. You should be sent to Google.
4. After login, Google should redirect to the backend callback.
5. The backend should create or update the user.
6. The backend should redirect you back to the Netlify frontend.
7. The frontend should now show you as logged in.

### If something fails

1. If you see `redirect_uri_mismatch`, the callback URL in Google Cloud Console does not exactly match the backend URL.
2. If login finishes but the site forgets the user, the cookie settings are wrong.
3. If the frontend cannot reach the backend, `VITE_API_URL` is wrong.
4. If Google says the app is blocked, the consent screen is still in testing or the scopes need verification.

---

## Step 9. Final production checklist

1. Frontend deployed on Netlify.
2. Backend deployed on Render.
3. Database still on Supabase.
4. `VITE_API_URL` points to the backend URL.
5. `GOOGLE_REDIRECT_URI` points to the backend callback.
6. OAuth consent screen is set to **External** and **Published**.
7. Netlify domain is allowed in backend CORS.
8. Session cookies work across the frontend and backend domains.

---

## Short version

1. Netlify hosts the UI.
2. Render hosts the FastAPI backend.
3. Supabase stays the database.
4. Google Console must point to the Render backend callback.
5. The frontend must use the backend URL through `VITE_API_URL`.
