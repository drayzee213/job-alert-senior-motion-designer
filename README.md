# 🎯 Job-Alarm – neue Stellenanzeigen sofort aufs Handy

Ein kleiner Telegram-Bot, der etwa alle 30 Minuten (7–22 Uhr) mehrere Jobbörsen und
Firmen-Karriereseiten abfragt und dich **sofort** benachrichtigt, wenn eine passende Stelle
neu online ist. Er läuft kostenlos bei GitHub („GitHub Actions“) – dein PC muss nicht an sein.

**Quellen**

| Quelle | Wie | Wie oft |
|---|---|---|
| Jobbörse der Arbeitsagentur | offene Schnittstelle, kein Konto nötig | jeder Lauf |
| Firmen-Karriereseiten (`firmen.yaml`, 25 Firmen) | öffentliche Schnittstellen der Bewerbungssysteme (Greenhouse, Lever, Ashby, Personio, Recruitee, SmartRecruiters, Workable, JOIN, Teamtailor, BambooHR, Workday) | jeder Lauf |
| Arbeitnow | kostenlose Jobbörse mit offener Schnittstelle, viele deutsche Tech-Firmen | jeder Lauf |
| Indeed und LinkedIn | über die Bibliothek *python-jobspy* | nur alle 2 Stunden (zurückhaltend) |

**So sieht eine Meldung aus**

```
🎯 Senior Motion Designer – Character Animation & Rive
🏢 Applimeda GmbH
📍 Remote (Deutschland)
💶 60.000–75.000 € / Jahr
📅 03.11.2026 · Arbeitsagentur
💡 Motion Design, Rive, Character Animation im Titel; Senior-Level; Remote.
⭐ Relevanz: 150 Punkte
🔗 Zur Anzeige
```

Starke Treffer kommen sofort. „Vielleicht“-Treffer kommen einmal am Abend (ab 20 Uhr)
gesammelt in einer Nachricht.

---

## Inhalt

1. [Einrichtung (einmalig, ca. 15 Minuten)](#einrichtung)
2. [Bedienung per Telegram](#bedienung-per-telegram)
3. [Suchbegriffe und Bewertung ändern](#suchbegriffe-und-bewertung-ändern)
4. [Firmen hinzufügen oder entfernen](#firmen-hinzufügen-oder-entfernen)
5. [So funktioniert der Bot](#so-funktioniert-der-bot)
6. [Kosten, öffentlich oder privat?](#kosten-öffentlich-oder-privat)
7. [Rechtlicher Hinweis zu Indeed und LinkedIn](#rechtlicher-hinweis-zu-indeed-und-linkedin)
8. [Abschalten](#abschalten)
9. [Hilfe bei Problemen](#hilfe-bei-problemen)
10. [Optional: KI-Bewertung](#optional-ki-bewertung)

---

## Einrichtung

Du brauchst: die **Telegram-App** auf dem Handy und ein kostenloses **GitHub-Konto**
(github.com → „Sign up“). Alles andere passiert im Browser. Windows ist kein Problem.

### Schritt 1: Telegram-Bot anlegen

1. Öffne Telegram und suche nach **@BotFather** (blauer Haken!). Tippe auf **Starten**.
2. Schicke ihm: `/newbot`
3. Er fragt nach einem **Namen** – z. B. `Mein Job-Alarm`.
4. Dann nach einem **Benutzernamen**, der auf `bot` enden muss – z. B. `andreas_jobalarm_bot`.
5. Der BotFather antwortet mit einem langen **Token**, etwa
   `7123456789:AAH...`. Das ist das Passwort deines Bots.
   **Gib es niemandem weiter, schick es nicht in Chats und kopiere es nicht in Dateien.**
   Du trägst es gleich nur an einer einzigen Stelle bei GitHub ein (Schritt 3).
6. Tippe in der Antwort des BotFather auf den Link zu deinem neuen Bot (`t.me/…`) und drücke
   **Starten**. Ohne diesen Schritt darf der Bot dir nicht schreiben.

### Schritt 2: Deine Chat-ID herausfinden

Die Chat-ID ist die Nummer deines Telegram-Kontos, damit der Bot weiß, wem er schreibt.

1. Suche in Telegram nach **@userinfobot** und tippe auf **Starten**.
2. Er antwortet mit `Id: 123456789`. Diese Zahl ist deine Chat-ID.

### Schritt 3: Token und Chat-ID bei GitHub eintragen („Secrets“)

Secrets sind verschlüsselte Einträge. Niemand – auch nicht in einem öffentlichen Repo – kann
sie lesen; nur der Bot bekommt sie beim Laufen.

1. Öffne dein Repository auf github.com (z. B. `github.com/DEIN-NAME/job-alarm`).
2. Klicke oben auf **Settings** (Zahnrad, ganz rechts in der Leiste).
3. Links: **Secrets and variables** → **Actions**.
4. Klicke **New repository secret**:
   - **Name:** `TELEGRAM_TOKEN`
   - **Secret:** das Token vom BotFather einfügen
   - **Add secret**
5. Noch einmal **New repository secret**:
   - **Name:** `TELEGRAM_CHAT_ID`
   - **Secret:** deine Zahl von @userinfobot
   - **Add secret**

Die Namen müssen genau so geschrieben sein (Großbuchstaben, Unterstrich).

### Schritt 4: Ersten Lauf starten

1. Klicke im Repository oben auf **Actions**.
   Falls dort ein grüner Knopf „I understand my workflows, go ahead and enable them“ steht,
   klicke ihn.
2. Links **Job-Alarm** auswählen → rechts **Run workflow**.
3. Du hast zwei Möglichkeiten:
   - **Nichts ankreuzen** (empfohlen): Der Bot merkt sich alle Anzeigen, die schon online
     sind, **ohne** sie zu schicken. Ab dann kommen nur neue.
   - **„Passende Anzeigen der letzten 7 Tage einmal schicken“** ankreuzen: Du bekommst
     einmalig die passenden Anzeigen der letzten Woche.
4. Grünen Knopf **Run workflow** drücken. Nach 1–3 Minuten bekommst du in Telegram
   „✅ Job-Alarm ist eingerichtet“.

Fertig. Ab jetzt läuft der Bot von selbst.

> **Hinweis zum Zeitplan:** GitHub startet geplante Läufe nicht immer pünktlich. Oft kommen
> sie 5–20 Minuten später, an vollen Tagen fällt auch mal einer aus. Ein Treffer kommt
> deshalb meist innerhalb von 30–60 Minuten nach Veröffentlichung – immer noch deutlich
> schneller als die Mail-Alerts der Portale.

---

## Bedienung per Telegram

Schreib deinem Bot einfach:

| Befehl | Wirkung |
|---|---|
| `/status` | letzter Lauf, Treffer heute, welche Quellen funktionieren |
| `/pause` | keine Meldungen mehr (z. B. im Urlaub) |
| `/weiter` | wieder einschalten |
| `/hilfe` | Befehlsübersicht |

Wichtig: Der Bot hat keinen eigenen Server. Er liest deine Befehle erst beim **nächsten
Lauf**. Die Antwort kann also bis zu ca. 30 Minuten dauern (nachts, 22–7 Uhr, erst morgens).

---

## Suchbegriffe und Bewertung ändern

Alle Einstellungen stehen in der Datei **`config.yaml`**. So änderst du sie im Browser:

1. Repository öffnen → auf `config.yaml` klicken → oben rechts auf das **Stift-Symbol**.
2. Ändern, dann oben rechts **Commit changes…** → **Commit changes**.
3. Beim nächsten Lauf gilt die neue Einstellung.

Beim Bearbeiten: Die Einrückung (Leerzeichen am Zeilenanfang) muss bleiben, wie sie ist.
Wenn du dich vertippst, zeigt der nächste Lauf unter **Actions** einen roten Fehler.
Mach die Änderung dann einfach rückgängig.

Die wichtigsten Stellen:

- **`suche → begriffe`**: Suchwörter für die Arbeitsagentur (eine Zeile pro Begriff, mit `- ` davor).
- **`quellen → jobspy → abfragen`**: Suchanfragen für Indeed und LinkedIn
  (`OR` heißt „oder“, Anführungszeichen für feste Wortgruppen).
- **`bewertung`**: das Punktesystem (siehe unten). `sofort_ab: 60` heißt: ab 60 Punkten
  sofort melden, `vielleicht_ab: 30` heißt: ab 30 Punkten in die Abend-Sammelnachricht.
- **`bewertung → ausschluss_titel`**: Wörter, bei denen eine Anzeige nie gemeldet wird
  (Junior, Praktikum, Werkstudent, Cutter, Social Media, Freelance …).
- **`benachrichtigung`**: Zeitfenster, Uhrzeit der Sammelnachricht, Warnung bei Fehlern.

### Das Punktesystem

| Was | Punkte |
|---|---|
| „Motion Design(er)“ im Titel | +50 |
| „Rive“ oder „Character Animation“ im Titel | je +45 |
| „Lottie“ im Titel | +40 |
| „Animator“ / „Animation“ / „Gamification“ im Titel | +30 / +25 / +25 |
| „Motion“ allein, „Product/UX/UI Design“, „Illustration“ im Titel | +20 / +15 / +10 |
| Stichworte im Anzeigentext (Rive, Lottie, After Effects, Characters, Maskottchen, Gamification, Micro-Interactions, Figma …) | zusammen höchstens +40 |
| Senior / Lead / erfahren | +10 |
| Berlin oder Remote in Deutschland/EU | +10 |
| nur vor Ort in einer anderen deutschen Stadt | −25 |
| Ausland ohne Remote | praktisch Ausschluss |
| „Video“, „Marketing“, „Teilzeit“ im Titel | −15 / −10 / −10 |
| Ausschlusswort im Titel (Junior, Praktikum, Cutter, …) | nie melden |

Beispiel „Senior Motion Designer – Character Animation & Rive“ (remote): 50 + 45 + 45 + 10
\+ Stichworte = deutlich über 60 → sofort.

---

## Firmen hinzufügen oder entfernen

Die Liste steht in **`firmen.yaml`**. Jede Firma ist ein kleiner Block:

```yaml
  - name: Duolingo
    system: greenhouse
    kennung: duolingo
```

**Wie finde ich System und Kennung?** Öffne die Stellenseite der Firma und klicke auf eine
Stelle. Schau dir den Link in der Adresszeile an:

| Link sieht so aus | system | kennung |
|---|---|---|
| `boards.greenhouse.io/firma/...` oder `job-boards.greenhouse.io/firma` | `greenhouse` | `firma` |
| `jobs.lever.co/firma/...` | `lever` | `firma` |
| `jobs.ashbyhq.com/firma/...` | `ashby` | `firma` |
| `firma.jobs.personio.de/...` | `personio` | `firma` |
| `firma.recruitee.com/...` | `recruitee` | `firma` |
| `jobs.smartrecruiters.com/Firma/...` | `smartrecruiters` | `Firma` |
| `apply.workable.com/firma/...` | `workable` | `firma` |
| `join.com/companies/firma/...` | `join` | `firma` |
| `firma.teamtailor.com/...` | `teamtailor` | `firma` |
| `firma.bamboohr.com/...` | `bamboohr` | `firma` |
| `jobs.eu.lever.co/firma/...` | `lever` + Zeile `region: eu` | `firma` |

Am Ende der Datei stehen einige geprüfte Reserve-Firmen mit `aktiv: false`. Zum
Einschalten einfach `, aktiv: false` löschen.

Nicht jede Firma hat eine abrufbare Stellen-Schnittstelle. Bei Applimeda zum Beispiel
gibt es keine verlinkte Stellenseite. Deren Anzeigen findet der Bot trotzdem, sobald sie
bei der Arbeitsagentur, LinkedIn oder Indeed erscheinen.

Danach unter **Actions → Quellen prüfen → Run workflow** testen. In der Zusammenfassung des
Laufs steht für jede Firma ✅ oder ❌.
Eine Firma vorübergehend abschalten: im Block die Zeile `aktiv: false` ergänzen.

---

## So funktioniert der Bot

- **Jede Anzeige nur einmal:** Jede Quelle liefert eine feste ID. Gemeldete Anzeigen stehen
  in `state/seen.json`. Der Bot speichert diese Datei nach jedem Lauf ins Repository.
  Das hält das Repository außerdem „aktiv“: GitHub schaltet geplante Läufe sonst nach
  60 Tagen ohne Änderungen ab.
- **Duplikate über Quellen hinweg:** Dieselbe Stelle bei Indeed, LinkedIn und der
  Arbeitsagentur wird erkannt (gleiche Firma ohne „GmbH“ usw. + sehr ähnlicher Titel ohne
  „(m/w/d)“) und nur einmal gemeldet.
- **Erster Lauf:** Alles, was schon online ist, wird still gespeichert, außer du wählst die
  Option „letzte 7 Tage“.
- **Link-Prüfung:** Vor jedem Senden ruft der Bot den Link auf. Wenn die Seite nicht mehr
  existiert (404) oder Sätze wie „nicht mehr verfügbar“ oder „no longer accepting
  applications“ enthält, wird die Anzeige nicht geschickt. Indeed blockt solche Prüfungen
  manchmal. Dann gilt: Die Anzeige stand gerade eben noch im Suchergebnis, also ist sie
  aktuell.
- **Warnungen:** Scheitert eine Quelle 3-mal hintereinander, bekommst du **einmal** eine
  Warnung und später **einmal** „funktioniert wieder“.
- **Höchstens 10 Sofort-Meldungen pro Lauf**, der Rest kommt in die Sammelnachricht.

---

## Kosten, öffentlich oder privat?

- **Telegram:** kostenlos.
- **GitHub Actions:** Ein Lauf dauert ca. 1–3 Minuten, das sind ca. 30 Läufe am Tag.
  - **Öffentliches Repository (empfohlen):** Für öffentliche Repositorys sind die
    Actions-Minuten bei GitHub kostenlos und unbegrenzt (Stand heute). Sichtbar sind dann
    für jeden: der Code, deine Suchbegriffe, die Firmenliste und die Liste der gefundenen
    Anzeigen. **Nicht sichtbar** sind Token und Chat-ID (Secrets). Dein Name steht nirgends
    im Code, nur dein GitHub-Benutzername ist sichtbar.
  - **Privates Repository:** Das kostenlose Konto enthält 2.000 Minuten im Monat. GitHub
    rundet jeden Lauf auf volle Minuten auf. Damit kommt der Bot bei einem Lauf alle
    30 Minuten **knapp über** dieses Kontingent. Ist es aufgebraucht, stoppt GitHub die
    Läufe bis zum Monatsende. Es kostet nichts, solange du kein Ausgabenlimit über 0 $
    einstellst. Wenn du privat bevorzugst, stell den Zeitplan auf stündlich (siehe unten).
- Du kannst die Sichtbarkeit jederzeit ändern: **Settings → General → ganz unten
  „Change visibility“**.

**Zeitplan ändern:** Datei `.github/workflows/job-alarm.yml`, Zeile mit `cron:`.
`"17,47 5-21 * * *"` heißt: um :17 und :47 jeder Stunde von 5 bis 21 Uhr **UTC**. Für
stündlich: `"17 5-21 * * *"`.

---

## Rechtlicher Hinweis zu Indeed und LinkedIn

Indeed und LinkedIn erlauben in ihren Nutzungsbedingungen kein automatisches Auslesen.
Das ist ein Verstoß gegen die Regeln der Plattform, keine Straftat. Im schlimmsten Fall
werden die Abfragen blockiert. Der Bot fragt deshalb nur alle 2 Stunden, mit wenigen
Ergebnissen und Pausen ab. Er meldet sich nicht an und nutzt **nicht** dein LinkedIn-Konto.
Wenn du das nicht möchtest: In `config.yaml` bei `jobspy` → `aktiv: false` setzen.
Arbeitsagentur, Arbeitnow und die Firmen-Schnittstellen sind öffentlich dafür gedacht.

---

## Abschalten

- **Kurz pausieren:** `/pause` an den Bot schicken, später `/weiter`.
- **Ganz abschalten:** Repository → **Actions** → links **Job-Alarm** → rechts oben **„…“** →
  **Disable workflow**. Zum Wiedereinschalten dort **Enable workflow**.
- **Für immer löschen:** Repository → **Settings** → ganz unten **Delete this repository**.
  Danach in Telegram beim @BotFather `/deletebot` schicken, oder mit `/revoke` das Token
  ungültig machen.

---

## Hilfe bei Problemen

| Problem | Lösung |
|---|---|
| Keine Nachricht nach dem ersten Lauf | **Actions** → letzten Lauf öffnen → rote Schritte ansehen. Meist ist ein Secret falsch geschrieben, oder du hast beim eigenen Bot nicht auf **Starten** gedrückt. |
| „FEHLER: Die GitHub-Secrets … fehlen“ | Schritt 3 wiederholen, Namen genau prüfen. |
| `Telegram sendMessage: HTTP 400 chat not found` | Chat-ID falsch, oder du hast dem Bot noch nicht geschrieben (Starten drücken). |
| `HTTP 401 Unauthorized` | Token falsch. Beim BotFather `/token` → neues Token holen und Secret ersetzen. |
| Warnung „Quelle gestört: LinkedIn“ | Normal, LinkedIn blockt manchmal. Der Bot macht mit den anderen Quellen weiter. |
| Geplante Läufe hören auf | Unter **Actions** steht evtl. „This scheduled workflow is disabled …“ → **Enable workflow**. |
| Zu viele / zu wenige Treffer | In `config.yaml` `sofort_ab` / `vielleicht_ab` anpassen oder Ausschlusswörter ergänzen. |

Jeder Lauf schreibt eine Zusammenfassung: **Actions** → Lauf anklicken → unten „Summary“.
Dort steht, welche Quelle wie viele Anzeigen geliefert hat und was gesendet wurde.

---

## Optional: KI-Bewertung

Standardmäßig **aus**. Wenn eingeschaltet, prüft das Sprachmodell Claude von Anthropic die
Anzeigen, die nach dem Punktesystem mindestens 20 Punkte haben (höchstens 10 pro Lauf). Es
entscheidet „sofort / vielleicht / nein“ und schreibt einen eigenen Satz, warum die Stelle passt.

**Kosten (Anthropic-Preise, Stand Oktober 2026, ca. 2.000 Wörter Text pro Anzeige):**

| Modell | pro Anzeige | bei ca. 10 Anzeigen am Tag |
|---|---|---|
| `claude-opus-5-5` (eingestellt) | ca. 1–2 Cent | ca. 3–6 € im Monat |
| `claude-haiku-5-5` (günstiger) | unter 0,1 Cent | unter 0,30 € im Monat |

Einschalten:
1. Bei console.anthropic.com ein Konto anlegen, Guthaben aufladen, API-Key erstellen.
2. In GitHub ein drittes Secret `ANTHROPIC_API_KEY` anlegen (wie in Schritt 3).
3. In `config.yaml` bei `ki_bewertung` → `aktiv: true` setzen. Für die günstige Variante
   zusätzlich `modell: claude-haiku-5-5` eintragen.

---

## Für Technikinteressierte

- Python 3.12, Code in `jobalarm/`. Einstiegspunkt: `python -m jobalarm.main`
  (`--dry-run` = nichts senden/speichern, `--force` = Zeitfenster ignorieren,
  `--recent-days 7`).
- Tests: `pip install -r requirements.txt -r requirements-dev.txt && python -m pytest`
  (laufen automatisch bei jeder Code-Änderung, Workflow „Tests“).
- Quellen prüfen: `python -m tools.check_sources [--jobspy] [--kandidaten]`.
- `state/seen.json`: bekannte Anzeigen. Anzeigen, die 45 Tage nirgends mehr auftauchen,
  werden vergessen. `state/status.json`: Pause, Quellen-Zustand, Sammelnachricht,
  Telegram-Position.
