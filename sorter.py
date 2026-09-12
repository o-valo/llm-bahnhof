#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
env-bahnhof-sorter – Routen einer LLM-Bahnhof-.env interaktiv anordnen.

Tasten:
  ↑ / ↓  oder  k / j   Cursor zwischen Routen bewegen
  Enter  oder  g        Route greifen / loslassen (zum Verschieben)
  ↑ / ↓  im Greif-Modus Route über/unter den Nachbarn verschieben
  d  oder  Leertaste    Route deaktivieren (# davor) / aktivieren (# entfernen)
  s                     Speichern (nummeriert ROUTE_01..N neu)
  q                     Beenden (fragt bei ungespeicherten Änderungen)
  ?                     Hilfe

Aufruf:
  python3 sorter.py [pfad/zur/.env]     (Default: ./.env)

Der sorter arbeitet nur auf der angegebenen Datei. Andere Zeilen
(Kommentare, Header) bleiben erhalten; direkt über einer Route stehende
Kommentare wandern mit der Route mit.

Die Erklärzeile `# ROUTE_XX = URL | Token | Ziel-Modell | Timeout` wird
beim Speichern IMMER direkt über `ROUTE_01` geschrieben – egal wo sie in
der Datei steht oder wie die Routen verschoben wurden.
"""

import curses
import re
import sys

VERSION = "1.1.0"
ROUTE_RE = re.compile(r"^\s*(#\s*)?ROUTE_(\d+)\s*=(.*)$")
# Erklärzeile: `# ROUTE_XX = URL | Token | …` (XX ist keine Zahl, also keine Route)
ERKL_RE = re.compile(r"^\s*#\s*ROUTE_XX\s*=(.*)$")


class Route:
    """Eine ROUTE_XX-Zeile der Bahnhof-.env."""

    def __init__(self, aktiv: bool, nummer: int, wert: str, pre_comments: list[str] | None = None):
        self.aktiv = aktiv            # True = ohne '#', False = auskommentiert
        self.nummer = nummer          # ursprüngliche Nummer (nur Anzeige)
        self.wert = wert.strip()      # alles nach dem ersten '='
        self.pre_comments = pre_comments or []  # direkt darüberstehende Kommentarzeilen

    @property
    def modell(self) -> str:
        """Drittes Feld (Ziel-Modell) aus URL|Token|Modell|Timeout."""
        teile = self.wert.split("|")
        return teile[2].strip() if len(teile) >= 3 else "(unvollständig)"

    def zeile(self, neue_nummer: int) -> str:
        """Zeile fürs Speichern – mit oder ohne '#'-Kommentar."""
        praefix = "" if self.aktiv else "# "
        return f"{praefix}ROUTE_{neue_nummer:02d}={self.wert}"


def parse(text: str) -> list:
    """
    Zerlegt die .env in eine Liste von Einträgen:
      ("text", zeile)            – bleibt an Ort und Stelle
      ("route", Route)           – beweglich, trägt seine Pre-Kommentare mit
    """
    items: list = []
    pending: list[str] = []
    for zeile in text.splitlines():
        m = ROUTE_RE.match(zeile)
        if m:
            route = Route(
                aktiv=(m.group(1) is None),
                nummer=int(m.group(2)),
                wert=m.group(3),
                pre_comments=pending,
            )
            pending = []
            items.append(("route", route))
        elif zeile.strip() == "" or not zeile.lstrip().startswith("#"):
            # Leerzeile / Code: Kommentar-Kette unterbrechen
            for pc in pending:
                items.append(("text", pc))
            pending = []
            items.append(("text", zeile))
        elif ERKL_RE.match(zeile):
            # Erklärzeile „# ROUTE_XX = …“: kein Pre-Kommentar der nächsten
            # Route, sondern Spezial-Eintrag – landet beim Speichern immer
            # direkt über ROUTE_01 (Invariante, siehe speichern()).
            items.append(("erkl", zeile))
        else:
            pending.append(zeile)
    for pc in pending:
        items.append(("text", pc))
    return items


def speichern(pfad: str, items: list) -> None:
    """Schreibt die .env: Text-Einträge unverändert, Routen neu nummeriert.
    Erklärzeilen (# ROUTE_XX = …) werden immer direkt über ROUTE_01 geschrieben."""
    # Erklärzeilen VORAB sammeln – egal an welcher Stelle der Datei sie stehen.
    erkl: list[str] = [val for typ, val in items if typ == "erkl"]
    out: list[str] = []
    laufende_nummer = 0
    erste_route = True
    for typ, val in items:
        if typ == "erkl":
            continue   # wird oben (direkt über ROUTE_01) geschrieben
        if typ == "text":
            out.append(val)
        else:
            if erste_route:
                # Invariante: Erklärzeile IMMER oberhalb von ROUTE_01
                out.extend(erkl)
                erste_route = False
            laufende_nummer += 1
            out.extend(val.pre_comments)
            out.append(val.zeile(laufende_nummer))
    if erste_route:   # keine Route vorhanden → Erklärzeilen am Ende erhalten
        out.extend(erkl)
    with open(pfad, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def routen_index(items: list) -> list[int]:
    """Indizes aller Route-Einträge in der items-Liste."""
    return [i for i, (typ, _) in enumerate(items) if typ == "route"]


def dump(pfad: str) -> None:
    """Nicht-interaktive Ausgabe der Routen-Reihenfolge (für Tests/Doku)."""
    with open(pfad, encoding="utf-8") as f:
        items = parse(f.read())
    print(f"Datei: {pfad}")
    for i, (typ, val) in enumerate(items):
        if typ == "route":
            status = "AKTIV    " if val.aktiv else "INAKTIV  "
            print(f"  {i:3d}  {status} ROUTE_{val.nummer:02d}  {val.modell:<22} {val.wert}")
    anzahl_aktiv = sum(1 for typ, val in items if typ == "route" and val.aktiv)
    print(f"\n{sum(1 for typ, _ in items if typ == 'route')} Routen, davon {anzahl_aktiv} aktiv.")


class Tui:
    """ncurses-Oberfläche."""

    def __init__(self, pfad: str, items: list):
        self.pfad = pfad
        self.items = items
        self.routen_pos = routen_index(items)   # Positionen der Routen in items
        self.cursor = 0                          # Index in routen_pos
        self.grab = -1                           # gegriffene Position in routen_pos, -1 = keiner
        self.dirty = False
        self.hilfe = False
        self.meldung = ""

    def init_curses(self, stdscr) -> None:
        """curses-Grundsetup – muss NACH initscr() laufen (also im run())."""
        stdscr.keypad(True)   # Pfeiltasten als KEY_UP/KEY_DOWN erkennen
        curses.use_default_colors()
        curses.curs_set(0)
        # Farbpaare
        curses.init_pair(1, curses.COLOR_GREEN, -1)      # aktiv
        curses.init_pair(2, curses.COLOR_YELLOW, -1)     # inaktiv
        curses.init_pair(3, curses.COLOR_CYAN, -1)       # gegriffen
        curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Cursor (invertiert)
        self.farben = {
            "aktiv": curses.color_pair(1),
            "inaktiv": curses.color_pair(2) | curses.A_DIM,
            "grab": curses.color_pair(3) | curses.A_BOLD,
            "cursor": curses.color_pair(4),
            "titel": curses.A_BOLD,
        }

    # ---------- Zeichnen ----------
    def zeichnen(self, stdscr) -> None:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        # Titelzeile
        titel = f" env-bahnhof-sorter v{VERSION} – {self.pfad} "
        if self.dirty:
            titel += " [ungespeichert]"
        stdscr.addnstr(0, 0, titel, w - 1, self.farben["titel"])

        # Routenliste
        sichtbar = min(len(self.routen_pos), h - 3)
        start = max(0, min(self.cursor - sichtbar + 1, len(self.routen_pos) - sichtbar))
        for zeile in range(sichtbar):
            pos = self.routen_pos[start + zeile]
            typ, val = self.items[pos]
            ist_cursor = (start + zeile) == self.cursor
            ist_grab = (start + zeile) == self.grab
            # Wie in der Datei: aktiv = ohne '#', deaktiviert = mit '#'
            symbol = "[ ]" if val.aktiv else "[#]"
            ziel = val.modell
            text = f" {symbol}  {ziel:<24} {val.wert}"
            attr = 0
            if ist_grab:
                attr = self.farben["grab"]
            elif ist_cursor:
                attr = self.farben["cursor"]
            elif val.aktiv:
                attr = self.farben["aktiv"]
            else:
                attr = self.farben["inaktiv"]
            stdscr.addnstr(zeile + 1, 0, text[:w - 1], w - 1, attr)

        # Fußzeile
        if self.grab >= 0:
            hilfe_text = "Greifen: ↑/↓ verschieben · Enter = loslassen · s = speichern · q = beenden"
        else:
            hilfe_text = "↑/↓ = Cursor · Enter = greifen · d = aktiv/inaktiv · s = speichern · q = beenden · ? = Hilfe"
        stdscr.addnstr(h - 2, 0, hilfe_text[:w - 1], w - 1, self.farben["inaktiv"])
        meldung = self.meldung[: w - 1]
        stdscr.addnstr(h - 1, 0, meldung, w - 1, self.farben["aktiv"])

        if self.hilfe:
            self.zeichne_hilfe(stdscr, h, w)
        stdscr.refresh()

    def zeichne_hilfe(self, stdscr, h: int, w: int) -> None:
        zeilen = [
            "Tasten:",
            "  ↑ / ↓  oder  k / j      Cursor zwischen Routen bewegen",
            "  Enter  oder  g           Route greifen / loslassen",
            "  ↑ / ↓ im Greif-Modus    Route über/unter Nachbarn verschieben",
            "  d  oder  Leertaste       deaktivieren (# davor) / aktivieren",
            "  s                        speichern (ROUTE_01..N neu nummeriert)",
            "  q                        beenden (fragt bei Änderungen)",
            "",
            "Die Reihenfolge oben = Priorität (ROUTE_01 zuerst probiert).",
            "Deaktivierte Routen werden vom Bahnhof ignoriert.",
        ]
        hoehe = len(zeilen) + 2
        breite = max(len(z) for z in zeilen) + 4
        y = max(0, (h - hoehe) // 2)
        x = max(0, (w - breite) // 2)
        fenster = curses.newwin(hoehe, breite, y, x)
        fenster.bkgd(" ", curses.color_pair(4))
        fenster.box()
        for i, z in enumerate(zeilen):
            fenster.addnstr(i + 1, 2, z[: breite - 4], breite - 4)
        fenster.refresh()

    # ---------- Interaktion ----------
    def toggle(self) -> None:
        pos = self.routen_pos[self.cursor]
        typ, val = self.items[pos]
        val.aktiv = not val.aktiv
        self.dirty = True
        self.meldung = f"ROUTE_{val.nummer:02d} → {'aktiv' if val.aktiv else 'deaktiviert'}"

    def verschiebe(self, richtung: int) -> None:
        """Richtung: -1 = nach oben, +1 = nach unten."""
        if self.grab < 0:
            return
        ziel = self.grab + richtung
        if ziel < 0 or ziel >= len(self.routen_pos):
            return
        a = self.routen_pos[self.grab]   # items-Index der gegriffenen Route
        b = self.routen_pos[ziel]        # items-Index der Nachbar-Route
        # Route-Einträge in items tauschen (pre_comments hängen am Objekt und wandern mit).
        # routen_pos NICHT tauschen: Es bleibt die aufsteigende Liste der Route-Indizes
        # in items – die Anzeige und das Speichern folgen der neuen items-Reihenfolge.
        self.items[a], self.items[b] = self.items[b], self.items[a]
        self.grab = ziel
        self.cursor = ziel
        self.dirty = True
        typ, val = self.items[b]
        self.meldung = f"ROUTE_{val.nummer:02d} nach {'unten' if richtung > 0 else 'oben'} verschoben"

    def speichern(self) -> None:
        try:
            speichern(self.pfad, self.items)
            self.dirty = False
            self.meldung = "Gespeichert ✓"
        except OSError as e:
            self.meldung = f"Fehler beim Speichern: {e}"

    def frage_beenden(self, stdscr) -> bool:
        """Rückfrage bei ungespeicherten Änderungen. True = beenden."""
        if not self.dirty:
            return True
        h, w = stdscr.getmaxyx()
        msg = "Ungespeicherte Änderungen – wirklich beenden? [j/N] "
        frage = curses.newwin(3, len(msg) + 2, h // 2 - 1, max(0, (w - len(msg)) // 2))
        frage.bkgd(" ", curses.color_pair(4))
        frage.addstr(1, 1, msg)
        frage.refresh()
        while True:
            c = stdscr.getch()
            if c in (ord("j"), ord("J"), ord("y"), ord("Y"), 10):
                return True
            if c in (ord("n"), ord("N"), 27):  # ESC
                return False

    def run(self, stdscr) -> None:
        self.init_curses(stdscr)
        while True:
            h, w = stdscr.getmaxyx()
            if h < 6 or w < 40:
                stdscr.erase()
                stdscr.addnstr(0, 0, "Terminal zu klein – mindestens 40x6 Zeichen nötig.", w - 1)
                stdscr.refresh()
                stdscr.getch()
                break
            self.zeichnen(stdscr)
            c = stdscr.getch()
            self.meldung = ""
            if self.hilfe:
                if c in (ord("?"), ord("q"), 27):
                    self.hilfe = False
                continue

            if c == ord("?"):
                self.hilfe = True
            elif c == ord("s"):
                self.speichern()
            elif c == ord("q"):
                if self.frage_beenden(stdscr):
                    break
            elif c in (ord("d"), ord(" ")):
                self.toggle()
            elif c in (curses.KEY_UP, ord("k")):
                if self.grab >= 0:
                    self.verschiebe(-1)
                elif self.cursor > 0:
                    self.cursor -= 1
            elif c in (curses.KEY_DOWN, ord("j")):
                if self.grab >= 0:
                    self.verschiebe(1)
                elif self.cursor < len(self.routen_pos) - 1:
                    self.cursor += 1
            elif c in (10, ord("g")):  # Enter
                if self.grab >= 0:
                    self.grab = -1
                    self.meldung = "Losgelassen"
                else:
                    self.grab = self.cursor
                    self.meldung = f"Greife ROUTE_{self.items[self.routen_pos[self.cursor]][1].nummer:02d} – ↑/↓ verschieben"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--version" in sys.argv or "-V" in sys.argv:
        print(f"env-bahnhof-sorter v{VERSION}")
        return 0
    if "--dump" in sys.argv:
        pfad = args[0] if args else ".env"
        try:
            with open(pfad, encoding="utf-8") as f:
                items = parse(f.read())
        except OSError as e:
            print(f"Fehler: {e}", file=sys.stderr)
            return 1
        dump(pfad)
        return 0
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return 0

    pfad = args[0] if args else ".env"
    try:
        with open(pfad, encoding="utf-8") as f:
            items = parse(f.read())
    except OSError as e:
        print(f"Fehler: Datei nicht lesbar – {e}", file=sys.stderr)
        print("Aufruf: python3 sorter.py [pfad/zur/.env]  (Default: ./.env)", file=sys.stderr)
        return 1

    if not any(typ == "route" for typ, _ in items):
        print(f"Keine ROUTE_XX-Einträge in {pfad} gefunden.", file=sys.stderr)
        return 1

    try:
        curses.wrapper(Tui(pfad, items).run)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())