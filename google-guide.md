# Google Cloud Guide

This is the cleanest way to publish Voxyl so other people can test it:

- Backend: Cloud Run
- Frontend: Firebase Hosting
- Database: keep Supabase for now
- Auth: Google OAuth only, no dev quick access

## Why this setup

- Cloud Run gives you a public HTTPS URL and scales automatically.
- Cloud Run services accept environment variables and secrets.
- Cloud Run containers must listen on `0.0.0.0` and use the port provided by `PORT`.
- Firebase Hosting is a simple way to publish the Vite frontend with HTTPS and SPA routing.

## 1. Create the Google Cloud project

1. Create a Google Cloud project.
2. Enable billing.
3. Enable these APIs:
   - Cloud Run
   - Cloud Build
   - Artifact Registry
   - Secret Manager
   - Firebase Hosting
4. Install and log in to the Google Cloud CLI:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

## 2. Store backend config safely

Do not commit secrets to GitHub for production.

Use Secret Manager for sensitive values like:

- `DATABASE_URL`
- `GOOGLE_CLIENT_SECRET`
- `GROQ_API_KEY`
- `APIFY_API_TOKEN`
- `APOLLO_API_KEY`
- `PDFCO_API_KEY`
- `SESSION_SECRET_KEY`
- `TOKEN_ENCRYPTION_KEY`
- `LANGCHAIN_API_KEY`

Keep non-secret values as service environment variables:

- `LLM_PROVIDER`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `GROQ_MODEL`
- `GEMINI_MODEL`
- `LANGCHAIN_TRACING_V2`
- `LANGCHAIN_PROJECT`
- `SCHEDULER_ENABLED`
- `SCHEDULER_INTERVAL_HOURS`

## 3. Deploy the backend to Cloud Run

Recommended service name: `voxyl-backend`

You can deploy from source with Cloud Run. Because this repo now has a `Dockerfile`, Cloud Run will use it:

```bash
gcloud run deploy voxyl-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars LLM_PROVIDER=groq,OLLAMA_BASE_URL=http://localhost:11434,OLLAMA_MODEL=minimax-m3:cloud,LANGCHAIN_TRACING_V2=true,LANGCHAIN_PROJECT=job-application-autopilot,SCHEDULER_ENABLED=true,SCHEDULER_INTERVAL_HOURS=24
```

If you prefer to manage secrets through Cloud Run, add them with Secret Manager and reference them on the service.

Important:

- Cloud Run services must listen on the port in `PORT`.
- Cloud Run services should bind to `0.0.0.0`, not `127.0.0.1`.
- If you use a Dockerfile, make sure the app starts with `uvicorn` or `gunicorn` on `$PORT`.

## 4. Update Google OAuth

After the backend is deployed, update your Google OAuth settings:

- Authorized redirect URI:
  - `https://YOUR_CLOUD_RUN_URL/auth/google/callback`
- If you have an OAuth consent screen or authorized origins, add the new frontend domain too.

Then update the backend environment variable:

- `GOOGLE_REDIRECT_URI=https://YOUR_CLOUD_RUN_URL/auth/google/callback`

## 5. Deploy the frontend to Firebase Hosting

Go to the `frontend/` folder.

Set the backend URL before building:

```bash
set VITE_API_URL=https://YOUR_CLOUD_RUN_URL
npm run build
```

If you are using PowerShell:

```powershell
$env:VITE_API_URL="https://YOUR_CLOUD_RUN_URL"
npm run build
```

Then deploy with Firebase Hosting:

```bash
firebase login
firebase init hosting
firebase deploy --only hosting
```

Use the `frontend/dist` folder as the hosting public directory.

Firebase Hosting should be configured for SPA routing so refreshes on client routes still work.

## 6. Test the public app

1. Open the Firebase Hosting URL.
2. Sign in with Google.
3. Upload a resume.
4. Open Jobs and Applications.
5. Run one job through tailoring.
6. Confirm the application shows:
   - tailored resume HTML
   - PDF URL from PDF.co
   - email draft
   - gap analysis

## 7. Production checklist

- Remove any dev-only login buttons or fallback user creation.
- Make sure `VITE_API_URL` points at the Cloud Run backend.
- Make sure Google OAuth redirect URIs match the deployed backend.
- Move secrets out of `.env` and into Secret Manager or the hosting platform settings.
- If you want stricter production cookies, set secure cookie behavior for HTTPS deployments.

## 8. Optional custom domain

If you want a custom domain later:

- Use Firebase Hosting custom domains for the frontend.
- Use a custom domain on Cloud Run if you want a branded backend URL.

## References

- Cloud Run source deploy: https://docs.cloud.google.com/run/docs/deploying-source-code
- Cloud Run env vars: https://docs.cloud.google.com/run/docs/configuring/services/environment-variables
- Cloud Run container contract: https://docs.cloud.google.com/run/docs/container-contract
- Firebase Hosting quickstart: https://firebase.google.com/docs/hosting/quickstart
