# PickMyWA — WhatsApp Username Checker

[![Live Demo](https://img.shields.io/badge/🚀_Live_Demo-pickmywa.onrender.com-25d366?style=for-the-badge)](https://pickmywa.onrender.com)
[![License](https://img.shields.io/badge/License-All_Rights_Reserved-red?style=flat-square)](LICENSE)

Free, AI-powered tool to generate creative WhatsApp username ideas and validate them against WhatsApp's format rules.

> **⚠️ Disclaimer:** This is an independent, third-party tool. It is **not affiliated with, endorsed by, or connected to** WhatsApp LLC or Meta Platforms, Inc. "WhatsApp" is a registered trademark of WhatsApp LLC. Suggested usernames are AI-generated ideas — always verify availability in the WhatsApp app.

## Features

- **AI-powered username generation** — powered by Groq's llama-3.3-70b-versatile
- **Format validation** — validates all suggestions against WhatsApp's username rules
- **Custom prompts** — describe exactly what kind of username you want
- **Niche-based** — generate usernames by category (gaming, crypto, fitness, etc.)
- **Multi-key rotation** — supports multiple Groq API keys for high throughput
- **Beautiful UI** — dark theme, responsive, SEO-optimized
- **Privacy-first** — no data collection, no cookies, no tracking

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
├── whatsapp_username_checker.py   # Backend (FastAPI + Groq suggestion engine)
├── static/
│   ├── index.html                 # SEO-optimized HTML (FAQPage + HowTo + WebApp schema)
│   ├── style.css                  # Dark theme styles
│   ├── app.js                     # Frontend logic
│   ├── favicon.png                # Favicon
│   ├── og-image.png               # Social share image (1200×630)
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
| `/smart-check` | GET | Main endpoint: generate + validate suggestions |
| `/check/{username}` | GET | Validate single username format |
| `/check/batch` | POST | Validate multiple usernames |
| `/suggest/{username}` | GET | AI suggestions only |
| `/validate/{username}` | GET | Format validation only |
| `/robots.txt` | GET | SEO robots |
| `/sitemap.xml` | GET | SEO sitemap |

## Tech Stack

- **Backend**: Python, FastAPI, uvicorn
- **AI**: Groq (llama-3.3-70b-versatile)
- **Frontend**: Vanilla HTML/CSS/JS
- **Hosting**: Render.com (free tier)

## Important Notice

This tool validates usernames against WhatsApp's publicly known format rules (5-30 chars, starts with letter, a-z 0-9 . _ only, no consecutive special chars). **WhatsApp has no public API for checking actual username availability.** Suggested usernames may already be claimed — always verify in the WhatsApp app (Settings → Account → Username).

This project does not access, scrape, or interact with any WhatsApp or Meta APIs, servers, or proprietary systems. All suggestions are generated independently by a general-purpose AI language model.

## License

All Rights Reserved. See [LICENSE](LICENSE) for details.
