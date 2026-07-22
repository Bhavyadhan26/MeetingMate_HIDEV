# Deployment Guide — MeetingMate

This guide walks you through deploying MeetingMate to get a **public working URL**. We'll use **Render** (backend + PostgreSQL) + **Qdrant Cloud** (free vector DB) + **Vercel** (frontend). All have generous free tiers.

## Architecture (Deployed)

```
Browser → https://meetingmate-frontend.vercel.app
              ↓  API calls to backend
         https://meetingmate-backend.onrender.com
              ↓  PostgreSQL + Qdrant Cloud
```

---

## Prerequisites

- A **GitHub** account (to push your code)
- A **Render** account (free at https://render.com)
- A **Vercel** account (free at https://vercel.com)
- A **Qdrant Cloud** account (free 1GB at https://cloud.qdrant.io)

---

## Step 1: Push Your Code to GitHub

```bash
# From your project root (d:/MeetingMate)
git init
git add .
git commit -m "Initial commit"
# Create a repo on GitHub first, then:
git remote add origin https://github.com/YOUR_USERNAME/meetingmate.git
git push -u origin main
```

---

## Step 2: Set Up Qdrant Cloud (Free Tier)

1. Go to https://cloud.qdrant.io and sign up
2. Create a **new cluster** (free tier — 1GB is enough)
3. Once created, you'll get:
   - **Cluster URL:** `https://xxxxx-xxxxx.us-east-0.aws.cloud.qdrant.io:6333`
   - **API Key:** A long string

Save these — you'll need them in Step 3.

---

## Step 3: Deploy Backend on Render

### 3a. Create a PostgreSQL Database

1. In Render dashboard, click **New → PostgreSQL**
2. Choose the **Free** plan
3. Give it a name: `meetingmate-db`
4. Wait for it to be provisioned (5-10 minutes)
5. Copy the **Internal Database URL** — looks like:
   `postgresql://meetingmate_user:xxxxx@dpg-xxxxx.render.com:5432/meetingmate`

### 3b. Create the Web Service

1. Click **New → Web Service**
2. Connect your GitHub repository
3. Configure:
   - **Name:** `meetingmate-backend`
   - **Environment:** `Docker`
   - **Branch:** `main`
   - **Root Directory:** Leave blank (Dockerfile is at root... wait)

**IMPORTANT:** The backend Dockerfile is at `backend/Dockerfile`, not the root. Render needs it at root. You need to create a root-level Dockerfile OR configure Render to use `backend/Dockerfile`.

Since Render's free tier needs the Dockerfile at root, **create this file in your repo**:

```dockerfile
# Dockerfile (at project root, not in backend/)
FROM python:3.12-slim

WORKDIR /workspace

# Copy backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Run the backend
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "10000"]
```

Add this to `.gitignore` to keep it clean? No, commit it:

```bash
echo "Dockerfile" >> .gitignore  
# Wait, we need it. Let me rephrase — don't add it to .gitignore
```

Actually, Render supports specifying the Dockerfile path. When creating the Web Service, in the **Advanced** section, set:
- **Dockerfile Path:** `backend/Dockerfile`
- **Publish Directory:** (leave blank)
- **Health Check Path:** `/v1/auth/config`

### 3c. Environment Variables

Add these in Render's **Environment** section:

| Variable | Value |
|----------|-------|
| `APP_ENV` | `production` |
| `MEMORY_BACKEND` | `qdrant` |
| `QDRANT_URL` | Your Qdrant Cloud URL from Step 2 |
| `QDRANT_API_KEY` | Your Qdrant Cloud API key |
| `DATABASE_URL` | Your Render PostgreSQL Internal URL |
| `GROQ_API_KEY` | Your Groq API key (get one free at console.groq.com) |
| `GROQ_MODEL` | `llama-3.1-8b-instant` |
| `DEEPGRAM_API_KEY` | Optional — for audio uploads |
| `AUTH_REQUIRED` | `0` (disable auth for now) |
| `REDACTION_MAP_ENCRYPTION_KEY` | Generate one: run `python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"` |
| `REQUIRE_HTTPS` | `0` |
| `TRANSCRIPT_JOB_TTL_SECONDS` | `3600` |
| `CONFLICT_ESCALATION_HOURS` | `24` |
| `TRACE_OUTPUT_PATH` | `/workspace/backend/app/observability/local_traces.jsonl` |

### 3d. Deploy

Click **Create Web Service**. Render will:
1. Build the Docker image (~5 min first time)
2. Deploy and start the server
3. Show a URL like `https://meetingmate-backend.onrender.com`

**Test it:** Visit `https://meetingmate-backend.onrender.com/v1/auth/config`
- Expected: `{"required":false,"domain":"","client_id":"","audience":""}`

---

## Step 4: Deploy Frontend on Vercel

### 4a. Prepare the Frontend

The current frontend has a broken React app. The working vanilla JS frontend is in:
- `frontend/src/index.html`
- `frontend/src/main.js`
- `frontend/src/api/client.js`
- `frontend/src/styles.css`
- `frontend/src/config.js`

Since the vanilla JS files work but the React app is broken, we'll deploy the **vanilla JS frontend** (it works and is fully functional).

For Vercel deployment, we need to serve the static files properly. The easiest approach:

**Option 1: Deploy as static files (recommended)**

Create a `vercel.json` in the frontend directory:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "src/**/*",
      "use": "@vercel/static"
    }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "/src/$1" }
  ]
}
```

Then update `frontend/src/config.js` to point to your Render backend URL:

```javascript
window.MEETINGMATE_API_BASE = window.MEETINGMATE_API_BASE || "https://meetingmate-backend.onrender.com";
```

### 4b. Deploy to Vercel

1. Go to https://vercel.com and sign in with GitHub
2. Click **Add New → Project**
3. Import your GitHub repository
4. Configure:
   - **Framework Preset:** `Other`
   - **Root Directory:** `frontend`
   - **Build Command:** (leave empty — static files)
   - **Output Directory:** `src`
5. Add environment variable:
   - `MEETINGMATE_API_BASE`: `https://meetingmate-backend.onrender.com`
6. Click **Deploy**

Vercel will give you a URL like `https://meetingmate-frontend.vercel.app`.

### 4c. Test It

Open `https://meetingmate-frontend.vercel.app`
- You should see the MeetingMate dashboard
- Try pasting a transcript and clicking **Process Text**
- The job should go through: Queued → Processing → Completed
- You'll see summary, action items, and decisions

---

## Step 5: Set Up CORS (Critical)

Add your frontend URL to the backend's CORS. In `backend/app/main.py`, the CORS middleware currently allows all origins (`["*"]`). For Render, this is fine since `allow_origins=["*"]` is set. No changes needed.

---

## Step 6: Verify Everything Works

Run through this checklist in your browser:

- [ ] Open `https://meetingmate-frontend.vercel.app`
- [ ] Paste a meeting transcript and hit **Process Text**
- [ ] Wait for it to complete (see summary + action items appear)
- [ ] Go to Decisions tab — see extracted decisions
- [ ] Paste a **contradictory** transcript like "Decision: no longer use Qdrant"
- [ ] Confirm a Conflict is flagged
- [ ] Go to Conflicts tab — see the conflict with escalation info
- [ ] Click **Resolve** — it should succeed
- [ ] Go to Memory tab — search "What did we decide about Qdrant?"
- [ ] See cited answer from your processed meetings

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Backend returns 503 | Qdrant Cloud URL or API key wrong | Check Qdrant Cloud dashboard |
| Backend returns 500 | Missing GROQ_API_KEY | Set it in Render env vars |
| Frontend shows blank page | CORS block | Check browser console: if CORS error, ensure backend `allow_origins=["*"]` |
| Audio upload fails | No DEEPGRAM_API_KEY | Add it, or just use text transcripts |
| Processing hangs on "Queued" | Worker thread issue on Render | Render free tier may have low CPU. Try restarting the service |
| Conflicts not detected | Memory backend not persisting | Check Qdrant Cloud connection |

---

## Alternative: All-in-One with Docker on a VPS

If you prefer a single-server approach with full docker-compose:

1. Get a cheap VPS (like **Hetzner** €4/mo or **DigitalOcean** $6/mo Droplet)
2. Install Docker + Docker Compose
3. Clone the repo on the VPS
4. Run:

```bash
# Set up .env with your API keys
cp .env.example .env
# Edit .env with Groq API key at minimum

# Deploy
docker compose up --build -d

# Your app is now at:
# http://YOUR_VPS_IP:5173 (frontend)
# http://YOUR_VPS_IP:8000 (backend API)
```

5. Set up **Nginx** as a reverse proxy with SSL (Certbot) to get HTTPS

---

## Quick Links After Deployment

| Component | URL |
|-----------|-----|
| **Frontend** | `https://meetingmate-frontend.vercel.app` |
| **Backend API** | `https://meetingmate-backend.onrender.com` |
| **API Health Check** | `https://meetingmate-backend.onrender.com/v1/auth/config` |
| **Qdrant Dashboard** | `https://cloud.qdrant.io` |

---

## Cost Summary (Free Tier)

| Service | Cost | What You Get |
|---------|------|-------------|
| **Render** (Web Service) | **Free** | 512MB RAM, 100GB bandwidth/mo |
| **Render** (PostgreSQL) | **Free** | 1GB storage, expires after 90 days (just recreate) |
| **Qdrant Cloud** | **Free** | 1GB storage, 1 cluster |
| **Vercel** | **Free** | Unlimited static hosting |
| **Groq** | **Free** | 30 req/min on llama-3.1-8b |
| **Total** | **$0/mo** | Fully working deployment |

