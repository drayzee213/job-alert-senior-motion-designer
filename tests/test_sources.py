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


def test_arbeitsagentur_alte_und_neue_feldnamen():
    v4 = {"refnr": "10000-1-S", "titel": "Motion Designer (m/w/d)", "arbeitgeber": "Applimeda GmbH",
          "arbeitsort": {"ort": "Berlin", "plz": "10115"}, "aktuelleVeroeffentlichungsdatum": "2026-11-03"}
    v6 = {"referenznummer": "10000-2-S", "stellenangebotsTitel": "Rive Animator",
          "arbeitgeber": "X GmbH", "arbeitsorte": [{"ort": "Hamburg"}],
          "veroeffentlichungsdatum": "2026-11-02T10:00:00"}
    a = arbeitsagentur.parse_item(v4)
    b = arbeitsagentur.parse_item(v6, homeoffice=True)
    assert a.uid == "arbeitsagentur:10000-1-S" and a.location == "Berlin" and a.posted == "2026-11-03"
    assert a.url == "https://www.arbeitsagentur.de/jobsuche/jobdetail/10000-1-S"
    assert b.title == "Rive Animator" and b.remote is True and b.posted == "2026-11-02"
    assert "Homeoffice" in b.location
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
