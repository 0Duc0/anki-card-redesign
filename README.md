# Card Redesign for Anki

One clean, consistent card layout for three large vocabulary decks — Chinese (CC-CEDICT), Japanese (JMdict)
and Vietnamese (v8) — plus a safe **deck updater** that brings in better meanings, more example sentences and
new words without touching your own notes or your learning progress.

| Chinese | Japanese | Vietnamese |
|---|---|---|
| ![Chinese card](docs/screenshots/cn-dongku.png) | ![Japanese card](docs/screenshots/jp-kimochi.png) | ![Vietnamese card](docs/screenshots/vn-thuong-after.png) |

## What the layout does

- The script asked on the front stays on top of the back. Chinese shows Taiwan and Mainland forms together
  (traditional first on the production card), Japanese shows kanji with the reading, Vietnamese the word with
  its part of speech.
- The main meanings come first, in the order they are actually used; rarer senses are folded under *also*.
- Up to three example sentences, each labelled with the meaning it shows, the word highlighted, audio
  (text-to-speech) per sentence and, for Chinese, pinyin behind a button. More examples are folded.
- Your own notes and mnemonics, then one *More* fold with spellings, stroke order, recordings, links and sources.
- Same fields and card types as before, so applying it never forces a full sync.

Design notes: [docs/design.md](docs/design.md) · per-language plans: [Chinese](docs/plan-chinese.md),
[Japanese & Vietnamese](docs/plan-jp-vn.md).

## The dialog

![Card redesign dialog](docs/screenshots/dialog.png)

*Tools › Card redesign…* has two parts.

**Card layout** – *Dry run* checks every note and writes a report (changes nothing); *Back up and apply* makes
a full Anki backup, cleans the note contents and installs the layout; *Restore old layout* puts back the saved
templates.

**Deck update** – applies an update file from
[anki-language-decks](https://github.com/0Duc0/anki-language-decks/releases):

1. *Choose file…* – e.g. `vietnamese-update-2026-11-20.json.gz`.
2. *Check* – compares the update with your collection and shows what would change. Nothing is written.
3. *Back up and apply* – Anki makes a full backup first; then the fields are updated and new words are added to
   the deck you picked.
4. *Undo an update…* – puts the fields back from the undo file written during the update.

### Why the updater is safe

- Notes are matched by their GUID (with the word as a fallback), so renamed decks or moved notes are found.
- Every changed field carries a fingerprint (SHA-1) of the content the update was made from. If you edited the
  field since, it does not match and **your version is kept**.
- Personal fields (`PersonalNotes`, `Notizen`, `Mnemonic`, `UserMnemonic`, `Eigene_Merkhilfe`) are never written.
- Review history, due dates, intervals, flags, tags and the deck of existing cards stay as they are.
- New words get stable GUIDs: applying the same update twice adds nothing, and a later update recognises them.
- The undo file is written while the update runs, so even an interrupted update can be undone. Undo keeps
  fields you changed afterwards and new words you have already studied.

Tested at full size on copies of the real collections: 22,221 Vietnamese notes and 2,882 new words in about
15 seconds; schedule unchanged, database integrity check clean, undo returns exactly the original.

## Install

Download `card_redesign-<version>.ankiaddon` from the [latest release](../../releases/latest), double-click it
(or *Tools › Add-ons › Install from file…*) and restart Anki. Requires Anki 25.09 or newer.

## Development

```
pip install anki aqt pytest beautifulsoup4
python -m pytest tests            # 114 tests; fixtures in tests/fixtures.zip
python -I tools/package.py dist/card_redesign-2.0.0.ankiaddon
```

| Path | |
|---|---|
| `card_redesign/cn.py`, `jp.py`, `vn.py` | per-language note cleaning |
| `card_redesign/*_templates.py`, `templates/` | card templates and CSS |
| `card_redesign/updater.py` | deck update: plan, apply, undo |
| `card_redesign/ui.py` | the Tools dialog |
| `card_redesign/fonts/` | bundled fonts (SIL Open Font License, see the OFL files) |
| `tools/render.py`, `tools/corpus_check.py` | render cards to HTML / check example corpora |

## License

Personal project, no license granted. Bundled fonts keep their SIL Open Font License (`card_redesign/fonts/OFL-*.txt`).
