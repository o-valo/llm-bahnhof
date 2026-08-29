# LLM-Bahnhof 🚂 (v1.0.0)

[DEU] **LLM-Bahnhof** ist ein schlanker, robuster, OpenAI-kompatibler Modell-Router und Fallback-Proxy für lokale und hybride KI-Infrastrukturen. Er fungiert als zentrale Weiche (*Bahnhof*) für deine LLM-Anfragen, leitet intelligent um und springt automatisch auf alternative Gleise (Modelle/Provider), wenn ein Endpunkt ausfällt.

[ENG] **LLM-Bahnhof** is a lightweight, robust, OpenAI-compatible model router and fallback proxy designed for local and hybrid LLM infrastructures. It acts as a central switching station (*Bahnhof*) for your AI requests, intelligently routing prompts and falling back to alternative endpoints if primary models fail.

Automatischer Fallback-Loop über beliebig viele Provider (ROUTE_01, ROUTE_02, ...), virtuelles Dummy-Modell (`/v1/models`), Modell-Mapping und flexible Timeouts.

**Version 1.0.0 ist der erste stabile Release — mit behobenen Bugs aus v0.2.0, die in v0.1.0 den Betrieb verhinderten. Details siehe [Änderungen in v1.0.0](#9-änderungen-in-v100).**

## 0. Features

- **OpenAI-kompatible API:** Drop-in-Ersatz für jeden OpenAI-Client (`openai`-SDK, `aider`, `Continue`, …).
- **Smart Routing & Fallback:** Anfragen je nach Modellvorlieben routen (Modell-Mapping), mit automatischem Fallback auf die nächste Route bei Fehlern.
- **Lokal & Hybrid:** Kombiniert lokale Ollama-Knoten und externe API-Provider (z. B. OpenAI, Hetzner, Groq, OpenRouter) in einem Endpunkt.
- **Leichtgewichtig & schnell:** Reines Python ohne schwergewichtige Abhängigkeiten.
- **Streaming:** Ungepuffertes SSE-Streaming inkl. Erkennung von HTML/Cloudflare-Fehlerseiten auch im Stream.
- **Diagnose:** `/health`-Endpunkt zeigt geladene Routen, Modelle und Timeouts.


## 1. Installation (via venv)

Erstelle das Virtual Environment und installiere die benötigten Abhängigkeiten:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Konfiguration (.env)

Kopiere `.env.example` nach `.env` und trage dort deine Routen ein:

```bash
cp .env.example .env
```

Das Schema einer Route:

| Feld     | Bedeutung                                                        |
|----------|------------------------------------------------------------------|
| URL      | **Basis-URL** des Providers. Der Router hängt automatisch `/chat/completions` an (z. B. `https://api.openai.com/v1` → `https://api.openai.com/v1/chat/completions`). |
| API-Key  | Schlüssel für den Provider. `none` oder leer = kein Authorization-Header (z. B. lokale Ollama-Instanzen); der eingehende Client-Key wird dann durchgereicht. `Bearer ...` wird akzeptiert, fehlendes `Bearer ` wird ergänzt. |
| Modell   | Ziel-Modell, das statt des virtuellen Dummy-Modells an den Provider geschickt wird (Modell-Mapping). |
| Timeout  | `30`, `90s`, `15m`, `2h` oder `0` (= kein Timeout). Leer/ungültig → `DEFAULT_TIMEOUT`. |

**Wichtig zum Timeout bei langsamem Modell-Start (Offloading):** Das Timeout gilt pro Socket-Lesevorgang, nicht für die Gesamtantwortzeit. Wenn ein Modell erst in den Speicher geladen/offloadet werden muss, können vor der ersten Antwort Minuten vergehen (v. a. bei Non-Streaming, wo Ollama erst nach kompletter Generierung sendet). Setze daher großzügige Timeouts (z. B. `10m`–`15m`) oder `0` (= kein Timeout) für lokale Ollama-Routen. Der Standard `DEFAULT_TIMEOUT=15m` in der `.env` ist entsprechend gewählt.

**Reihenfolge = Fallback-Reihenfolge:** ROUTE_01 wird zuerst probiert, dann ROUTE_02 usw. Bei Fehlern springt der Router automatisch zur nächsten Route.

### Optionale Einstellungen

| Variable          | Standard | Bedeutung                                              |
|-------------------|----------|--------------------------------------------------------|
| `ROUTER_HOST`     | `0.0.0.0`| Bind-Adresse                                           |
| `ROUTER_PORT`     | `8000`   | Port                                                   |
| `ROUTER_MAX_PASSES` | `1`    | Wie oft alle Routen bei Fehlern komplett durchlaufen werden (Schutz gegen transiente Fehler) |
| `ROUTER_CORS`     | `1`      | Permissive CORS-Header für Browser-Tools (`0` = aus)   |
| `DOTENV_PATH`     | `.env`   | Alternativer Pfad zur .env-Datei (für Tests)           |

## 3. Starten des Routers

```bash
source venv/bin/activate
python llm_bahnhof.py
```

Der Router lauscht standardmäßig auf http://0.0.0.0:8000 (Adresse/Port über `ROUTER_HOST`/`ROUTER_PORT` änderbar).

## 4. Verwendung mit dem OpenAI-Python-SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"  # Lokaler Proxy
)

response = client.chat.completions.create(
    model="llm-bahnhof",  # dein VIRTUAL_MODEL; wird pro Route aufs Ziel-Modell gemappt
    messages=[{"role": "user", "content": "Hallo vom Gleis 1!"}],
    stream=True,
)

for chunk in response:
    print(chunk.choices[0].delta.content or "", end="")
```

Da LLM-Bahnhof OpenAI-kompatibel ist, funktioniert jedes OpenAI-SDK bzw. jedes Tool mit `base_url`-Support (openai, aider, Continue, Open WebUI, …).

## 5. Endpunkte

| Endpunkt                         | Beschreibung                                              |
|----------------------------------|-----------------------------------------------------------|
| `GET /v1/models`                 | Liefert das virtuelle Dummy-Modell (OpenAI-kompatibel)    |
| `POST /v1/chat/completions`      | Proxy mit Fallback-Loop (OpenAI-Format, inkl. Streaming)  |
| `POST /api/v1/chat/completions`  | Alias für Kompatibilität                                  |
| `GET /health`                    | Status, geladene Routen und Timeouts (Diagnose)           |

## 6. Verwendung in Coding-Tools / Software

Trage in deiner Software (z. B. Aider oder anderen Tools) folgendes ein:

- **Base URL:** `http://localhost:8000/v1`
- **API Key:** anything (wird vom Router durchgereicht oder durch den Routen-Key ersetzt)
- **Modell:** `llm-bahnhof` (bzw. dein `VIRTUAL_MODEL`) — das virtuelle Dummy-Modell

Streaming wird unterstützt: Der Router leitet SSE-Antworten ungepuffert durch und erkennt HTML/Cloudflare-Fehlerseiten auch im Stream.

## 7. Cloud-Endpunkte (OpenAI-kompatible APIs)

Cloud-APIs wie OpenAI, Hetzner AI, Groq, OpenRouter, Mistral usw. funktionieren, da sie das OpenAI-Format (`/v1/chat/completions` + Bearer-Key) sprechen — genau dafür ist der Router gebaut. Beispiel:

```
ROUTE_05=https://api.openai.com/v1|sk-dein-openai-key|gpt-4o|45s
```

Der API-Key kann mit oder ohne `Bearer `-Präfix angegeben werden (der Router ergänzt ihn). **Wichtig:** Der Modellname muss die **Provider-Modell-ID** sein (z. B. `gpt-4o`, `Qwen3.8-27B`).

Verifiziert durch Test 7 der Testsuite (Cloud-Simulation mit API-Key-Pflicht: falscher Key → 401 → automatischer Fallback zur Route mit korrektem Key).

### Bekannte Grenzen / worauf du achten solltest

- **Nur OpenAI-kompatibel.** Anthropics native API (`/v1/messages`) funktioniert nicht direkt (anderes Format/Headers) — dafür bräuchte es einen Adapter.
- **HTTPS:** Zertifikate werden geprüft (Standard). Selbstsignierte Zertifikate würden fehlschlagen.
- **Rate-Limits (429):** Die Route wird übersprungen und die nächste probiert (kein automatischer Retry). Bei transienten Fehlern hilft `ROUTER_MAX_PASSES=2` oder höher.
- **Kosten:** Bei Ausfall lokaler Routen kann der Router automatisch auf Cloud-Routen ausweichen — bewusst so konfigurierbar, aber kostenrelevant.
- Timeouts: Für Cloud-APIs reichen meist 30–60s; bei langsamen Modellen großzügiger wählen.

## 8. Tests

Die Tests laufen **ohne echte API-Keys** und verwenden lokale Mock-Provider (funktionierend, kaputt, HTML-Fehlerseite, Stream, langsam):

```bash
source venv/bin/activate
python tests/test_router.py
```

Geprüft werden u. a.: `/v1/models`, Fallback-Loop (Timeout → HTTP 500 → HTML → guter Provider), ungepuffertes SSE-Streaming, sauberer 503 mit Fehlerdetails sowie die Durchreichung des API-Keys. Logs der Testläufe landen in `tests/*.log`.

## 9. Änderungen in v1.0.0

**v1.0.0 ist der erste stabile Release** (Stand: 29.08.2026). Die Änderungen gegenüber v0.1.0:

### Behobene Fehler (Debugging)

1. **Konfiguration wurde nie geladen (Hauptfehler).** Der Code las getrennte Variablen wie `ROUTE_01_URL`, `ROUTE_01_MODEL`, `ROUTE_01_KEY` — die `.env` definiert aber das dokumentierte Pipe-Format `ROUTE_01=URL|Key|Modell|Timeout`. Dadurch fielen alle Routen auf Platzhalter-URLs (`.example`) zurück und wurden übersprungen → der Router antwortete immer mit 503.
   - **Fix:** `load_routes()` parst jetzt das Pipe-Format, sortiert nach Nummer (ROUTE_01 zuerst) und überspringt nur wirklich ungültige/Platzhalter-URLs.
2. **Basis-URL wurde nicht um `/chat/completions` ergänzt.** Der Router rief die konfigurierte Basis-URL direkt auf (404 beim Provider). Jetzt hängt `normalize_url()` den Endpunkt automatisch an.
3. **Streaming lieferte nur den ersten Chunk.** Durch `next(iter_content(...))` plus einen *neuen* `iter_content()`-Iterator gingen nach dem ersten Chunk alle weiteren verloren (urllib3-Chunked-Verhalten). Der Stream wurde außerdem über `response.text` komplett gepuffert.
   - **Fix:** Ein einziger Iterator wird weiterverwendet; der erste Chunk wird nur kurz geprüft (HTML/Cloudflare-Erkennung) und dann ungepuffert durchgereicht. `X-Accel-Buffering: no` verhindert Zwischenpufferung.
4. **Timeout war hart auf 30 s codiert.** Jetzt gilt das Timeout pro Route (Format `30`, `90s`, `15m`, `0` = kein Timeout), Fallback auf `DEFAULT_TIMEOUT`.
5. **Kein `/v1/models`-Endpunkt, kein virtuelles Modell.** Das im README versprochene Dummy-Modell (`VIRTUAL_MODEL`) wurde ignoriert.
   - **Fix:** `GET /v1/models` (und Alias) liefert das virtuelle Modell; beim Proxy wird das Client-Modell pro Route auf das Ziel-Modell gemappt.
6. **Unbrauchbare 503-Antwort ohne Diagnose.** Jetzt enthält der Fehler `routes_tried` und `details` (welcher Provider welchen Fehler lieferte).

### Neue Funktionen

- `GET /health` für Status und Konfigurations-Diagnose.
- `ROUTER_MAX_PASSES` für wiederholte Durchläufe über alle Routen.
- `ROUTER_CORS` (Standard an) für Browser-basierte Tools.
- API-Key-Handling: Route-Key gewinnt; ohne eigenen Key wird der Client-Key durchgereicht; `none` = kein Authorization-Header.
- Automatische Tests mit lokalen Mock-Providern (`tests/`).

### Konfigurations-Fix in `.env`

- Tippfehler korrigiert: `https://10.7.0.93:/11434/v1` (leerer Port) → `http://10.7.0.93:11434/v1`.
- Modellnamen korrigiert: `qwen3:8b` existierte auf 10.7.0.79 nicht (Ollama: „model not found“ → die Route schlug immer fehl). Für die Tests wurden schnelle, hardwaregerechte Modelle gesetzt: ROUTE_01 → `granite4.1:8b` (10.7.0.79), ROUTE_02 → `granite4.1:8b` (10.7.0.93) – 8B-Modelle laufen auf der RTX 5060 problemlos und liefern Antworten ohne Reasoning-`<think>`-Präfix.
- ROUTE_03 ergänzt: `qwen3.5-9b-babel-brief:latest` (10.7.0.24, Timeout 30m) als weiterer Fallback-Provider – Modell läuft dort dauerhaft, generiert aber langsam (großzügiges Timeout gesetzt).
- ROUTE_04 ergänzt: `qwen2.5:3b` (10.7.0.81, Timeout 15m) – Host mit sehr kleinen Modellen, primär für Tests gedacht.

### Verifikation gegen echte Provider (End-to-End)

Der Router wurde mit den echten Ollama-Instanzen unter 10.7.0.79 und 10.7.0.93 getestet (WireGuard):

- `GET /v1/models` → liefert `llm-bahnhof`.
- Non-Streaming: Client sendet `llm-bahnhof` → Router mappt auf `phi4-mini-reasoning:3.8b`, Antwort in ~2 s (HTTP 200).
- Streaming: SSE-Chunks kommen ungepuffert live durch (HTTP 200, `text/event-stream`).
- Fallback real belegt: ROUTE_01 mit nicht existierendem Modell (404) → Router springt automatisch auf ROUTE_02 (200).
- `GET /health` zeigt Konfiguration (Routen, Modelle, Timeouts).

### Testumgebung

- `tests/mock_provider.py` — steuerbarer Mock-Provider (`MOCK_MODE=ok|stream|fail500|html|slow`).
- `tests/test_router.py` — vollautomatische Testsuite (siehe [Abschnitt 8](#8-tests)).

## 10. Lizenz

**LLM-Bahnhof** ist unter der [MIT-Lizenz](LICENSE) veröffentlicht.
Du darfst den Code frei verwenden, modifizieren und verteilen.

**Autor:** Olav Surawski — [github.com/o-valo/llm-bahnhof](https://github.com/o-valo/llm-bahnhof/)

---

_🤖 **Powered by AI** – Die Erstellung dieses Projekts wurde durch KI-Unterstützung begleitet._
_Zum Glück von einem Menschen geprüft und veröffentlicht._ 😉

