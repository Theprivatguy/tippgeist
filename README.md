# ⌨️ Tippgeist

Ein Tipptrainer fürs Terminal, bei dem **dein eigener letzter Lauf als Geist gegen dich antritt**.

Jeder Lauf zeichnet nicht nur das Ergebnis auf, sondern die komplette Fahrt – jeden Anschlag mit Zeitstempel. Beim nächsten Mal wird diese Aufzeichnung in Echtzeit abgespielt: ein zweiter Balken, der neben dir durch den Text rennt, mit exakt dem Tempo, das du letzte Woche hattest. Inklusive der Stelle, an der du bei "Schraubenzieher" ins Stocken gerätst.

Keine Abhängigkeiten, kein Setup, keine Cloud. Nur Python und ein Terminal.

```
TIPPGEIST   Der Kaffeeautomat  (297 Zeichen)
──────────────────────────────────────────────────────────────

DU   ████████████████░░░░░░░░░░░░░░░░░░░░  44%   61.3 WPM   98.2%
GEIST███████████████████░░░░░░░░░░░░░░░░░  52%   58.0 WPM   96.0%

Der Kaffeeautomat im dritten Stock hat ein Eigenleben entwickelt. Er
brüht nur dann guten Kaffee, wenn niemand zusieht, und verschluckt
jede zweite Münze mit einem zufriedenen Brummen. Die Kollegen nennen
ihn respektvoll den Automaten, mit großem A, und niemand traut sich
mehr, ihn zu reparieren.

12.4s   Tab = neu   ESC = raus
```

Grün ist richtig, rot ist daneben, der unterstrichene cyanfarbene Buchstabe weiter vorne im Text ist der Geist. Am Ende steht entweder „Gewonnen!" oder „Dein Geist war 2.6s schneller. Nochmal?" – und meistens klickt man dann auf nochmal.

## Loslegen

```bash
python3 -m tippgeist
```

Das war's. Python 3.8 oder neuer, sonst nichts – `curses` und `json` bringt die Standardbibliothek mit. Entwickelt und getestet auf macOS mit dem System-Python 3.9.

## Bedienung

| Taste | Wirkung |
|---|---|
| einfach tippen | die Uhr startet beim ersten Anschlag, nicht vorher |
| ⌫ | letztes Zeichen zurück (der Fehler bleibt trotzdem in der Statistik) |
| `Tab` | Lauf neu starten |
| `ESC` | raus |
| `Leertaste` | im Ergebnis: nochmal |
| `n` | im Ergebnis: anderer Text |
| `q` | im Ergebnis: Schluss |

## Optionen

```bash
python3 -m tippgeist                     # zufälliger Text, Geist = deine Bestzeit
python3 -m tippgeist -t kaffee           # fester Text
python3 -m tippgeist -g last             # gegen den letzten Lauf statt gegen die Bestzeit
python3 -m tippgeist -g none             # ohne Geist, nur du
python3 -m tippgeist -f notizen.txt      # eigener Text aus einer Datei
python3 -m tippgeist --list              # welche Texte gibt es, und was ist die Bestzeit
python3 -m tippgeist --stats             # was bisher geschah
```

`--stats` sieht so aus:

```
  TEXT                   LÄUFE    BESTE   SCHNITT  GENAUIG.
  Der Kaffeeautomat         14     67.2      58.9     97.4%
  Nachts im Büro             6     61.0      55.1     96.2%

  Persönlicher Rekord: 67.2 WPM auf "Der Kaffeeautomat".
```

## Wie der Geist funktioniert

Ein Lauf speichert `track` – eine Liste von `(Sekunde, Cursorposition)`, ein Eintrag pro Anschlag:

```json
{"wpm": 61.3, "accuracy": 98.2,
 "track": [[0.0, 0], [0.0, 1], [0.18, 2], [0.31, 3], [0.94, 4]]}
```

Beim Rennen wird für die aktuell verstrichene Zeit per Binärsuche nachgeschlagen, wo der alte Lauf zu diesem Zeitpunkt stand. Deshalb ist der Geist keine gleichmäßig laufende Durchschnittsgeschwindigkeit, sondern die echte Aufzeichnung: er zögert an denselben Wörtern wie du damals und zieht in den Passagen davon, die dir leicht fielen. Wenn du damals zurückgelöscht hast, läuft der Geist an dieser Stelle rückwärts.

Ein paar Entscheidungen, die bewusst so sind:

- **Die Uhr startet beim ersten Anschlag.** Nachdenken vor dem Start ist frei.
- **Falsche Zeichen rücken den Cursor trotzdem vor.** Sie bleiben rot stehen, bis man sie wegräumt – so sieht man den Fehler, statt gegen eine unsichtbare Wand zu tippen.
- **Zurücklöschen repariert die Position, nicht die Genauigkeit.** Die Trefferquote zählt alle Anschläge, auch die zurückgenommenen.
- **WPM = korrekte Zeichen ÷ 5 ÷ Minuten.** Fünf Anschläge pro Wort, wie überall sonst auch. Zusätzlich wird die rohe Geschwindigkeit ausgewiesen, die auch die Fehler mitzählt.

## Wo die Daten liegen

Eine einzige JSON-Datei unter `~/.tippgeist/history.json`. Nichts verlässt den Rechner. Löschen setzt alle Geister zurück:

```bash
rm ~/.tippgeist/history.json
```

Ein anderer Ort geht über die Umgebungsvariable `TIPPGEIST_HOME` – praktisch, um mal ohne Folgen für die eigene Statistik zu spielen:

```bash
TIPPGEIST_HOME=/tmp/spielwiese python3 -m tippgeist
```

Geschrieben wird atomar über eine temporäre Datei, gelesen defensiv: eine kaputte History kostet die alten Läufe, aber nicht den aktuellen.

## Eigene Texte

`-f datei.txt` nimmt jede Textdatei. Zeilenumbrüche und Mehrfach-Leerzeichen werden zu einfachen Leerzeichen zusammengezogen, typografische Anführungszeichen und Gedankenstriche auf Tastaturzeichen zurückgesetzt – sonst tippt man sich an Zeichen tot, die auf keiner Taste liegen. Der Geist hängt am Inhalt der Datei, nicht am Dateinamen: derselbe Text unter anderem Namen behält seine Bestzeit.

## Tests

```bash
python3 -m unittest discover
```

34 Tests, keine Testabhängigkeiten. Die Zeitmessung läuft über eine einspeisbare Uhr, die Läufe im Test bewegen sich also in exakter, nicht in echter Zeit.

## Aufbau

```
tippgeist/
├── engine.py     Tipp-Logik, Kennzahlen, Geist-Wiedergabe, Zeilenumbruch
├── storage.py    JSON-History lesen und schreiben
├── texts.py      eingebaute Texte und Datei-Import
├── ui.py         curses: Rennstrecke, Text, Ergebnis
└── __main__.py   Kommandozeile
```

`engine.py` und `storage.py` kennen kein curses und sind deshalb komplett ohne Terminal testbar.

## Lizenz

MIT
