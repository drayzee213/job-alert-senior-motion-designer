from jobalarm.dedupe import fingerprint, is_duplicate, normalize_company, normalize_title


def test_firmennamen_werden_vereinheitlicht():
    assert normalize_company("Applimeda GmbH") == normalize_company("applimeda")
    assert normalize_company("Kaia Health Software GmbH") == "kaia health software"
    assert normalize_company("Müller & Co. KG") == normalize_company("Mueller")


def test_gender_zusaetze_werden_entfernt():
    a = normalize_title("Senior Motion Designer (m/w/d)")
    b = normalize_title("Senior Motion Designer (all genders)")
    c = normalize_title("Senior Motion Designer:in (w/m/d)")
    assert a == b == c == "senior motion designer"


def test_gleiche_anzeige_ueber_zwei_quellen():
    known = {fingerprint("Applimeda GmbH", "Senior Motion Designer – Character Animation & Rive (m/w/d)")}
    fp = fingerprint("Applimeda", "Senior Motion Designer - Character Animation & Rive")
    assert is_duplicate(fp, known)


def test_titel_leicht_anders_aber_gleiche_firma():
    known = {fingerprint("Applimeda GmbH", "Senior Motion Designer")}
    fp = fingerprint("Applimeda", "Senior Motion Designer – Character Animation & Rive")
    assert is_duplicate(fp, known)


def test_andere_firma_ist_kein_duplikat():
    known = {fingerprint("Firma A GmbH", "Senior Motion Designer")}
    assert not is_duplicate(fingerprint("Firma B GmbH", "Senior Motion Designer"), known)


def test_andere_stelle_gleiche_firma_ist_kein_duplikat():
    known = {fingerprint("Duolingo", "Senior Character Animator")}
    assert not is_duplicate(fingerprint("Duolingo", "Staff Product Designer"), known)
