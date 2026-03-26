# Elif Voice Assistant — Deployment Knowledge Base

## Project Overview

**Elif** is a voice-enabled civic assistant for Bahçeşehir/Başakşehir, Istanbul. Users press and hold a mic button, ask questions in Turkish, and get voice responses about pharmacies, events, emergencies, and utilities.

**Stack:** FastAPI (Python) + Vanilla JS + Tailwind CSS + SQLite + OpenAI

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   User Browser  │────▶│   Fly.io (API)  │────▶│   OpenAI API    │
│   (Frontend)    │◀────│   + Static      │◀────│   GPT-4 + TTS   │
└─────────────────┘     │   Files         │     └─────────────────┘
                        └─────────────────┘
                                │
                                ▼
                        ┌─────────────────┐
                        │   SQLite DB     │
                        │   (Analytics)   │
                        └─────────────────┘
```

**Key Design:** Single container serves both API and static frontend files. No separate frontend host needed.

---

## Folder Structure

```
elif.ai/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── analytics.py         # SQLite logging
│   ├── scrape_nobetci.py    # Pharmacy scraper
│   ├── data/                # JSON data files
│   │   ├── pharmacies.json
│   │   ├── emergency.json
│   │   ├── events.json
│   │   ├── water.json
│   │   └── closures.json
│   ├── audio_responses/     # Generated TTS files
│   └── pitch/               # Pitch deck pages
├── frontend/
│   ├── index.html           # Voice assistant UI
│   ├── eczaneler.html       # Pharmacy finder
│   ├── ayarlar.html         # Settings
│   ├── app.js               # Voice recording logic
│   ├── shared.js            # Nav + branding
│   └── icons/               # PWA icons
├── Dockerfile               # Container definition
├── fly.toml                 # Fly.io config
├── requirements.txt         # Python deps (root)
└── .gitignore               # Protect .env!
```

---

## Key Configuration Files

### fly.toml
```toml
app = "elif-cityconcierge"
primary_region = "ams"  # Amsterdam

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "stop"    # Save money: sleeps when idle
  auto_start_machines = true     # Wakes on request
  min_machines_running = 0       # Can scale to zero

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"
```

### Dockerfile
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ ./backend/
COPY frontend/ ./frontend/
WORKDIR /app/backend
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## Environment Variables (Secrets)

| Variable | Purpose | Set Via |
|----------|---------|---------|
| `OPENAI_API_KEY` | GPT-4 + Text-to-Speech | `fly secrets set` |
| `ADMIN_USERNAME` | Dashboard login | `fly secrets set` |
| `ADMIN_PASSWORD` | Dashboard password | `fly secrets set` |
| `BRANDING_MODE` | `cityconcierge` or `basaksehir` | `fly secrets set` |
| `PORT` | Server port (default 8080) | fly.toml |

**NEVER commit `.env` to Git!** Use `fly secrets set` instead.

---

## Deployment Commands Reference

### First-Time Deploy
```powershell
# 1. Navigate to project
cd "C:\Users\meteh\My Drive\My_Claude_Workspace\cityconcierge\elif.ai"

# 2. Install flyctl (one-time)
iwr https://fly.io/install.ps1 -useb | iex

# 3. Login
fly auth login

# 4. Create app (only once!)
fly launch --name elif-cityconcierge --region ams --no-deploy

# 5. Set secrets (REQUIRED before deploy!)
fly secrets set OPENAI_API_KEY="sk-..."
fly secrets set ADMIN_USERNAME="admin"
fly secrets set ADMIN_PASSWORD="secure-password"

# 6. Deploy
fly deploy

# 7. Check
fly status
fly logs
```

### Subsequent Updates
```powershell
cd "C:\Users\meteh\My Drive\My_Claude_Workspace\cityconcierge\elif.ai"

# Push code first
git add -A
git commit -m "Update description"
git push

# Deploy
fly deploy
```

### Destroy & Start Over
```powershell
fly destroy elif-cityconcierge --yes
```

---

## Data Update Workflow

Before major demos, refresh data:

```powershell
cd "C:\Users\meteh\My Drive\My_Claude_Workspace\cityconcierge\elif.ai\backend"
.\venv\Scripts\activate

# Update pharmacies (scraper)
python scrape_nobetci.py

# Update last_updated dates in other JSONs manually
# Then commit and deploy
git add backend/data/
git commit -m "Update data for demo"
git push
fly deploy
```

---

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| "Could not find Dockerfile" | Wrong directory | `cd` to project root first |
| App already exists | Name taken | Use `fly destroy` or pick new name |
| 500 errors on voice | Missing OPENAI_API_KEY | `fly secrets set OPENAI_API_KEY=...` |
| CORS errors | Wrong origin | Check `ALLOWED_ORIGINS` in main.py |
| 30s delay on first request | Machine was sleeping | Normal for free tier, wait or set `min_machines_running=1` |
| Turkish characters broken | Wrong encoding | Ensure JSON files are UTF-8 |

---

## API Endpoints

| Endpoint | Purpose | Auth |
|----------|---------|------|
| `POST /api/voice` | Main voice endpoint | None |
| `GET /api/pharmacies` | List pharmacies | None |
| `GET /api/emergency` | Emergency info + toplanma alanları | None |
| `GET /api/events` | Events | None |
| `GET /api/water` | Water outages | None |
| `GET /api/branding` | White-label config | None |
| `GET /health` | Health check | None |
| `GET /admin` | Analytics dashboard | Basic Auth |
| `GET /api/admin/stats` | Dashboard data | Basic Auth |

---

## Local Development

```powershell
# Terminal 1: Backend
cd backend
.\venv\Scripts\activate
uvicorn main:app --reload

# Terminal 2: Frontend (serve static files)
cd frontend
python -m http.server 3000

# Access: http://localhost:3000
# API: http://localhost:8000
```

---

## Custom Domain Setup

```powershell
# 1. Add cert
fly certs add elif.cityconcierge.io

# 2. At your DNS provider, add CNAME:
# Name: elif
# Value: elif-cityconcierge.fly.dev

# 3. Wait for DNS propagation
fly certs show elif.cityconcierge.io
```

---

## Cost Optimization (Free Tier)

**Fly.io free allowance per month:**
- 234,000 GB-seconds (enough for demo)
- 160,000 request-seconds
- 10,000 build minutes

**Tips to stay free:**
- `auto_stop_machines = "stop"` ✓ (already set)
- `min_machines_running = 0` ✓ (already set)
- Scale down after demos: `fly scale count 0`

---

## Git Workflow

```bash
# Daily workflow
git add -A
git commit -m "Description of changes"
git push
fly deploy

# Never commit:
# - .env
# - backend/__pycache__/
# - backend/audio_responses/
# - backend/data/analytics.db
```

---

## Security Checklist

- [ ] `.env` in `.gitignore`
- [ ] `OPENAI_API_KEY` set via `fly secrets`, not in code
- [ ] Admin password is strong
- [ ] CORS origins are specific (not `*`)
- [ ] No API keys in git history

---

## Design Tokens (Civic Serenity)

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#f7f4ef` | Page background (limestone) |
| Primary | `#00595c` | Buttons, links (İznik turquoise) |
| Primary Container | `#0d7377` | Hover states |
| On Surface | `#1c1c19` | Body text |
| Secondary | `#506072` | Muted text (slate) |
| Font | Plus Jakarta Sans | All text |

---

## Voice Flow

```
User presses mic → Audio recorded → Sent to /api/voice
                                            ↓
Response audio ← TTS (OpenAI) ← GPT-4 generates text ← Transcript (Whisper)
```

**Key files:**
- Recording: `frontend/app.js` (MediaRecorder API)
- Processing: `backend/main.py` (process_voice function)

---

## White-Label Support

Two modes via `BRANDING_MODE` env var:

| Mode | Title | Accent | Stripe |
|------|-------|--------|--------|
| `cityconcierge` | Elif | Turquoise `#0d7377` | No |
| `basaksehir` | Başakşehir Belediyesi | Blue `#004B93` | Yes |

---

## Emergency Data Structure

```json
{
  "toplanma_alanlari": [
    {
      "name": "Bahçeşehir Gölet Parkı",
      "address": "...",
      "capacity": "5.000 kişi",
      "coordinates": {"lat": 41.0712, "lng": 28.6558},
      "facilities": ["İlk yardım", "Jeneratör"]
    }
  ],
  "deprem_rehberi": {
    "sirasinda": ["Çök-Kapan-Tutun", ...],
    "sonrasinda": ["Gaz vanasını kapat", ...]
  },
  "emergency_numbers": {
    "afad": "122",
    "ambulans": "112"
  }
}
```

---

## Related Files in This Repo

- `BUILD-WEB.md` — Frontend build steps
- `pre-deploy.md` — Pre-deployment checklist
- `DEPLOY-FLYIO.md` — Original Fly.io deploy guide
- `CODEX-FIXES.md` — Security fixes applied

---

## Support

- Fly.io docs: https://fly.io/docs/
- FastAPI docs: https://fastapi.tiangolo.com/
- Dashboard: https://fly.io/dashboard
- Logs: `fly logs` or https://fly.io/apps/elif-cityconcierge/monitoring

---

*Last updated: 2026-03-26*
*App: elif-cityconcierge on Fly.io*
*Domain: elif.cityconcierge.io (pending DNS)*
