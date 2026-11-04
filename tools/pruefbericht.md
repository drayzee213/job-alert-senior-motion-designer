# Prüfbericht Quellen – 04.11.2026 21:06 UTC

## Hauptquellen

- Arbeitsagentur v6 Suche: HTTP 200
  - Schlüssel der Antwort: `['ergebnisliste', 'facetten', 'maxErgebnisse', 'page', 'size', 'woOutput']`
  - Anzahl Stellen: 2, maxErgebnisse: 2
  - Felder einer Stelle: `['aenderungsdatum', 'alleBerufe', 'alternativBeruf1', 'alternativBeruf2', 'arbeitgeberKundennummerHash', 'arbeitszeitSchichtNachtWochenende', 'arbeitszeitTeilzeitAbend', 'arbeitszeitTeilzeitFlexibel', 'arbeitszeitTeilzeitNachmittag', 'arbeitszeitTeilzeitVormittag', 'arbeitszeitVollzeit', 'datumErsteVeroeffentlichung', 'eintrittszeitraum', 'entfernung', 'firma', 'hauptberuf', 'homeofficemoeglich', 'homeofficetyp', 'referenznummer', 'stellenangebotsTitel', 'stellenangebotsart', 'stellenlokationen', 'verguetungsangabe', 'veroeffentlichungszeitraum', 'vertragsdauer']`
  - Beispiel (gekürzt): `{"stellenangebotsart": "ARBEIT", "stellenangebotsTitel": "Kommunikationsdesigner (m/w/d)", "arbeitszeitSchichtNachtWochenende": false, "arbeitszeitTeilzeitAbend": false, "arbeitszeitTeilzeitNachmittag": false, "arbeitszeitTeilzeitVormittag": false, "arbeitszeitTeilzeitFlexibel": false, "arbeitszeitVollzeit": true, "eintrittszeitraum": {"von": "2026-11-02"}, "verguetungsangabe": "KEINE_ANGABEN", "vertragsdauer": "UNBEFRISTET", "stellenlokationen": [{"adresse": {"strasse": "Am Gewerbering", "hausnummer": "27", "plz": "15374", "ort": "Müncheberg", "region": "BRANDENBURG", "land": "DEUTSCHLAND"}, "breite": 52.509766, "laenge": 14.1461549}], "homeofficemoeglich": true, "homeofficetyp": "NACH_VERE`
  - Geparst: Kommunikationsdesigner (m/w/d) | Niklas Möller - Natural Goods Berlin | Müncheberg (Homeoffice möglich) | 2026-11-02 | https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1003947043-S
  - Details nachgeladen: Beschreibung 2074 Zeichen
  - Linkprüfung: ('ok', 'Details abrufbar')
- Arbeitsagentur Homeoffice (arbeitszeit=ho): HTTP 200, 0 Stellen
- Arbeitsagentur kompletter Abruf mit config.yaml: 7 Stellen
  - GUI-Designer Automotive (m/w/d) | Akkodis Germany Tech Experts GmbH | München | 2026-10-29
  - GUI-Designer Automotive (m/w/d) | Guldberg GmbH | München | 2026-10-28
  - GUI Designer Automotive (all gender) | ALTEN Consulting Services GmbH | München | 2026-10-28
  - Kommunikationsdesigner (m/w/d) | Niklas Möller - Natural Goods Berlin | Müncheberg (Homeoffice möglich) | 2026-11-02
  - Art Director (m/w/d) | Pharmatechnik KG 01 | Starnberg | 2026-11-02
  - Cloud and Systems Integration Developer (m/w/d) | MAXON Computer GmbH | Bad Homburg vor der Höhe | 2026-10-29
  - Brand & Creative Director (m/w/d) | MAXON Computer GmbH | Bad Homburg vor der Höhe | 2026-10-29
- Arbeitnow: 900 Stellen, z. B. IT Systemintegrator (m/w/d); Product Engineer (Frontend) (m/f/d); Bauleitung / Objektüberwachung HLS (m/w/d)
- Telegram-API erreichbar: HTTP 401 (401/404 ist hier richtig)
- python-jobspy Version: unbekannt
- indeed: 1 Stellen in 0s, Fehler: {}, Warnungen: {}
  - Art Director Performance Creatives (m/w/d) | Performancepixel | Berlin, BE, Germany | 2026-11-03 | None
    Linkprüfung: ('unknown', 'HTTP 401 (Seite blockt automatische Prüfung)')
- linkedin: 5 Stellen in 0s, Fehler: {}, Warnungen: {}
  - AI Video Creator & Automation Specialist (m/w/d) | easycosmetic Recruiting GmbH | Berlin, Berlin, Germany | 2026-11-02 | None
    Linkprüfung: ('ok', 'HTTP 200')
  - Grafik Designer:in / Motion Designer:in (m/w/d) | PB3C GmbH | Berlin, Berlin, Germany | 2026-10-31 | None
    Linkprüfung: ('ok', 'HTTP 200')
  - Performance Designer & Video Editor (a) | Oviva | Berlin, Berlin, Germany | 2026-10-30 | None
    Linkprüfung: ('ok', 'HTTP 200')

## Firmen aus firmen.yaml

| Firma | System | Anzeigen gesamt | davon DE/Remote | Status |
|---|---|---|---|---|
| Duolingo | greenhouse:duolingo | 55 | 0 | ✅ |
| Babbel | ashby:babbel | 10 | 8 | ✅ |
| simpleclub | join:simpleclub | 2 | 2 | ✅ |
| ANTON | personio:anton | 8 | 8 | ✅ |
| sofatutor | recruitee:sofatutor | 1 | 1 | ✅ |
| Knowunity | ashby:knowunity | 6 | 6 | ✅ |
| StudySmarter | personio:studysmarter | 4 | 3 | ✅ |
| Oviva | ashby:oviva | 31 | 16 | ✅ |
| YAZIO | ashby:yazio | 3 | 3 | ✅ |
| HelloBetter | personio:geton | 1 | 1 | ✅ |
| Clue | bamboohr:helloclue | 2 | 0 | ✅ |
| Wooga | greenhouse:wooga | 5 | 5 | ✅ |
| Kolibri Games | lever:kolibrigames | 4 | 4 | ✅ |
| InnoGames | lever:innogames | 6 | 6 | ✅ |
| Goodgame Studios | teamtailor:goodgamestudios | 1 | 1 | ✅ |
| GameDuell | join:gameduell | 2 | 2 | ✅ |
| Travian Games | personio:traviangames | 2 | 2 | ✅ |
| Yager | personio:yager | 0 | 0 | ✅ |
| Ubisoft | smartrecruiters:Ubisoft2 | 298 | 1 | ✅ |
| Rive | workable:rivecareers | 0 | 0 | ✅ |
| Trade Republic | greenhouse:traderepublicbank | 48 | 10 | ✅ |
| N26 | greenhouse:n26 | 36 | 21 | ✅ |
| GetYourGuide | greenhouse:getyourguide | 69 | 55 | ✅ |
| Delivery Hero | smartrecruiters:DeliveryHero | 906 | 38 | ✅ |
| Figma | greenhouse:figma | 145 | 8 | ✅ |
