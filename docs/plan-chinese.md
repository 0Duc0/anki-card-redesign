# Card Redesign – Chinese (plan 1 of 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An Anki add-on ("Card Redesign") that rewrites the Chinese note contents into one simple HTML structure and installs a new script-free answer layout, without touching scheduling or the note type's schema.

**Architecture:** Pure-Python cleaners (stdlib only, no Anki imports) turn old field HTML into new field HTML. A runner applies them to a collection (dry run / apply / restore templates). A template builder writes new fronts, backs and CSS into the existing three card types. A thin Qt UI wraps the runner. Japanese and Vietnamese later reuse `html.py`, `runner.py` and `base.css` (plans 2 and 3).

**Tech Stack:** Python 3.12+, stdlib `html.parser`; `anki` 26.x from PyPI for tests (live Anki is 25.09); pytest; Playwright (Chromium) for screenshots.

**Spec:** project doc `claude/card-redesign-design.md` (approved 2026-11-16).

## Global Constraints
- No field or card type may be added, removed, renamed or reordered (that forces a one-way full sync). Test: `col.db.scalar("select scm from col")` is unchanged after apply.
- Never modify `Notizen`, `UserMnemonic`, any card's scheduling, decks, presets or media files.
- Back layout order: head (both scripts + pinyin + audio) → meanings → extra definitions → examples → own notes → one closed "More" fold.
- Simplified and traditional are the same size. Captions: `simplified` / `traditional`. When ScriptDiff is empty (identical scripts), the word is shown once with the caption `same in both scripts`.
- Card 3 front shows `Write both: simplified + traditional` when `ScriptDiff` is non-empty.
- Examples: at most 3 visible, the rest in `<details>` "More examples (n)". Each sentence shows in the card's script: card 2 → traditional, cards 1 and 3 → simplified, "both" when only one script is known.
- Main meanings: if a reading has ≤ 4 glosses, all are main; otherwise the first 3 are main and the rest go under "also". More than 6 "also" glosses → the remainder goes in a fold "more meanings (k)".
- No layout JavaScript. The only script kept is the existing Hanzi Writer stroke-order block, moved verbatim into the More fold.
- Output folder on the Mac: `~/Downloads/ANKI/Claude/Add-ons/Card_Redesign/` (`source/`, `tests/`, `tools/`, `card_redesign.ankiaddon`). Work repo in the VM: `/home/claude/work/Card_Redesign` (git).
- Test corpus: `/home/claude/data/cn55.sqlite` (29,924 real Chinese notes, same 30 fields as live v5.7).

## Review Focus
1. **Multi-reading entries** (e.g. 了, 你 with `form-head` "Written 妳 (traditional)"): every reading keeps its own pinyin label and form label. The pinyin label is hidden only when the note has exactly one reading. → test in Task 2.
2. **Identical-script words** (`ScriptDiff` empty, e.g. 人): the head shows one word with `same in both scripts`, the examples have `data-script="both"`, and no "Write both" appears. → tests in Tasks 3 and 4.
3. **Unknown or hand-edited field HTML:** a field the cleaner can't fully recognise is left exactly as it was and listed in the report. Content is never silently lost. → test in Task 3.
4. **Audio tokens:** every `[sound:…]` and `[anki:tts…]…[/anki:tts]` survives, except in examples dropped as non-sentences, and those are counted in the report. → test in Task 3, corpus check in Task 5.
5. **Empty fields:** a note with no examples or no other reference fields renders no empty boxes or headings. → test in Task 4.

---

### Task 1: Repo scaffold and mini HTML tree

**Files:**
- Create: `source/manifest.json`, `source/__init__.py` (empty placeholder), `source/html.py`, `tests/test_html.py`, `pytest.ini`, `.gitignore`

**Interfaces:**
- Produces:
  - `parse(fragment: str) -> Node`: root node, lossless for the tag soup used in these fields (void tags `br`, `img`; text kept exactly, including `[sound:…]` tokens).
  - `Node`: `.tag: str | None` (None = text), `.attrs: dict[str, str]`, `.children: list[Node]`, `.text` (for text nodes), `.classes -> set[str]`, `find_all(cls: str | None = None, tag: str | None = None) -> list[Node]` (depth-first), `find(cls=None, tag=None) -> Node | None`, `text_content() -> str`, `inner_html() -> str`, `outer_html() -> str`.
  - `serialize(nodes: list[Node]) -> str`

- [ ] **Step 1:** `git init /home/claude/work/Card_Redesign`, add `manifest.json` `{"package": "card_redesign", "name": "Card Redesign (by Claude)", "min_point_version": 250900}` and `pytest.ini` with `pythonpath = source`.
- [ ] **Step 2: Write failing tests** in `tests/test_html.py`:
  - `test_roundtrip_exact`: for the 高兴 `ExampleSentence` and `DefinitionsHTML` strings (copy them from `cn55.sqlite` into `tests/fixtures/cn/gaoxing.json`), `serialize(parse(s).children) == s`.
  - `test_find_by_class`: `len(parse(gaoxing_examples).find_all("ex")) == 2`, `parse(...).find("v2-sense").text_content() == "gāo xìng · glad; happy; pleased; delighted"`.
  - `test_sound_token_is_text`: `parse("<b>x</b>[sound:a.mp3]").children[1].text == "[sound:a.mp3]"`.
- [ ] **Step 3:** Run `pytest tests/test_html.py -v`. Expected: FAIL (module missing).
- [ ] **Step 4:** Implement `source/html.py` on `html.parser.HTMLParser` with `convert_charrefs=False`. Keep entity and char refs as raw text so the round trip is exact.
- [ ] **Step 5:** Run the tests. Expected: PASS.
- [ ] **Step 6:** Commit `feat: scaffold and mini HTML tree`.

### Task 2: Chinese meanings cleaner (+ fixtures)

**Files:**
- Create: `tools/make_fixtures.py`, `tests/fixtures/cn/*.json`, `source/cn.py`, `tests/test_cn_definitions.py`

**Interfaces:**
- Consumes: `html.parse`, `Node` (Task 1)
- Produces:
  - `MARK = "cr-v1"`: class on the root element of every cleaned field. A field that starts with `<div class="cr-v1` is already clean and is returned unchanged.
  - `clean_definitions(html: str) -> str | None`: returns new HTML, or `None` if the input isn't recognised.
  - Output shape: `<div class="cr-v1 cr-defs" data-readings="N">` then per reading `<section class="r"><div class="r-py">gāo xìng</div>[<div class="r-form">traditional: <span lang="zh-Hant">妳</span></div>]<ol class="m-main"><li>…</li></ol>[<p class="m-also"><span>also</span> a; b; c</p>][<details class="m-fold"><summary>more meanings (k)</summary><p>…</p></details>]</section>`, then `</div>`. Inner HTML of each `<li>` (`inline-pinyin`, `script-variants` spans) is kept verbatim.

- [ ] **Step 1:** Write `tools/make_fixtures.py <sqlite> <out_dir>`: for these keys (Simplified field) it dumps all 30 fields as JSON: `高兴` (two `.ex` + a non-sentence v2), `的` (v2 with `v2-alternate`), `你` (`form-head`, 2 readings), `了` (multi-reading), `人` (ScriptDiff empty), `振作` (old plain-sentence format + `example-translation` in ExampleTranslation), plus the first note with `OrthographyHTML`, the first with `ClassifiersHTML`, the first with an empty `ExampleSentence`, and the first whose `DefinitionsHTML` has > 10 glosses. Run it on `cn55.sqlite`. Commit the fixtures.
- [ ] **Step 2: Write failing tests:**
  - `test_gaoxing_main_all_four`: 4 glosses → `m-main` has 4 `<li>` (happy, glad, willing (to do sth), in a cheerful mood), no `m-also`.
  - `test_long_entry_splits_3_also_fold`: for the >10-gloss fixture, `m-main` has 3 items, `m-also` has 6 glosses joined by `"; "`, `m-fold` summary is `more meanings (k)` with k = total − 9.
  - `test_ni_keeps_two_readings_and_forms`: `data-readings="2"`, two `r-form` with 你 and 妳.
  - `test_idempotent`: `clean_definitions(clean_definitions(x)) == clean_definitions(x)`.
  - `test_unknown_returns_none`: `clean_definitions("<table><tr><td>x</td></tr></table>") is None`.
- [ ] **Step 3:** Run them. Expected: FAIL.
- [ ] **Step 4:** Implement `clean_definitions` in `source/cn.py`. A `form-head` applies to the `section.reading` that follows it. The gloss source is the `<li>` children of the section's `<ul>`. Anything else at the top level → `None`.
- [ ] **Step 5:** Run them. Expected: PASS. **Step 6:** Commit `feat(cn): meanings cleaner`.

### Task 3: Chinese examples and sources cleaner

**Files:**
- Modify: `source/cn.py`
- Create: `tests/test_cn_examples.py`

**Interfaces:**
- Consumes: `html.parse` (Task 1), fixtures (Task 2)
- Produces:
  - `clean_examples(examples_html: str, translation_html: str, simplified: str, traditional: str) -> CleanedExamples | None`
  - `@dataclass CleanedExamples: examples: str; sources: str; dropped: list[str]; audio_in: int; audio_out: int`
  - `examples` shape: `<div class="cr-v1 cr-ex">` + up to 3 × `EX` + optional `<details class="ex-more"><summary>More examples (n)</summary>EX…</details>` + `</div>`, where `EX` = `<div class="ex"><div class="ex-s" data-script="simp|trad|both" lang="zh-Hans|zh-Hant">…<b class="hl">word</b>… <span class="ex-a">AUDIO</span></div>[second ex-s for the other script]<div class="ex-r">pinyin</div><div class="ex-t">translation</div></div>`. AUDIO is the original token only, without the "Device voice" label.
  - `sources` shape (written to `ExampleTranslation`): `<div class="cr-v1 cr-src"><ul><li>…</li></ul></div>`. It collects the old plain-text attribution, every `v2-source` link, `example-source` details text, and human-recording link texts, de-duplicated in first-seen order.
- Rules: a `v2-example` whose sentence (whitespace and punctuation removed) equals an `.ex` simplified or traditional sentence is merged (its source kept, the block dropped). A `v2-example` without any of `。！？!?；…」”` and ≤ 8 characters is dropped and recorded in `dropped`. The traditional sentence gets `<b class="hl">` around the first occurrence of `traditional` if it has no highlight. Only one script known → one `ex-s` with `data-script="both"`. Old format (plain sentence + audio in ExampleSentence, translation in `div.example-translation`) becomes one EX with the translation moved in.

- [ ] **Step 1: Write failing tests:**
  - `test_gaoxing_two_examples_one_dropped`: 2 `.ex` in output, `dropped == ["高興得了不得"]`, sources contain `Wiktionary / Kaikki` and `Wiktionary via Kaikki (CC BY-SA)`, and no output text contains `Device voice`.
  - `test_trad_highlight_added`: in 高兴 the second `ex-s` is `很<b class="hl">高興</b>認識你。` plus audio span.
  - `test_de_alternate_gives_both_scripts`: the `v2-alternate` example yields `data-script="simp"` 这是我的钥匙。 and `data-script="trad"` 這是我的鑰匙。.
  - `test_zhenzuo_old_format`: one EX with `data-script="both"`, `ex-t` = "The situation is improving, so cheer up!", and sources contain `tatoeba.org #263782`.
  - `test_more_than_three_folded`: a synthetic input of 5 `.ex` → 3 visible, `More examples (2)`.
  - `test_audio_preserved`: for every fixture, `audio_out == audio_in − len(dropped audio)`. Count tokens with regex `\[sound:[^\]]+\]|\[anki:tts[^\]]*\].*?\[/anki:tts\]`.
  - `test_unknown_html_returns_none`: `clean_examples("<p>my own note</p>", "", "x", "x") is None`.
  - `test_idempotent`.
- [ ] **Step 2:** Run. Expected: FAIL. **Step 3:** Implement in `source/cn.py`. **Step 4:** Run. Expected: PASS. **Step 5:** Commit `feat(cn): examples and sources cleaner`.

### Task 4: Chinese templates and CSS

**Files:**
- Create: `source/templates/base.css`, `source/templates/cn.css`, `source/templates/cn_back.html`, `source/templates/cn_front_1.html`, `cn_front_2.html`, `cn_front_3.html`, `source/cn_templates.py`, `tests/test_cn_templates.py`

**Interfaces:**
- Produces:
  - `build_cn_templates(model: dict) -> dict`: returns a copy with `tmpls[i]["qfmt"/"afmt"]` and `css` replaced. Raises `ValueError` unless there are exactly 3 templates named `1 Simplified → Meaning`, `2 Traditional → Meaning`, `3 Meaning → Hanzi` and the old `afmt` contains `<details class="stroke-tools"`.
  - The back for card i is `cn_back.html` with `{{SCRIPT}}` → `show-simp` (cards 1 and 3) / `show-trad` (card 2) and `{{STROKES}}` → the old stroke block, copied verbatim from `<details class="stroke-tools"` through the end of its following `</script>`.
  - The back uses only the existing field names. Sections are guarded with `{{#Field}}`. Order: head → `DefinitionsHTML` → `ExampleSentence` → `Notizen` / `UserMnemonic` (visible, headed "Notizen" / "Mnemonic") → More. "More" is one `<details class="cr-more"><summary>More</summary>` holding, in order: Other spellings (`OrthographyHTML`), Classifiers, Pronunciation notes (`NotesHTML`), Level & frequency (`MetadataHTML`), Stroke order, Other recordings (`AlternativeHumanAudioHTML`), Dictionary links (`LookupHTML`), Rare Unicode, Sources (`HumanAudioSourceHTML` + `ExampleTranslation`), Raw CC-CEDICT.
  - CSS: `.show-simp [data-script="trad"], .show-trad [data-script="simp"] {display:none}`; `.cr-defs[data-readings="1"] .r-py {display:none}`; light and night themes via `.nightMode`; max width 760px; examples in the card's script.

- [ ] **Step 1: Write failing tests** (render with the `anki` package on a temp collection that holds the 10 fixture notes, already cleaned by Tasks 2–3):
  - `test_head_both_scripts`: 高兴 card 1 answer HTML contains both `simplified` and `traditional` captions, and `高興` sits in an element with the same class as `高兴`.
  - `test_head_same_script`: 人 shows `same in both scripts` once and no `traditional` caption.
  - `test_write_both_on_card3_front`: 高兴 card 3 question contains `Write both: simplified + traditional`. 人's card 3 question doesn't.
  - `test_no_empty_sections`: for the empty-example fixture, the answer contains no `cr-ex` and no `Examples` heading.
  - `test_no_layout_script`: the answer contains exactly one `<script` (the stroke loader).
  - `test_wrong_model_raises`: a model with 2 templates → `ValueError`.
- [ ] **Step 2:** Run. Expected: FAIL. **Step 3:** Implement. **Step 4:** Run. Expected: PASS. **Step 5:** Commit `feat(cn): templates and css`.

### Task 5: Runner (dry run / apply / restore) + corpus check

**Files:**
- Create: `source/runner.py`, `tests/test_runner.py`, `tools/corpus_check.py`

**Interfaces:**
- Consumes: `clean_definitions`, `clean_examples` (Tasks 2–3), `build_cn_templates` (Task 4)
- Produces:
  - `LANGS = {"cn": LangSpec(model_prefix="CC-CEDICT Optimized EN", clean_note=cn.clean_note, build_templates=build_cn_templates)}`
  - `cn.clean_note(fields: dict[str, str]) -> NoteResult` with `changes: dict[str, str]` (changed fields only), `unrecognised: list[str]` (field names), `dropped: list[str]`, `audio_in: int`, `audio_out: int`.
  - `dry_run(col, lang: str, sample: int = 20) -> Report`, `apply(col, lang: str, template_backup_dir: str, progress: Callable[[int, int], None] | None = None) -> Report`, `restore_templates(col, backup_json: str) -> None`
  - `Report` (dataclass, JSON-serialisable): `notes_total, notes_changed, fields_changed: dict[str, int], unrecognised: dict[str, list[int]] (field → note ids, first 50), dropped_examples: int, dropped_samples: list[str], audio_in, audio_out, samples: list[{nid, field, before, after}], templates_updated: bool, template_backup: str | None`
- Notes are written in batches of 500 with `col.update_notes`. Templates are saved with `col.models.update_dict` after the old model JSON is written to `template_backup_dir/cn-templates-YYYYmmdd-HHMMSS.json`.

- [ ] **Step 1: Write failing tests** on a temp copy of a 10-note collection built from the fixtures:
  - `test_dry_run_changes_nothing`: the `mod` of every note and `col.mod` are unchanged, and `report.notes_changed > 0`.
  - `test_apply_keeps_schema_and_scheduling`: `scm` is unchanged; `(id, due, ivl, factor, reps, lapses, queue, type, did)` is identical for all cards; the card count is unchanged.
  - `test_apply_never_touches_personal`: `Notizen`/`UserMnemonic` are byte-identical.
  - `test_apply_twice_second_is_noop`: second `apply` → `notes_changed == 0`.
  - `test_restore_templates`: after `restore_templates`, every `qfmt`/`afmt`/`css` equals the original.
- [ ] **Step 2:** Run. Expected: FAIL. **Step 3:** Implement. **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Corpus check:** `python3 tools/corpus_check.py /home/claude/data/cn55.sqlite` runs `dry_run` over all 29,924 notes. Expected output: `unrecognised` ≤ 0.5 % of notes per field (every case listed), `audio_out == audio_in − dropped audio`, and the dropped samples printed. Fix the cleaners until this holds. Write the summary to `reports/corpus-cn55.json`.
- [ ] **Step 6:** Commit `feat: runner and corpus check`.

### Task 6: Screenshots for your check (checkpoint)

**Files:**
- Create: `tools/render.py`, output `reports/screens/*.png`

**Interfaces:**
- Consumes: `apply` (Task 5) on a temp copy of `cn55.sqlite`.
- `render.py <collection> <out_dir> <word…>`: for each word and each of its cards, writes the question and answer HTML with the model CSS. `[anki:play…]` is replaced with a ▶ glyph. Playwright Chromium screenshots each at 420 px and 900 px wide, light and dark (`<body class="card nightMode">`).

- [ ] **Step 1:** Render 高兴, 的, 你, 了, 人, 振作, the long-entry fixture, the no-example fixture: all cards, 2 widths, 2 themes.
- [ ] **Step 2:** Check every image yourself against the Global Constraints (order, equal script size, ≤3 visible examples, no attribution outside More, no empty boxes). Fix and re-render until all pass.
- [ ] **Step 3:** Send the user a contact sheet (one PNG grid per word) and the corpus summary. **Stop here until the user approves the look.**
- [ ] **Step 4:** Commit `chore: render tool and approved screenshots`.

### Task 7: Anki UI and package

**Files:**
- Modify: `source/__init__.py`
- Create: `source/README.md`, `tools/package.py`; output `card_redesign.ankiaddon`

**Interfaces:**
- Consumes: `dry_run`, `apply`, `restore_templates` (Task 5)
- UI: Tools → "Card redesign…" opens a dialog with a language choice (only Chinese enabled in this plan) and three buttons: **Dry run** (writes the report JSON to `user_files/` and shows counts plus 5 before/after samples), **Back up and apply** (`mw.create_backup_now()` must succeed or nothing happens, then `QueryOp` with progress, then `mw.reset()`), and **Restore old layout** (choose a template backup JSON).

- [ ] **Step 1:** Implement the UI, following the pattern in `Chinese_Deck_Upgrade/source/__init__.py` (QueryOp, progress, report file).
- [ ] **Step 2:** `python3 tools/package.py` zips `source/` (without `__pycache__`, `user_files`) to `card_redesign.ankiaddon`. Expected: the zip contains `__init__.py`, `manifest.json`, `templates/*`.
- [ ] **Step 3:** Copy `source/`, `tests/`, `tools/`, the `.ankiaddon` and `reports/` to `~/Downloads/ANKI/Claude/Add-ons/Card_Redesign/` with `device_commit_files`. Add one line for it to `ANKI/Claude/README.txt`.
- [ ] **Step 4:** Commit `feat: anki ui and package`.

### Task 8: Live run (with the user)

- [ ] **Step 1:** Ask the user to confirm that no other tool (Codex/ChatGPT) is editing the Chinese note type, and that Anki is synced.
- [ ] **Step 2:** Install the add-on (Tools → Add-ons → Install from file, then restart Anki). Run **Dry run** on the live collection. Compare its counts with `corpus-cn55.json`. Any `unrecognised` field that didn't appear in the corpus check → stop, fix, repackage.
- [ ] **Step 3:** With the user's OK: **Back up and apply**. Verify in Anki: open 高兴, 人, 你 in the reviewer/previewer (all cards), check against the screenshots, and check that the deck counts (new/due) are unchanged.
- [ ] **Step 4:** Update the project docs: `claude/chinese-rebuild-status.md` (what ran, report path, template backup path) and the status line of the design doc.
