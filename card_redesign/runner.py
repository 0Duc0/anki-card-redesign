"""Apply a language's cleaners and templates to a collection: dry run, apply, restore."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass, field
from typing import Callable

try:  # inside Anki this module lives in the package `card_redesign`
    from . import cn, fieldnames, fonts, jp, vn
    from .cn_templates import build_cn_templates
    from .jp_templates import build_jp_templates
    from .vn_templates import build_vn_templates
    from .zh_lex import Lexicon
except ImportError:  # tests and tools import it directly
    import cn
    import fieldnames
    import fonts
    import jp
    import vn
    from cn_templates import build_cn_templates
    from jp_templates import build_jp_templates
    from vn_templates import build_vn_templates
    from zh_lex import Lexicon

BATCH = 500
SAMPLE_CHARS = 3000


def cn_lexicon(col, model: dict) -> "Lexicon":
    """Simplified/traditional/pinyin dictionary from every note of the CC-CEDICT note type."""
    names = fieldnames.canonical_names(model, "cn")
    i_s, i_t, i_p = names.index("Simplified"), names.index("Traditional"), names.index("PinyinMarked")
    lx = Lexicon()
    for (flds,) in col.db.all("select flds from notes where mid = ?", model["id"]):
        v = flds.split("\x1f")
        lx.add(v[i_s], v[i_t], v[i_p])
    lx.meanings = cn.meaning_index(col, model)   # for the "Not:" line on Meaning → Chinese
    return lx


@dataclass
class LangSpec:
    model_prefix: tuple                # note type name starts with one of these
    clean_note: Callable[..., "cn.NoteResult"]
    build_templates: Callable[[dict], dict]
    prepare: Callable | None = None   # (col, model) -> context passed to clean_note


LANGS = {
    "cn": LangSpec(("CC-CEDICT Optimized EN", "CC-CEDICT (ZH"), cn.clean_note, build_cn_templates, cn_lexicon),
    "jp": LangSpec(("JP Vocabulary", "JMdict (JP"), jp.clean_note, build_jp_templates, jp.meaning_index),
    "vn": LangSpec(("Vietnamese Optimized EN", "Kaikki/Underthesea/FVDP (VN"), vn.clean_note, build_vn_templates),
}


@dataclass
class Report:
    lang: str = ""
    model: str = ""
    notes_total: int = 0
    notes_changed: int = 0
    fields_changed: dict = field(default_factory=dict)
    unrecognised: dict = field(default_factory=dict)        # field -> first 50 note ids
    unrecognised_count: dict = field(default_factory=dict)  # field -> count
    dropped_examples: int = 0
    dropped_samples: list = field(default_factory=list)
    audio_in: int = 0
    audio_out: int = 0
    audio_dropped: int = 0
    samples: list = field(default_factory=list)
    templates_updated: bool = False
    template_backup: str | None = None
    fonts_installed: list = field(default_factory=list)
    template_error: str | None = None    # why the new layout can't be built for this note type
    card_check: str | None = None        # result of the card-generation check on a scratch collection
    missing_cards: int = 0               # notes lacking a card the current templates would make (Anki would re-add it)
    form_card_nids: list = field(default_factory=list)
    merged_groups: int = 0               # Japanese: written forms that had several notes (merged into one)
    merged_notes: int = 0                # notes folded into another note's "Other readings"
    merged_cards: int = 0                # their cards, removed with them
    merge_samples: list = field(default_factory=list)
    new_cards: int = 0                   # cards switched on by this run (ScriptDiff "" -> non-empty)
    removed_cards: int = 0               # "Taiwan form" cards removed (ScriptDiff "form" -> "")
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def find_model(col, lang: str) -> dict:
    spec = LANGS[lang]
    found = [m for m in col.models.all() if m["name"].startswith(spec.model_prefix)]
    if len(found) != 1:
        raise ValueError(f"Expected exactly one note type starting with {' or '.join(spec.model_prefix)}, found {len(found)}")
    return found[0]


def _scan(col, lang: str, sample: int, progress, collect_notes: bool):
    spec, model = LANGS[lang], find_model(col, lang)
    rep = Report(lang=lang, model=model["name"])
    t0 = time.time()
    ctx = spec.prepare(col, model) if spec.prepare else None
    nids = col.models.nids(model["id"])
    rep.notes_total = len(nids)
    fmap = fieldnames.resolve(model, lang)          # canonical -> actual field name
    inv = {v: k for k, v in fmap.items()}
    changed, form_cards = [], rep.form_card_nids
    for i, nid in enumerate(nids):
        note = col.get_note(nid)
        fields = {inv.get(k, k): note[k] for k in note.keys()}   # canonical names
        res = spec.clean_note(fields, ctx) if ctx is not None else spec.clean_note(fields)
        rep.audio_in += res.audio_in
        rep.audio_out += res.audio_out
        rep.audio_dropped += res.audio_dropped
        rep.dropped_examples += len(res.dropped)
        if res.dropped and len(rep.dropped_samples) < 200:
            rep.dropped_samples += [f"{fields.get('Simplified', nid)}: {d}" for d in res.dropped]
        for f in res.unrecognised:
            rep.unrecognised_count[f] = rep.unrecognised_count.get(f, 0) + 1
            lst = rep.unrecognised.setdefault(f, [])
            if len(lst) < 50:
                lst.append(nid)
        if res.changes.get("ScriptDiff", "").strip() and not fields.get("ScriptDiff", "").strip():
            rep.new_cards += 1
        if fields.get("ScriptDiff", "") == "form" and res.changes.get("ScriptDiff") == "":
            rep.removed_cards += 1          # user 2026-11-19: no separate Taiwan-form cards, studied or not
            if collect_notes:
                form_cards.append(nid)
        if res.changes:
            rep.notes_changed += 1
            for f, v in res.changes.items():
                rep.fields_changed[f] = rep.fields_changed.get(f, 0) + 1
                if len(rep.samples) < sample:
                    rep.samples.append({"nid": nid, "field": f, "before": fields[f][:SAMPLE_CHARS],
                                        "after": v[:SAMPLE_CHARS]})
            if collect_notes:
                for f, v in res.changes.items():
                    note[fmap.get(f, f)] = v
                changed.append(note)
        if progress and i % 1000 == 0:
            progress(i, len(nids))
    rep.seconds = round(time.time() - t0, 1)
    return rep, model, changed


def _front_fields(model: dict) -> list[str]:
    names = {f["name"] for f in model["flds"]}
    refs = set()
    for t in model["tmpls"]:
        for ref in re.findall(r"{{[#^/]?([^}]+)}}", t["qfmt"]):
            name = ref.split(":")[-1].strip()
            if name in names:
                refs.add(name)
    return sorted(refs)


def check_card_generation(col, model: dict, new_model: dict, per_pattern: int = 3, details: dict | None = None) -> str:
    """Apply the new fronts to a scratch collection holding sample notes of every emptiness pattern of the
    fields the fronts use, and raise ValueError if any note would get or lose a card."""
    from anki.collection import Collection

    names = [f["name"] for f in model["flds"]]
    refs = sorted(set(_front_fields(model)) | set(_front_fields(new_model)))
    idx = [names.index(r) for r in refs]
    samples: dict[tuple, list[list[str]]] = {}
    for (flds,) in col.db.all("select flds from notes where mid = ?", model["id"]):
        vals = flds.split("\x1f")
        key = tuple(bool(vals[i].strip()) for i in idx)
        bucket = samples.setdefault(key, [])
        if len(bucket) < per_pattern:
            bucket.append(vals)
    tmp = tempfile.mkdtemp(prefix="card_redesign_check_")
    scratch = Collection(os.path.join(tmp, "check.anki2"))
    try:
        m = copy.deepcopy(model)
        m["id"] = 0
        scratch.models.add_dict(m)
        nt = scratch.models.by_name(model["name"])
        for bucket in samples.values():
            for vals in bucket:
                note = scratch.new_note(nt)
                for i, v in enumerate(vals[:len(note.fields)]):
                    note.fields[i] = v
                scratch.add_note(note, 1)
        before = {nid: sorted(c.ord for c in scratch.get_note(nid).cards()) for nid in scratch.find_notes("")}
        if details is not None:  # pattern -> card ords the current templates make
            keys = [key for key, bucket in samples.items() for _ in bucket]
            details["idx"] = idx
            details["ords"] = {k: set(before[nid]) for k, nid in zip(keys, sorted(before))}
        nt = scratch.models.by_name(model["name"])
        for t, n in zip(nt["tmpls"], new_model["tmpls"]):
            t["qfmt"], t["afmt"] = n["qfmt"], n["afmt"]
        scratch.models.update_dict(nt)
        after = {nid: sorted(c.ord for c in scratch.get_note(nid).cards()) for nid in before}
    finally:
        scratch.close()
        shutil.rmtree(tmp, ignore_errors=True)
    changed = [nid for nid in before if before[nid] != after[nid]]
    if changed:
        raise ValueError(f"The new card fronts would add or remove cards for {len(changed)} of {len(before)} "
                         f"sample notes; nothing was changed.")
    return f"ok: {len(before)} sample notes across {len(samples)} field patterns keep exactly their cards"


def count_missing_cards(col, model: dict, details: dict) -> int:
    """Notes that lack a card the current templates would generate (saving them would re-create it)."""
    idx, expected = details["idx"], details["ords"]
    have: dict[int, set[int]] = {}
    for nid, ord_ in col.db.all("select c.nid, c.ord from cards c join notes n on n.id = c.nid where n.mid = ?",
                                model["id"]):
        have.setdefault(nid, set()).add(ord_)
    missing = 0
    for nid, flds in col.db.all("select id, flds from notes where mid = ?", model["id"]):
        vals = flds.split("\x1f")
        key = tuple(bool(vals[i].strip()) for i in idx)
        if expected.get(key, set()) - have.get(nid, set()):
            missing += 1
    return missing


def _prepare_templates(col, lang: str, model: dict) -> dict:
    new = LANGS[lang].build_templates(model)  # raises ValueError if the note type isn't the expected one
    return new


def _merge_plan(col, lang: str, model: dict, rep: "Report") -> list:
    if lang != "jp":
        return []
    plan = jp.plan_merges(col, model)
    rep.merged_groups = len(plan)
    rep.merged_notes = sum(len(g.others) for g in plan)
    others = [n for g in plan for n in g.others]
    rep.merged_cards = sum(col.db.scalar(f"select count() from cards where nid in ({','.join(map(str, others[i:i + 900]))})")
                           for i in range(0, len(others), 900)) if others else 0
    names = fieldnames.canonical_names(model, "jp")
    for g in plan[:sample_n(rep)]:
        def reading(nid):
            return dict(zip(names, col.get_note(nid).fields)).get("Reading", "")
        rep.merge_samples.append(f"{g.word}: {reading(g.primary)} + " + ", ".join(reading(n) for n in g.others))
    return plan


def sample_n(rep) -> int:
    return 30


def _do_merges(col, model: dict, plan: list) -> None:
    """Fold every group into its main note: other readings listed, personal notes kept, other notes removed."""
    fmap = fieldnames.resolve(model, "jp")
    names = fieldnames.canonical_names(model, "jp")
    act = lambda c: fmap.get(c, c)  # noqa: E731
    gone = []
    for g in plan:
        main = col.get_note(g.primary)
        others = [dict(zip(names, col.get_note(n).fields)) for n in g.others]
        main[act("RecognitionAlternativesHTML")] = jp.homographs_html(others)
        extra = [f'<b>{o.get("Reading", "")}:</b> {o["PersonalNotes"]}' for o in others if o.get("PersonalNotes", "").strip()]
        if extra:
            pn = main[act("PersonalNotes")]
            main[act("PersonalNotes")] = "<br>".join([pn] + extra if pn.strip() else extra)
        col.update_note(main)
        gone += g.others
    for i in range(0, len(gone), BATCH):
        col.remove_notes(gone[i:i + BATCH])


def dry_run(col, lang: str, sample: int = 20, progress=None) -> Report:
    rep, model, _ = _scan(col, lang, sample, progress, collect_notes=False)
    _merge_plan(col, lang, model, rep)
    try:
        new = _prepare_templates(col, lang, model)
        details: dict = {}
        rep.card_check = check_card_generation(col, model, new, details=details)
        rep.missing_cards = count_missing_cards(col, model, details)
    except ValueError as e:
        rep.template_error = str(e)
    return rep


def apply(col, lang: str, template_backup_dir: str, progress: Callable[[int, int], None] | None = None,
          sample: int = 20) -> Report:
    model = find_model(col, lang)
    # 1. everything that can fail is checked before the first write
    new = _prepare_templates(col, lang, model)
    layout_changes = ([(t["qfmt"], t["afmt"]) for t in new["tmpls"]] != [(t["qfmt"], t["afmt"]) for t in model["tmpls"]]
                      or new["css"] != model["css"])
    details: dict = {}
    card_check = check_card_generation(col, model, new, details=details) if layout_changes else None
    if details:
        missing = count_missing_cards(col, model, details)
        if missing:
            raise ValueError(f"{missing:,} notes are missing a card that Anki would re-create when the note is "
                             "saved (for example after Tools > Empty Cards). Nothing was changed.")
    path = None
    if layout_changes:
        os.makedirs(template_backup_dir, exist_ok=True)
        path = os.path.join(template_backup_dir, f"{lang}-templates-{time.strftime('%Y%m%d-%H%M%S')}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(model, f, ensure_ascii=False, indent=1)
    # 2. writes: fonts first (harmless on their own, and a failure here leaves every note untouched)
    fonts_installed = fonts.install(col, lang)
    mrep = Report(lang=lang, model=model["name"])
    plan = _merge_plan(col, lang, model, mrep)
    if plan:                                              # Japanese: one note per written form
        c0 = col.card_count()
        _do_merges(col, model, plan)
        if col.card_count() != c0 - mrep.merged_cards:
            raise ValueError(f"Merging removed {c0 - col.card_count():,} cards, expected {mrep.merged_cards:,}. "
                             "Restore Anki's backup made before this run.")
    rep, model, changed = _scan(col, lang, sample, progress, collect_notes=True)
    rep.card_check, rep.template_backup, rep.fonts_installed = card_check, path, fonts_installed
    for k in ("merged_groups", "merged_notes", "merged_cards", "merge_samples"):
        setattr(rep, k, getattr(mrep, k))
    cards_before = col.card_count()
    for i in range(0, len(changed), BATCH):
        col.update_notes(changed[i:i + BATCH])
        if progress:
            progress(min(i + BATCH, len(changed)), len(changed))
    if layout_changes:
        col.models.update_dict(new)
        rep.templates_updated = True
    if rep.form_card_nids:
        ids = col.db.list(f"select id from cards where ord = 1 and nid in ({','.join(map(str, rep.form_card_nids))})")
        if len(ids) != rep.removed_cards:
            raise ValueError(f"Expected {rep.removed_cards:,} Taiwan-form cards to remove, found {len(ids):,}. "
                             "Restore Anki's backup made before this run.")
        col.remove_cards_and_orphaned_notes(ids)   # cards 1 and 3 stay, so no note is ever orphaned
    expected = cards_before + rep.new_cards - rep.removed_cards
    if col.card_count() != expected:
        raise ValueError(f"Card count changed from {cards_before:,} to {col.card_count():,} "
                         f"(expected {expected:,}). Restore Anki's backup made before this run.")
    return rep


def restore_templates(col, backup_json: str) -> None:
    with open(backup_json, encoding="utf-8") as f:
        old = json.load(f)
    model = col.models.get(old["id"])
    if model is None or [t["name"] for t in model["tmpls"]] != [t["name"] for t in old["tmpls"]]:
        raise ValueError("The backup does not match the current note type")
    for t, o in zip(model["tmpls"], old["tmpls"]):
        t["qfmt"], t["afmt"] = o["qfmt"], o["afmt"]
    model["css"] = old["css"]
    col.models.update_dict(model)
