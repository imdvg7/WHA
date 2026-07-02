FROM python:3.12-slim

# curl is needed for wa.me probes (aiohttp gets TLS-blocked by WhatsApp)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render sets PORT env var dynamically
ENV PORT=8000
EXPOSE ${PORT}

CMD ["python", "whatsapp_username_checker.py"]
