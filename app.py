import ast
import base64
from copy import deepcopy
import hmac
import os
import re
import secrets
import threading
from threading import Thread as WorkerThread
import time
import uuid
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor
import requests
from flask import Flask, render_template, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from prompts import (
    LOOK_FAST_PROMPT,
    LOOK_PART_A_PROMPT,
    LOOK_PART_B_PROMPT,
    OUTFIT_PROMPT,
    SYNTHESIZER_PROMPT,
    OPTIMIZER_PROMPT,
)
from raw_prompts import (
    RAW_SYNTHESIZER_PROMPT,
    RAW_OUTFIT_LINE,
    RAW_FABRIC_BLOCK,
    RAW_NEGATIVE_ADDITIONS,
)
from github import Github, Auth
from atelier_engine.flask_uploads import prepare_legacy_studio_request
from atelier_engine.job_store import InMemoryJobStore, RedisJobStore
from atelier_engine.job_payloads import RedisJobPayloadStore
from atelier_engine.job_queue import RedisJobQueue
from atelier_engine.worker_runtime import current_worker_lease
from atelier_engine.vision_lab_pipeline import run_vision_lab_pipeline
from atelier_engine.vision_lab_repair import propose_prompt_repair
from atelier_engine.vision_studio import (
    build_studio_intelligence, build_studio_prompt_context, build_studio_analysis_report,
    validate_reference_analysis, validate_studio_prompt,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


def parse_trusted_proxy_hops(value):
    """Return a bounded proxy count; invalid configuration fails closed."""
    try:
        return max(0, min(5, int(value)))
    except (TypeError, ValueError):
        return 0


TRUSTED_PROXY_HOPS = parse_trusted_proxy_hops(os.environ.get("TRUSTED_PROXY_HOPS", "0"))
if TRUSTED_PROXY_HOPS:
    # Only enable this when the configured proxy strips and rewrites
    # X-Forwarded-For; otherwise clients could spoof their rate-limit identity.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=TRUSTED_PROXY_HOPS)


@app.errorhandler(429)
def rate_limit_exceeded(error):
    response = jsonify({"error": "Too many requests. Please wait before retrying."})
    response.status_code = 429
    try:
        retry_after = error.get_response().headers.get("Retry-After")
        if retry_after:
            response.headers["Retry-After"] = retry_after
    except Exception:
        pass
    return response


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "Request is too large. Reference images must be 4 MB each and the full request must stay within 10 MB."}), 413


@app.errorhandler(500)
def internal_server_error(_error):
    """Return a generic API-safe response without exposing exception details."""
    return jsonify({"error": "An unexpected server error occurred. Please retry."}), 500


@app.after_request
def add_security_headers(response):
    """Set safe browser defaults without imposing a CSP on inline app assets."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    # Never allow caches to retain prompts, reference-analysis details, or private job metadata.
    if request.method == "POST" or request.path.startswith("/status/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response

# Configure a shared Redis-compatible store in production for cross-worker limits.
_RATE_LIMIT_STORAGE = os.environ.get("RATELIMIT_STORAGE_URI", "memory://").strip() or "memory://"
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=_RATE_LIMIT_STORAGE,
    strategy="fixed-window",
    default_limits=[],
)

_APP_ENV = (os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV", "")).strip().lower()
if _APP_ENV in {"production", "prod"}:
    _rate_limit_url = urlsplit(_RATE_LIMIT_STORAGE)
    if _rate_limit_url.scheme != "rediss":
        raise RuntimeError(
            "Production requires RATELIMIT_STORAGE_URI to use a TLS-protected rediss:// Redis URL."
        )
    if not _rate_limit_url.password:
        raise RuntimeError(
            "Production RATELIMIT_STORAGE_URI requires Redis authentication."
        )

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
APP_URL = (
    os.environ.get("APP_URL", "").strip().rstrip("/")
    or "https://boutique-prompt.onrender.com"
)

# --- TELEGRAM & GITHUB CONFIGURATION FOR WEBHOOK ---
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "").strip()
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN", "").strip()
OWNER_TELEGRAM_ID = os.environ.get("OWNER_TELEGRAM_ID", "").strip()  # sirf is user ka message accept hoga
REPO_NAME = os.environ.get("TELEGRAM_REPO", "LokeshofficialGit/ATELIER_PROMPT_ENG.").strip()
BRANCH = os.environ.get("TELEGRAM_BRANCH", "visual-lab-rebuild").strip()
TELEGRAM_WEBHOOK_ENABLED = os.environ.get("TELEGRAM_WEBHOOK_ENABLED", "").strip().lower() == "true"
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
MAX_TELEGRAM_MESSAGE_CHARS = 4096

MODEL = "nvidia/nemotron-3.5-super-vl:free"

OPTIMIZER_MODELS = []
for _m in [
    os.environ.get("OPTIMIZER_MODEL", "google/gemma-4-31b-it:free"),
    MODEL,
]:
    if _m and _m not in OPTIMIZER_MODELS:
        OPTIMIZER_MODELS.append(_m)

MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_TEXT_CHARS = 1500
SCRATCH_MAX_ATTRIBUTES = 80
SCRATCH_MAX_ATTRIBUTE_VALUE_CHARS = 300
SCRATCH_MAX_TOTAL_ATTRIBUTE_CHARS = 6000
SCRATCH_ALLOWED_FIELDS = {"raw_keywords", "attributes", "style", "ar", "detail"}
MAX_SKELETON_CHARS = 8000
MAX_JOBS_KEPT = 20
# Bound abandoned workers and retain completed results only temporarily.
MAX_JOB_RUNTIME_SECONDS = 15 * 60
FINISHED_JOB_TTL_SECONDS = 60 * 60


def parse_max_active_jobs(value):
    """Bound worker concurrency and fall back safely on invalid configuration."""
    try:
        return max(1, min(16, int(value)))
    except (TypeError, ValueError):
        return 4


MAX_ACTIVE_JOBS = parse_max_active_jobs(os.environ.get("MAX_ACTIVE_JOBS", "4"))
RETRY_WAITS = [6, 12]
VALID_MODES = {"BOTH", "LOOK_ONLY", "OUTFIT_ONLY"}
VALID_OUTPUTS = {"full", "raw"}
OPTIMIZE_TARGET = 1500
OPTIMIZE_HARD_LIMIT = 1800
OPTIMIZE_TOKENS = 1000

REPAIR_SYSTEM = """You fix one labelled image prompt for Nano Banana 2.1.
You receive the PROMPT (labelled lines) and a list of MISSING FACTS, each with the original sentence it came from.
Add each missing fact into the matching section as a short clause. Keep every label and keep one line per section. No blank lines.
Keep the total under the HARD LIMIT characters. Output only the full prompt, no markdown, no quotes, no introduction."""

CUT_SYSTEM = """You shorten one labelled image prompt for Nano Banana 2.1.
Rules:
Keep every PROTECTED FACT word for word, including numbers, hex codes, Kelvin values and screen-left or screen-right.
Keep every hairstyle fact (length, parting, volume, ends, placement, colour, texture). Shorten the wording only.
Keep every label and keep one line per section. No blank lines.
Remove repeated words, repeated clauses, filler adjectives and any fact written twice.
Stay under the TARGET length.
Output only the full shortened prompt, no markdown, no quotes, no introduction."""

DETAIL_LEVELS = {
    "fast":     {"look_mode": "combined",  "target": 1200,  "analysis_tokens": 1400,  "synth_tokens": 1100},
    "balanced": {"look_mode": "split",     "target": 2000,  "analysis_tokens": 1000,  "synth_tokens": 1600},
    "detailed": {"look_mode": "split",     "target": 3000,  "analysis_tokens": 1200,  "synth_tokens": 2200},
}
DEFAULT_DETAIL = "balanced"

RAW_SECTION_ORDER = [
    "SUBJECT PHYSIQUE", "HAIRSTYLE", "MAKEUP", "OUTFIT",
    "POSE AND ACTION", "AND GAZE", "BACKGROUND AND ENVIRONMENT",
    "LIGHTING AND CAMERA", "COMPOSITION", "QUALITY", "NEGATIVE PROMPT",
]
ALL_LABELS = RAW_SECTION_ORDER + ["JEWELLERY AND ACCESSORIES"]

COMPACT_ORDER = [
    "SUBJECT PHYSIQUE", "HAIRSTYLE", "MAKEUP", "OUTFIT", "JEWELLERY AND ACCESSORIES",
    "POSE AND ACTION", "AND GAZE", "BACKGROUND AND ENVIRONMENT", "LIGHTING AND CAMERA",
    "COMPOSITION", "QUALITY", "NEGATIVE PROMPT",
]

jobs = {}
jobs_lock = threading.Lock()
JOB_QUEUE_ENABLED = os.environ.get("JOB_QUEUE_ENABLED", "").strip().lower() == "true"
JOB_STORE_REDIS_URL = os.environ.get("JOB_STORE_REDIS_URL", "").strip()
job_queue = None
job_payload_store = None
redis_client = None
if JOB_QUEUE_ENABLED:
    if not JOB_STORE_REDIS_URL:
        raise RuntimeError("JOB_QUEUE_ENABLED requires JOB_STORE_REDIS_URL; refusing local-only fallback.")
    if _APP_ENV in {"production", "prod"}:
        redis_url = urlsplit(JOB_STORE_REDIS_URL)
        if redis_url.scheme != "rediss":
            raise RuntimeError("Production queue mode requires a TLS-protected rediss:// Redis URL.")
        if not redis_url.password:
            raise RuntimeError("Production queue mode requires Redis authentication in JOB_STORE_REDIS_URL.")
    import redis
    redis_client = redis.Redis.from_url(
        JOB_STORE_REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=10,
        health_check_interval=30,
    )
    redis_client.ping()
    job_store = RedisJobStore(
        redis_client,
        namespace=os.environ.get("JOB_STORE_NAMESPACE", "atelier:jobs:v1"),
        max_active=MAX_ACTIVE_JOBS,
        record_ttl_seconds=int(os.environ.get("JOB_RECORD_TTL_SECONDS", "86400")),
    )
    job_payload_store = RedisJobPayloadStore(
        redis_client,
        namespace=os.environ.get("JOB_PAYLOAD_NAMESPACE", "atelier:job-payloads:v1"),
        ttl_seconds=int(os.environ.get("JOB_PAYLOAD_TTL_SECONDS", "86400")),
        max_payload_bytes=15 * 1024 * 1024,
    )
    job_queue = RedisJobQueue(
        redis_client,
        namespace=os.environ.get("JOB_QUEUE_NAMESPACE", "atelier:queue:v1"),
        lease_seconds=int(os.environ.get("JOB_QUEUE_LEASE_SECONDS", "90")),
        max_attempts=int(os.environ.get("JOB_QUEUE_MAX_ATTEMPTS", "3")),
        completed_ttl_seconds=int(os.environ.get("JOB_QUEUE_COMPLETED_TTL_SECONDS", "86400")),
        recovery_batch_size=int(os.environ.get("JOB_QUEUE_RECOVERY_BATCH_SIZE", "100")),
    )
else:
    # Safe single-process development/test mode only. Redis queue mode is opt-in
    # and fails closed when its shared store cannot be configured.
    job_store = InMemoryJobStore(records=jobs)

QUEUE_HANDLER_NAMES = {
    "run_generate_job", "run_optimize_job", "run_scratch_job", "run_vision_lab_job",
}

class LLMError(Exception):
    pass

def set_job(job_id, **fields):
    with jobs_lock:
        lease = current_worker_lease.get()
        now = time.time()
        if lease is not None:
            lease_job_id, lease_token = lease
            if lease_job_id != job_id or job_queue is None:
                return False
            if hasattr(job_store, "update_running_with_lease"):
                # The job update and lease-token check happen in one Redis Lua transaction.
                return job_store.update_running_with_lease(
                    job_id, fields, now, queue=job_queue, lease_token=lease_token
                )
            if not job_queue.heartbeat(job_id, lease_token):
                return False
        if hasattr(job_store, "touch_running") and not job_store.touch_running(job_id, now):
            return False
        # Ignore late worker results after the job has timed out or otherwise ended.
        return job_store.update_running(job_id, fields, finished_at=now)

def evict_finished_jobs(now=None):
    now = time.time() if now is None else now
    job_store.maintain(
        now=now,
        max_runtime_seconds=MAX_JOB_RUNTIME_SECONDS,
        finished_ttl_seconds=FINISHED_JOB_TTL_SECONDS,
        max_records=MAX_JOBS_KEPT,
    )

def new_job(kind, detail, output=None):
    job_id = uuid.uuid4().hex
    with jobs_lock:
        evict_finished_jobs()
        active_jobs = job_store.active_count()
        if active_jobs >= MAX_ACTIVE_JOBS:
            return None
        created = job_store.create(job_id, {
            "kind": kind,
            "status": "running",
            "step": "Shuru ho raha hai",
            "prompt": None,
            "error": None,
            "mode": None,
            "detail": detail,
            "output": output,
            "warnings": [],
            "optimizer_model": None,
            "created": time.time(),
            "finished_at": None,
            "access_token": secrets.token_urlsafe(32),
        })
        if not created:
            return None
        evict_finished_jobs()
    return job_id

def get_job_snapshot(job_id):
    """Return an isolated job snapshot so response serialization cannot race updates."""
    with jobs_lock:
        evict_finished_jobs()
        return job_store.snapshot(job_id)


def job_access_token(job_id):
    with jobs_lock:
        return job_store.access_token(job_id)

def job_access_response(job_id):
    return {"job_id": job_id, "access_token": job_access_token(job_id)}


def start_job_worker(job_id, target, args):
    """Enqueue durable work when enabled; otherwise use single-process dev threads."""
    if JOB_QUEUE_ENABLED:
        try:
            handler_name = getattr(target, "__name__", "")
            if handler_name not in QUEUE_HANDLER_NAMES:
                raise ValueError("Background handler is not allowlisted.")
            if not job_payload_store.save(job_id, {
                "handler": handler_name,
                "args": args,
            }):
                raise RuntimeError("Could not persist background job input.")
            if not job_queue.enqueue(job_id, available_at=time.time()):
                raise RuntimeError("Could not enqueue background job.")
            return True
        except Exception:
            app.logger.exception("Could not persist or enqueue background job")
            if job_payload_store is not None:
                job_payload_store.delete(job_id)
            with jobs_lock:
                job_store.delete(job_id)
            return False
    try:
        worker = WorkerThread(target=target, args=args, daemon=True)
        worker.start()
        return True
    except Exception:
        app.logger.exception("Could not start background worker")
        with jobs_lock:
            job_store.delete(job_id)
        return False

def llm_chat(messages, label, temperature=0.3, max_tokens=1000, model=MODEL):
    if not OPENROUTER_API_KEY:
        raise LLMError("OPENROUTER_API_KEY set nahi hai. Render Environment mein add karein.")
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": APP_URL,
        "X-Title": "Prompt Engine by Lokesh",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "reasoning": {"enabled": False},
    }
    last_error = "Unknown error"
    last_status = None
    
    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            resp = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=75, allow_redirects=False)
        except requests.Timeout:
            last_error = "Model ne time mein jawab nahi diya (timeout)."
            last_status = None
            break
        except requests.RequestException:
            # Do not expose transport exception details in client-facing errors.
            last_error = "Model provider network request failed. Please retry shortly."
            last_status = None
            if attempt < len(RETRY_WAITS):
                time.sleep(RETRY_WAITS[attempt])
                continue
            break
            
        if resp.status_code == 200:
            try:
                data = resp.json()
            except ValueError:
                data = {}
            if data.get("error"):
                raise LLMError(f"OpenRouter error: {str(data['error'])[:250]}")
            try:
                choice = data["choices"][0]
                content = choice["message"]["content"]
                finish = choice.get("finish_reason")
            except (KeyError, IndexError, TypeError):
                content, finish = "", None
                
            if finish == "length":
                raise LLMError(
                    f"{model} ka output beech mein kat gaya (token limit)."
                )
            if content and str(content).strip():
                return str(content).strip()
            raise LLMError(f"{model} ne khali response diya.")
            
        last_status = resp.status_code
        last_error = f"{model} request failed with HTTP {resp.status_code}."
        if resp.status_code in (429, 502, 503) and attempt < len(RETRY_WAITS):
            time.sleep(RETRY_WAITS[attempt])
            continue
        break
        
    if last_status in (429, 502, 503):
        raise LLMError(f"{model} abhi busy ya free limit par hai.")
    raise LLMError(last_error)

def chain_chat(messages, label, models, temperature=0.3, max_tokens=1000):
    last_error = None
    for model in models:
        try:
            text = llm_chat(messages, label=label, temperature=temperature,
                            max_tokens=max_tokens, model=model)
            return text, model
        except LLMError as e:
            last_error = e
    raise last_error or LLMError("Koi model available nahi.")

def describe_image(img_bytes, mime, system_prompt, label, max_tokens):
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": system_prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ],
    }]
    return llm_chat(messages, label=label, temperature=0.2, max_tokens=max_tokens, model=MODEL)

def analyze_look_and_outfit(look, outfit, pose_text, cfg):
    """Analyze each reference independently so one provider failure does not discard other results."""
    futures = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        if look is not None:
            img, mime = look
            if cfg["look_mode"] == "combined":
                futures["look"] = pool.submit(
                    describe_image, img, mime, LOOK_FAST_PROMPT,
                    "look-combined", cfg["analysis_tokens"]
                )
            else:
                futures["look_pose"] = pool.submit(
                    describe_image, img, mime, LOOK_PART_A_PROMPT,
                    "look-pose", cfg["analysis_tokens"]
                )
                futures["look_detail"] = pool.submit(
                    describe_image, img, mime, LOOK_PART_B_PROMPT,
                    "look-detail", cfg["analysis_tokens"]
                )
        if outfit is not None:
            img, mime = outfit
            futures["outfit"] = pool.submit(
                describe_image, img, mime, OUTFIT_PROMPT,
                "outfit", cfg["analysis_tokens"]
            )
        results = {}
        errors = {}
        for task, future in futures.items():
            try:
                value = future.result()
                if isinstance(value, str) and value.strip():
                    results[task] = value.strip()
                    check = validate_reference_analysis(task, value)
                    if check['review_required']:
                        missing = ', '.join(check['missing_sections'])
                        errors[task] = (
                            f"{task.replace('_', ' ').title()} analysis is incomplete "
                            f"({check['coverage_score']}% labelled-section coverage). "
                            f"Missing or empty sections: {missing}. Retry this reference."
                        )
                else:
                    errors[task] = f"{task.replace('_', ' ').title()} analysis returned no usable text."
            except Exception:
                errors[task] = f"{task.replace('_', ' ').title()} analysis could not be completed. Retry this reference."
    if cfg["look_mode"] == "combined":
        look_desc = results.get("look", "")
    else:
        look_desc = "\n".join(x for x in (results.get("look_pose", ""), results.get("look_detail", "")) if x)
    return look_desc, results.get("outfit", ""), errors

def synthesize(detail, mode, subject_text, hair_text, pose_text, outfit_override, look_desc, outfit_desc, studio_context=""):
    cfg = DETAIL_LEVELS[detail]
    parts = [
        f"MODE: {mode}",
        f"DETAIL LEVEL: {detail}",
        f"TARGET LENGTH: about {cfg['target']} characters",
    ]
    if mode != "OUTFIT_ONLY":
        parts.append(f"SUBJECT TEXT:\n{subject_text or 'Not provided'}")
        parts.append(f"HAIRSTYLE TEXT:\n{hair_text or 'Not provided'}")
        parts.append(f"POSE TEXT:\n{pose_text or 'Not provided'}")
        parts.append(f"OUTFIT OVERRIDE:\n{outfit_override or 'Not provided'}")
        parts.append(f"LOOK DESCRIPTION:\n{look_desc or 'Not provided'}")
        parts.append(f"OUTFIT DESCRIPTION:\n{outfit_desc or 'Not provided'}")
    if studio_context:
        parts.append(studio_context)
        
    messages = [
        {"role": "system", "content": SYNTHESIZER_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
    return llm_chat(messages, label="synthesizer", temperature=0.4,
                    max_tokens=cfg["synth_tokens"], model=MODEL)

def synthesize_raw(detail, subject_text, hair_text, pose_text, look_desc, studio_context=""):
    cfg = DETAIL_LEVELS[detail]
    parts = [
        f"DETAIL LEVEL: {detail}",
        f"TARGET LENGTH: about {cfg['target']} characters",
        f"SUBJECT TEXT:\n{subject_text or 'Not provided'}",
        f"HAIRSTYLE TEXT:\n{hair_text or 'Not provided'}",
        f"POSE TEXT:\n{pose_text or 'Not provided'}",
        f"LOOK DESCRIPTION:\n{look_desc or 'Not provided'}",
    ]
    if studio_context:
        parts.append(studio_context)
    messages = [
        {"role": "system", "content": RAW_SYNTHESIZER_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
    return llm_chat(messages, label="synthesizer-raw", temperature=0.4,
                    max_tokens=cfg["synth_tokens"], model=MODEL)

def parse_any_labels(text):
    out = {}
    active = None
    for line in (text or "").split("\n"):
        t = line.strip()
        if not t:
            continue
        hit = next((l for l in ALL_LABELS if t.upper().startswith(l + ":")), None)
        if hit:
            active = hit
            out[hit] = t[len(hit) + 1:].strip()
        elif active:
            out[active] = (out.get(active, "") + " " + t).strip()
    return out

def build_raw_prompt(model_text):
    parsed = parse_any_labels(model_text)
    lines = []
    for lbl in RAW_SECTION_ORDER:
        if lbl == "OUTFIT":
            lines.append(f"OUTFIT: {RAW_OUTFIT_LINE.split(':', 1)[1].strip()} {RAW_FABRIC_BLOCK}")
            continue
        val = (parsed.get(lbl, "") or "").strip()
        if lbl == "NEGATIVE PROMPT":
            base = val.rstrip(". ").strip()
            val = ", ".join(x for x in (base, RAW_NEGATIVE_ADDITIONS) if x)
        if val:
            lines.append(f"{lbl}: {val}")
    return "\n\n".join(lines)

def get_mode(has_look, has_outfit):
    if has_look and has_outfit:
        return "BOTH"
    if has_look:
        return "LOOK_ONLY"
    return "OUTFIT_ONLY"

COMPACT_TOTAL = 1000
COMPACT_BUDGET = {
    "SUBJECT PHYSIQUE": 90, "HAIRSTYLE": 110, "MAKEUP": 50, "OUTFIT": 140,
    "JEWELLERY AND ACCESSORIES": 30, "POSE AND ACTION": 100, "AND GAZE": 35,
    "BACKGROUND AND ENVIRONMENT": 35, "LIGHTING AND CAMERA": 100,
    "COMPOSITION": 20, "QUALITY": 25, "NEGATIVE PROMPT": 35,
}

COMPACT_CUT_ORDER = [
    "NEGATIVE PROMPT", "QUALITY", "BACKGROUND AND ENVIRONMENT", "AND GAZE",
    "JEWELLERY AND ACCESSORIES", "MAKEUP", "LIGHTING AND CAMERA", "POSE AND ACTION",
    "OUTFIT", "SUBJECT PHYSIQUE", "HAIRSTYLE",
]
COMPACT_MODE_SECTIONS = {"OUTFIT_ONLY": {"OUTFIT", "JEWELLERY AND ACCESSORIES", "MAKEUP", "NEGATIVE PROMPT"}}

COMPOSE_SYSTEM = """You write ONE compact image prompt for Nano Banana 2.1 (vertical 9:16 editorial portrait) from analysis notes.
Output these labelled lines in this exact order. Each line is "LABEL: text". Stay within each max length.
SUBJECT PHYSIQUE: (max 90) start with "Use the reference face." then only the 4 to 6 strongest body facts from SUBJECT TEXT.
HAIRSTYLE: (max 110) keep length, parting, volume, ends and placement from HAIRSTYLE TEXT. Drop adjectives.
MAKEUP: (max 50) lipstick shade and finish, eyeliner. Mehndi only if present in the notes.
OUTFIT: (max 140) each visible garment with colour (hex if given), fabric and fit. Footwear type and colour only if the feet are in frame.
JEWELLERY AND ACCESSORIES: (max 30) one earring style and one bangle style, only if visible. Otherwise omit this line.
POSE AND ACTION: (max 100) use POSE TEXT if given, otherwise the LOOK pose. Screen-left and screen-right. Only body parts inside the frame.
AND GAZE: (max 35) eye direction, expression, lips.
BACKGROUND AND ENVIRONMENT: (max 35) main setting and the surfaces the body touches.
LIGHTING AND CAMERA: (max 100) key light direction, quality, Kelvin, catchlight, lens look, depth of field.
COMPOSITION: (max 20) the framing from the LOOK notes, then "vertical 9:16 portrait".
QUALITY: (max 25) "photorealistic, natural skin texture, sharp focus".
NEGATIVE PROMPT: (max 35) 4 to 5 core faults only: extra fingers, plastic skin, distorted hands, text or watermark, face different from the reference.
RULES:
Keep every number, Kelvin value, hex code, screen-left and screen-right exactly.
Never mention anything outside the frame. Never write the words none, not provided, not visible or no outside NEGATIVE PROMPT.
One footwear item, one earring style, one bangle style.
No degrees, no markdown, no bullets, no quotes, no introduction.
If MODE is OUTFIT_ONLY, write only OUTFIT, JEWELLERY AND ACCESSORIES, MAKEUP (only if lipstick or mehndi is in the notes) and NEGATIVE PROMPT."""

def cut_to(text, limit):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    pieces = [p for p in re.split(r"(?<=[,.;])\s+", text) if p.strip()]
    keep = [False] * len(pieces)
    
    def joined(flags):
        return " ".join(p for p, k in zip(pieces, flags) if k).strip()
        
    for i, p in enumerate(pieces):
        if section_protected(p):
            keep[i] = True
            if len(joined(keep)) > limit:
                keep[i] = False
                
    for i, p in enumerate(pieces):
        if not keep[i]:
            keep[i] = True
            if len(joined(keep)) > limit:
                keep[i] = False
                
    out = joined(keep)
    if not out:
        out = text[:limit].rsplit(" ", 1)[0]
    return out.rstrip(" ,;:")

def build_compact(sections, mode, hair_text, source_text):
    warnings = []
    allowed = COMPACT_MODE_SECTIONS.get(mode)
    secs = {
        k: v for k, v in sections.items()
        if k in COMPACT_BUDGET and (allowed is None or k in allowed) and v
    }
    for k in list(secs):
        secs[k] = cut_to(secs[k], COMPACT_BUDGET[k])
        
    for k in COMPACT_CUT_ORDER:
        if len(assemble_sections(secs)) <= COMPACT_TOTAL:
            break
        if k in secs:
            secs[k] = cut_to(secs[k], max(20, int(COMPACT_BUDGET[k] * 0.6)))
            
    text = assemble_sections(secs)
    lost = [f for f in section_protected(source_text) if compact(f) not in compact(text)]
    if lost:
        warnings.append("Ye facts prompt mein nahi aaye: " + ", ".join(lost))
        
    if hair_text and mode != "OUTFIT_ONLY":
        need = hair_groups_in(hair_text)
        have = hair_groups_in(secs.get("HAIRSTYLE", ""))
        if not need <= have:
            warnings.append("Hairstyle ki kuch details cut ho gayi: " + ", ".join(sorted(need - have)))
            
    if len(text) > COMPACT_TOTAL:
        warnings.append(f"Compact prompt {len(text)} characters hai, limit {COMPACT_TOTAL}.")
    return text, warnings

def run_compose(mode, subject_text, hair_text, pose_text, outfit_override, look_desc, outfit_desc):
    content = "\n\n".join([
        f"MODE: {mode}",
        f"SUBJECT TEXT:\n{subject_text or 'Not provided'}",
        f"HAIRSTYLE TEXT:\n{hair_text or 'Not provided'}",
        f"POSE TEXT:\n{pose_text or 'Not provided'}",
        f"OUTFIT OVERRIDE:\n{outfit_override or 'Not provided'}",
        f"LOOK NOTES:\n{look_desc or 'Not provided'}",
        f"OUTFIT NOTES:\n{outfit_desc or 'Not provided'}",
    ])
    messages = [
        {"role": "system", "content": COMPOSE_SYSTEM},
        {"role": "user", "content": content},
    ]
    raw, _ = chain_chat(messages, "compose", OPTIMIZER_MODELS, temperature=0.2, max_tokens=450)
    sections = loose_parse_sections(raw)
    if not sections:
        raise LLMError("Compact prompt ka output khali aaya.")
    return build_compact(sections, mode, hair_text, raw)

def run_generate_job(job_id, look, outfit, subject_text, hair_text, outfit_override, pose_text, detail, output, studio_intelligence=None):
    try:
        cfg = DETAIL_LEVELS[detail]
        studio_context = build_studio_prompt_context(studio_intelligence) if studio_intelligence else ""
        set_job(job_id, visual_analysis_status="analyzing")
        if output == "raw":
            if look is None:
                raise LLMError("RAW ke liye Look photo zaroori hai.")
            set_job(job_id, step="Look photo analyze ho rahi hai")
            look_desc, _, analysis_errors = analyze_look_and_outfit(look, None, pose_text, cfg)
            reference_analysis = build_studio_analysis_report(studio_intelligence, look_desc, "", analysis_errors) if studio_intelligence else {}
            set_job(job_id, visual_analysis_status=reference_analysis.get("status", "ready"), reference_analysis=reference_analysis, step="RAW prompt likh raha hoon")
            model_text = synthesize_raw(detail, subject_text, hair_text, pose_text, look_desc, studio_context)
            final = build_raw_prompt(model_text)
            quality = validate_studio_prompt(final, studio_intelligence) if studio_intelligence else {}
            review_warnings = list(quality.get("warnings", []))
            review_warnings.extend(reference_analysis.get("notes", []))
            set_job(job_id, status="done", step="", prompt=final, mode="RAW",
                    detail=detail, output="raw", studio_quality=quality,
                    reference_analysis=reference_analysis,
                    visual_analysis_status=reference_analysis.get("status", "ready"),
                    warnings=review_warnings, processing_status=quality.get("status", "ready"))
            return
            
        mode = get_mode(look is not None, outfit is not None)
        set_job(job_id, step="Photos analyze ho rahi hain")
        look_desc, outfit_desc, analysis_errors = analyze_look_and_outfit(look, outfit, pose_text, cfg)
        reference_analysis = build_studio_analysis_report(studio_intelligence, look_desc, outfit_desc, analysis_errors) if studio_intelligence else {}
        set_job(job_id, visual_analysis_status=reference_analysis.get("status", "ready"), reference_analysis=reference_analysis, step="Master aur compact prompt likh raha hoon")
        
        set_job(job_id, step="Master aur compact prompt likh raha hoon")
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_synth = pool.submit(
                synthesize, detail, mode, subject_text, hair_text, pose_text,
                outfit_override, look_desc, outfit_desc, studio_context
            )
            f_comp = pool.submit(
                run_compose, mode, subject_text, hair_text, pose_text,
                outfit_override, look_desc, outfit_desc
            )
            final_prompt = f_synth.result()
            try:
                compact_text, compact_warn = f_comp.result()
            except LLMError as e:
                compact_text, compact_warn = "", [f"Compact prompt nahi bana: {str(e)[:120]}"]
                
        quality = validate_studio_prompt(final_prompt, studio_intelligence) if studio_intelligence else {}
        review_warnings = list(quality.get("warnings", []))
        review_warnings.extend(reference_analysis.get("notes", []))
        set_job(job_id, status="done", step="", prompt=final_prompt, mode=mode,
                detail=detail, output="full", compact=compact_text,
                compact_warnings=compact_warn, studio_quality=quality,
                reference_analysis=reference_analysis,
                visual_analysis_status=reference_analysis.get("status", "ready"),
                warnings=review_warnings, processing_status=quality.get("status", "ready"))
    except LLMError:
        set_job(job_id, status="error",
                error="AI service could not complete this request. Please retry shortly.",
                step="", visual_analysis_status="failed")
    except Exception:
        app.logger.exception("Vision Studio generation job failed")
        set_job(job_id, status="error",
                error="An unexpected server error occurred. Please retry.",
                step="", visual_analysis_status="failed")

ALIASES = {
    "SUBJECT": "SUBJECT PHYSIQUE", "PHYSIQUE": "SUBJECT PHYSIQUE",
    "HAIR": "HAIRSTYLE", "MAKEUP LOOK": "MAKEUP",
    "OUTFIT TYPE": "OUTFIT", "TOP": "OUTFIT", "BOTTOM": "OUTFIT",
    "JEWELLERY": "JEWELLERY AND ACCESSORIES", "ACCESSORIES": "JEWELLERY AND ACCESSORIES",
    "POSE": "POSE AND ACTION", "GAZE": "AND GAZE",
    "BACKGROUND": "BACKGROUND AND ENVIRONMENT", "LIGHTING": "LIGHTING AND CAMERA",
    "AVOID": "NEGATIVE PROMPT", "NEGATIVE": "NEGATIVE PROMPT",
}

HEADER_RE = re.compile(r"^\s*\*\s*([A-Za-z][A-Za-z &/-]{1,40}?)\s*\*\s*:\s*(.*)$")

HAIR_GROUPS = {
    "length": r"length|shoulder|chest|waist|collarbone|inch|\blong\b|\bshort\b|\bbob\b|mid-back",
    "parting": r"part",
    "volume": r"volume|root|crown|lift|sleek|flat",
    "ends": r"\bends?\b|\btips?\b|flick",
    "placement": r"tuck|drap|rest|cascad|\bfalls?\b|behind|\bover\b|\bbare\b",
}

def section_protected(text):
    facts = []
    facts += re.findall(r"\b\d{3,5}\s?K\b", text)
    facts += re.findall(r"#[0-9A-Fa-f]{6}\b", text)
    low = (text or "").lower()
    for term in ("screen-left", "screen-right"):
        if term in low:
            facts.append(term)
    return facts

def hair_groups_in(text):
    low = (text or "").lower()
    return {g for g, pat in HAIR_GROUPS.items() if re.search(pat, low)}

def loose_parse_sections(text):
    out = {}
    active = None
    for raw_line in (text or "").split("\n"):
        t = (raw_line or "").replace("**", "").strip()
        t = re.sub(r"^[-*#\s]+", "", t)
        t = " ".join(t.split())
        if not t:
            continue
        m = HEADER_RE.match(t)
        if m:
            key = " ".join(m.group(1).upper().split())
            canon = ALIASES.get(key, key)
            if canon in COMPACT_ORDER:
                active = canon
                val = m.group(2).strip().strip('"').strip()
                if val and val.lower() not in ("none", "not provided", "not visible"):
                    out[canon] = (out.get(canon, "") + " " + val).strip()
                else:
                    out.setdefault(canon, "")
                continue
        if active:
            out[active] = (out.get(active, "") + " " + t).strip()
    return {k: v for k, v in out.items() if v}

def assemble_sections(sections):
    return "\n".join(f"{l}: {sections[l]}" for l in COMPACT_ORDER if sections.get(l))

def compact(s):
    return re.sub(r"\s+", "", s).lower()

def collect_facts(skeleton):
    facts = []
    facts += re.findall(r"\b\d{3,5}\s?K\b", skeleton)
    facts += re.findall(r"#[0-9A-Fa-f]{6}\b", skeleton)
    low = skeleton.lower()
    for term in ("screen-left", "screen-right"):
        if term in low:
            facts.append(term)
    seen, unique = set(), []
    for f in facts:
        if compact(f) not in seen:
            seen.add(compact(f))
            unique.append(f)
    return unique

def missing_facts(skeleton, text):
    body = compact(text)
    return [f for f in collect_facts(skeleton) if compact(f) not in body]

PARAGRAPH_LIMIT = 1000
PARAGRAPH_SYSTEM = """You rewrite a labelled image prompt into ONE flowing editorial paragraph for Nano Banana 2.1 (vertical 9:16 portrait).
Rules:
Output ONE paragraph of natural English sentences. No labels, no lists, no markdown, no quotes, no line breaks.
Maximum 1000 characters. Aim for about 950.
Start with "Use the reference face." Then the 4 to 6 strongest body facts from SUBJECT PHYSIQUE.
Then hairstyle (keep length, parting, ends, placement), makeup, outfit with colour, hex and fit (footwear only if the feet are in frame), one jewellery item of each kind, pose and gaze (keep screen-left and screen-right exact), background, light and camera (keep Kelvin, direction and catchlight), framing with vertical 9:16, and quality in a few words.
Keep every number, Kelvin value, hex code, screen-left and screen-right exactly.
End with a short avoid clause of 4 to 5 items.
Never write none, not provided, not visible or no outside the avoid clause. Do not add facts that are not in the input."""

def to_paragraph(raw):
    lines = []
    for line in (raw or "").split("\n"):
        t = line.replace("**", "").strip()
        t = re.sub(r"^[-*#\s]+", "", t)
        t = " ".join(t.split())
        if t and t.endswith(":") and len(t) <= 25:
            continue
        if t:
            lines.append(t)
    text = " ".join(lines).strip().strip('"').strip()
    text = re.sub(r"^(Paragraph|Prompt|Output)\s*:\s*", "", text, flags=re.I)
    return " ".join(text.split())

def cut_paragraph(text, limit=PARAGRAPH_LIMIT):
    if len(text) <= limit:
        return text
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    keep = [False] * len(sents)
    
    def joined():
        return " ".join(s for s, k in zip(sents, keep) if k).strip()
        
    for i, s in enumerate(sents):
        if section_protected(s):
            keep[i] = True
            if len(joined()) > limit:
                keep[i] = False
                
    for i, s in enumerate(sents):
        if not keep[i]:
            keep[i] = True
            if len(joined()) > limit:
                keep[i] = False
                
    out = joined()
    if not out:
        out = text[:limit].rsplit(" ", 1)[0]
    return out

def run_optimize_job(job_id, skeleton, mode, detail):
    try:
        models = OPTIMIZER_MODELS
        warnings = []
        set_job(job_id, step="Paragraph prompt likh raha hoon", mode=mode, detail=detail)
        messages = [
            {"role": "system", "content": PARAGRAPH_SYSTEM},
            {"role": "user", "content": f"MODE: {mode}\n\nSKELETON PROMPT:\n{skeleton}"},
        ]
        raw, used_model = chain_chat(messages, "optimizer-paragraph", models,
                                     temperature=0.2, max_tokens=500)
        para = to_paragraph(raw)
        if not para:
            raise LLMError("Paragraph khali aaya. Dobara try karein.")
        para = cut_paragraph(para, PARAGRAPH_LIMIT)
        
        missing = missing_facts(skeleton, para)
        if missing:
            warnings.append("Ye details paragraph mein nahi aaye: " + ", ".join(missing))
            
        set_job(job_id, status="done", step="", prompt=para, warnings=warnings,
                optimizer_model=used_model, over_budget=len(para) > PARAGRAPH_LIMIT, section_chars={})
    except LLMError:
        set_job(job_id, status="error",
                error="AI service could not optimize this prompt. Please retry shortly.", step="")
    except Exception:
        app.logger.exception("Prompt optimization job failed")
        set_job(job_id, status="error",
                error="An unexpected server error occurred. Please retry.", step="")

def validate_telegram_repo_path(path):
    """Accept only safe repository-relative paths from Telegram commands."""
    if not isinstance(path, str): return None
    normalized = path.strip()
    if not normalized or len(normalized) > 240 or normalized.startswith("/"): return None
    if any(ord(char) < 32 or ord(char) == 92 for char in normalized): return None
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts) or parts[0] == ".git": return None
    return normalized
# ---------- TELEGRAM WEBHOOK ROUTE WITH REPLY SUPPORT ----------
def send_telegram_reply(chat_id, message):
    """Send a bounded-time Telegram reply without leaking transport errors."""
    if not TELEGRAM_TOKEN:
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": str(message)[:3500]},
            timeout=10,
            allow_redirects=False,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        # Request exceptions may include the bot-token URL; never log their details.
        app.logger.warning("Telegram webhook reply delivery failed.")
        return False


def apply_patch(content, old, new):
    if old in content:
        return content.replace(old, new), content.count(old)
    rx = re.compile(r"\s+".join(re.escape(t) for t in old.split()))
    n = len(rx.findall(content))
    if not n:
        return content, 0
    return rx.sub(lambda m: new, content), n

@app.route("/")
def index():
    return render_template("index.html")

@app.route(f"/{TELEGRAM_TOKEN}" if TELEGRAM_TOKEN else "/_tg_disabled", methods=["POST"])
@limiter.limit("30 per minute")
def telegram_webhook():
    if not TELEGRAM_WEBHOOK_ENABLED or not TELEGRAM_TOKEN or not TELEGRAM_WEBHOOK_SECRET:
        return "", 404
    supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(
        supplied_secret.encode("utf-8"),
        TELEGRAM_WEBHOOK_SECRET.encode("utf-8"),
    ):
        return "", 403
    allowed_repo = "LokeshofficialGit/ATELIER_PROMPT_ENG."
    allowed_branch = "visual-lab-rebuild"
    if REPO_NAME.casefold() != allowed_repo.casefold() or BRANCH != allowed_branch:
        app.logger.error("Telegram webhook blocked: target is outside the development allowlist.")
        return "", 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return "OK", 200
    msg = data.get("message")
    if not isinstance(msg, dict):
        return "OK", 200
    chat = msg.get("chat")
    text = msg.get("text", "")
    if not isinstance(chat, dict) or "id" not in chat or not isinstance(text, str):
        return "OK", 200
    chat_id = chat["id"]
    if isinstance(chat_id, bool) or not isinstance(chat_id, int):
        return "OK", 200
    if len(text) > MAX_TELEGRAM_MESSAGE_CHARS:
        app.logger.warning("Telegram webhook ignored an oversized message.")
        return "OK", 200
    reply_msg = ""

    # OWNER CHECK: sirf owner ka message process hoga. Baaki sab silently ignore.
    sender = msg.get("from")
    sender_id = str(sender.get("id", "")) if isinstance(sender, dict) else ""
    if not OWNER_TELEGRAM_ID or sender_id != OWNER_TELEGRAM_ID:
        return "OK", 200

    try:
        auth = Auth.Token(GITHUB_TOKEN)
        repo = Github(auth=auth).get_repo(REPO_NAME)

        # 1. PATCH MODE (Choti line badalne ke liye)
        if "---PATCH---" in text:
            head, body = text.split("---PATCH---", 1)
            path = validate_telegram_repo_path(head.replace("file:", "").strip() or "app.py")
            if not path:
                send_telegram_reply(chat_id, "⚠️ Invalid repository file path.")
                return "OK", 200

            f = repo.get_contents(path, ref=BRANCH)
            content = f.decoded_content.decode("utf-8")
            original = content
            ok = 0

            for block in body.split("---NEXT---"):
                if "===>" not in block: 
                    continue
                old, new = block.split("===>", 1)
                content, n = apply_patch(content, old.strip(), new.strip())
                if n: 
                    ok += 1

            if ok and content != original:
                if path.endswith(".py"):
                    ast.parse(content)  # galat Python code commit nahi hoga
                repo.update_file(path, f"patch {path} via Telegram webhook", content, f.sha, branch=BRANCH)
                reply_msg = f"✅ Patched successfully! ({path})"
            else:
                reply_msg = f"⚠️ Patching failed or no changes found for '{path}'."

        # 2. FULL FILE MODE (Poori file overwrite karne ke liye)
        elif "file:" in text and "---CODE---" in text:
            parts = text.split("---CODE---", 1)
            path = validate_telegram_repo_path(parts[0].replace("file:", "").strip())
            code = parts[1].strip()
            if not path:
                send_telegram_reply(chat_id, "⚠️ Invalid repository file path.")
                return "OK", 200
            if path.endswith(".py"):
                ast.parse(code)  # galat Python code commit nahi hoga

            try:
                f = repo.get_contents(path, ref=BRANCH)
                repo.update_file(path, f"update {path} via Telegram webhook", code, f.sha, branch=BRANCH)
                reply_msg = f"✅ Replaced successfully! ({path})"
            except Exception:
                repo.create_file(path, f"create {path} via Telegram webhook", code, branch=BRANCH)
                reply_msg = f"✅ Replaced (Created new) successfully! ({path})"

        # Telegram ko success reply bhejne ke liye
        if reply_msg:
            send_telegram_reply(chat_id, reply_msg)

    except Exception:
        # GitHub/API exception text can contain sensitive request metadata; keep logs generic.
        app.logger.warning("Telegram webhook processing failed.")
        send_telegram_reply(chat_id, "❌ Webhook request failed. Please check server logs.")

    return "OK", 200

@app.route("/generate", methods=["POST"])
@limiter.limit("10 per minute")
def generate():
    if not OPENROUTER_API_KEY:
        return jsonify({"error": "AI provider is not configured on the server."}), 503
        
    output = request.form.get("output", "full").strip().lower()
    if output not in VALID_OUTPUTS:
        output = "full"
        
    try:
        prepared = prepare_legacy_studio_request(request.form, request.files)
        look_upload = prepared.uploads_by_field.get("image1")
        outfit_upload = prepared.uploads_by_field.get("image2")
        look = (
            (look_upload.content, look_upload.declared_mime_type)
            if look_upload is not None else None
        )
        outfit = (
            (outfit_upload.content, outfit_upload.declared_mime_type)
            if outfit_upload is not None else None
        )
        studio_intelligence = build_studio_intelligence(prepared.payload, request.form)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if output == "raw":
        if look is None:
            return jsonify({"error": "RAW prompt ke liye Look photo upload karein."}), 400
        outfit = None
        
    detail = request.form.get("detail", DEFAULT_DETAIL).strip().lower()
    if detail not in DETAIL_LEVELS:
        detail = DEFAULT_DETAIL
        
    subject_text = request.form.get("subject_text", "").strip()[:MAX_TEXT_CHARS]
    hair_text = request.form.get("hair_text", "").strip()[:MAX_TEXT_CHARS]
    pose_text = request.form.get("pose_text", "").strip()[:MAX_TEXT_CHARS]
    outfit_override = request.form.get("outfit_override", "").strip()[:MAX_TEXT_CHARS]
    
    job_id = new_job("generate", detail, output=output)
    if job_id is None:
        return jsonify({"error": "Server is busy processing other jobs. Please retry shortly."}), 429
    with jobs_lock:
        job_store.update_running(
            job_id, {"studio_intelligence": studio_intelligence},
            finished_at=time.time(),
        )
    access_response = job_access_response(job_id)
    if not start_job_worker(
        job_id, run_generate_job,
        (job_id, look, outfit, subject_text, hair_text, outfit_override, pose_text, detail, output, studio_intelligence),
    ):
        return jsonify({"error": "Background processing could not start. Please retry."}), 503
    return jsonify(access_response), 202

@app.route("/optimize", methods=["POST"])
@limiter.limit("10 per minute")
def optimize():
    if not OPENROUTER_API_KEY:
        return jsonify({"error": "AI provider is not configured on the server."}), 503
        
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request must be a JSON object."}), 400
    skeleton = payload.get("skeleton", "")
    mode = payload.get("mode", "BOTH")
    detail = payload.get("detail", DEFAULT_DETAIL)
    if not isinstance(skeleton, str):
        return jsonify({"error": "Prompt skeleton must be text."}), 400
    if not isinstance(mode, str) or not isinstance(detail, str):
        return jsonify({"error": "Mode and detail must be text values."}), 400
    skeleton = skeleton.strip()
    mode = mode.strip().upper()
    detail = detail.strip().lower()

    if not skeleton:
        return jsonify({"error": "Pehle prompt generate karein."}), 400
    if len(skeleton) > MAX_SKELETON_CHARS:
        return jsonify({"error": "Prompt bahut lamba hai. Kuch sections chhote karein."}), 400
    if mode not in VALID_MODES:
        mode = "BOTH"
    if detail not in DETAIL_LEVELS:
        detail = DEFAULT_DETAIL
        
    job_id = new_job("optimize", detail)
    if job_id is None:
        return jsonify({"error": "Server is busy processing other jobs. Please retry shortly."}), 429
    access_response = job_access_response(job_id)
    if not start_job_worker(job_id, run_optimize_job, (job_id, skeleton, mode, detail)):
        return jsonify({"error": "Background processing could not start. Please retry."}), 503
    return jsonify(access_response), 202

@app.route("/status/<job_id>")
@limiter.limit("180 per minute")
def status(job_id):
    # Job identifiers are generated as UUID hex strings; reject malformed
    # paths before touching the job store.
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        response = jsonify({"status": "error", "error": "Job nahi mila ya access valid nahi hai."})
        response.status_code = 404
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    job = get_job_snapshot(job_id)
    if not job:
        response = jsonify({"status": "error", "error": "Job nahi mila ya access valid nahi hai."})
        response.status_code = 404
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    supplied_token = request.headers.get("Authorization", "")
    expected_token = "Bearer " + job.get("access_token", "")
    if not job.get("access_token") or not hmac.compare_digest(supplied_token, expected_token):
        # Use the same response as an unknown job to avoid revealing valid job IDs.
        response = jsonify({"status": "error", "error": "Job nahi mila ya access valid nahi hai."})
        response.status_code = 404
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    keys = ("kind", "status", "step", "prompt", "error", "mode", "detail",
            "output", "warnings", "optimizer_model", "over_budget", "section_chars",
            "compact", "compact_warnings", "ai_status", "quality", "model_profile",
            "processing_status", "rule_findings", "instruction_integrity", "studio_quality",
            "optimization_warnings", "provider_error", "deterministic_prompt", "output_language", "studio_intelligence",
            "visual_analysis_status", "reference_analysis")
    response = jsonify({k: job.get(k) for k in keys})
    # Job responses contain private prompts and bearer-token-protected data.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response

SCRATCH_DETAIL_LEVELS = {
    "fast":     {"chars": 600,  "tokens": 700},
    "balanced": {"chars": 1000, "tokens": 1200},
    "detailed": {"chars": 2000, "tokens": 1800},
}


def run_scratch_job(job_id, raw_keywords, attributes, style, ar, detail="balanced"):
    try:
        sys_prompt = (
            "You are a master creative director and high-fashion editorial prompt architect specializing in "
            "photorealistic portraiture and cinema photography for Nano Banana 2.1, Midjourney v6, and SDXL.\n"
            "Your objective: Transform raw concepts and anatomical attribute selections into a cohesive, breathtaking, "
            "ultra-realistic image generation prompt.\n\n"
            "Strict synthesis guidelines:\n"
            "1. Logic Priority:\n"
            "   - If Raw Keywords are provided, treat them as the central anchor and vibe of the scene.\n"
            "   - Seamlessly blend any selected anatomical attributes (gender, ethnicity, body silhouette, bust/waist/hips, "
            "hair, eyes, skin texture, expression, nuances) into the subject description without robotic repetition.\n"
            "   - If attributes are missing, organically hallucinate authentic matching garments (e.g., luxury handloom silks, "
            "couture drapes), jewelry, atmospheric background, and optical lighting matching the raw concept.\n"
            "   - If only attributes are provided with no keywords, create a full character portrait in an evocative luxury/editorial setting.\n"
            "2. Format Output strictly in these standard labeled uppercase sections:\n"
            "SUBJECT PHYSIQUE: [Descriptive organic prose of the person, ethnicity, bone structure, skin pores, zero wax/airbrush]\n"
            "HAIRSTYLE: [Hair length, architecture, parting, stray flyaways]\n"
            "MAKEUP: [Realistic minimal or editorial makeup, lip texture, skin glow]\n"
            "OUTFIT: [Detailed garment weave, fabric tension, natural drape, embroidery relief]\n"
            "JEWELLERY AND ACCESSORIES: [Authentic metals, stones, styling]\n"
            "POSE AND ACTION: [Natural stance, weight distribution, tactile hand placement]\n"
            "AND GAZE: [Eye contact, specular catchlights, genuine micro-expression]\n"
            "BACKGROUND AND ENVIRONMENT: [Atmospheric depth, environmental contact shadows, luxury or vintage setting]\n"
            "LIGHTING AND CAMERA: [85mm f/1.4 prime lens, optical bokeh, Kelvin temperature, chiaroscuro or window bounce]\n"
            "COMPOSITION: [Framing matching requested Aspect Ratio, golden ratio]\n"
            "QUALITY: [Subsurface scattering, textile micro-relief, 8k resolution, raw photograph]\n"
            "NEGATIVE PROMPT: [plastic skin, waxy mannequin, airbrushed textures, bad anatomy, deformed limbs, floating artifacts]\n\n"
            "Return ONLY the synthesized prompt text. Do not include markdown preamble, conversational filler, or notes."
        )
        
        attr_summary_list = []
        for k, v in attributes.items():
            if v and str(v).lower() != "any":
                attr_summary_list.append(f"{k.replace('_', ' ').title()}: {v}")
        attr_summary = "; ".join(attr_summary_list) if attr_summary_list else "None specified (auto-enrich organically)"
        
        user_content = (
            f"STYLE PREFERENCE: {style}\n"
            f"ASPECT RATIO: {ar}\n"
            f"RAW KEYWORDS / BRAINSTORM: {raw_keywords or 'None provided (generate character portrait based on attributes)'}\n"
            f"SPECIFIED ATTRIBUTES: {attr_summary}\n"
            f"LENGTH TARGET: about {SCRATCH_DETAIL_LEVELS[detail]['chars']} characters\n\n"
            "Please synthesize the master editorial prompt now."
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content},
        ]
        models_to_try = [MODEL] + [m for m in OPTIMIZER_MODELS if m != MODEL]
        set_job(job_id, step="Scratch prompt synthesize ho raha hai")
        result_prompt, used_model = chain_chat(
            messages, label="scratchpad-synthesizer", models=models_to_try,
            temperature=0.6, max_tokens=SCRATCH_DETAIL_LEVELS[detail]["tokens"],
        )
        set_job(job_id, status="done", step="", prompt=result_prompt, optimizer_model=used_model)
    except LLMError:
        set_job(job_id, status="error",
                error="AI service could not synthesize this prompt. Please retry shortly.", step="")
    except Exception:
        app.logger.exception("Scratch synthesis job failed")
        set_job(job_id, status="error",
                error="An unexpected server error occurred. Please retry.", step="")

@app.route("/synthesize-scratch", methods=["POST"])
@limiter.limit("20 per minute")
def synthesize_scratch():
    if not OPENROUTER_API_KEY:
        return jsonify({"error": "AI provider is not configured on the server."}), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request must be a JSON object."}), 400

    unknown_fields = set(data) - SCRATCH_ALLOWED_FIELDS
    if unknown_fields:
        return jsonify({
            "error": "Unsupported field(s): " + ", ".join(sorted(str(x) for x in unknown_fields))
        }), 400

    raw_keywords = data.get("raw_keywords", "")
    if not isinstance(raw_keywords, str):
        return jsonify({"error": "Raw keywords must be text."}), 400
    raw_keywords = raw_keywords.strip()
    if len(raw_keywords) > MAX_TEXT_CHARS:
        return jsonify({"error": f"Raw keywords must be {MAX_TEXT_CHARS} characters or fewer."}), 400

    attributes = data.get("attributes", {})
    if not isinstance(attributes, dict):
        return jsonify({"error": "Attributes must be a JSON object."}), 400
    if len(attributes) > SCRATCH_MAX_ATTRIBUTES:
        return jsonify({"error": f"At most {SCRATCH_MAX_ATTRIBUTES} attributes are allowed."}), 400

    clean_attributes = {}
    total_attribute_chars = 0
    for key, value in attributes.items():
        if not isinstance(key, str) or not key.strip() or len(key) > 80:
            return jsonify({"error": "Each attribute name must be non-empty text of 80 characters or fewer."}), 400
        if not isinstance(value, str):
            return jsonify({"error": f"Attribute '{key}' must have a text value."}), 400
        value = value.strip()
        if len(value) > SCRATCH_MAX_ATTRIBUTE_VALUE_CHARS:
            return jsonify({
                "error": f"Attribute '{key}' must be {SCRATCH_MAX_ATTRIBUTE_VALUE_CHARS} characters or fewer."
            }), 400
        total_attribute_chars += len(key) + len(value)
        if total_attribute_chars > SCRATCH_MAX_TOTAL_ATTRIBUTE_CHARS:
            return jsonify({
                "error": f"Combined attribute text must be {SCRATCH_MAX_TOTAL_ATTRIBUTE_CHARS} characters or fewer."
            }), 400
        if value and value.lower() != "any":
            clean_attributes[key.strip()] = value

    style = data.get("style", "editorial")
    if not isinstance(style, str) or not style.strip() or len(style.strip()) > 40:
        return jsonify({"error": "Style must be non-empty text of 40 characters or fewer."}), 400
    style = style.strip()

    ar = data.get("ar", "9:16")
    if not isinstance(ar, str) or not re.fullmatch(r"\d{1,2}:\d{1,2}", ar.strip()):
        return jsonify({"error": "Aspect ratio must use a format such as 9:16 or 1:1."}), 400
    ar = ar.strip()

    detail = data.get("detail", "balanced")
    if not isinstance(detail, str) or detail.lower() not in SCRATCH_DETAIL_LEVELS:
        return jsonify({"error": "Detail must be fast, balanced, or detailed."}), 400
    detail = detail.lower()

    if not raw_keywords and not clean_attributes:
        return jsonify({"error": "Raw keywords ya attributes mein se kuch dein."}), 400

    job_id = new_job("scratch", detail)
    if job_id is None:
        return jsonify({"error": "Server is busy processing other jobs. Please retry shortly."}), 429
    access_response = job_access_response(job_id)
    if not start_job_worker(job_id, run_scratch_job,
                            (job_id, raw_keywords, clean_attributes, style, ar, detail)):
        return jsonify({"error": "Background processing could not start. Please retry."}), 503
    return jsonify(access_response), 202

# Vision Lab — structured, text-only creative construction API.
VISION_LAB_ALLOWED_MODELS = {
    '', 'openai/gpt-image', 'google/gemini-2.5-flash-image',
    'black-forest-labs/flux.1-pro', 'midjourney',
}

def run_vision_lab_job(job_id, payload, reasoning_model_id='', target_model_id=''):
    try:
        result = run_vision_lab_pipeline(payload, model_id=reasoning_model_id or MODEL, target_model_id=target_model_id or None, use_ai=True)
        set_job(job_id, status='done', step='', prompt=result['prompt'],
                ai_status=result['ai_status'], quality=result['quality'],
                model_profile=result['model_profile'],
                processing_status=result['processing_status'],
                rule_findings=result['rule_findings'],
                instruction_integrity=result['instruction_integrity'],
                optimization_warnings=result['optimization_warnings'],
                provider_error=result.get('provider_error'),
                deterministic_prompt=result['deterministic_prompt'],
                output_language=result['output_language'])
    except ValueError:
        app.logger.exception('Vision Lab job rejected an invalid internal value')
        set_job(job_id, status='error', step='',
                error='Vision Lab could not process this request. Please review the inputs and retry.')
    except Exception:
        app.logger.exception('Vision Lab job failed')
        set_job(job_id, status='error', step='',
                error='Vision Lab could not complete this request. Please retry.')

@app.route('/vision-lab/generate', methods=['POST'])
@limiter.limit('10 per minute')
def vision_lab_generate():
    if not OPENROUTER_API_KEY:
        return jsonify({'error': 'AI provider is not configured on the server.'}), 503
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'error': 'Request must be a JSON object.'}), 400
    target_model_id = payload.get('target_model_id', '')
    if not isinstance(target_model_id, str) or target_model_id not in VISION_LAB_ALLOWED_MODELS:
        return jsonify({'error': 'Selected model is not supported.'}), 400
    try:
        from atelier_engine.vision_lab import normalize_vision_lab_draft
        draft = normalize_vision_lab_draft(payload)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    clean = {'mode': draft.mode, 'language': draft.language,
             'instructions': draft.instructions,
             'selections': dict(draft.selections)}
    job_id = new_job('vision_lab', draft.mode)
    if job_id is None:
        return jsonify({'error': 'Server is busy processing other jobs. Please retry shortly.'}), 429
    access_response = job_access_response(job_id)
    if not start_job_worker(
        job_id, run_vision_lab_job,
        (job_id, clean, os.getenv('VISION_LAB_MODEL') or os.getenv('MODEL') or MODEL, target_model_id),
    ):
        return jsonify({'error': 'Background processing could not start. Please retry.'}), 503
    return jsonify(access_response), 202

@app.route('/vision-lab/repair', methods=['POST'])
@limiter.limit('5 per minute')
def vision_lab_repair():
    if not OPENROUTER_API_KEY:
        return jsonify({'error': 'AI provider is not configured on the server.'}), 503
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'error': 'Request must be a JSON object.'}), 400
    prompt = payload.get('prompt')
    instructions = payload.get('instructions', '')
    target_model_id = payload.get('target_model_id', '')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20000:
        return jsonify({'error': 'Prompt must contain 1 to 20000 characters.'}), 400
    if not isinstance(instructions, str) or len(instructions) > 20000:
        return jsonify({'error': 'Protected instructions must be text of 20000 characters or fewer.'}), 400
    if not isinstance(target_model_id, str) or target_model_id not in VISION_LAB_ALLOWED_MODELS:
        return jsonify({'error': 'Selected model is not supported.'}), 400
    try:
        result = propose_prompt_repair(prompt, protected_instructions=instructions,
                                       model_id=os.getenv('VISION_LAB_MODEL') or os.getenv('MODEL') or MODEL,
                                       target_model_id=target_model_id or None)
        return jsonify(result), 200
    except Exception:
        app.logger.exception('Vision Lab repair failed')
        return jsonify({'error': 'Prompt repair is temporarily unavailable. Your original prompt is unchanged.'}), 502


@app.route('/vision-lab/validate', methods=['POST'])
@limiter.limit('30 per minute')
def vision_lab_validate():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'error': 'Request must be a JSON object.'}), 400
    prompt = payload.get('prompt')
    instructions = payload.get('instructions', '')
    target_model_id = payload.get('target_model_id', '')
    if not isinstance(prompt, str) or len(prompt) > 20000:
        return jsonify({'error': 'Prompt must be text of 20000 characters or fewer.'}), 400
    if not isinstance(instructions, str) or len(instructions) > 20000:
        return jsonify({'error': 'Protected instructions must be text of 20000 characters or fewer.'}), 400
    if not isinstance(target_model_id, str) or target_model_id not in VISION_LAB_ALLOWED_MODELS:
        return jsonify({'error': 'Selected model is not supported.'}), 400
    from atelier_engine.model_profiles import get_model_profile
    from atelier_engine.vision_lab_quality import quality_report_to_dict, validate_prompt_quality
    profile = get_model_profile(target_model_id)
    report = validate_prompt_quality(prompt, protected_instructions=instructions, max_chars=profile.max_prompt_chars)
    return jsonify({'quality': quality_report_to_dict(report), 'model_profile': {'display_name': profile.display_name, 'max_prompt_chars': profile.max_prompt_chars}, 'instruction_integrity': 'preserved' if instructions in prompt or not instructions else 'review_required'}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
