#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bahnhof-routing-check – Erreichbarkeit + Test-Call aller aktiven Routen.

Liest eine LLM-Bahnhof-.env (ROUTE_XX = URL | Token | Ziel-Modell | Timeout),
ignoriert auskommentierte Routen (Zeilen mit '#') und prüft für jede aktive
Route:
  1. Erreichbarkeit  – Verbindung zur Basis-URL (bzw. /health)
  2. Test-Call       – minimale Chat-Completion über /chat/completions

Aufruf:
  python3 check.py [pfad/zur/.env]                  (Default: ./.env)
  python3 check.py [pfad/zur/.env] -i HOST[:PORT]   Host ersetzen
  python3 check.py [pfad/zur/.env] -p PORT          Port ersetzen
  python3 check.py [pfad/zur/.env] -i HOST -p PORT  beides ersetzen
  python3 check.py -r URL[:PORT]  Remote-Check eines Bahnhofs OHNE .env/Token:
      Router-Erreichbarkeit (/health bzw. Basis-URL), /v1/models (virtuelles
      Modell) und ein Test-Call ohne Token über die aktuelle Start-Route des
      Routers (Sticky-Fallback, antwortet ein echtes LLM?).

      Host und/oder Port ALLER Routen-URLs werden nur für diesen Lauf ersetzt –
      so lässt sich dieselbe Routenliste gegen andere Bahnhofs-Instanzen prüfen
      (z. B. -i 10.7.0.124, -p 8000 oder -i 10.7.0.124 -p 8000). Die Datei
      bleibt unverändert.

Exit-Code: 0 = alle Routen OK, 1 = mindestens eine Route fehlgeschlagen,
           2 = Datei-/Aufruffehler.
"""

import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "1.3.2"
ROUTE_RE = re.compile(r"^\s*ROUTE_(\d+)\s*=(.*)$")
DEFAULT_TIMEOUT = 60  # Sekunden, wenn keine Zeitangabe in der Route steht
MAX_VERSUCHE = 2  # pro Route: 1. Versuch + 1 Wiederholung (Warm-up / transiente Fehler)

# Token-Werte, die "kein eigener API-Key" bedeuten. Bewusst identisch zum
# Router (llm_bahnhof.build_headers), sonst wuerde der Check einen
# Authorization-Header senden, den der Router nie senden wuerde.
KEIN_KEY = ("", "none", "-", "ollama", "leer")


def parse_timeout(wert: str | None, default: float = DEFAULT_TIMEOUT) -> float:
    """'30' -> 30s, '90s' -> 90s, '15m' -> 900s, '0'/'leer' -> `default`.

    `default` ist normalerweise `DEFAULT_TIMEOUT` bzw. der `DEFAULT_TIMEOUT`-Wert
    aus der .env – so wird ein dort gesetzter Default auch wirklich benutzt.

    Hinweis: Der Router deutet einen Route-Timeout von `0` als "kein Timeout".
    Der Check setzt hier bewusst `default` ein, damit er bei einer solchen
    Route nicht unbegrenzt haengt (siehe README, Abschnitt 8.2).
    """
    if not wert:
        return default
    w = wert.strip().lower()
    if w in ("0", "", "none", "-"):
        return default
    try:
        if w.endswith("m"):
            return float(w[:-1]) * 60
        if w.endswith("s"):
            return float(w[:-1])
        if w.endswith("h"):
            return float(w[:-1]) * 3600
        return float(w)
    except ValueError:
        return default


def routen_lesen(pfad: str) -> list[dict]:
    """Alle AKTIVEN Routen aus der .env lesen (auskommentierte ignorieren)."""
    routen = []
    try:
        with open(pfad, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"Fehler: Datei nicht lesbar – {e}", file=sys.stderr)
        sys.exit(2)

    # DEFAULT_TIMEOUT zuerst suchen – unabhängig davon, wo die Zeile in der
    # Datei steht (sonst würden davor stehende Routen den Modul-Default nutzen).
    default_timeout = DEFAULT_TIMEOUT
    m = re.search(r"^\s*DEFAULT_TIMEOUT\s*=\s*(\S+)", text, re.MULTILINE)
    if m:
        default_timeout = parse_timeout(m.group(1))

    for zeile in text.splitlines():
        m = ROUTE_RE.match(zeile)
        if not m:
            continue
        nummer, rest = int(m.group(1)), m.group(2)
        felder = [f.strip() for f in rest.split("|")]
        if len(felder) < 3:
            print(f"⚠️  ROUTE_{nummer:02d}: ungültiges Format (erwartet URL|Token|Modell[|Timeout]) – übersprungen", file=sys.stderr)
            continue
        url, token, modell = felder[0], felder[1], felder[2]
        timeout = parse_timeout(felder[3] if len(felder) > 3 else None, default_timeout)
        routen.append({"nummer": nummer, "url": url, "token": token, "modell": modell, "timeout": timeout})

    if not routen:
        print(f"Keine aktiven ROUTE_XX-Einträge in {pfad} gefunden.", file=sys.stderr)
        sys.exit(1)
    return routen


def chat_url(url: str) -> str:
    """Basis-URL -> /chat/completions (wird nicht doppelt angehängt)."""
    u = url.rstrip("/")
    if u.endswith("/chat/completions"):
        return u
    return u + "/chat/completions"


def basis_url(url: str) -> str:
    """Basis-URL ohne /chat/completions (für den Erreichbarkeits-Check)."""
    u = url.rstrip("/")
    if u.endswith("/chat/completions"):
        return u[: -len("/chat/completions")]
    return u


def _host_port(netloc: str) -> tuple[str, str | None]:
    """'host:8000' -> ('host', '8000'); 'host' -> ('host', None)."""
    if netloc.count(":") == 1:
        h, p = netloc.rsplit(":", 1)
        if p.isdigit():
            return h, p
    return netloc, None


def url_ersetzen(url: str, host: str | None = None, port: str | None = None) -> str:
    """Host und/oder Port einer Routen-URL temporär ersetzen (Datei bleibt unverändert).

    Beispiele mit url='http://localhost:11434/v1':
        host='10.7.0.124'              -> 'http://10.7.0.124:11434/v1'
        host='10.7.0.124', port='8000' -> 'http://10.7.0.124:8000/v1'
        port='8000'                    -> 'http://localhost:8000/v1'
    """
    if "://" in url:
        s = urllib.parse.urlsplit(url)
        net_host, net_port = _host_port(s.netloc)
        neu_host = host if host else net_host
        neu_port = port if port else net_port
        netloc = neu_host + (f":{neu_port}" if neu_port else "")
        return urllib.parse.urlunsplit((s.scheme, netloc, s.path, s.query, s.fragment))
    # URL ohne Schema (z. B. '10.0.0.5:8000/v1')
    vorne, sep, hinten = url.partition("/")
    net_host, net_port = _host_port(vorne)
    neu_host = host if host else net_host
    neu_port = port if port else net_port
    neu_vorne = neu_host + (f":{neu_port}" if neu_port else "")
    return neu_vorne + sep + hinten


def erreichbar(url: str, timeout: float) -> tuple[bool, str]:
    """True, wenn überhaupt eine HTTP-Verbindung zustande kommt (auch 4xx/5xx)."""
    basis = basis_url(url)
    letzter_fehler = "keine Verbindung"
    for test_url in (basis + "/health", basis):
        try:
            req = urllib.request.Request(test_url, method="GET")
            with urllib.request.urlopen(req, timeout=min(timeout, 10)) as r:
                return True, f"HTTP {r.status} ({test_url})"
        except urllib.error.HTTPError as e:
            # Verbindung steht – nur der Statuscode ist nicht 2xx
            return True, f"HTTP {e.code} ({test_url})"
        except Exception as e:
            # URLError, OSError/Timeout, http.client-Fehler, ungültige URL, …
            letzter_fehler = f"{type(e).__name__}: {e}"
    return False, f"keine Verbindung ({letzter_fehler[:60]})"


def test_call(route: dict) -> tuple[bool, str, str]:
    """Minimale Chat-Completion an /chat/completions senden."""
    url = chat_url(route["url"])
    body = json.dumps({
        "model": route["modell"],
        "messages": [{"role": "user", "content": "Antworte nur mit: OK"}],
        "max_tokens": 10,
        "stream": False,
        "temperature": 0,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = (route["token"] or "").strip()
    if token.lower() not in KEIN_KEY:
        if token.lower().startswith("bearer "):
            headers["Authorization"] = token
        else:
            headers["Authorization"] = "Bearer " + token

    start = time.monotonic()
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=route["timeout"]) as r:
            dauer = time.monotonic() - start
            roh = r.read().decode("utf-8", "replace").strip()
            try:
                daten = json.loads(roh)
            except ValueError:
                # HTTP 200 mit Nicht-JSON (z. B. HTML-Fehlerseite) – sauber melden, kein Crash
                return False, f"{dauer:.1f}s", f"kein JSON: {roh[:60]}"
            try:
                antwort = daten["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                antwort = None
            if not isinstance(antwort, str):
                # z. B. content=null oder Nicht-String: HTTP 200 zählt als
                # erfolgreicher Test-Call, Rohdaten nur zur Anzeige.
                antwort = json.dumps(daten)[:80]
            return True, f"{dauer:.1f}s", antwort.strip()[:60]
    except urllib.error.HTTPError as e:
        dauer = time.monotonic() - start
        detail = ""
        try:
            detail = " – " + e.read().decode("utf-8", "replace")[:120].replace("\n", " ")
        except Exception:
            pass
        return False, f"{dauer:.1f}s", f"HTTP {e.code}{detail}"
    except urllib.error.URLError as e:
        dauer = time.monotonic() - start
        grund = getattr(e, "reason", e)
        return False, f"{dauer:.1f}s", f"URLError: {grund}"
    except OSError as e:
        # deckt auch TimeoutError/socket.timeout ab
        dauer = time.monotonic() - start
        return False, f"{dauer:.1f}s", f"Timeout/Verbindung: {e}"
    except http.client.HTTPException as e:
        # z. B. IncompleteRead (Verbindung mitten in der Antwort abgebrochen), BadStatusLine
        dauer = time.monotonic() - start
        return False, f"{dauer:.1f}s", f"Verbindung abgebrochen: {type(e).__name__}"
    except Exception as e:
        # letzte Absicherung – der Check darf niemals mit einem Traceback enden
        dauer = time.monotonic() - start
        return False, f"{dauer:.1f}s", f"{type(e).__name__}: {e}"


def pruefe_route(route: dict) -> dict:
    """Route prüfen – bei Fehlschlag automatisch wiederholen (Warm-up, transiente Störungen)."""
    letztes = None
    for versuch in range(1, MAX_VERSUCHE + 1):
        ok_er, hinweis = erreichbar(route["url"], route["timeout"])
        if ok_er:
            ok_call, dauer, detail = test_call(route)
        else:
            ok_call, dauer, detail = False, "–", "nicht geprüft (Endpunkt nicht erreichbar)"
        if ok_call:
            if versuch > 1:
                detail = f"[{versuch}. Versuch ok] {detail}"
            return {"route": route, "ok_erreichbar": True, "hinweis": hinweis,
                    "ok_call": True, "dauer": dauer, "detail": detail}
        letztes = {"route": route, "ok_erreichbar": ok_er, "hinweis": hinweis,
                   "ok_call": False, "dauer": dauer, "detail": detail}
        if versuch < MAX_VERSUCHE:
            time.sleep(1)  # kurze Pause, dann Wiederholungsversuch
    return letztes


def _http_get(url: str, timeout: float = 10.0) -> tuple[int | None, str]:
    """GET: (Status, Text). Status None = keine Verbindung; 4xx/5xx zählt als Antwort."""
    try:
        req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(200_000).decode("utf-8", "replace")
        except Exception:
            return e.code, ""
    except Exception:
        return None, ""


def remote_check(base: str, port: str | None = None) -> int:
    """Remote-Prüfung eines Bahnhofs ohne .env/Token.

    1. Router-Erreichbarkeit (/health, dann Basis-URL)
    2. /v1/models -> virtuelles Modell (VIRTUAL_MODEL des Routers)
    3. Test-Call OHNE Token -> antwortet ein echtes LLM (aktuelle
       Start-Route, Sticky-Fallback)?
    """
    b = base.strip()
    if not b.startswith(("http://", "https://")):
        b = "http://" + b
    b = b.rstrip("/")
    if b.endswith("/chat/completions"):
        b = b[: -len("/chat/completions")]
    if port:
        b = url_ersetzen(b, None, port)

    print(f"🔍 Bahnhof-Remote-Check v{VERSION} für {b}")
    print("   Ohne .env/Token – Router-Erreichbarkeit + LLM-Test-Call über die aktuelle Start-Route (Sticky-Fallback)\n")

    root = b[: -len("/v1")] if b.endswith("/v1") else b

    # --- 1) Router erreichbar? ---
    antwort_ok = False
    diag = {}
    for u in dict.fromkeys((root + "/health", b, root)):
        status, text = _http_get(u)
        if status is None:
            continue
        antwort_ok = True
        try:
            diag = json.loads(text)
        except ValueError:
            diag = {}
        if not isinstance(diag, dict):
            diag = {}
        print(f"✅ Router antwortet: HTTP {status} ({u})")
        if diag.get("status"):
            print(f"   Status: „{diag['status']}“")
        if isinstance(diag.get("routes"), list):
            print(f"   Konfigurierte Routen: {len(diag['routes'])}")
        break
    if not antwort_ok:
        print("❌ Router antwortet nicht – keine Verbindung.")
        return 1

    # --- 2) /v1/models: virtuelles Modell ermitteln ---
    virtual = diag.get("virtual_model")
    models_urls = [b + "/models" if b.endswith("/v1") else b + "/v1/models",
                   root + "/api/v1/models"]
    for mu in dict.fromkeys(models_urls):
        status, text = _http_get(mu)
        if status is None or status >= 400:
            continue
        try:
            daten = json.loads(text)
            data = daten.get("data") or []
            if data and data[0].get("id"):
                virtual = data[0]["id"]
                print(f"🤖 /v1/models meldet virtuelles Modell: „{virtual}“ "
                      f"(VIRTUAL_MODEL aus der .env des Routers)")
                break
        except (ValueError, TypeError, AttributeError, IndexError):
            continue
    if not virtual:
        print("ℹ️  Kein Modellname ermittelbar (/v1/models nicht verfügbar) – "
              "Test-Call nutzt ‚llm-bahnhof‘.")
        virtual = "llm-bahnhof"

    # --- 3) Test-Call OHNE Token: antwortet ein echtes LLM? ---
    chat_url = (b if b.endswith("/v1") else b + "/v1") + "/chat/completions"
    body = json.dumps({
        "model": virtual,
        "messages": [{"role": "user", "content": "Antworte nur mit: OK"}],
        "max_tokens": 10,
        "stream": False,
        "temperature": 0,
    }).encode("utf-8")
    start = time.monotonic()
    try:
        req = urllib.request.Request(chat_url, data=body,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as r:
            dauer = time.monotonic() - start
            roh = r.read(200_000).decode("utf-8", "replace")
            antwort = ""
            try:
                daten = json.loads(roh)
                antwort = daten["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError):
                antwort = ""
            if not isinstance(antwort, str) or not antwort.strip():
                # z. B. content=null oder leere Antwort – dann Rohdaten zeigen
                antwort = roh[:100]
            print(f"✅ LLM antwortet (aktuelle Start-Route): HTTP {r.status} ({dauer:.1f}s)")
            print(f"   Antwort: „{str(antwort).strip()[:80]}“")
            print()
            print("✅ Remote-Check bestanden: Router erreichbar UND ein LLM liefert eine Antwort.")
            return 0
    except urllib.error.HTTPError as e:
        dauer = time.monotonic() - start
        roh = ""
        try:
            roh = e.read(200_000).decode("utf-8", "replace")
        except Exception:
            pass
        if e.code == 503:
            print(f"❌ Router erreichbar, aber ALLE Routen fehlgeschlagen (HTTP 503, {dauer:.1f}s):")
            try:
                fehler = json.loads(roh).get("error", {})
                for d in (fehler.get("details") or [])[:6]:
                    print(f"   - {str(d)[:100]}")
            except ValueError:
                print(f"   {roh[:160]}")
            print()
            print("❌ Remote-Check fehlgeschlagen: Kein LLM erreichbar (Router selbst ist OK).")
            return 1
        print(f"❌ Router erreichbar, aber Test-Call abgelehnt: HTTP {e.code} ({dauer:.1f}s)")
        if roh:
            print(f"   {roh[:160].strip()}")
        if e.code in (401, 403):
            print("   → Der Bahnhof verlangt offenbar einen Client-Token (Router selbst ist aber OK).")
        print()
        print("❌ Remote-Check fehlgeschlagen: Test-Call ohne Token nicht möglich.")
        return 1
    except Exception as exc:
        dauer = time.monotonic() - start
        print(f"❌ Test-Call fehlgeschlagen: {type(exc).__name__}: {exc} ({dauer:.1f}s)")
        print()
        print("❌ Remote-Check fehlgeschlagen.")
        return 1


def main() -> int:
    pfad = ".env"
    ziel_host_raw = None
    ziel_port = None
    remote_url = None
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(__doc__)
            return 0
        if a in ("-V", "--version"):
            print(f"bahnhof-routing-check v{VERSION}")
            return 0
        if a in ("-r", "--remote"):
            i += 1
            if i >= len(argv) or argv[i].startswith("-"):
                print("Fehler: -r/--remote erwartet eine URL wie http://10.7.0.124:8000 "
                      "(oder 10.7.0.124:8000)", file=sys.stderr)
                return 2
            remote_url = argv[i]
        elif a.startswith("--remote="):
            remote_url = a.split("=", 1)[1]
        elif a in ("-i", "--ip"):
            i += 1
            if i >= len(argv) or argv[i].startswith("-"):
                print("Fehler: -i/--ip erwartet eine Angabe wie 10.7.0.124 oder 10.7.0.124:8000", file=sys.stderr)
                return 2
            ziel_host_raw = argv[i]
        elif a.startswith("--ip="):
            ziel_host_raw = a.split("=", 1)[1]
        elif a in ("-p", "--port"):
            i += 1
            if i >= len(argv) or argv[i].startswith("-"):
                print("Fehler: -p/--port erwartet eine Portnummer wie 8000", file=sys.stderr)
                return 2
            ziel_port = argv[i]
        elif a.startswith("--port="):
            ziel_port = a.split("=", 1)[1]
        elif a.startswith("-"):
            print(f"Unbekannte Option: {a} (siehe --help)", file=sys.stderr)
            return 2
        else:
            pfad = a
        i += 1

    # Ziel-Host/Port ermitteln: -i HOST[:PORT] und -p PORT lassen sich kombinieren
    host_opt, port_opt = None, None
    if ziel_host_raw:
        z = ziel_host_raw.strip().rstrip("/")
        if "://" in z:  # komplette URL erlaubt, z. B. http://10.7.0.124:8000
            z = urllib.parse.urlsplit(z).netloc or urllib.parse.urlsplit(z).path
        h, p = _host_port(z)
        host_opt, port_opt = h, p
    if ziel_port is not None:
        port_opt = ziel_port
    if port_opt is not None and (not port_opt.isdigit() or not (1 <= int(port_opt) <= 65535)):
        print(f"Fehler: Ungültiger Port „{port_opt}“ (erwartet 1–65535)", file=sys.stderr)
        return 2

    # Remote-Modus: keine .env nötig
    if remote_url is not None:
        if host_opt:
            print("Fehler: -r/--remote lässt sich nicht mit -i/--ip kombinieren "
                  "(Remote braucht keine .env-Routen).", file=sys.stderr)
            return 2
        return remote_check(remote_url, port_opt)

    routen = routen_lesen(pfad)

    print(f"🔍 Bahnhof-Routing-Check v{VERSION} für {pfad}")
    if host_opt or port_opt:
        for route in routen:
            route["url"] = url_ersetzen(route["url"], host_opt, port_opt)
        teile = [f"Host „{host_opt}“" if host_opt else None,
                 f"Port „{port_opt}“" if port_opt else None]
        print("   ⚡ Alle Routen temporär auf " + " und ".join(t for t in teile if t) + " umgeschrieben (Datei unverändert)")
    print(f"   {len(routen)} aktive Routen (bis zu {MAX_VERSUCHE} Versuchen pro Route)\n")

    ergebnisse = [pruefe_route(route) for route in routen]

    # Tabelle
    breite_url = max(len(r["url"]) for r in routen)
    breite_modell = max(len(r["modell"]) for r in routen)
    breite_url = min(max(breite_url, 12), 48)
    breite_modell = min(max(breite_modell, 10), 30)

    kopf = (f"{'Route':<9} {'Modell':<{breite_modell}} {'Endpunkt':<{breite_url}} "
            f"{'Erreichbar':<11} {'Test-Call':<10} {'Zeit':<8} Hinweis")
    print(kopf)
    print("-" * min(len(kopf) + 60, 140))

    alle_ok = True
    for e in ergebnisse:
        r = e["route"]
        sym_er = "✅" if e["ok_erreichbar"] else "❌"
        sym_call = "✅" if e["ok_call"] else "❌"
        url_anzeige = r["url"] if len(r["url"]) <= breite_url else r["url"][: breite_url - 3] + "..."
        if not e["ok_call"]:
            alle_ok = False
        print(f"ROUTE_{r['nummer']:02d} {r['modell']:<{breite_modell}} {url_anzeige:<{breite_url}} "
              f"{sym_er:<11} {sym_call:<10} {e['dauer']:<8} {e['detail'][:70]}")
        if not e["ok_erreichbar"]:
            print(f"           {'':<{breite_modell}} {'':<{breite_url}} {'':<11} {'':<10} {'':<8} ↳ {e['hinweis']}")

    print()
    if alle_ok:
        print("✅ Alle aktiven Routen antworten korrekt.")
        return 0
    print("❌ Mindestens eine Route ist fehlgeschlagen – siehe Tabelle oben.")
    return 1


if __name__ == "__main__":
    sys.exit(main())