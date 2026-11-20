# Card redesign – Chinese, Japanese, Vietnamese (design, 2026-11-16)

Status: **approved 2026-11-16 13:41**, including the five calls listed at the end. Next: implementation plan.

## Why
The answer side of the Chinese cards got harder to read after several rounds of changes (v5.5 → v5.7, the last ones made with ChatGPT/Codex). The v5.7 back template is mostly a ~200-line script that rearranges the HTML stored in the fields while you review. That's why:
- the pinyin sits under "Meanings" (it's stored inside `DefinitionsHTML`),
- the same sentence appears two or three times (simplified, traditional, "Device voice" copy),
- a Wiktionary phrase (高興得了不得) shows up as a mismatched "example",
- source/licence notes show up all over the card (7 of them on 高兴).

The goal is a card that helps you learn: the word, how it sounds, what it means and how it's used, in that order. Everything else goes out of the way. It should look and behave the same across all three languages, and be hard to break.

## What you decided
- **Approach:** first clean the field contents with an add-on, then use a simple template with no layout script (the "approach 2" you picked).
- **Chinese – both scripts:** you're learning simplified **and** traditional, so they get equal weight.
- **Chinese cards per word:** keep the current three: Simplified → Meaning, Traditional → Meaning (only when the scripts differ), Meaning → Chinese. On the production card, the front asks for both forms when they differ, and the back shows both at the same size.
- **Order on the back:** characters → meanings → extra definitions → examples.
- **All three languages** get the same layout. Chinese goes first as the model.

## Goals
1. The back reads top to bottom in learning order with one clear visual hierarchy.
2. Simplified and traditional are equally prominent (Chinese).
3. Examples have one consistent format: sentence with the word highlighted, reading, translation, play button.
4. Sources, licences, stroke order and other reference material sit in one fold at the bottom.
5. Readable on desktop, phone and in night mode.

## Non-goals
- No change to scheduling, review history, decks, presets, card count or which cards exist.
- No new content (writing missing examples is a separate job, already on the to-do list).
- The front sides keep their current question. They're only restyled, plus the "write both" hint.

## Anti-goals (a failure even if it "works")
- **Forcing a one-way full sync.** Adding, removing or renaming fields or card types forces one. So no field or card-type changes: the new layout uses only the existing fields and card types.
- Losing anything you wrote (Notizen, PersonalNotes, UserMnemonic) or any audio file.
- Dropping source/licence info completely. It moves into the bottom fold.
- Losing review progress or due dates on any card.
- A layout that depends on a script rearranging the card at review time.

## Approaches considered
| | Approach | Trade-off | Result |
|---|---|---|---|
| 1 | New template only, fields untouched | Fast, but still needs a script to untangle field HTML, the same fragility as now | rejected |
| **2** | **Clean field contents with an add-on, then a simple template** | More work, and touches every note, but stable and consistent across languages | **chosen** |
| 3 | Brand-new note types, notes moved over | Cleanest schema, but forces a full sync and risks review data | rejected |

## Layout (answer side, all three languages)

```
┌───────────────────────────────────────────┐
│   高兴              高興                   │  Chinese: both scripts, equal size,
│   simplified        traditional            │  small caption under each
│                                            │  (same in both → shown once, tag
│   gāo xìng   ▶                             │   "same in both scripts")
├───────────────────────────────────────────┤
│   happy · glad                     adj.    │  main meanings (2–4), large
│   also: willing (to do sth); cheerful mood │  extra definitions, smaller;
│                                            │  long lists fold after ~4 lines
├───────────────────────────────────────────┤
│   很高兴认识你。 ▶                          │  up to 3 examples, word highlighted
│   Hěn gāoxìng rènshi nǐ.                   │  reading, smaller
│   Pleased to meet you.                     │  translation
│   ▸ more examples (n)                      │
├───────────────────────────────────────────┤
│   Notizen / Mnemonic (if any)              │  your own notes, always visible
├───────────────────────────────────────────┤
│   ▸ More: other spellings · classifiers ·  │  one fold, closed by default
│     stroke order · level · sources         │
└───────────────────────────────────────────┘
```

Per language:
- **Chinese:** the head shows both scripts. The reading row has pinyin with tone marks and one play button. Audio attribution moves into the fold.
- **Japanese:** the head shows the word (kanji) large, with the kana reading underneath (in the reading row, the same place as pinyin), and the part of speech as a small tag. KanjiVG stroke order and "other entries with this spelling" go into the fold.
- **Vietnamese:** the head shows the word large. The reading row has the play button, with IPA/regional pronunciation folded. "Complete the expression" and pronunciation production cards keep their fronts.

Production cards (all languages): the back puts the target word in the head first. The rest of the back is the same as on the recognition card.

## Data clean-up (the add-on)
A new add-on, "Card Redesign", in `Downloads/ANKI/Claude/Add-ons/Card_Redesign/` (source + tests + .ankiaddon). It:
1. **Makes a backup first** and refuses to run without one.
2. **Dry run:** reads every note of the three note types and writes a report (counts, ~20 before/after samples per language, anything it couldn't parse). Changes nothing.
3. **Apply:** rewrites field **contents only** into one fixed, simple HTML structure:
   - meanings: main meanings and extra definitions as two separate lists. The reading is taken out of the meanings field (Chinese pinyin stays only in `PinyinMarked`).
   - examples: one block per example with fixed parts (sentence, reading, translation, audio, source). Mirrored/duplicate examples merge into one. Entries that aren't sentences (e.g. 高興得了不得) are dropped from examples. Example sources are collected in one closed "sources" block at the end of the examples field.
   - reference material (spellings, classifiers, notes, lookups, recording sources) keeps its own fields, cleaned to the same simple markup.
   - never touches `Notizen`, `PersonalNotes` or `UserMnemonic`, scheduling or media files.
4. Installs the new templates and CSS (same card types, same fields), with the old templates saved to a JSON backup.
5. Can be run again safely (does nothing to an already-clean note), and can restore the old templates.

Rollout: Chinese on a **copy of the collection** first, with screenshots of ~10 test words (高兴, 就, 考, 人, a long-definition word, a word with no examples, a production card…) at desktop and phone width, light and dark. You look at those before anything touches the live collection. Then the live run, then Japanese, then Vietnamese, the same way each time.

## Constraints
- Anki 25.09 desktop plus mobile clients. Plain HTML/CSS. The only script left is the existing stroke-order loader, which runs only when you open that fold.
- No other tool (Codex/ChatGPT) edits these note types while this runs, or the two will overwrite each other.
- All outputs go in the dedicated `Downloads/ANKI/Claude/` folder.

## Calls I made (check these)
1. **Example script on Chinese cards:** examples appear in the script of the card you're reviewing (traditional card → traditional sentences; simplified and production cards → simplified). You see both over your three cards, and each sentence appears only once.
2. **3 examples shown**, the rest behind "more examples".
3. **Main meanings = first 2–4 learner meanings**, the rest under "also".
4. **No field or card-type changes**, to avoid a full sync.
5. Your own notes are **visible** (not folded), after the examples.

## Left to the builder
Exact CSS (colours, fonts, spacing within the dark/light themes), class names, the parser for each old field format, and the test harness.
