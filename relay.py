"""
relay.py — VPS Relay Server for MasterHttpRelayVPN
https://github.com/masterking32/MasterHttpRelayVPN

Optimizations:
  - Connection pooling
  - Parallel batch processing
  - DNS caching
  - GET response caching
  - Accept-Encoding (compressed responses)
  - Waitress WSGI server

Usage:
    VPS_KEY="your_secret" python3 relay.py
"""

from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from cachetools import TTLCache
import requests
import base64
import logging
import os
import threading
import hashlib
import time
import socket as _socket

# ── Config ────────────────────────────────────────────────────────────────────
VPS_KEY   = os.environ.get("VPS_KEY",   "CHANGE_ME_TO_A_STRONG_SECRET")
PORT      = int(os.environ.get("PORT",      "8080"))
WORKERS   = int(os.environ.get("WORKERS",   "30"))
TIMEOUT   = int(os.environ.get("TIMEOUT",   "25"))
CACHE_MAX = int(os.environ.get("CACHE_MAX", "500"))
CACHE_TTL = int(os.environ.get("CACHE_TTL", "30"))

SKIP_HEADERS = {
    "host", "connection", "content-length", "transfer-encoding",
    "proxy-connection", "proxy-authorization", "te",
}
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

# ── Connection Pool ───────────────────────────────────────────────────────────
_session = requests.Session()
_adapter = HTTPAdapter(
    pool_connections=100,
    pool_maxsize=200,
    max_retries=requests.adapters.Retry(
        total=2,
        backoff_factor=0.2,
        status_forcelist=[502, 503, 504],
    ),
)
_session.mount("http://",  _adapter)
_session.mount("https://", _adapter)

# ── DNS Cache ─────────────────────────────────────────────────────────────────
_dns_cache: dict = {}
_dns_lock = threading.Lock()
_orig_getaddrinfo = _socket.getaddrinfo

def _cached_getaddrinfo(host, port, *args, **kwargs):
    key = (host, port, args)
    with _dns_lock:
        entry = _dns_cache.get(key)
        if entry and time.time() - entry[1] < 300:
            return entry[0]
    result = _orig_getaddrinfo(host, port, *args, **kwargs)
    with _dns_lock:
        _dns_cache[key] = (result, time.time())
    return result

_socket.getaddrinfo = _cached_getaddrinfo

# ── Response Cache ────────────────────────────────────────────────────────────
_cache      = TTLCache(maxsize=CACHE_MAX, ttl=CACHE_TTL)
_cache_lock = threading.Lock()

def _cache_key(item: dict):
    if (item.get("m") or "GET").upper() != "GET":
        return None
    if item.get("b"):
        return None
    raw = item.get("u", "") + str(sorted((item.get("h") or {}).items()))
    return hashlib.md5(raw.encode()).hexdigest()

def _get_cache(key):
    with _cache_lock:
        return _cache.get(key)

def _set_cache(key, value):
    with _cache_lock:
        _cache[key] = value

# ── Fetch ─────────────────────────────────────────────────────────────────────
def do_fetch(item: dict) -> dict:
    url = item.get("u", "")
    if not url or not url.startswith(("http://", "https://")):
        return {"e": "bad url"}

    ck = _cache_key(item)
    if ck:
        cached = _get_cache(ck)
        if cached:
            return cached

    method  = (item.get("m") or "GET").upper()
    headers = {k: v for k, v in (item.get("h") or {}).items()
               if k.lower() not in SKIP_HEADERS}

    headers.setdefault("Accept-Encoding", "gzip, deflate, br")
    headers.setdefault("Connection", "keep-alive")

    body = None
    if item.get("b"):
        try:
            body = base64.b64decode(item["b"])
        except Exception:
            return {"e": "bad base64"}

    if item.get("ct"):
        headers["Content-Type"] = item["ct"]

    t0 = time.time()
    try:
        r = _session.request(
            method, url,
            headers=headers,
            data=body,
            allow_redirects=item.get("r", True),
            verify=True,
            timeout=(5, TIMEOUT),
        )
        elapsed = int((time.time() - t0) * 1000)

        resp_headers = {k: v for k, v in r.headers.items()
                        if k.lower() not in {"transfer-encoding", "connection",
                                             "keep-alive", "te", "trailers", "upgrade"}}
        result = {
            "s":  r.status_code,
            "h":  resp_headers,
            "b":  base64.b64encode(r.content).decode(),
            "ms": elapsed,
        }

        if ck and r.status_code in (200, 301, 302, 304):
            _set_cache(ck, result)

        return result

    except requests.exceptions.SSLError       as e: return {"e": "ssl: "  + str(e)[:100]}
    except requests.exceptions.ConnectionError as e: return {"e": "conn: " + str(e)[:100]}
    except requests.exceptions.Timeout:              return {"e": "timeout"}
    except Exception                           as e: return {"e": str(e)[:200]}

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/relay", methods=["POST"])
def relay():
    try:
        req = request.get_json(force=True, silent=True)
        if not req:
            return jsonify({"e": "invalid json"}), 400
        if req.get("vk") != VPS_KEY:
            logging.warning("unauthorized from %s", request.remote_addr)
            return jsonify({"e": "unauthorized"}), 403

        if "q" in req and isinstance(req["q"], list):
            items   = req["q"]
            results = [None] * len(items)
            logging.info("batch %d from %s", len(items), request.remote_addr)
            with ThreadPoolExecutor(max_workers=min(WORKERS, len(items))) as ex:
                futures = {ex.submit(do_fetch, item): i for i, item in enumerate(items)}
                for future in as_completed(futures):
                    idx = futures[future]
                    try:    results[idx] = future.result()
                    except Exception as e: results[idx] = {"e": str(e)}
            return jsonify({"q": results})

        logging.info("%s %s", req.get("m", "GET"), req.get("u", "")[:80])
        return jsonify(do_fetch(req))

    except Exception as e:
        logging.exception("relay error")
        return jsonify({"e": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    with _cache_lock: cs = len(_cache)
    with _dns_lock:   ds = len(_dns_cache)
    return jsonify({"status": "ok", "cache": cs, "dns_cache": ds, "workers": WORKERS})


@app.route("/cache/clear", methods=["POST"])
def clear_cache():
    if request.headers.get("X-VPS-Key") != VPS_KEY:
        return jsonify({"e": "unauthorized"}), 403
    with _cache_lock: _cache.clear()
    return jsonify({"status": "cleared"})


@app.route("/", methods=["GET"])
def index():
    return "<h1>OK</h1>", 200


# ── Start ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.info("relay → 0.0.0.0:%d  workers=%d  cache=%d×%ds",
                 PORT, WORKERS, CACHE_MAX, CACHE_TTL)
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=PORT, threads=WORKERS)
    except ImportError:
        logging.warning("waitress not found, using Flask dev server")
        app.run(host="0.0.0.0", port=PORT, threaded=True)
