#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM-Bahnhof (version 1.0.0)
============================

OpenAI-kompatibler Modell-Proxy mit automatischem Fallback-Loop ueber
beliebig viele Provider (ROUTE_01, ROUTE_02, ...), virtuellem Dummy-Modell
(/v1/models), Modell-Mapping und flexiblen Timeouts.

Konfiguration (.env):
    VIRTUAL_MODEL=llm-bahnhof
    DEFAULT_TIMEOUT=60s
    ROUTE_01=https://api.example.com/v1|dein_token|gpt-4o|45s
    ROUTE_02=http://10.0.0.1:11434/v1|none|qwen3:8b|0

Format einer Route (durch | getrennt):
    URL | API-Key | Ziel-Modell | Timeout

    - API-Key: "none" oder leer  -> kein Authorization-Header; der
      eingehende Client-Key wird durchgereicht, falls vorhanden.
      "Bearer ..." wird akzeptiert, "Bearer " wird bei Bedarf ergaenzt.
    - Timeout: 30, 90s, 15m, 2h oder 0 (= kein Timeout).
      Leer/ungueltig -> DEFAULT_TIMEOUT.

Endpunkte:
    GET  /v1/models                    -> virtuelles Dummy-Modell
    POST /v1/chat/completions          -> Proxy mit Fallback
    POST /api/v1/chat/completions      -> Alias (legacy)
    GET  /health                       -> Status/Diagnose
"""

import os
import re
import logging
import requests
from flask import Flask, request, Response, jsonify
from dotenv import load_dotenv

# Umgebungsvariablen laden (fuer Tests via DOTENV_PATH ueberschreibbar).
load_dotenv(os.getenv("DOTENV_PATH", ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("LLM_BAHNHOF")

app = Flask(__name__)

HOST = os.getenv("ROUTER_HOST", "0.0.0.0")
PORT = int(os.getenv("ROUTER_PORT", "8000"))

# Virtuelles Modell, das Clients verwenden; wird pro Route auf das
# echte Ziel-Modell gemappt.
VIRTUAL_MODEL = os.getenv("VIRTUAL_MODEL", "llm-bahnhof")
DEFAULT_TIMEOUT = os.getenv("DEFAULT_TIMEOUT", "60s")

# Wie viele komplette Durchlaeufe ueber alle Routen bei Fehlern versucht
# werden (Schutz gegen transiente Fehler).
MAX_PASSES = int(os.getenv("ROUTER_MAX_PASSES", "1"))


def parse_timeout(value, default=None):
    """Wandelt '30', '90s', '15m', '2h' oder '0' (kein Timeout) in Sekunden um.

    Rueckgabe: float (Sekunden) oder None (= kein Timeout).
    Leere/ungueltige Werte fallen auf `default` bzw. DEFAULT_TIMEOUT zurueck.
    """
    if default is None:
        default = DEFAULT_TIMEOUT

    raw = str(value).strip().lower() if value is not None else ""
    if raw == "":
        raw = str(default).strip().lower()
    if raw == "0":
        return None

    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smh]?)", raw)
    if not match:
        logger.warning(f"[CONFIG] Ungueltiger Timeout '{value}', verwende Default {default}")
        if str(value).strip().lower() == str(default).strip().lower():
            return 60.0  # Default selbst ungueltig -> harter Fallback
        return parse_timeout(default)

    number = float(match.group(1))
    unit = match.group(2)
    return {"": number, "s": number, "m": number * 60, "h": number * 3600}[unit]


def normalize_url(url):
    """Haengt '/chat/completions' an, falls die Basis-URL es nicht schon enthaelt.

    Konfiguriert wird eine Basis-URL (z. B. https://api.example.com/v1),
    der tatsaechliche Endpunkt ist .../chat/completions.
    """
    url = url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    return url


def load_routes():
    """Liest alle ROUTE_XX Variablen (Pipe-Format) aus der Umgebung.

    Reihenfolge der Routen = aufsteigende Nummer (ROUTE_01 zuerst).
    Ungueltige/Platzhalter-URLs werden uebersprungen.
    """
    routes = []
    entries = []

    for key, value in os.environ.items():
        match = re.fullmatch(r"ROUTE_(\d+)", key)
        if match:
            entries.append((int(match.group(1)), key, value))

    entries.sort()
    for number, key, value in entries:
        parts = value.split("|")
        url = parts[0].strip() if parts else ""
        if not url or "example" in url:
            logger.warning(f"[CONFIG] {key} uebersprungen (keine gueltige URL: '{url}')")
            continue

        routes.append({
            "name": f"ROUTE_{number:02d}",
            "url": normalize_url(url),
            "api_key": (parts[1].strip() if len(parts) > 1 else ""),
            "model": (parts[2].strip() if len(parts) > 2 else ""),
            "timeout": parse_timeout(parts[3].strip() if len(parts) > 3 else ""),
        })

    return routes


def build_headers(route, incoming_auth, stream):
    """Baut die Header fuer den Upstream-Request.

    Hat die Route einen eigenen Key, wird er gesetzt; sonst wird der
    eingehende Authorization-Header des Clients durchgereicht.
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
        "User-Agent": "LLMBahnhof/1.0.0",
    }

    api_key = route["api_key"]
    if api_key and api_key.lower() not in ("none", "-", "ollama"):
        auth = api_key if api_key.lower().startswith("bearer ") else f"Bearer {api_key}"
        headers["Authorization"] = auth
    elif incoming_auth:
        headers["Authorization"] = incoming_auth

    return headers


ROUTES = load_routes()

logger.info(f"[CONFIG] Virtuelles Dummy-Modell fuer Clients: '{VIRTUAL_MODEL}'")
logger.info(f"[CONFIG] {len(ROUTES)} Route(n) geladen:")
for route in ROUTES:
    logger.info(
        f"  -> {route['name']} {route['url']} | Modell: {route['model']} | Timeout: {route['timeout']}"
    )


@app.route("/v1/models", methods=["GET"])
@app.route("/api/v1/models", methods=["GET"])
def list_models():
    """Liefert das virtuelle Dummy-Modell (OpenAI-kompatibel)."""
    return jsonify({
        "object": "list",
        "data": [{
            "id": VIRTUAL_MODEL,
            "object": "model",
            "created": 0,
            "owned_by": "llm-bahnhof",
        }],
    })


@app.route("/health", methods=["GET"])
@app.route("/", methods=["GET"])
def health():
    """Status-/Diagnose-Endpunkt."""
    return jsonify({
        "status": "ok",
        "virtual_model": VIRTUAL_MODEL,
        "routes": [
            {
                "name": r["name"],
                "url": r["url"],
                "model": r["model"],
                "timeout": r["timeout"],
            }
            for r in ROUTES
        ],
    })


@app.route("/v1/chat/completions", methods=["POST"])
@app.route("/api/v1/chat/completions", methods=["POST"])
def proxy_chat_completions():
    """Proxy mit Fallback: probiert alle Routen der Reihe nach durch."""
    incoming = request.get_json(silent=True)
    if not isinstance(incoming, dict):
        return jsonify({
            "error": {
                "code": 400,
                "message": "JSON-Objekt erwartet.",
                "type": "invalid_request",
            }
        }), 400

    stream = bool(incoming.get("stream", False))
    incoming_auth = request.headers.get("Authorization", "")
    errors = []

    for pass_no in range(1, MAX_PASSES + 1):
        for route in ROUTES:
            payload = dict(incoming)
            # Modell-Mapping: Client-Modell wird durch das Ziel-Modell der Route ersetzt.
            payload["model"] = route["model"] or payload.get("model") or VIRTUAL_MODEL
            if stream:
                payload["stream"] = True

            logger.info(
                f"[ROUTER] Durchlauf {pass_no}/{MAX_PASSES} | Versuch {route['name']} -> "
                f"{route['url']} [Modell: {payload['model']}, Timeout: {route['timeout']}]"
            )

            try:
                upstream = requests.post(
                    route["url"],
                    json=payload,
                    headers=build_headers(route, incoming_auth, stream),
                    timeout=route["timeout"],
                    stream=stream,
                )
            except requests.exceptions.RequestException as exc:
                logger.error(f"[ROUTER] Verbindungsfehler/Timeout bei {route['name']}: {exc}")
                errors.append(f"{route['name']}: {exc}")
                continue

            content_type = (upstream.headers.get("Content-Type") or "").lower()

            if upstream.status_code != 200:
                snippet = upstream.text[:200] if not stream else ""
                logger.warning(f"[ROUTER] {route['name']} Status {upstream.status_code}: {snippet}")
                errors.append(f"{route['name']}: HTTP {upstream.status_code}")
                upstream.close()
                continue

            if "text/html" in content_type:
                logger.warning(f"[ROUTER] {route['name']} lieferte HTML statt JSON/SSE – uebersprungen.")
                errors.append(f"{route['name']}: HTML-Antwort")
                upstream.close()
                continue

            if stream:
                # Ersten Chunk pruefen (HTML/Cloudflare-Fallback-Seiten erkennen),
                # ohne den Stream komplett zu puffern. WICHTIG: denselben
                # Iterator weiterverwenden – ein NEUER iter_content()-Iterator
                # wuerde nach next() keine weiteren Chunks mehr liefern
                # (urllib3-Chunked-Verhalten).
                chunks = upstream.iter_content(chunk_size=4096)
                try:
                    first_chunk = next(chunks, b"")
                except requests.exceptions.RequestException as exc:
                    logger.error(f"[ROUTER] Streamfehler bei {route['name']}: {exc}")
                    errors.append(f"{route['name']}: {exc}")
                    upstream.close()
                    continue

                if b"<html" in first_chunk.lower() or b"cloudflare" in first_chunk.lower():
                    logger.warning(f"[ROUTER] {route['name']} Stream enthaelt HTML – uebersprungen.")
                    errors.append(f"{route['name']}: HTML im Stream")
                    upstream.close()
                    continue

                def generate(chunks=chunks, first_chunk=first_chunk, upstream=upstream):
                    try:
                        if first_chunk:
                            yield first_chunk
                        for chunk in chunks:
                            if chunk:
                                yield chunk
                    finally:
                        upstream.close()

                logger.info(f"[ROUTER] Erfolg bei {route['name']} – leite Stream durch.")
                # WICHTIG: Beim Streaming IMMER text/event-stream senden. Manche
                # Upstreams (z. B. manche Cloud/Proxy-Endpunkte) liefern auch bei SSE application/json,
                # was Clients wie Open WebUI daran hindert, die Antwort als Stream
                # zu verarbeiten (ewiger Lade-Kreis ohne Ausgabe).
                response = Response(
                    generate(),
                    status=200,
                    content_type="text/event-stream",
                )
                response.headers["X-Accel-Buffering"] = "no"
                response.headers["Cache-Control"] = "no-cache"
                return response

            # Nicht-Streaming: Antwort komplett pruefen und durchreichen.
            body = upstream.text
            if "<html" in body.lower() or "cloudflare" in body.lower():
                logger.warning(f"[ROUTER] {route['name']} Antwort enthaelt HTML/Cloudflare – uebersprungen.")
                errors.append(f"{route['name']}: HTML/Cloudflare im Body")
                continue

            logger.info(f"[ROUTER] Erfolg bei {route['name']} (Status 200) – reiche JSON durch.")
            return Response(body, status=200, content_type="application/json")

    logger.critical("[CRITICAL] Alle Endpunkte fehlgeschlagen.")
    return jsonify({
        "error": {
            "code": 503,
            "message": "LLM-Bahnhof Error: Keine verwertbare Modell-Antwort von keinem Endpunkt erhalten.",
            "type": "router_error",
            "routes_tried": [r["name"] for r in ROUTES],
            "details": errors,
        }
    }), 503


@app.after_request
def add_cors_headers(response):
    """Permissive CORS-Header (optional, Standard: an) – fuer Browser-Tools."""
    if os.getenv("ROUTER_CORS", "1") == "1":
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)

#EOF
