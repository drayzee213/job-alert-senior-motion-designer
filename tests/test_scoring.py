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


@pytest.mark.parametrize("location", ["München", "Hamburg, Hamburg, Germany",
                                      "Neckarsulm (Homeoffice möglich)",
                                      "Düsseldorf, Hamburg (Homeoffice möglich)"])
def test_andere_stadt_wird_nie_gemeldet(location):
    job = score_job(make("Senior Motion Designer (m/w/d)", location=location,
                         description="Rive, Lottie, After Effects"), CFG)
    assert job.category == "nein"


@pytest.mark.parametrize("location", ["Berlin", "Potsdam", "Berlin (Homeoffice möglich)",
                                      "Berlin, München", "Teltow"])
def test_berlin_und_umland(location):
    job = score_job(make("Motion Designer (m/w/d)", location=location), CFG)
    assert job.category == "sofort"


def test_andere_stadt_mit_remote_im_text_bleibt_moeglich():
    job = score_job(make("Senior Motion Designer", location="Konstanz",
                         description="Remote möglich. After Effects, Rive."), CFG)
    assert job.category in ("vielleicht", "sofort")
    assert any("falls wirklich Remote" in r for r in job.reasons)


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
    ("Berlin (Homeoffice möglich)", None, "berlin"),
    ("Deutschland", True, "remote_de"),
    ("Remote, EMEA", None, "remote_de"),
    ("München", None, "anderer_ort_de"),
    ("Hamburg (Homeoffice möglich)", None, "hybrid_anderer_ort"),
    ("Potsdam", None, "berlin"),
    ("London, UK", None, "ausland"),
    ("Remote (US)", True, "ausland"),
    ("", None, "unbekannt"),
    ("Germany", None, "unbekannt"),
])
def test_ortsklassifikation(location, remote, expected):
    assert classify_location(location, remote)[0] == expected


def test_plain_text_entfernt_html():
    assert plain_text("&lt;p&gt;Hallo &amp; <b>Welt</b>&lt;/p&gt;") == "Hallo & Welt"


@pytest.mark.parametrize("title,description", [
    # echte Fehltreffer aus dem Trockenlauf vom 04.11.2026
    ("Senior Embedded Software Engineer (All Genders)", "Join our community. Strong character and Unity of purpose."),
    ("Senior Manager - Global Product Ops Excellence (All Genders)", "community, characters"),
    ("Sr. Product Designer", "Design systems in Figma for our data community."),
])
def test_keine_fehltreffer_durch_allgemeine_woerter(title, description):
    assert score_job(make(title, description=description), CFG).category == "nein"


def test_product_designer_braucht_motion_bezug():
    ohne = score_job(make("Senior Product Designer", description="Figma, user research"), CFG)
    mit = score_job(make("Senior Product Designer", description="Figma, Lottie and Rive animations"), CFG)
    assert ohne.category == "nein"
    assert mit.category in ("vielleicht", "sofort")


@pytest.mark.parametrize("title,location", [
    ("Lead Animator", "Da Nang, , Vietnam"),
    ("Commerciale Responsable D'agence D'animation Evenementielle Enfants", "Nice"),
    ("Senior Character Animator", "Montpellier, Occitanie, France"),
])
def test_ausland_wird_erkannt(title, location):
    assert score_job(make(title, location=location), CFG).category == "nein"


def test_arbeitsagentur_kleinstadt_gilt_als_deutschland_und_faellt_raus():
    job = make("Motion Designer", location="Müncheberg, Strausberg, Seelow")
    job.source = "arbeitsagentur"
    job = score_job(job, CFG)
    assert job.location_label.startswith("Müncheberg")
    assert any("vor Ort" in r for r in job.reasons)
    assert job.category == "nein"


def test_character_animator_in_hamburg_wird_nicht_gemeldet():
    job = score_job(make("Character Animator", location="Hamburg, Hamburg, Germany"), CFG)
    assert job.category == "nein"


def test_fachfremder_titel_mit_gamification_im_text_ist_kein_treffer():
    # Fehltreffer vom 05.11.2026 (Amplitude)
    job = score_job(make("Senior Customer Success Manager - DACH & North",
                         description="Help customers with gamification, animations and Figma dashboards."), CFG)
    assert job.category == "nein"


def test_fachfremder_titel_mit_rive_und_lottie_im_text_bleibt_moeglich():
    job = score_job(make("Senior Creative Technologist",
                         description="Build interactive Rive and Lottie animations with After Effects."), CFG)
    assert job.category in ("vielleicht", "sofort")


def test_maskottchen_allein_reicht_nicht_ohne_fachbegriff_im_titel():
    job = score_job(make("Senior Customer Success Manager", location="Remote-Germany",
                         description="Our mascot loves data."), CFG)
    assert job.category == "nein"


@pytest.mark.parametrize("location,label", [
    ("Berlin, Berlin, Germany", "Berlin"),
    ("Berlin, BE, Germany", "Berlin"),
    ("Berlin (Homeoffice möglich)", "Berlin (Homeoffice möglich)"),
    ("Potsdam, Brandenburg, Germany", "Potsdam"),
])
def test_berlin_label_kurz(location, label):
    assert classify_location(location)[1] == label
