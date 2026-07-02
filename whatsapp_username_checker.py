"""
WhatsApp Username Availability Checker + Groq Suggestion Engine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Prerequisites:
    pip install aiohttp groq python-dotenv fastapi uvicorn[standard]

Run:
    python whatsapp_username_checker.py
    # API at http://0.0.0.0:8000
    # Docs at http://0.0.0.0:8000/docs
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import aiohttp
import subprocess as _sp
from dotenv import load_dotenv
from groq import AsyncGroq
from groq import RateLimitError as GroqRateLimitError

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Load .env — check same directory first, then parent (GroqTr/.env)
_env_path_local = Path(__file__).resolve().parent / ".env"
_env_path_parent = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path_local)
load_dotenv(_env_path_parent)

# Groq API keys — supports multiple comma-separated keys for rotation
_raw_keys = os.getenv("GROQ_API_KEYS", "") or os.getenv("GROQ_API_KEY", "")
GROQ_API_KEYS: list[str] = [k.strip() for k in _raw_keys.split(",") if k.strip()]
GROQ_MODEL: str = "llama-3.3-70b-versatile"

# WhatsApp public routing base
WA_BASE_URL: str = "https://wa.me/"

# Concurrency & retry
MAX_CONCURRENT_CHECKS: int = 5
HTTP_TIMEOUT_S: int = 12
MAX_RETRIES: int = 2
RETRY_BACKOFF_BASE: float = 0.3

# Server — Render sets PORT dynamically
HOST: str = "0.0.0.0"
PORT: int = int(os.getenv("PORT", "8000"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("wa-checker")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Data Models (FastAPI-serializable)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class UsernameStatus(str, Enum):
    VALID = "valid"           # passes WhatsApp format rules
    INVALID = "invalid"       # fails format validation
    # NOTE: WhatsApp has NO public API for availability checking.
    # We can only validate format rules, not actual availability.


@dataclass
class CheckResult:
    username: str
    status: UsernameStatus
    http_code: Optional[int] = None
    latency_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "status": self.status.value,
            "http_code": self.http_code,
            "latency_ms": round(self.latency_ms, 2),
            "error": self.error,
        }


@dataclass
class FullResponse:
    query: str
    result: CheckResult
    suggestions: list[str] = field(default_factory=list)
    suggestion_latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "result": self.result.to_dict(),
            "suggestions": self.suggestions,
            "suggestion_latency_ms": round(self.suggestion_latency_ms, 2),
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Username Validation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# WhatsApp usernames: 5-30 chars, lowercase alphanumeric + underscores/periods,
# must start with a letter, no consecutive periods/underscores
_USERNAME_RE = re.compile(r"^[a-z][a-z0-9._]{4,29}$")
_CONSECUTIVE_SPECIAL = re.compile(r"[._]{2}")


def validate_username(username: str) -> Optional[str]:
    """Return None if valid, else return a reason string."""
    u = username.strip().lower()
    if not u:
        return "empty username"
    if len(u) < 5:
        return f"too short ({len(u)} chars, minimum 5)"
    if len(u) > 30:
        return f"too long ({len(u)} chars, maximum 30)"
    if not _USERNAME_RE.match(u):
        return "must start with a letter; only a-z, 0-9, '.', '_' allowed"
    if _CONSECUTIVE_SPECIAL.search(u):
        return "consecutive periods or underscores not allowed"
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WhatsApp Check Engine (async)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class WAChecker:
    """Username format validator for WhatsApp.

    NOTE: WhatsApp has NO public API for checking username availability.
    The wa.me endpoint returns identical responses for ALL usernames
    (taken AND available) — it cannot distinguish them.
    This was confirmed by testing + Meta's official docs (July 2026).

    This class validates WhatsApp username FORMAT RULES only:
    - 5-30 chars, starts with letter, a-z 0-9 . _ only, no consecutive ./_ 
    """

    def __init__(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def check_single(self, username: str) -> CheckResult:
        """Validate username format (instant, no network call)."""
        username = username.strip().lower()
        reason = validate_username(username)
        if reason:
            return CheckResult(
                username=username,
                status=UsernameStatus.INVALID,
                error=reason,
            )
        return CheckResult(
            username=username,
            status=UsernameStatus.VALID,
        )

    async def check_batch(self, usernames: list[str]) -> list[CheckResult]:
        """Validate multiple usernames (instant, no network calls)."""
        return [await self.check_single(u) for u in usernames]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Groq Suggestion Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SuggestionEngine:
    """Uses Groq (llama-3.3-70b-versatile) to generate username suggestions.
    Supports multiple API keys with round-robin rotation + rate-limit failover.
    Token-economy: compact prompts, tight max_tokens, TTL response cache."""

    # ── System prompts (input tokens) ─────────────────────────────────────────
    # Single-list call: returns {"s":[...]}
    _SYS_SINGLE = (
        "WA username generator. Rules: 5-30 chars, letter-start, a-z0-9._ only, "
        "no consecutive ./_ Return ONLY JSON {\"s\":[...]}."
    )
    # Combined call: returns {"u":[username-alts], "n":[niche-alts]}
    _SYS_COMBINED = (
        "WA username generator. Rules: 5-30 chars, letter-start, a-z0-9._ only, "
        "no consecutive ./_ Return ONLY JSON {\"u\":[...],\"n\":[...]}."
    )

    # ── Response cache (TTL = 5 min) — shared across all instances ────────────
    _cache: dict[str, tuple[list | dict, float]] = {}
    _CACHE_TTL: float = 300.0  # seconds

    def __init__(self, api_keys: list[str] | None = None) -> None:
        keys = api_keys or GROQ_API_KEYS
        if not keys:
            raise ValueError(
                "No Groq API keys found. Set GROQ_API_KEYS (comma-separated) "
                "or GROQ_API_KEY in environment or .env"
            )
        self._clients = [AsyncGroq(api_key=k) for k in keys]
        self._key_count = len(self._clients)
        self._call_counter = 0
        log.info("suggestion engine ready — %d groq key(s) loaded", self._key_count)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _next_client(self) -> AsyncGroq:
        """Round-robin key rotation."""
        client = self._clients[self._call_counter % self._key_count]
        self._call_counter += 1
        return client

    @classmethod
    def _cache_key(cls, *parts: str) -> str:
        return hashlib.md5("|".join(parts).encode()).hexdigest()

    @classmethod
    def _cache_get(cls, key: str) -> list | dict | None:
        entry = cls._cache.get(key)
        if entry and (time.monotonic() - entry[1]) < cls._CACHE_TTL:
            return entry[0]
        return None

    @classmethod
    def _cache_set(cls, key: str, value: list | dict) -> None:
        cls._cache[key] = (value, time.monotonic())
        # Evict stale entries if cache grows large
        if len(cls._cache) > 500:
            now = time.monotonic()
            cls._cache = {k: v for k, v in cls._cache.items() if now - v[1] < cls._CACHE_TTL}

    async def _call_groq(self, user_prompt: str, count: int) -> list[str]:
        """Single-list Groq call with cache + rate-limit failover across all keys.

        Token budget per call (count=10):
          system  ≈ 35 tokens  |  user ≈ 15 tokens  |  output ≈ 60 tokens  = ~110 total
        """
        ck = self._cache_key("single", user_prompt, str(count))
        cached = self._cache_get(ck)
        if cached is not None:
            log.info("groq cache hit — 0 tokens used")
            return cached  # type: ignore[return-value]

        messages = [
            {"role": "system", "content": self._SYS_SINGLE},
            {"role": "user", "content": f"{user_prompt} Give {count}."},
        ]
        # Try every key in the pool before giving up
        for attempt in range(self._key_count):
            t0 = time.perf_counter()
            client = self._next_client()
            try:
                chat = await client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    temperature=0.85,
                    max_tokens=180,   # 20 usernames × avg 9 chars ≈ 60 tokens; 180 is safe headroom
                    response_format={"type": "json_object"},
                )
                raw = chat.choices[0].message.content or "{}"
                elapsed = (time.perf_counter() - t0) * 1000
                log.info("groq in %.0fms (key slot %d)", elapsed, (self._call_counter - 1) % self._key_count)

                parsed = json.loads(raw)
                # Accept {"s":[...]} or any dict-with-list or bare list
                if isinstance(parsed, list):
                    items = parsed
                elif isinstance(parsed, dict):
                    items = parsed.get("s") or next((v for v in parsed.values() if isinstance(v, list)), [])
                else:
                    items = []

                valid = [
                    s.strip().lower()
                    for s in items
                    if isinstance(s, str) and validate_username(s.strip().lower()) is None
                ][:count]
                self._cache_set(ck, valid)
                return valid
            except GroqRateLimitError as exc:
                log.warning(
                    "groq key slot %d rate-limited (attempt %d/%d) — trying next key: %s",
                    (self._call_counter - 1) % self._key_count, attempt + 1, self._key_count, exc,
                )
                continue
            except Exception as exc:
                log.error("groq failed (attempt %d/%d): %s", attempt + 1, self._key_count, exc)
                return []

        log.error("all %d groq key(s) rate-limited — returning empty", self._key_count)
        return []

    async def suggest(
        self,
        taken_username: str,
        niche: str = "general",
        count: int = 10,
    ) -> list[str]:
        """Generate alternatives based on a taken username (optionally niche-aware)."""
        # Ultra-compact prompt — every word counts against token budget
        prompt = f'"{taken_username}" taken. niche={niche}.'
        result = await self._call_groq(prompt, count)
        return result or self._fallback_suggestions(taken_username, count)

    async def suggest_by_niche(
        self,
        niche: str,
        count: int = 10,
    ) -> list[str]:
        """Generate usernames purely from a niche/category."""
        prompt = f'niche={niche}.'
        result = await self._call_groq(prompt, count)
        return result or self._fallback_suggestions(niche, count)

    async def suggest_custom(
        self,
        custom_prompt: str,
        username: str = "",
        niche: str = "",
        count: int = 30,
    ) -> list[str]:
        """Generate usernames from a free-form user prompt."""
        # Keep user's own prompt intact (it defines quality); only trim our appended metadata
        extras = ""
        if username:
            extras += f' user={username}'
        if niche:
            extras += f' niche={niche}'
        prompt = custom_prompt + extras
        result = await self._call_groq(prompt, count)
        return result or self._fallback_suggestions(username or niche or 'user', count)

    async def suggest_combined(
        self,
        username: str,
        niche: str,
        count_username: int = 5,
        count_niche: int = 5,
    ) -> dict:
        """Single Groq call for both username-alts + niche suggestions (most token-efficient).

        Uses short JSON keys {"u":[...],"n":[...]} in the LLM response to save output tokens.
        """
        ck = self._cache_key("combined", username, niche, str(count_username), str(count_niche))
        cached = self._cache_get(ck)
        if cached is not None:
            log.info("groq combined cache hit — 0 tokens used")
            return cached  # type: ignore[return-value]

        # Compact prompt: short key names save tokens in BOTH prompt AND response
        prompt = f'"{username}" taken. niche={niche}. u={count_username} username-alts, n={count_niche} niche-names.'
        messages = [
            {"role": "system", "content": self._SYS_COMBINED},
            {"role": "user", "content": prompt},
        ]
        # Try each key in the pool on rate-limit
        for attempt in range(self._key_count):
            t0 = time.perf_counter()
            client = self._next_client()
            try:
                chat = await client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    temperature=0.85,
                    max_tokens=180,   # same budget as _call_groq; combined total is similar
                    response_format={"type": "json_object"},
                )
                raw = chat.choices[0].message.content or "{}"
                elapsed = (time.perf_counter() - t0) * 1000
                log.info("groq combined in %.0fms (key slot %d)", elapsed, (self._call_counter - 1) % self._key_count)

                parsed = json.loads(raw)

                def _extract(key: str, fallback_count: int) -> list[str]:
                    items = parsed.get(key, [])
                    return [
                        s.strip().lower()
                        for s in items
                        if isinstance(s, str) and validate_username(s.strip().lower()) is None
                    ][:fallback_count]

                # Primary keys are short "u" / "n"; fall back to verbose names for robustness
                u_based = _extract("u", count_username) or _extract("username_based", count_username)
                n_based = _extract("n", count_niche)    or _extract("niche_based", count_niche)

                # Last resort: model returned a flat list — split it
                if not u_based and not n_based:
                    flat = next((v for v in parsed.values() if isinstance(v, list)), [])
                    valid = [
                        s.strip().lower() for s in flat
                        if isinstance(s, str) and validate_username(s.strip().lower()) is None
                    ]
                    u_based = valid[:count_username]
                    n_based = valid[count_username:count_username + count_niche]

                result = {
                    "username_based": u_based or self._fallback_suggestions(username, count_username),
                    "niche_based":    n_based or self._fallback_suggestions(niche, count_niche),
                    "latency_ms":     round(elapsed, 2),
                }
                self._cache_set(ck, result)
                return result
            except GroqRateLimitError as exc:
                log.warning(
                    "groq combined key slot %d rate-limited (attempt %d/%d) — trying next key: %s",
                    (self._call_counter - 1) % self._key_count, attempt + 1, self._key_count, exc,
                )
                continue
            except Exception as exc:
                log.error("groq combined failed (attempt %d/%d): %s", attempt + 1, self._key_count, exc)
                return {
                    "username_based": self._fallback_suggestions(username, count_username),
                    "niche_based":    self._fallback_suggestions(niche, count_niche),
                    "latency_ms":     0,
                }

        log.error("all %d groq key(s) rate-limited for combined call — using fallback", self._key_count)
        return {
            "username_based": self._fallback_suggestions(username, count_username),
            "niche_based":    self._fallback_suggestions(niche, count_niche),
            "latency_ms":     0,
        }

    @staticmethod
    def _fallback_suggestions(base: str, count: int) -> list[str]:
        """Deterministic fallback when Groq is unreachable (zero API tokens)."""

        base = re.sub(r"[^a-z0-9]", "", base.lower())[:15]
        if len(base) < 4:
            base = base + "user"
        suffixes = [
            "x", "hq", "io", "fx", "hub", "lab", "dev", "pro", "now", "app",
            "go", "run", "one", "ace", "max", "zen", "sky", "net", "top", "vip",
        ]
        results: list[str] = []
        for sfx in suffixes:
            candidate = f"{base}.{sfx}"
            if validate_username(candidate) is None and candidate not in results:
                results.append(candidate)
            if len(results) >= count:
                break

        h = int(hashlib.md5(base.encode()).hexdigest()[:6], 16)
        i = 0
        while len(results) < count:
            candidate = f"{base}{(h + i) % 10000:04d}"
            if validate_username(candidate) is None and candidate not in results:
                results.append(candidate)
            i += 1
        return results[:count]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Orchestrator — combines check + suggestions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class UsernameOrchestrator:
    """High-level interface: check availability → suggest if taken."""

    def __init__(self) -> None:
        self.checker = WAChecker()
        self.suggester = SuggestionEngine()

    async def process(
        self,
        username: str,
        niche: str = "general",
    ) -> FullResponse:
        result = await self.checker.check_single(username)

        suggestions: list[str] = []
        suggestion_latency = 0.0

        if result.status == UsernameStatus.TAKEN:
            t0 = time.perf_counter()
            suggestions = await self.suggester.suggest(username, niche=niche)
            suggestion_latency = (time.perf_counter() - t0) * 1000

        return FullResponse(
            query=username,
            result=result,
            suggestions=suggestions,
            suggestion_latency_ms=suggestion_latency,
        )

    async def smart_process(
        self,
        username: str = "",
        niche: str = "",
        limit: int = 10,
        custom_prompt: str = "",
    ) -> dict:
        """Smart endpoint: generate AI suggestions, validate format.

        NOTE: WhatsApp has NO public API for availability checking.
        We validate format rules only. Users must check availability
        in the WhatsApp app (Settings > Account > Username).

        Flow:
        1. Validate user's exact username format (if provided)
        2. Generate suggestions from Groq
        3. Validate all suggestions pass WhatsApp format rules
        4. Return validated suggestions (up to limit)
        """
        username = username.strip().lower()
        niche = niche.strip().lower()
        custom_prompt = custom_prompt.strip()
        limit = max(1, min(limit, 25))
        # Over-generate by a small fixed buffer (not 2×) — the model respects our rules well.
        # limit+3 gives enough padding for occasional invalid outputs without wasting tokens.
        generate_count = min(limit + 3, 20)

        response: dict = {
            "mode": "unknown",
            "check_result": None,
            "suggestions": [],
            "suggestion_latency_ms": 0,
            "limit": limit,
        }

        # 1. Validate user's exact username format if provided
        if username:
            result = await self.checker.check_single(username)
            response["check_result"] = result.to_dict()

        # 2. Generate suggestions from Groq
        t0 = time.perf_counter()
        candidates: list[str] = []

        if custom_prompt:
            response["mode"] = "custom"
            candidates = await self.suggester.suggest_custom(
                custom_prompt, username=username, niche=niche, count=generate_count
            )
        elif username and niche:
            response["mode"] = "both"
            combined = await self.suggester.suggest_combined(
                username, niche,
                count_username=generate_count // 2,
                count_niche=generate_count - generate_count // 2,
            )
            candidates = combined["username_based"] + combined["niche_based"]
        elif username:
            response["mode"] = "username"
            candidates = await self.suggester.suggest(username, count=generate_count)
        elif niche:
            response["mode"] = "niche"
            candidates = await self.suggester.suggest_by_niche(niche, count=generate_count)

        response["suggestion_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        # 3. Deduplicate and validate format
        seen = set()
        validated: list[dict] = []
        for c in candidates:
            if c not in seen and c != username:
                seen.add(c)
                reason = validate_username(c)
                if reason is None:
                    validated.append({"username": c, "valid": True})

        response["suggestions"] = validated[:limit]

        return response

    async def process_batch(
        self,
        usernames: list[str],
        niche: str = "general",
    ) -> list[FullResponse]:
        tasks = [self.process(u, niche=niche) for u in usernames]
        return await asyncio.gather(*tasks)

    async def close(self) -> None:
        await self.checker.close()


from collections import defaultdict
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the orchestrator lifecycle."""
    app.state.orchestrator = UsernameOrchestrator()
    log.info("orchestrator ready — groq model: %s, keys: %d", GROQ_MODEL, len(GROQ_API_KEYS))
    yield
    await app.state.orchestrator.close()
    log.info("orchestrator shut down")


app = FastAPI(
    title="WhatsApp Username Checker",
    description="Check WhatsApp username availability & get AI-powered suggestions",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security headers middleware ──────────────────────────────────────────────
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "X-XSS-Protection": "1; mode=block",
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers[header] = value
    # HSTS only on HTTPS (Render always terminates TLS)
    if request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── Per-IP rate limiter for /smart-check (protects Groq token budget) ────────
_rate_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 30      # max requests
_RATE_WINDOW = 60.0   # per 60 seconds


def _check_rate_limit(ip: str) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.monotonic()
    timestamps = _rate_store[ip]
    # Purge old entries
    _rate_store[ip] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(_rate_store[ip]) >= _RATE_LIMIT:
        return False
    _rate_store[ip].append(now)
    return True


# Serve static files (CSS, JS)
_static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/", summary="Web UI")
async def web_ui():
    """Serve the main HTML page."""
    return FileResponse(str(_static_dir / "index.html"), media_type="text/html")


@app.get("/health", summary="Health check")
async def health():
    return {
        "status": "ok",
        "service": "whatsapp-username-checker",
        "groq_model": GROQ_MODEL,
        "keys_loaded": len(GROQ_API_KEYS),
    }


@app.get("/robots.txt", summary="SEO: robots.txt")
async def robots_txt():
    return FileResponse(str(_static_dir / "robots.txt"), media_type="text/plain")


@app.get("/sitemap.xml", summary="SEO: sitemap")
async def sitemap_xml():
    return FileResponse(str(_static_dir / "sitemap.xml"), media_type="application/xml")


@app.get("/check/{username}", summary="Check single username availability")
async def check_username(
    username: str,
    niche: str = Query("general", description="Niche/context for suggestions"),
):
    """
    Check if a WhatsApp username is available.
    If taken, returns AI-generated alternatives.
    """
    orch: UsernameOrchestrator = app.state.orchestrator
    response = await orch.process(username, niche=niche)
    return JSONResponse(content=response.to_dict())


@app.post("/check/batch", summary="Check multiple usernames")
async def check_batch(payload: dict):
    """
    Check multiple usernames in one request.
    Body: {"usernames": ["name1", "name2", ...], "niche": "optional"}
    """
    usernames = payload.get("usernames", [])
    if not usernames or not isinstance(usernames, list):
        raise HTTPException(status_code=422, detail="'usernames' must be a non-empty list")
    if len(usernames) > 50:
        raise HTTPException(status_code=422, detail="max 50 usernames per batch")

    niche = payload.get("niche", "general")
    orch: UsernameOrchestrator = app.state.orchestrator
    results = await orch.process_batch(usernames, niche=niche)
    return JSONResponse(content=[r.to_dict() for r in results])


@app.get("/suggest/{username}", summary="Get suggestions only (skip check)")
async def suggest_only(
    username: str,
    niche: str = Query("general", description="Niche/context for suggestions"),
    count: int = Query(10, ge=5, le=50, description="Number of suggestions"),
):
    """Generate username alternatives without checking availability."""
    orch: UsernameOrchestrator = app.state.orchestrator
    t0 = time.perf_counter()
    suggestions = await orch.suggester.suggest(username, niche=niche, count=count)
    elapsed = (time.perf_counter() - t0) * 1000
    return JSONResponse(content={
        "query": username,
        "niche": niche,
        "suggestions": suggestions,
        "latency_ms": round(elapsed, 2),
    })


@app.get("/validate/{username}", summary="Validate username format only")
async def validate_only(username: str):
    """Check if a username meets WhatsApp format requirements (no network call)."""
    reason = validate_username(username)
    return JSONResponse(content={
        "username": username.strip().lower(),
        "valid": reason is None,
        "reason": reason,
    })


@app.get("/smart-check", summary="Smart check: username, niche, or both")
async def smart_check(
    request: Request,
    username: str = Query("", description="Username to check (optional)"),
    niche: str = Query("", description="Niche for suggestions (optional)"),
    limit: int = Query(10, ge=1, le=25, description="Max suggestions to return (default 10, max 25)"),
    prompt: str = Query("", description="Custom prompt for Groq (optional)"),
):
    """
    Smart endpoint — provide username, niche, or both + optional custom prompt.
    Rate-limited: 30 requests/minute per IP to protect Groq token budget.
    """
    # Rate limit check
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded — max 30 requests per minute. Please wait and try again.",
        )

    if not username.strip() and not niche.strip() and not prompt.strip():
        raise HTTPException(status_code=422, detail="Provide at least a username, niche, or prompt")
    orch: UsernameOrchestrator = app.state.orchestrator
    result = await orch.smart_process(username, niche, limit=limit, custom_prompt=prompt)
    return JSONResponse(content=result)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entrypoint
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entrypoint
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _free_port(port: int) -> None:
    """Kill any process currently bound to `port` so we can reuse it."""
    import signal
    import subprocess

    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        pids = result.stdout.strip().split()
        my_pid = os.getpid()
        for raw_pid in pids:
            if not raw_pid:
                continue
            pid = int(raw_pid)
            if pid == my_pid:
                continue
            log.warning("killing stale process %d on port %d", pid, port)
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if pids:
            time.sleep(0.3)  # let OS release the socket
    except FileNotFoundError:
        # lsof not available — try ss as fallback
        try:
            result = subprocess.run(
                ["ss", "-tlnp", f"sport = :{port}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines()[1:]:
                # extract pid from "pid=XXXX"
                match = re.search(r"pid=(\d+)", line)
                if match:
                    pid = int(match.group(1))
                    if pid != my_pid:
                        log.warning("killing stale process %d on port %d", pid, port)
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
            time.sleep(0.3)
        except Exception:
            log.warning("could not check for stale processes on port %d", port)
    except Exception as exc:
        log.warning("port-free check failed: %s", exc)


if __name__ == "__main__":
    import uvicorn

    _free_port(PORT)
    log.info("starting server on %s:%d", HOST, PORT)
    uvicorn.run(
        "whatsapp_username_checker:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
        access_log=True,
    )
