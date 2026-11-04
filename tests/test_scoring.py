import pytest

from jobalarm.config import load_config
from jobalarm.location import classify_location
from jobalarm.models import Job
from jobalarm.scoring import plain_text, score_job

CFG = load_config()


def make(title, location="Berlin", description="", remote=None, company="Firma GmbH"):
    return Job(source="test", source_id=title, title=title, company=company,
               location=location, description=description, remote=remote)


def test_volltreffer_applimeda():
    job = score_job(make("Senior Motion Designer – Character Animation & Rive",
                         location="Remote", remote=True,
                         description="Wir suchen Verstärkung für unsere Gesundheits-App. Rive, After Effects, Lottie."),
                    CFG)
    assert job.category == "sofort"
    assert job.score >= 100
    text = " ".join(job.reasons)
    assert "Motion Design" in text and "Rive" in text and "Character Animation" in text
    assert "Senior-Level" in text


@pytest.mark.parametrize("title", [
    "Junior Motion Designer (m/w/d)",
    "Werkstudent Motion Design",
    "Praktikum Motion Design / Animation",
    "Internship: Motion Designer",
    "Video Editor / Cutter (m/w/d)",
    "Motion Designer Social Media (m/w/d)",
    "Freelance Motion Designer",
    "Motion Control Engineer",
    "Animateur / Kinderanimation (m/w/d)",
])
def test_ausschluesse(title):
    job = score_job(make(title), CFG)
    assert job.category == "nein"
    assert job.reasons[0].startswith("ausgeschlossen")


def test_product_designer_mit_motion_schwerpunkt():
    job = score_job(make("Senior Product Designer (all genders)",
                         description="You will own micro-interactions, prototype in Figma and "
                                     "bring our mascot to life with Rive and Lottie animations. Gamification."),
                    CFG)
    assert job.category == "sofort"
    assert "Maskottchen" in " ".join(job.reasons)


def test_unpassender_job_ohne_fachbegriff():
    job = score_job(make("Senior Backend Engineer", description="Python, Kubernetes"), CFG)
    assert job.category == "nein"
    assert job.score <= 0


def test_anderer_ort_ohne_remote_ist_schwaecher():
    berlin = score_job(make("Motion Designer (m/w/d)", location="Berlin"), CFG)
    muenchen = score_job(make("Motion Designer (m/w/d)", location="München"), CFG)
    assert berlin.score - muenchen.score == 35
    assert berlin.category == "vielleicht" or berlin.category == "sofort"
    assert muenchen.category == "nein"


def test_ausland_ohne_remote_wird_nie_gemeldet():
    job = score_job(make("Senior Motion Designer", location="New York, NY"), CFG)
    assert job.category == "nein"


def test_remote_usa_wird_nicht_als_deutschland_gewertet():
    job = score_job(make("Senior Motion Designer", location="Remote - US"), CFG)
    assert job.category == "nein"


def test_video_abzug():
    plain = score_job(make("Motion Designer"), CFG)
    video = score_job(make("Video Motion Designer"), CFG)
    assert plain.score - video.score == 15


def test_rive_nicht_in_anderen_woertern():
    job = score_job(make("Truck Driver", description="drive, arrive, derive"), CFG)
    assert job.category == "nein"
    assert not any("Rive" in r for r in job.reasons)


@pytest.mark.parametrize("location,remote,expected", [
    ("Berlin", None, "berlin"),
    ("Berlin, Germany", True, "berlin"),
    ("Remote", True, "remote_unklar"),
    ("Remote - Germany", None, "remote_de"),
    ("Hamburg (Homeoffice möglich)", True, "remote_de"),
    ("Deutschland", True, "remote_de"),
    ("Remote, EMEA", None, "remote_de"),
    ("München", None, "anderer_ort_de"),
    ("London, UK", None, "ausland"),
    ("Remote (US)", True, "ausland"),
    ("", None, "unbekannt"),
])
def test_ortsklassifikation(location, remote, expected):
    assert classify_location(location, remote)[0] == expected


def test_plain_text_entfernt_html():
    assert plain_text("&lt;p&gt;Hallo &amp; <b>Welt</b>&lt;/p&gt;") == "Hallo & Welt"
