# Changelog – LLM-Bahnhof 🚂

[DEU] Alle nennenswerten Änderungen am Repo, aufgeschlüsselt nach Komponenten:
`llm_bahnhof.py` (Haupt-Router), `sorter.py` + `check.py` (Bahnhofs-Manager).

[ENG] All notable changes to this repository, per component:
`llm_bahnhof.py` (main router), `sorter.py` + `check.py` (Bahnhofs-Manager).

[DEU] Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung folgt [SemVer](https://semver.org/lang/de/).

[ENG] Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [SemVer](https://semver.org/).

---

## 2026-09-09 – Repo / Struktur

[DEU] Die beiden Verwaltungs-Werkzeuge wurden als `sorter.py` und `check.py`
direkt ins Repo-Root aufgenommen (vorher getrennte Ordner
`env-bahnhof-sorter/` und `bahnhof-routing-check/`). Ihre Bedienung ist im
README unter „8. Bahnhof-Tools / Bahnhofs-Manager“ dokumentiert.

[ENG] The two management tools were added directly to the repo root as
`sorter.py` and `check.py` (previously separate folders `env-bahnhof-sorter/`
and `bahnhof-routing-check/`). Usage is documented in the README under
“8. Bahnhof-Tools / Bahnhofs-Manager”.

---

## `check.py`

### [1.3.1] – 2026-09-09

[DEU] Bugfix (beim ersten echten Remote-Lauf gegen 10.7.0.124 gefunden):
Antwort mit `content: null` bei HTTP 200 (z. B. leere Content-Felder eines
Upstreams) führte zu `AttributeError`. Leere/null-Antworten werden jetzt
sauber behandelt (Anzeige der Rohdaten statt Crash) – der Check endet mit
Exit `0`, sobald der Router eine 200-Antwort liefert.

[ENG] Bugfix (found on the first real remote run against 10.7.0.124): a
`content: null` field in an HTTP 200 response (e.g. empty content fields of an
upstream) caused an `AttributeError`. Empty/null answers are now handled
cleanly (raw data is shown instead of a crash) – the check exits `0` as soon
as the router delivers a 200 response.

### [1.3.0] – 2026-09-09

[DEU]
- **Neu:** `-r URL[:PORT]` / `--remote` – Remote-Check eines Bahnhofs **ohne**
  dessen `.env` und **ohne Token**:
  1. Router-Erreichbarkeit (`/health` bzw. Basis-URL),
  2. `/v1/models` → virtuelles Modell (`VIRTUAL_MODEL`),
  3. Test-Call **ohne Token** über `/v1/chat/completions` – der Router nimmt
     den eigenen Upstream-Key aus seiner `.env` und mappt auf die erste
     aktive Route. Exit `0` nur, wenn Router **und** ein LLM antworten.
- Scheitern alle Routen, werden die 503-Details des Routers ausgegeben
  (welche Route welchen Fehler lieferte); kombinierbar mit `-p`.
- Verifiziert gegen einen Mock-Bahnhof: Happy Path, `/v1/models`-Ausfall,
  alle Routen down (503), keine Verbindung – jeweils korrekter Exit-Code,
  kein Traceback.

[ENG]
- **New:** `-r URL[:PORT]` / `--remote` – remote check of a Bahnhof **without**
  its `.env` and **without a token**:
  1. router reachability (`/health` or base URL),
  2. `/v1/models` → virtual model (`VIRTUAL_MODEL`),
  3. test call **without token** via `/v1/chat/completions` – the router uses
     its own upstream key from its `.env` and maps to the first active route.
     Exit `0` only if the router **and** an LLM answer.
- If all routes fail, the router's 503 details are printed (which route
  failed with which error); combinable with `-p`.
- Verified against a mock Bahnhof: happy path, `/v1/models` outage, all
  routes down (503), no connection – each with the correct exit code, no
  traceback.

### [1.2.0] – 2026-09-09

[DEU]
- **Neu:** `-p PORT` / `--port PORT` – ersetzt den Port aller Routen-URLs nur
  für diesen Lauf; einzeln oder zusammen mit `-i` nutzbar.
- `-i` akzeptiert weiterhin `HOST:PORT` oder eine komplette URL
  (`http://host:port`). Wird nur der Host ersetzt, bleibt der Port der Route
  erhalten – und umgekehrt.
- Port-Validierung (1–65535), sonst Exit-Code 2.

[ENG]
- **New:** `-p PORT` / `--port PORT` – replaces the port of all route URLs for
  this run only; usable alone or combined with `-i`.
- `-i` still accepts `HOST:PORT` or a full URL (`http://host:port`). If only
  the host is replaced, each route keeps its port – and vice versa.
- Port validation (1–65535), otherwise exit code 2.

### [1.1.0] – 2026-09-09

[DEU]
- **Neu:** `-i HOST[:PORT]` / `--ip` – ersetzt den Host aller Routen-URLs nur
  für diesen Lauf (die `.env` bleibt unverändert). Damit lässt sich dieselbe
  Routenliste gegen beliebige Bahnhofs-Instanzen prüfen („mehrere Bahnhöfe
  überwachen“).

[ENG]
- **New:** `-i HOST[:PORT]` / `--ip` – replaces the host of all route URLs for
  this run only (the `.env` is left untouched), so the same route list can be
  checked against any Bahnhof instance (“monitor several Bahnhöfe”).

### [1.0.1] – 2026-09-09

[DEU]
- **Robustheit:** Der Check endet nie mehr mit einem Python-Traceback –
  zusätzlich abgefangen: `http.client`-Fehler (z. B. `IncompleteRead`,
  `BadStatusLine`), HTTP-200-Antworten ohne JSON, ungültige URLs u. a.
- **Automatische Wiederholung:** Schlägt eine Route fehl (Timeout, Warm-up,
  Verbindungsabbruch), wird sie einmal automatisch wiederholt, bevor sie als
  fehlgeschlagen gilt.
- Ausführlichere Fehlermeldungen (Fehlertyp + Grund).

[ENG]
- **Robustness:** The check never ends with a Python traceback again –
  additionally caught: `http.client` errors (e.g. `IncompleteRead`,
  `BadStatusLine`), HTTP 200 responses without JSON, invalid URLs, etc.
- **Automatic retry:** If a route fails (timeout, warm-up, dropped connection)
  it is retried once automatically before being marked as failed.
- More detailed error messages (error type + reason).

### [1.0.0] – 2026-09-09

[DEU]
- **Neu:** Prüft alle aktiven Routen einer Bahnhof-`.env`:
  1. **Erreichbarkeit** – Verbindung zur Basis-URL (zuerst `/health`, kurzer
     Timeout; 4xx/5xx zählt als erreichbar, da die Verbindung steht).
  2. **Test-Call** – minimale Chat-Completion über `/chat/completions`
     (Latenz + Antwort/Fehlerdetail).
- Exit-Codes: `0` = alle OK, `1` = mindestens eine Route fehlgeschlagen,
  `2` = Datei-/Aufruffehler.
- Per-Route-Timeout (`30`, `90s`, `15m`, `2h`), Fallback `DEFAULT_TIMEOUT`.
- `--version` / `-V`.

[ENG]
- **New:** Checks all active routes of a Bahnhof `.env`:
  1. **Reachability** – connection to the base URL (first `/health`, short
     timeout; 4xx/5xx counts as reachable since the connection stands).
  2. **Test call** – minimal chat completion via `/chat/completions`
     (latency + response/error detail).
- Exit codes: `0` = all OK, `1` = at least one route failed,
  `2` = file/usage error.
- Per-route timeout (`30`, `90s`, `15m`, `2h`), fallback `DEFAULT_TIMEOUT`.
- `--version` / `-V`.

---

## `sorter.py`

### [1.0.0] – 2026-09-09

[DEU]
- **Neu:** Interaktives ncurses-Tool zum Anordnen der Routen einer
  Bahnhof-`.env` (Reihenfolge = Priorität).
- Greifen/Verschieben (`Enter`/`g`, dann `↑`/`↓`), deaktivieren/aktivieren
  (`d`/Leertaste setzt bzw. entfernt `#`), Speichern mit Neunummerierung
  (`ROUTE_01..N`), `--dump` für Vorschau ohne TUI.
- Anzeige spiegelt die Datei wider: `[ ]` = aktiv, `[#]` = deaktiviert.
- Kommentare direkt über einer Route wandern beim Verschieben mit
  (Erklärungszeile ist als Pre-Kommentar an `ROUTE_01` verankert).
- `--version` / `-V`.

[ENG]
- **New:** Interactive ncurses tool to reorder the routes of a Bahnhof `.env`
  (order = priority).
- Grab/move (`Enter`/`g`, then `↑`/`↓`), deactivate/reactivate (`d`/Space sets
  or removes `#`), save with renumbering (`ROUTE_01..N`), `--dump` for a
  preview without the TUI.
- Display mirrors the file: `[ ]` = active, `[#]` = deactivated.
- Comments directly above a route move along with it (the explanation line is
  anchored as a pre-comment of `ROUTE_01`).
- `--version` / `-V`.

---

## `llm_bahnhof.py` (Haupt-Router)

### [1.0.0] – 2026-08-29

[DEU] Erster stabiler Release. Behebt die sechs Fehler aus v0.1.0/v0.2.0, die
den Betrieb verhinderten (u. a. nie geladene Pipe-Format-Konfiguration,
fehlender `/chat/completions`-Suffix, Streaming nur mit erstem Chunk, harter
30-s-Timeout, fehlender `/v1/models`-Endpunkt, 503 ohne Diagnose). Details
siehe README „10. Änderungen in v1.0.0“.

[ENG] First stable release. Fixes the six bugs from v0.1.0/v0.2.0 that
prevented operation (incl. never-loaded pipe-format configuration, missing
`/chat/completions` suffix, streaming only delivering the first chunk, hard
30 s timeout, missing `/v1/models` endpoint, 503 without diagnostics). Details
in the README “10. Changes in v1.0.0”.
