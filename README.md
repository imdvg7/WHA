# WhatsApp Username Checker

Free, AI-powered tool to check WhatsApp username availability and generate creative alternatives.

## Features

- **Username availability check** — probes wa.me to detect taken/available
- **AI suggestions** — powered by Groq's llama-3.3-70b-versatile
- **Custom prompts** — describe exactly what kind of username you want
- **Niche-based** — generate usernames by category (gaming, crypto, fitness, etc.)
- **Bulk verification** — generates 3× your limit, checks ALL against WhatsApp
- **Multi-key rotation** — supports multiple Groq API keys for high throughput
- **Beautiful UI** — dark theme with green/red availability indicators

## Setup

```bash
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file:

```env
# Single key
GROQ_API_KEY=gsk_your_key_here

# OR multiple keys (comma-separated) for rotation
GROQ_API_KEYS=gsk_key1,gsk_key2,gsk_key3
```

### Run locally

```bash
python whatsapp_username_checker.py
```

Open **http://localhost:8000**

## Deploy to Render (Free)

1. Push to GitHub
2. Go to [render.com](https://render.com) → New Web Service → Connect repo
3. Render auto-detects the `Dockerfile`
4. Set environment variable: `GROQ_API_KEYS` = your comma-separated keys
5. Deploy → get free URL: `https://your-app.onrender.com`

Or use the **render.yaml** blueprint for one-click deploy.

## Project Structure

```
├── whatsapp_username_checker.py   # Backend (FastAPI + WAChecker + Groq engine)
├── static/
│   ├── index.html                 # SEO-optimized HTML
│   ├── style.css                  # Dark theme styles
│   ├── app.js                     # Frontend logic
│   ├── og-image.png               # Social share image
│   ├── robots.txt                 # SEO
│   └── sitemap.xml                # SEO
├── requirements.txt
├── Dockerfile
├── render.yaml                    # Render blueprint
└── .gitignore
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Web UI |
| `/health` | GET | Health check |
| `/smart-check` | GET | Main endpoint: check + suggest |
| `/check/{username}` | GET | Check single username |
| `/check/batch` | POST | Check multiple usernames |
| `/suggest/{username}` | GET | Suggestions only |
| `/validate/{username}` | GET | Format validation only |
| `/robots.txt` | GET | SEO robots |
| `/sitemap.xml` | GET | SEO sitemap |

## Tech Stack

- **Backend**: Python, FastAPI, uvicorn
- **AI**: Groq (llama-3.3-70b-versatile)
- **Check**: curl subprocess (bypasses WhatsApp TLS fingerprinting)
- **Frontend**: Vanilla HTML/CSS/JS
- **Hosting**: Render.com (free tier)

## Note on Availability Checking

WhatsApp has no public API for username lookups (zero-discovery design). Our tool uses a best-effort `wa.me` redirect probe via curl. Results are accurate in most cases but should be confirmed in the WhatsApp app.
