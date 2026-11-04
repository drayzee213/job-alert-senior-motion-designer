import math

from jobalarm import linkcheck
from jobalarm.sources import arbeitnow, arbeitsagentur, ats
from jobalarm.sources.jobspy_source import record_to_job

COMPANY = {"name": "Testfirma", "kennung": "testfirma"}


class FakeResp:
    def __init__(self, data=None, content=b"", text=""):
        self._data, self.content, self.text = data, content, text

    def json(self):
        return self._data


def test_arbeitsagentur_v6_echtes_format():
    # Felder wie in der echten Antwort vom 04.11.2026 (gekürzt)
    v6 = {"stellenangebotsart": "ARBEIT", "stellenangebotsTitel": "Motion Designer (m/w/d)",
          "vertragsdauer": "BEFRISTET", "befristungInMonaten": 24,
          "stellenlokationen": [{"adresse": {"plz": "40212", "ort": "Düsseldorf", "land": "DEUTSCHLAND"}},
                                {"adresse": {"plz": "20359", "ort": "Hamburg", "land": "DEUTSCHLAND"}}],
          "homeofficemoeglich": True, "homeofficetyp": "NACH_VEREINBARUNG",
          "veroeffentlichungszeitraum": {"von": "2026-11-03"}, "datumErsteVeroeffentlichung": "2026-10-27",
          "firma": "Interone GmbH", "referenznummer": "10001-1003918246-S"}
    j = arbeitsagentur.parse_item(v6)
    assert j.uid == "arbeitsagentur:10001-1003918246-S"
    assert j.title == "Motion Designer (m/w/d) [befristet]"
    assert j.company == "Interone GmbH"
    assert j.location == "Düsseldorf, Hamburg (Homeoffice möglich)"
    assert j.posted == "2026-10-27"
    assert j.url == "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1003918246-S"
    ext = arbeitsagentur.parse_item({**v6, "externeURL": "https://www.stellenanzeigen.de/job/x"})
    assert ext.url == "https://www.stellenanzeigen.de/job/x"


def test_arbeitsagentur_alte_feldnamen():
    v4 = {"refnr": "10000-1-S", "titel": "Motion Designer (m/w/d)", "arbeitgeber": "Applimeda GmbH",
          "arbeitsort": {"ort": "Berlin", "plz": "10115"}, "aktuelleVeroeffentlichungsdatum": "2026-11-03"}
    a = arbeitsagentur.parse_item(v4)
    assert a.location == "Berlin" and a.posted == "2026-11-03" and a.company == "Applimeda GmbH"
    assert arbeitsagentur._items({"ergebnisliste": [v4]}) == [v4]
    assert arbeitsagentur.parse_item({"titel": "ohne Nummer"}) is None


def test_greenhouse(monkeypatch):
    data = {"jobs": [{"id": 42, "title": "Senior Character Animator", "location": {"name": "Berlin, Germany"},
                      "absolute_url": "https://boards.greenhouse.io/testfirma/jobs/42",
                      "content": "&lt;p&gt;Rive &amp; Lottie&lt;/p&gt;", "updated_at": "2026-11-01T12:00:00Z"}]}
    monkeypatch.setattr(ats.http, "get", lambda *a, **k: FakeResp(data))
    jobs = ats.greenhouse(COMPANY)
    assert jobs[0].uid == "greenhouse:testfirma:42"
    assert jobs[0].description == "Rive & Lottie"
    assert jobs[0].company == "Testfirma" and jobs[0].posted == "2026-11-01"


def test_lever_und_ashby(monkeypatch):
    lever = [{"id": "abc", "text": "Motion Designer", "categories": {"location": "Berlin"},
              "workplaceType": "remote", "hostedUrl": "https://jobs.lever.co/t/abc",
              "createdAt": 1762000000000, "descriptionPlain": "Rive"}]
    monkeypatch.setattr(ats.http, "get", lambda *a, **k: FakeResp(lever))
    j = ats.lever(COMPANY)[0]
    assert j.remote is True and j.posted.startswith("2025") and j.url.endswith("/abc")
    ashby = {"jobs": [{"id": "u-1", "title": "Rive Designer", "location": "Remote (Germany)", "isRemote": True,
                       "jobUrl": "https://jobs.ashbyhq.com/t/u-1", "publishedAt": "2026-10-30T00:00:00Z",
                       "descriptionPlain": "x", "compensation": {"compensationTierSummary": "€70K – €85K"}},
                      {"id": "u-2", "title": "Hidden", "isListed": False}]}
    monkeypatch.setattr(ats.http, "get", lambda *a, **k: FakeResp(ashby))
    jobs = ats.ashby(COMPANY)
    assert len(jobs) == 1 and jobs[0].salary == "€70K – €85K"


def test_personio_xml():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <workzag-jobs><position><id>123</id><office>Berlin</office>
    <additionalOffices><office>Remote</office></additionalOffices>
    <name>Senior Motion Designer (m/w/d)</name>
    <jobDescriptions><jobDescription><name>Aufgaben</name><value><![CDATA[<p>Rive &amp; After Effects</p>]]></value></jobDescription></jobDescriptions>
    <createdAt>2026-10-28T09:00:00+00:00</createdAt></position></workzag-jobs>"""
    jobs = ats.parse_personio(xml, COMPANY, "https://testfirma.jobs.personio.de")
    assert jobs[0].url == "https://testfirma.jobs.personio.de/job/123"
    assert jobs[0].location == "Berlin, Remote"
    assert "Rive & After Effects" in jobs[0].description


def test_join_next_data():
    data = {"props": {"pageProps": {"initialState": {"jobs": {"items": [
        {"id": 99, "idParam": "99-motion-designer", "title": "Motion Designer", "city": {"cityName": "Berlin"},
         "workplaceType": "HYBRID", "createdAt": "2026-11-01T00:00:00Z"}]}}}}}
    jobs = ats.parse_join(data, COMPANY)
    assert jobs[0].url == "https://join.com/companies/testfirma/99-motion-designer"
    assert jobs[0].location == "Berlin"


def test_arbeitnow():
    data = {"data": [{"slug": "motion-designer-x", "company_name": "X", "title": "Motion Designer",
                      "description": "<p>Rive</p>", "remote": True, "url": "https://www.arbeitnow.com/jobs/x",
                      "location": "Berlin", "created_at": 1762300000}]}
    j = arbeitnow.parse(data)[0]
    assert j.uid == "arbeitnow:motion-designer-x" and j.remote is True and j.description == "Rive"


def test_jobspy_record_mit_leeren_werten():
    rec = {"id": "in-abc", "job_url": "https://de.indeed.com/viewjob?jk=abc", "title": "Motion Designer",
           "company": "Firma", "location": "Berlin, BE, DE", "date_posted": "2026-11-04",
           "min_amount": 55000.0, "max_amount": 70000.0, "currency": "EUR", "interval": "yearly",
           "is_remote": float("nan"), "description": float("nan")}
    j = record_to_job(rec, "indeed")
    assert j.salary == "55.000–70.000 € / Jahr"
    assert j.remote is None and j.description == ""
    assert record_to_job({"id": None, "job_url": None, "title": math.nan}, "indeed") is None


def test_linkcheck_erkennt_abgelaufene_seiten():
    assert linkcheck.page_says_dead("<html><h1>Diese Stelle ist leider nicht mehr verfügbar</h1></html>")
    assert linkcheck.page_says_dead("<div>No longer accepting applications</div>")
    assert not linkcheck.page_says_dead(
        "<script>var msg='job has expired';</script><h1>Senior Motion Designer</h1><p>Jetzt bewerben</p>")


def test_teamtailor_rss():
    rss = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:tt="https://teamtailor.com/locations"><channel><title>Goodgame Studios</title>
    <item><title>Senior 2D Animator (f/m/d)</title><link>https://goodgamestudios.teamtailor.com/jobs/123-senior-2d-animator</link>
    <guid>abc-123</guid><pubDate>Mon, 02 Nov 2026 10:00:00 +0100</pubDate>
    <description>&lt;p&gt;Spine &amp;amp; After Effects&lt;/p&gt;</description><remoteStatus>hybrid</remoteStatus>
    <tt:locations><tt:location><tt:name>HQ</tt:name><tt:city>Hamburg</tt:city><tt:country>Germany</tt:country></tt:location></tt:locations>
    </item></channel></rss>"""
    j = ats.parse_teamtailor(rss, COMPANY)[0]
    assert j.uid == "teamtailor:testfirma:abc-123"
    assert j.location == "Hamburg" and j.posted == "2026-11-02"
    assert "Spine & After Effects" in j.description


def test_bamboohr(monkeypatch):
    data = {"meta": {"totalCount": 1}, "result": [{"id": "47", "jobOpeningName": "Senior Motion Designer",
                                                   "location": {"city": "Berlin", "state": None}, "isRemote": None}]}
    monkeypatch.setattr(ats.http, "get", lambda *a, **k: FakeResp(data))
    j = ats.bamboohr(COMPANY)[0]
    assert j.url == "https://testfirma.bamboohr.com/careers/47" and j.location == "Berlin"
