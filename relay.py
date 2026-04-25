"""
Usage:
    VPS_KEY="your_secret" python3 relay.py
"""

from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor
import requests
import base64
import logging
import os

app = Flask(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

VPS_KEY = os.environ.get("VPS_KEY", "CHANGE_ME_TO_A_STRONG_SECRET")
PORT    = int(os.environ.get("PORT", 8080))
TIMEOUT = 25
WORKERS = 20

SKIP_HEADERS = {
    "host", "connection", "content-length",
    "transfer-encoding", "proxy-connection",
    "proxy-authorization", "te",
}


def do_fetch(item: dict) -> dict:
    url = item.get("u", "")
    if not url or not url.startswith(("http://", "https://")):
        return {"e": "bad url"}

    method = (item.get("m") or "GET").upper()

    headers = {}
    for k, v in (item.get("h") or {}).items():
        if k.lower() not in SKIP_HEADERS:
            headers[k] = v

    body = None
    if item.get("b"):
        try:
            body = base64.b64decode(item["b"])
        except Exception:
            return {"e": "bad base64"}

    if item.get("ct"):
        headers["Content-Type"] = item["ct"]

    try:
        r = requests.request(
            method, url,
            headers=headers,
            data=body,
            allow_redirects=item.get("r", True),
            verify=True,
            timeout=TIMEOUT,
        )
        return {
            "s": r.status_code,
            "h": dict(r.headers),
            "b": base64.b64encode(r.content).decode(),
        }
    except requests.exceptions.SSLError as e:
        return {"e": "ssl: " + str(e)[:100]}
    except requests.exceptions.ConnectionError as e:
        return {"e": "conn: " + str(e)[:100]}
    except requests.exceptions.Timeout:
        return {"e": "timeout"}
    except Exception as e:
        return {"e": str(e)[:200]}


@app.route("/relay", methods=["POST"])
def relay():
    try:
        req = request.get_json(force=True, silent=True)
        if not req:
            return jsonify({"e": "invalid json"}), 400
        if req.get("vk") != VPS_KEY:
            logging.warning("unauthorized from %s", request.remote_addr)
            return jsonify({"e": "unauthorized"}), 403

        # batch — موازی
        if "q" in req and isinstance(req["q"], list):
            logging.info("batch %d from %s", len(req["q"]), request.remote_addr)
            with ThreadPoolExecutor(max_workers=WORKERS) as ex:
                results = list(ex.map(do_fetch, req["q"]))
            return jsonify({"q": results})

        # single
        logging.info("%s %s", req.get("m", "GET"), req.get("u", "")[:80])
        return jsonify(do_fetch(req))

    except Exception as e:
        logging.exception("relay error")
        return jsonify({"e": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def index():
    return "<h1>OK</h1>", 200


if __name__ == "__main__":
    logging.info("relay on 0.0.0.0:%d", PORT)
    app.run(host="0.0.0.0", port=PORT, threaded=True)
