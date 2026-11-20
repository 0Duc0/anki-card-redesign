import json, os, pathlib, sys

# the add-on's modules are imported directly (they fall back to plain imports outside Anki)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "card_redesign"))
CHROME = "/usr/bin/google-chrome" if os.path.exists("/usr/bin/google-chrome") else None
FIX = pathlib.Path(__file__).parent / "fixtures" / "cn"

def fixture(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))

NAMES = ["gaoxing", "de", "ni", "le", "ren", "zhenzuo", "classifiers", "long_entry", "orthography", "no_examples"]


def model_dict() -> dict:
    return json.loads((FIX / "model.json").read_text(encoding="utf-8"))


def make_collection(path, names=NAMES, model=None, clean=True):
    """New collection holding the old Chinese note type and the fixture notes.
    clean=True runs the meanings/examples cleaners on the fields first."""
    from anki.collection import Collection
    import cn
    col = Collection(str(path))
    m = model or model_dict()
    m = dict(m, id=0)
    col.models.add_dict(m)
    nt = col.models.by_name(m["name"])
    nids = {}
    for name in names:
        f = fixture(name)
        note = col.new_note(nt)
        for k in note.keys():
            note[k] = f.get(k, "")
        if clean:
            d = cn.clean_definitions(note["DefinitionsHTML"])
            if d is not None:
                note["DefinitionsHTML"] = d
            e = cn.clean_examples(note["ExampleSentence"], note["ExampleTranslation"], note["Simplified"], note["Traditional"])
            if e is not None:
                note["ExampleSentence"], note["ExampleTranslation"] = e.examples, e.sources
        col.add_note(note, 1)
        nids[name] = note.id
    return col, nids


def jp_fixture(name: str) -> dict:
    return json.loads((FIX.parent / "jp" / f"{name}.json").read_text(encoding="utf-8"))


def vn_fixture(name: str) -> dict:
    return json.loads((FIX.parent / "vn" / f"{name}.json").read_text(encoding="utf-8"))


def make_lang_collection(path, lang: str, names: list[str], clean_note=None):
    """New collection with the old note type of `lang` ("jp"/"vn") and its fixture notes, optionally cleaned."""
    from anki.collection import Collection
    col = Collection(str(path))
    m = json.loads((FIX.parent / lang / "model.json").read_text(encoding="utf-8"))
    col.models.add_dict(dict(m, id=0))
    nt = col.models.by_name(m["name"])
    nids = {}
    for name in names:
        f = json.loads((FIX.parent / lang / f"{name}.json").read_text(encoding="utf-8"))
        note = col.new_note(nt)
        for k in note.keys():
            note[k] = f.get(k, "")
        if clean_note is not None:
            for k, v in clean_note({k: note[k] for k in note.keys()}).changes.items():
                note[k] = v
        col.add_note(note, 1)
        nids[name] = note.id
    return col, nids


def visible_text(card_html: str, dark: bool = False) -> str:
    """innerText of a rendered card (respects display:none), via headless Chrome."""
    from playwright.sync_api import sync_playwright
    body = f'<!doctype html><html><head><meta charset="utf-8"></head><body class="card{" nightMode" if dark else ""}">{card_html}</body></html>'
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)
        pg = b.new_page()
        pg.set_content(body)
        txt = pg.inner_text("body")
        b.close()
    return txt


def element_tops(card_html: str, selectors: list[str]) -> list[float]:
    """On-screen top position of the first element matching each selector (respects CSS order)."""
    from playwright.sync_api import sync_playwright
    body = f'<!doctype html><html><head><meta charset="utf-8"></head><body class="card">{card_html}</body></html>'
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)
        pg = b.new_page(viewport={"width": 420, "height": 800})
        pg.set_content(body)
        tops = [pg.eval_on_selector(s, "e => e.getBoundingClientRect().top") for s in selectors]
        b.close()
    return tops
