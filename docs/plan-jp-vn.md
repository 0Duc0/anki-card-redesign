# Card Redesign – Japanese + Vietnamese (plans 2 and 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, chosen by the user). Steps use checkbox syntax.

**Goal:** Extend the Card Redesign add-on to the Japanese (JMdict v1.17, 59,601 notes) and Vietnamese (v8, 31,852 notes) note types with the same layout and safety as Chinese.

**Architecture:** Shared helpers move from `cn.py` to `common.py` (no behaviour change for Chinese). `jp.py` / `vn.py` clean fields; `jp_templates.py` / `vn_templates.py` build fronts, backs and CSS; `runner.LANGS` gains `jp` and `vn`, so dry run, template checks, the card-generation check and the per-note safety net apply unchanged. The dialog enables all three languages.

**Spec:** `docs/design.md` (approved) plus the Chinese decisions the user made on 2026-11-16: the script/word asked on the front stays in the same place on the back; smaller headword; examples = ONE closed "Examples (n)" dropdown, each example a main line plus one compact line; no other example fold; short phrases kept after sentences.

## Global Constraints
- No field or card type added/removed/renamed; `scm` and card count unchanged (existing runner checks).
- Never write `PersonalNotes` (JP), `Notizen` (VN), `MainMeaning`, `English`, `ProductionPrompt`, `RecognitionHintHTML`, `RecognitionAlternativesHTML`, `Reading`, `Word`, `Vietnamese` (fronts and the search add-on read them).
- Written fields: JP `MainSenses`, `AllDefinitions`, `ExampleJP`; VN `DetailsHTML`, `ExampleVietnamese`. `ExampleEN`, `ExampleEnglish`, `ExampleSource` stay untouched and are no longer shown (their content is carried into the examples block).
- Back order: mode line → headword (same class/size as the front) → reading + play + part-of-speech tag → meanings (≤ 4 all main, else 3 main + "also" + fold after 6) → usage line (JP) → Examples dropdown (closed) → own notes → More fold.
- JP example: Japanese sentence main line (word highlighted) + compact line with the English. VN example: Vietnamese main line + compact line with the English. Sense caption only when the examples cover more than one sense.
- Every example's sources are collected in one small "Sources" line at the end of the examples dropdown.
- Outputs: same repo/branch; package copied to `~/Downloads/ANKI/Claude/Add-ons/Card_Redesign/`.

## Review Focus
1. Japanese verbs/adjectives conjugate inside sentences (食べていく): highlight must never break markup; no highlight is fine.
2. Notes with examples only in `AllDefinitions` (with audio) and the same sentence in `MainSenses` (without): merged once, audio kept.
3. VN notes without an "English meanings" section (646 + 10,696 without examples): meanings fall back to `English`; nothing rendered empty.
4. VN `DetailsHTML` disclosures other than "English meanings" (IPA, Vietnamese definitions, compounds…) are kept verbatim.
5. Unrecognised shapes are left unchanged and reported (safety net), across all written fields of a note together.

---

### Task 1: Shared helpers (`common.py`), Chinese unchanged
- Move `MARK`, `is_clean`, `AUDIO_RE`, `count_audio`, `_esc`, `_glosses`, `_meanings_html`, `_norm`, `_words`, `LABEL_WORDS` to `source/common.py`; `cn.py` imports them.
- Add `SimpleEx` (`text`, `translation`, `audio: list[str]`, `key`, `phrase`, `notes`, `lang`) and `render_examples(exs, highlight: Callable[[str], str], sources: list[str]) -> str` producing `<details class="cr-v1 cr-ex" data-multi=…><summary>Examples (n)</summary>EX…[<p class="ex-src">Sources: …</p>]</details>`, EX = `<div class="ex[ ex-phrase]">[ex-k]<div class="ex-row"><div class="ex-s ex-main" lang=…>…</div>[ex-a]</div>[<div class="ex-sub"><span class="ex-t">…</span></div>][ex-n]</div>`.
- Test: the full existing suite stays green (64); new `tests/test_common.py::test_render_examples_shape`.

### Task 2: Japanese cleaner
- Fixtures from `/home/claude/data/jp.sqlite` (`tools/make_fixtures_jp.py`): 食べる, 気持ち, first note with > 4 sense titles, first with AllDefinitions examples, first without any example, first with RecognitionAlternativesHTML.
- `jp.clean_note(fields, ctx=None) -> NoteResult`: `MainSenses` → `cr-defs` with sense titles; `AllDefinitions` → `cr-dict` sense list without examples; `ExampleJP` → examples block from MainSenses `.example/.example-en`, `v2-example` sections, AllDefinitions `.study-meaning-example`, and the old ExampleJP/ExampleEN pair; duplicates merged (human `[sound:]` preferred). Safety net over all written fields together.
- Tests: 食べる has main ["to eat", "to live on (e.g. a salary); to live off"], 2 examples, each once, audio kept; 気持ち examples include the v2 sentence with `<strong>` kept; idempotent; unknown HTML → unrecognised; audio balance.

### Task 3: Japanese templates
- `build_jp_templates(model)`: requires card types `["JP → EN", "EN → JP"]` and the `{{#StrokeOrder}}…{{/StrokeOrder}}` block in the old back (copied verbatim into More). Fronts restyled with the same mode/headword classes as the back. More: Other written forms, Other entries with this spelling, Full dictionary entry (`AllDefinitions`), Kanji stroke order, Level & sources.
- Tests: head word same class front/back; no Furigana ruby in head; reading row has `Reading`; examples dropdown closed; `PersonalNotes` visible as "Notizen"; v1.17 model applies with the card check passing.

### Task 4: Vietnamese cleaner
- Fixtures from `/home/claude/data/vn.sqlite`: ăn, nhà, first without "English meanings", first with only ExampleVietnamese, first with nothing.
- `vn.clean_note`: `DetailsHTML` → `cr-defs` (definitions of the "English meanings" senses, usage labels kept) + `<details class="cr-dict"><summary>Full dictionary entry</summary>` holding every other disclosure verbatim; `ExampleVietnamese` → examples block from ExampleVietnamese/ExampleEnglish (+ audio token from ExampleSource) and the English-meaning `sense-example`s.
- Tests: ăn main = first 3 definitions + also; examples include "ăn thịt — to eat meat; to be carnivorous"; "Regional IPA" disclosure kept verbatim; nothing-note unchanged; idempotent; safety net.

### Task 5: Vietnamese templates
- `build_vn_templates(model)`: requires `["Vietnamese → English", "English → Vietnamese"]`; production front keeps both branches (complete-the-expression / pronunciation). Meanings fall back to `{{English}}` when DetailsHTML has no `cr-defs`. More: Recordings & audio sources, Frequency · Tier, Sources.
- Tests mirror Task 3.

### Task 6: Corpus checks, screenshots, UI, package
- `tools/corpus_check.py <collection> <lang>`: JP and VN: unrecognised ≤ 0.5 %, audio balanced, card check ok, second apply no-op.
- Render 食べる, 気持ち, ăn, nhà (+ edge fixtures), both cards, phone + desktop dark; send to the user.
- Dialog lists Chinese, Japanese, Vietnamese; package and copy to the Mac.

### Task 7: Independent review of the branch, fix pass, then the live run with the user (dry run first).
