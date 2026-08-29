# LLM-Bahnhof 🚂 (v1.0.0)

[DEU] **LLM-Bahnhof** ist ein schlanker, robuster, OpenAI-kompatibler Modell-Router und Fallback-Proxy für lokale und hybride KI-Infrastrukturen. Er fungiert als zentrale Weiche (*Bahnhof*) für deine LLM-Anfragen, leitet intelligent um und springt automatisch auf alternative Gleise (Modelle/Provider), wenn ein Endpunkt ausfällt.

[ENG] **LLM-Bahnhof** is a lightweight, robust, OpenAI-compatible model router and fallback proxy designed for local and hybrid LLM infrastructures. It acts as a central switching station (*Bahnhof*) for your AI requests, intelligently routing prompts and falling back to alternative endpoints if primary models fail.

[DEU] Automatischer Fallback-Loop über beliebig viele Provider (ROUTE_01, ROUTE_02, ...), virtuelles Dummy-Modell (`/v1/models`), Modell-Mapping und flexible Timeouts.

[ENG] Automatic fallback loop across any number of providers (ROUTE_01, ROUTE_02, ...), virtual dummy model (`/v1/models`), model mapping and flexible timeouts.

[DEU] **Version 1.0.0 ist der erste stabile Release** — mit behobenen Bugs aus v0.2.0, die in v0.1.0 den Betrieb verhinderten. Details siehe [Änderungen in v1.0.0](#9-änderungen-in-v100).

[ENG] **Version 1.0.0 is the first stable release** — fixing bugs from v0.2.0 that prevented v0.1.0 from working. Details in [Changes in v1.0.0](#9-änderungen-in-v100).

---

## 0. Features

[DEU]
- **OpenAI-kompatible API:** Drop-in-Ersatz für jeden OpenAI-Client (`openai`-SDK, `aider`, `Continue`, …).
- **Smart Routing & Fallback:** Anfragen je nach Modellvorlieben routen (Modell-Mapping), mit automatischem Fallback auf die nächste Route bei Fehlern.
- **Lokal & Hybrid:** Kombiniert lokale Ollama-Knoten und externe API-Provider (z. B. OpenAI, Hetzner, Groq, OpenRouter) in einem Endpunkt.
- **Leichtgewichtig & schnell:** Reines Python ohne schwergewichtige Abhängigkeiten.
- **Streaming:** Ungepuffertes SSE-Streaming inkl. Erkennung von HTML/Cloudflare-Fehlerseiten auch im Stream.
- **Diagnose:** `/health`-Endpunkt zeigt geladene Routen, Modelle und Timeouts.

[ENG]
- **OpenAI-compatible API:** Drop-in replacement for any OpenAI client (`openai` SDK, `aider`, `Continue`, …).
- **Smart Routing & Fallback:** Route requests by model preference (model mapping), with automatic fallback to the next route on errors.
- **Local & Hybrid:** Combines local Ollama nodes and external API providers (e.g. OpenAI, Hetzner, Groq, OpenRouter) in a single endpoint.
- **Lightweight & fast:** Pure Python without heavy dependencies.
- **Streaming:** Unbuffered SSE streaming, including detection of HTML/Cloudflare error pages even in the stream.
- **Diagnostics:** `/health` endpoint shows loaded routes, models and timeouts.

---

## 1. Installation (via venv)

[DEU] Erstelle das Virtual Environment und installiere die benötigten Abhängigkeiten:

[ENG] Create the virtual environment and install the required dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 2. Konfiguration / Configuration (.env)

[DEU] Kopiere `.env.example` nach `.env` und trage dort deine Routen ein:

[ENG] Copy `.env.example` to `.env` and enter your routes:

```bash
cp .env.example .env
```

[DEU] Das Schema einer Route:

[ENG] The schema of a route:

| Field    | Meaning                                                          |
|----------|------------------------------------------------------------------|
| URL      | **Base URL** of the provider. The router automatically appends `/chat/completions` (e.g. `https://api.openai.com/v1` → `https://api.openai.com/v1/chat/completions`). |
| API key  | Key for the provider. `none` or empty = no Authorization header (e.g. local Ollama instances); the incoming client key is then passed through. `Bearer ...` is accepted, a missing `Bearer ` prefix is added. |
| Model    | Target model that is sent to the provider instead of the virtual dummy model (model mapping). |
| Timeout  | `30`, `90s`, `15m`, `2h` or `0` (= no timeout). Empty/invalid → `DEFAULT_TIMEOUT`. |

[DEU] **Wichtig zum Timeout bei langsamem Modell-Start (Offloading):** Das Timeout gilt pro Socket-Lesevorgang, nicht für die Gesamtantwortzeit. Wenn ein Modell erst in den Speicher geladen/offloadet werden muss, können vor der ersten Antwort Minuten vergehen (v. a. bei Non-Streaming, wo Ollama erst nach kompletter Generierung sendet). Setze daher großzügige Timeouts (z. B. `10m`–`15m`) oder `0` (= kein Timeout) für lokale Ollama-Routen. Der Standard `DEFAULT_TIMEOUT=15m` in der `.env` ist entsprechend gewählt.

[ENG] **Important about timeouts with slow model startup (offloading):** The timeout applies per socket read operation, not to the total response time. If a model first has to be loaded/offloaded into memory, minutes can pass before the first answer arrives (especially with non-streaming, where Ollama only sends after complete generation). Therefore use generous timeouts (e.g. `10m`–`15m`) or `0` (= no timeout) for local Ollama routes. The default `DEFAULT_TIMEOUT=15m` in `.env` is chosen accordingly.

[DEU] **Reihenfolge = Fallback-Reihenfolge:** ROUTE_01 wird zuerst probiert, dann ROUTE_02 usw. Bei Fehlern springt der Router automatisch zur nächsten Route.

[ENG] **Order = fallback order:** ROUTE_01 is tried first, then ROUTE_02, etc. On errors the router automatically switches to the next route.

### Optionale Einstellungen / Optional settings

[DEU]

| Variable          | Default | Meaning                                                       |
|-------------------|---------|---------------------------------------------------------------|
| `ROUTER_HOST`     | `0.0.0.0` | Bind address                                               |
| `ROUTER_PORT`     | `8000`  | Port                                                          |
| `ROUTER_MAX_PASSES` | `1`   | How often all routes are cycled through completely on errors (protection against transient failures) |
| `ROUTER_CORS`     | `1`     | Permissive CORS headers for browser tools (`0` = off)         |
| `DOTENV_PATH`     | `.env`  | Alternative path to the .env file (for tests)                 |

[ENG]

| Variable          | Default | Meaning                                                       |
|-------------------|---------|---------------------------------------------------------------|
| `ROUTER_HOST`     | `0.0.0.0` | Bind address                                               |
| `ROUTER_PORT`     | `8000`  | Port                                                          |
| `ROUTER_MAX_PASSES` | `1`   | How often all routes are cycled through completely on errors (protection against transient failures) |
| `ROUTER_CORS`     | `1`     | Permissive CORS headers for browser tools (`0` = off)         |
| `DOTENV_PATH`     | `.env`  | Alternative path to the .env file (for tests)                 |

---

## 3. Starten des Routers / Starting the router

```bash
source venv/bin/activate
python llm_bahnhof.py
```

[DEU] Der Router lauscht standardmäßig auf http://0.0.0.0:8000 (Adresse/Port über `ROUTER_HOST`/`ROUTER_PORT` änderbar).

[ENG] By default the router listens on http://0.0.0.0:8000 (address/port configurable via `ROUTER_HOST`/`ROUTER_PORT`).

---

## 4. Verwendung mit dem OpenAI-Python-SDK / Usage with the OpenAI Python SDK

[DEU] Beispiel:

[ENG] Example:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"  # Local proxy / Lokaler Proxy
)

response = client.chat.completions.create(
    model="llm-bahnhof",  # your VIRTUAL_MODEL; mapped per route to the target model
    messages=[{"role": "user", "content": "Hallo vom Gleis 1!"}],
    stream=True,
)

for chunk in response:
    print(chunk.choices[0].delta.content or "", end="")
```

[DEU] Da LLM-Bahnhof OpenAI-kompatibel ist, funktioniert jedes OpenAI-SDK bzw. jedes Tool mit `base_url`-Support (openai, aider, Continue, Open WebUI, …).

[ENG] Since LLM-Bahnhof is OpenAI-compatible, any OpenAI SDK or tool with `base_url` support works (openai, aider, Continue, Open WebUI, …).

---

## 5. Endpunkte / Endpoints

[DEU]

| Endpunkt                         | Beschreibung                                              |
|----------------------------------|-----------------------------------------------------------|
| `GET /v1/models`                 | Liefert das virtuelle Dummy-Modell (OpenAI-kompatibel)    |
| `POST /v1/chat/completions`      | Proxy mit Fallback-Loop (OpenAI-Format, inkl. Streaming)  |
| `POST /api/v1/chat/completions`  | Alias für Kompatibilität                                  |
| `GET /health`                    | Status, geladene Routen und Timeouts (Diagnose)           |

[ENG]

| Endpoint                         | Description                                                |
|----------------------------------|------------------------------------------------------------|
| `GET /v1/models`                 | Returns the virtual dummy model (OpenAI-compatible)       |
| `POST /v1/chat/completions`      | Proxy with fallback loop (OpenAI format, incl. streaming) |
| `POST /api/v1/chat/completions`  | Alias for compatibility                                    |
| `GET /health`                    | Status, loaded routes and timeouts (diagnostics)           |

---

## 6. Verwendung in Coding-Tools / Usage in coding tools

[DEU] Trage in deiner Software (z. B. Aider oder anderen Tools) folgendes ein:

[ENG] Enter the following in your software (e.g. Aider or other tools):

- **Base URL:** `http://localhost:8000/v1`
- **API Key:** anything (passed through by the router or replaced by the route key)
- **Model:** `llm-bahnhof` (or your `VIRTUAL_MODEL`) — the virtual dummy model

[DEU] Streaming wird unterstützt: Der Router leitet SSE-Antworten ungepuffert durch und erkennt HTML/Cloudflare-Fehlerseiten auch im Stream.

[ENG] Streaming is supported: the router passes SSE responses through unbuffered and detects HTML/Cloudflare error pages even in the stream.

---

## 7. Cloud-Endpunkte / Cloud endpoints (OpenAI-compatible APIs)

[DEU] Cloud-APIs wie OpenAI, Hetzner AI, Groq, OpenRouter, Mistral usw. funktionieren, da sie das OpenAI-Format (`/v1/chat/completions` + Bearer-Key) sprechen — genau dafür ist der Router gebaut. Beispiel:

[ENG] Cloud APIs such as OpenAI, Hetzner AI, Groq, OpenRouter, Mistral etc. work because they speak the OpenAI format (`/v1/chat/completions` + Bearer key) — that's exactly what the router is built for. Example:

```
ROUTE_05=https://api.openai.com/v1|sk-your-openai-key|gpt-4o|45s
```

[DEU] Der API-Key kann mit oder ohne `Bearer `-Präfix angegeben werden (der Router ergänzt ihn). **Wichtig:** Der Modellname muss die **Provider-Modell-ID** sein (z. B. `gpt-4o`, `Qwen3.8-27B`).

[ENG] The API key can be given with or without the `Bearer ` prefix (the router adds it). **Important:** the model name must be the **provider model ID** (e.g. `gpt-4o`, `Qwen3.8-27B`).

[DEU] Verifiziert durch Test 7 der Testsuite (Cloud-Simulation mit API-Key-Pflicht: falscher Key → 401 → automatischer Fallback zur Route mit korrektem Key).

[ENG] Verified by test 7 of the test suite (cloud simulation with mandatory API key: wrong key → 401 → automatic fallback to the route with the correct key).

### Bekannte Grenzen / Known limitations

[DEU]
- **Nur OpenAI-kompatibel.** Anthropics native API (`/v1/messages`) funktioniert nicht direkt (anderes Format/Headers) — dafür bräuchte es einen Adapter.
- **HTTPS:** Zertifikate werden geprüft (Standard). Selbstsignierte Zertifikate würden fehlschlagen.
- **Rate-Limits (429):** Die Route wird übersprungen und die nächste probiert (kein automatischer Retry). Bei transienten Fehlern hilft `ROUTER_MAX_PASSES=2` oder höher.
- **Kosten:** Bei Ausfall lokaler Routen kann der Router automatisch auf Cloud-Routen ausweichen — bewusst so konfigurierbar, aber kostenrelevant.
- Timeouts: Für Cloud-APIs reichen meist 30–60s; bei langsamen Modellen großzügiger wählen.

[ENG]
- **OpenAI-compatible only.** Anthropic's native API (`/v1/messages`) does not work directly (different format/headers) — it would require an adapter.
- **HTTPS:** Certificates are verified (default). Self-signed certificates would fail.
- **Rate limits (429):** The route is skipped and the next one is tried (no automatic retry). For transient failures `ROUTER_MAX_PASSES=2` or higher helps.
- **Costs:** If local routes fail, the router may automatically fall back to cloud routes — intentionally configurable, but cost-relevant.
- Timeouts: 30–60s usually suffice for cloud APIs; choose more generous values for slow models.

---

## 8. Tests

[DEU] Die Tests laufen **ohne echte API-Keys** und verwenden lokale Mock-Provider (funktionierend, kaputt, HTML-Fehlerseite, Stream, langsam):

[ENG] The tests run **without real API keys** and use local mock providers (working, broken, HTML error page, stream, slow):

```bash
source venv/bin/activate
python tests/test_router.py
```

[DEU] Geprüft werden u. a.: `/v1/models`, Fallback-Loop (Timeout → HTTP 500 → HTML → guter Provider), ungepuffertes SSE-Streaming, sauberer 503 mit Fehlerdetails sowie die Durchreichung des API-Keys. Logs der Testläufe landen in `tests/*.log`.

[ENG] Checked among others: `/v1/models`, fallback loop (timeout → HTTP 500 → HTML → good provider), unbuffered SSE streaming, clean 503 with error details, and API key pass-through. Test logs go to `tests/*.log`.

---

## 9. Änderungen in v1.0.0

[ENG] Changes in v1.0.0

[DEU] **v1.0.0 ist der erste stabile Release** (Stand: 29.08.2026). Die Änderungen gegenüber v0.1.0:

[ENG] **v1.0.0 is the first stable release** (as of 29.08.2026). The changes compared to v0.1.0:

### Behobene Fehler / Fixed bugs (debugging)

[DEU]
1. **Konfiguration wurde nie geladen (Hauptfehler).** Der Code las getrennte Variablen wie `ROUTE_01_URL`, `ROUTE_01_MODEL`, `ROUTE_01_KEY` — die `.env` definiert aber das dokumentierte Pipe-Format `ROUTE_01=URL|Key|Modell|Timeout`. Dadurch fielen alle Routen auf Platzhalter-URLs (`.example`) zurück und wurden übersprungen → der Router antwortete immer mit 503.
   - **Fix:** `load_routes()` parst jetzt das Pipe-Format, sortiert nach Nummer (ROUTE_01 zuerst) und überspringt nur wirklich ungültige/Platzhalter-URLs.
2. **Basis-URL wurde nicht um `/chat/completions` ergänzt.** Der Router rief die konfigurierte Basis-URL direkt auf (404 beim Provider). Jetzt hängt `normalize_url()` den Endpunkt automatisch an.
3. **Streaming lieferte nur den ersten Chunk.** Durch `next(iter_content(...))` plus einen *neuen* `iter_content()`-Iterator gingen nach dem ersten Chunk alle weiteren verloren (urllib3-Chunked-Verhalten). Der Stream wurde außerdem über `response.text` komplett gepuffert.
   - **Fix:** Ein einziger Iterator wird weiterverwendet; der erste Chunk wird nur kurz geprüft (HTML/Cloudflare-Erkennung) und dann ungepuffert durchgereicht. `X-Accel-Buffering: no` verhindert Zwischenpufferung.
4. **Timeout war hart auf 30 s codiert.** Jetzt gilt das Timeout pro Route (Format `30`, `90s`, `15m`, `0` = kein Timeout), Fallback auf `DEFAULT_TIMEOUT`.
5. **Kein `/v1/models`-Endpunkt, kein virtuelles Modell.** Das im README versprochene Dummy-Modell (`VIRTUAL_MODEL`) wurde ignoriert.
   - **Fix:** `GET /v1/models` (und Alias) liefert das virtuelle Modell; beim Proxy wird das Client-Modell pro Route auf das Ziel-Modell gemappt.
6. **Unbrauchbare 503-Antwort ohne Diagnose.** Jetzt enthält der Fehler `routes_tried` und `details` (welcher Provider welchen Fehler lieferte).

[ENG]
1. **Configuration was never loaded (main bug).** The code read separate variables like `ROUTE_01_URL`, `ROUTE_01_MODEL`, `ROUTE_01_KEY` — but `.env` defines the documented pipe format `ROUTE_01=URL|Key|Model|Timeout`. Therefore all routes fell back to placeholder URLs (`.example`) and were skipped → the router always answered with 503.
   - **Fix:** `load_routes()` now parses the pipe format, sorts by number (ROUTE_01 first) and only skips truly invalid/placeholder URLs.
2. **Base URL was not extended with `/chat/completions`.** The router called the configured base URL directly (404 at the provider). Now `normalize_url()` appends the endpoint automatically.
3. **Streaming only delivered the first chunk.** `next(iter_content(...))` plus a *new* `iter_content()` iterator lost all subsequent chunks after the first one (urllib3 chunked behavior). The stream was also fully buffered via `response.text`.
   - **Fix:** A single iterator is reused; the first chunk is only briefly checked (HTML/Cloudflare detection) and then passed through unbuffered. `X-Accel-Buffering: no` prevents intermediate buffering.
4. **Timeout was hardcoded to 30 s.** Now the timeout applies per route (format `30`, `90s`, `15m`, `0` = no timeout), falling back to `DEFAULT_TIMEOUT`.
5. **No `/v1/models` endpoint, no virtual model.** The dummy model promised in the README (`VIRTUAL_MODEL`) was ignored.
   - **Fix:** `GET /v1/models` (and alias) returns the virtual model; in the proxy the client model is mapped per route to the target model.
6. **Useless 503 response without diagnostics.** Now the error contains `routes_tried` and `details` (which provider returned which error).

### Neue Funktionen / New features

[DEU]
- `GET /health` für Status und Konfigurations-Diagnose.
- `ROUTER_MAX_PASSES` für wiederholte Durchläufe über alle Routen.
- `ROUTER_CORS` (Standard an) für Browser-basierte Tools.
- API-Key-Handling: Route-Key gewinnt; ohne eigenen Key wird der Client-Key durchgereicht; `none` = kein Authorization-Header.
- Automatische Tests mit lokalen Mock-Providern (`tests/`).

[ENG]
- `GET /health` for status and configuration diagnostics.
- `ROUTER_MAX_PASSES` for repeated passes over all routes.
- `ROUTER_CORS` (enabled by default) for browser-based tools.
- API key handling: route key wins; without an own key the client key is passed through; `none` = no Authorization header.
- Automated tests with local mock providers (`tests/`).

### Konfigurations-Fix in `.env` / Configuration fix in `.env`

[DEU]
- Tippfehler korrigiert: `https://10.7.0.93:/11434/v1` (leerer Port) → `http://10.7.0.93:11434/v1`.
- Modellnamen korrigiert: `qwen3:8b` existierte auf 10.7.0.79 nicht (Ollama: „model not found“ → die Route schlug immer fehl). Für die Tests wurden schnelle, hardwaregerechte Modelle gesetzt: ROUTE_01 → `granite4.1:8b` (10.7.0.79), ROUTE_02 → `granite4.1:8b` (10.7.0.93) – 8B-Modelle laufen auf der RTX 5060 problemlos und liefern Antworten ohne Reasoning-`<think>`-Präfix.
- ROUTE_03 ergänzt: `qwen3.5-9b-babel-brief:latest` (10.7.0.24, Timeout 30m) als weiterer Fallback-Provider – Modell läuft dort dauerhaft, generiert aber langsam (großzügiges Timeout gesetzt).
- ROUTE_04 ergänzt: `qwen2.5:3b` (10.7.0.81, Timeout 15m) – Host mit sehr kleinen Modellen, primär für Tests gedacht.

[ENG]
- Typo fixed: `https://10.7.0.93:/11434/v1` (empty port) → `http://10.7.0.93:11434/v1`.
- Model names fixed: `qwen3:8b` did not exist on 10.7.0.79 (Ollama: "model not found" → the route always failed). Fast, hardware-appropriate models were set for the tests: ROUTE_01 → `granite4.1:8b` (10.7.0.79), ROUTE_02 → `granite4.1:8b` (10.7.0.93) – 8B models run fine on the RTX 5060 and answer without a reasoning `<think>` prefix.
- ROUTE_03 added: `qwen3.5-9b-babel-brief:latest` (10.7.0.24, timeout 30m) as an additional fallback provider – model runs permanently there, but generates slowly (generous timeout set).
- ROUTE_04 added: `qwen2.5:3b` (10.7.0.81, timeout 15m) – host with very small models, primarily intended for tests.

### Verifikation gegen echte Provider / Verification against real providers (end-to-end)

[DEU] Der Router wurde mit den echten Ollama-Instanzen unter 10.7.0.79 und 10.7.0.93 getestet (WireGuard):

[ENG] The router was tested with the real Ollama instances at 10.7.0.79 and 10.7.0.93 (WireGuard):

[DEU]
- `GET /v1/models` → liefert `llm-bahnhof`.
- Non-Streaming: Client sendet `llm-bahnhof` → Router mappt auf `phi4-mini-reasoning:3.8b`, Antwort in ~2 s (HTTP 200).
- Streaming: SSE-Chunks kommen ungepuffert live durch (HTTP 200, `text/event-stream`).
- Fallback real belegt: ROUTE_01 mit nicht existierendem Modell (404) → Router springt automatisch auf ROUTE_02 (200).
- `GET /health` zeigt Konfiguration (Routen, Modelle, Timeouts).

[ENG]
- `GET /v1/models` → returns `llm-bahnhof`.
- Non-streaming: client sends `llm-bahnhof` → router maps to `phi4-mini-reasoning:3.8b`, answer in ~2 s (HTTP 200).
- Streaming: SSE chunks come through unbuffered live (HTTP 200, `text/event-stream`).
- Fallback proven in practice: ROUTE_01 with non-existent model (404) → router automatically switches to ROUTE_02 (200).
- `GET /health` shows the configuration (routes, models, timeouts).

### Testumgebung / Test environment

[DEU]
- `tests/mock_provider.py` — steuerbarer Mock-Provider (`MOCK_MODE=ok|stream|fail500|html|slow`).
- `tests/test_router.py` — vollautomatische Testsuite (siehe [Abschnitt 8](#8-tests)).

[ENG]
- `tests/mock_provider.py` — controllable mock provider (`MOCK_MODE=ok|stream|fail500|html|slow`).
- `tests/test_router.py` — fully automated test suite (see [Section 8](#8-tests)).

---

## 10. Lizenz / License

[DEU] **LLM-Bahnhof** ist unter der [MIT-Lizenz](LICENSE) veröffentlicht.
Du darfst den Code frei verwenden, modifizieren und verteilen.

[ENG] **LLM-Bahnhof** is published under the [MIT license](LICENSE).
You are free to use, modify and distribute the code.

**Autor / Author:** Olav Surawski — [github.com/o-valo/llm-bahnhof](https://github.com/o-valo/llm-bahnhof/)

---

_🤖 **Powered by AI** – Die Erstellung dieses Projekts wurde durch KI-Unterstützung begleitet. / The creation of this project was accompanied by AI support._
_Zum Glück von einem Menschen geprüft und veröffentlicht. / Fortunately reviewed and published by a human._ 😉
