"""Tools > Card redesign… dialog: card layout (dry run, apply, restore) and deck updates (content packs)."""

import json
import os
import time

from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import (QAction, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                    QPushButton, QVBoxLayout)
from aqt.utils import askUser, showInfo, showWarning

from . import runner, updater

ADDON_DIR = os.path.dirname(__file__)
USER_DIR = os.path.join(ADDON_DIR, "user_files")
LANG_LABELS = {"cn": "Chinese (CC-CEDICT)", "jp": "Japanese (JMdict)", "vn": "Vietnamese (v8)"}


def _exec(d):
    return (getattr(d, "exec", None) or d.exec_)()


def _write_report(rep: "runner.Report", kind: str) -> str:
    os.makedirs(USER_DIR, exist_ok=True)
    path = os.path.join(USER_DIR, f"{kind}-{rep.lang}-{time.strftime('%Y%m%d-%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rep.to_dict(), f, ensure_ascii=False, indent=1)
    return path


def _summary(rep: "runner.Report") -> str:
    lines = [f"Note type: {rep.model}",
             f"Notes: {rep.notes_total:,} · would change / changed: {rep.notes_changed:,}",
             "Fields: " + (", ".join(f"{k} {v:,}" for k, v in rep.fields_changed.items()) or "none")]
    if rep.unrecognised_count:
        lines.append("Left unchanged (not recognised): "
                     + ", ".join(f"{k} {v:,}" for k, v in rep.unrecognised_count.items()))
    else:
        lines.append("Every note was recognised.")
    balanced = rep.audio_out == rep.audio_in - rep.audio_dropped
    lines.append(f"Example audio: {rep.audio_in:,} before · {rep.audio_out:,} after · "
                 f"{rep.audio_dropped:,} duplicate copies merged · {'OK' if balanced else 'CHECK!'}")
    if rep.template_error:
        lines.append(f"NEW LAYOUT CAN'T BE INSTALLED: {rep.template_error}")
    elif rep.card_check:
        lines.append(f"Card check: {rep.card_check}")
        if rep.missing_cards:
            lines.append(f"STOP: {rep.missing_cards:,} notes are missing a card Anki would re-create; "
                         "Back up and apply will refuse to run.")
    if rep.merged_groups:
        lines.append(f"Merged: {rep.merged_groups:,} written forms had several notes -> one note each; "
                     f"{rep.merged_notes:,} notes ({rep.merged_cards:,} cards) become 'Same spelling, other words' "
                     "of the main note (personal notes are kept)")
        if rep.merge_samples:
            lines.append("  e.g. " + " | ".join(rep.merge_samples[:5]))
    if rep.removed_cards:
        lines.append(f"Removed cards: {rep.removed_cards:,} 'Taiwan form → meaning' cards")
    if rep.new_cards:
        lines.append(f"New cards: {rep.new_cards:,} 'Taiwan form → meaning' cards for words whose Taiwan and "
                     "mainland forms differ (same deck as the word's other cards)")
    return "\n".join(lines)


def _progress(label):
    def cb(done, total):
        mw.taskman.run_on_main(lambda: mw.progress.update(label=f"{label}… {done:,}/{total:,}", value=done, max=total))
    return cb


def dry_run(lang: str) -> None:
    def done(rep):
        path = _write_report(rep, "dry-run")
        samples = "\n\n".join(f"• {s['field']} (note {s['nid']})\n  before: {s['before'][:160]}…\n  after:  {s['after'][:160]}…"
                              for s in rep.samples[:5])
        showInfo(f"Dry run – nothing was changed.\n\n{_summary(rep)}\n\nFirst examples:\n\n{samples}\n\n"
                 f"Full report:\n{path}")
    QueryOp(parent=mw, op=lambda col: runner.dry_run(col, lang, progress=_progress("Checking notes")),
            success=done).with_progress("Checking notes…").run_in_background()


def apply(lang: str) -> None:
    if not askUser(f"Apply the new layout to {LANG_LABELS[lang]}?\n\n"
                   "Anki makes a full backup first. Note contents and the card layout change; "
                   "review history, due dates, Notizen and mnemonics stay as they are.\n\n"
                   "Please don't close Anki while it runs."):
        return
    def done(rep):
        path = _write_report(rep, "applied")
        mw.reset()
        showInfo(f"Done.\n\n{_summary(rep)}\n\nCard layout updated: {'yes' if rep.templates_updated else 'no (already new)'}\n"
                 f"Fonts added to the media folder: {', '.join(rep.fonts_installed) or 'none (already there)'}\n"
                 f"Old layout saved to: {rep.template_backup or '–'}\n\nReport: {path}\n\nSync afterwards as usual.")
    def op(col):
        mw.create_backup_now()  # raises on failure, so nothing below runs without a backup
        return runner.apply(col, lang, USER_DIR, progress=_progress("Updating notes"))

    def failed(err):
        mw.reset()
        showWarning(f"The run stopped:\n\n{err}\n\nChecks happen before anything is written, so usually nothing changed. "
                    "If notes were already changed, restore the backup Anki made at the start "
                    "(File > Switch Profile > Open Backup…).")

    QueryOp(parent=mw, op=op, success=done).failure(failed).with_progress(
        "Backing up, then updating notes…").run_in_background()


def restore(parent) -> None:
    path, _ = QFileDialog.getOpenFileName(parent, "Choose a saved layout", USER_DIR, "Layout backup (*-templates-*.json)")
    if not path:
        return
    if not askUser("Put back the card layout from this file?\n\nNote contents stay as they are now "
                   "(use Anki's backup to restore those)."):
        return
    try:
        runner.restore_templates(mw.col, path)
    except Exception as e:
        showWarning(f"Could not restore the layout:\n{e}")
        return
    mw.reset()
    showInfo("The previous card layout is back.")


class UpdatePanel(QGroupBox):
    """Deck update: pick a content pack, check it, back up and apply, or undo an earlier update."""

    def __init__(self, parent) -> None:
        super().__init__("Deck update (new meanings, example sentences, new words)")
        self.parent_dialog = parent
        self.pack = None
        self.plan = None
        lay = QVBoxLayout(self)
        intro = QLabel("Apply an update file (<i>*.json.gz</i>) from the anki-language-decks project. Only fields "
                       "you have not changed yourself are updated; your notes, mnemonics, review history and "
                       "due dates are never touched. New words go into the deck chosen below.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QFormLayout()
        row = QHBoxLayout()
        self.file_label = QLabel("No file chosen")
        self.file_label.setWordWrap(True)
        pick = QPushButton("Choose file…")
        pick.clicked.connect(self.choose)
        row.addWidget(self.file_label, 1)
        row.addWidget(pick)
        form.addRow("Update:", row)
        self.deck = QComboBox()
        self.deck.setEnabled(False)
        form.addRow("New words go to:", self.deck)
        lay.addLayout(form)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        buttons = QHBoxLayout()
        self.check_btn = QPushButton("Check")
        self.apply_btn = QPushButton("Back up and apply")
        undo_btn = QPushButton("Undo an update…")
        self.check_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)
        self.check_btn.clicked.connect(self.check)
        self.apply_btn.clicked.connect(self.apply)
        undo_btn.clicked.connect(self.undo)
        for b in (self.check_btn, self.apply_btn, undo_btn):
            buttons.addWidget(b)
        lay.addLayout(buttons)

    def choose(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a deck update", os.path.expanduser("~"),
                                              "Deck update (*.json.gz *.json)")
        if not path:
            return
        try:
            self.pack = updater.load_pack(path)
        except updater.PackError as e:
            showWarning(str(e), parent=self)
            return
        st = self.pack.get("stats", {})
        self.file_label.setText(f"<b>{self.pack.get('title', os.path.basename(path))}</b><br>"
                                f"{st.get('updated_notes', 0):,} notes to improve · {st.get('new_notes', 0):,} new words"
                                f" · made {self.pack.get('created', '?')}")
        self.plan = None
        self.apply_btn.setEnabled(False)
        self.check_btn.setEnabled(True)
        self.status.setText("Press <b>Check</b>: it compares the update with your notes and changes nothing.")

    def _fill_decks(self, model_id: int) -> None:
        self.deck.clear()
        default = updater.default_deck(mw.col, self.pack, model_id)
        for d in sorted(mw.col.decks.all_names_and_ids(include_filtered=False), key=lambda d: d.name.lower()):
            self.deck.addItem(d.name, int(d.id))
            if int(d.id) == default:
                self.deck.setCurrentIndex(self.deck.count() - 1)
        self.deck.setEnabled(True)

    def check(self) -> None:
        pack = self.pack

        def done(p):
            self.plan = p
            self._fill_decks(p.model_id)
            fields = ", ".join(f"{k} {v:,}" for k, v in p.fields_to_change.items()) or "nothing"
            kept = sum(p.kept_your_edit.values())
            lines = [f"Note type: <b>{p.model_name}</b>",
                     f"Notes found: {p.matched:,} of {p.notes_in_pack:,}" + (f" ({p.matched_by_key:,} by word)" if p.matched_by_key else ""),
                     f"Fields to update: {fields}",
                     f"New words to add: {len(p.new_notes):,}" + (f" ({p.new_already_there:,} already there)" if p.new_already_there else "")]
            if kept:
                lines.append(f"Left as you edited them: {kept:,} fields")
            if p.already_done:
                lines.append(f"Already up to date: {p.already_done:,} fields")
            if p.not_found:
                lines.append(f"Not in your collection (deleted or never imported): {p.not_found:,} notes")
            if p.unknown_fields:
                lines.append("Fields your note type does not have: " + ", ".join(p.unknown_fields))
            self.status.setText("<br>".join(lines))
            self.apply_btn.setEnabled(bool(p.to_change or p.new_notes))
            path = _write_json_report(p.summary(), "update-check", p.language)
            self.status.setToolTip(f"Full report: {path}")

        def failed(err):
            showWarning(f"The check stopped:\n\n{err}", parent=self)

        QueryOp(parent=self, op=lambda col: updater.plan(col, pack), success=done).failure(failed) \
            .with_progress("Comparing the update with your notes…").run_in_background()

    def apply(self) -> None:
        if not self.plan or not self.pack:
            return
        p, pack, deck_id = self.plan, self.pack, self.deck.currentData()
        if not askUser(f"Apply \u201c{p.title}\u201d?\n\nAnki makes a full backup first. {len(p.to_change):,} notes are "
                       f"improved and {len(p.new_notes):,} new words go to \u201c{self.deck.currentText()}\u201d.\n\n"
                       "Review history, due dates and your own notes stay as they are. You can undo the update "
                       "later with \u201cUndo an update…\u201d.", parent=self):
            return

        def op(col):
            mw.create_backup_now()       # raises on failure: nothing is written without a backup
            fresh = updater.plan(col, pack)
            return updater.apply(col, pack, fresh, deck_id, USER_DIR, progress=_progress("Updating notes"))

        def done(r):
            mw.reset()
            self.apply_btn.setEnabled(False)
            showInfo(f"Done in {r.seconds:.0f} s.\n\nImproved notes: {r.changed_notes:,} ({r.changed_fields:,} fields)\n"
                     f"New words: {r.added_notes:,} ({r.added_cards:,} cards)\n\nUndo file: {r.undo_file}\n\n"
                     "Sync afterwards as usual.", parent=self)

        def failed(err):
            mw.reset()
            showWarning(f"The update stopped:\n\n{err}\n\nThe undo file in user_files lists everything written so far; "
                        "\u201cUndo an update…\u201d puts it back. Anki's backup from the start is also there.", parent=self)

        QueryOp(parent=mw, op=op, success=done).failure(failed).with_progress(
            "Backing up, then updating notes…").run_in_background()

    def undo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose the update to undo", USER_DIR, "Undo file (update-undo-*.json)")
        if not path or not askUser("Undo this update?\n\nFields you have changed since the update stay as they are. "
                                   "New words you have already studied stay; the others are removed.", parent=self):
            return

        def done(r):
            mw.reset()
            showInfo(f"Undone.\n\nFields restored: {r.restored_fields:,}\nKept (edited since the update): "
                     f"{r.kept_newer_edit:,}\nNew words removed: {r.removed_notes:,}\nKept (already studied): "
                     f"{r.kept_studied_notes:,}", parent=self)

        QueryOp(parent=mw, op=lambda col: updater.restore(col, path), success=done) \
            .failure(lambda e: showWarning(f"Could not undo:\n{e}", parent=self)) \
            .with_progress("Undoing the update…").run_in_background()


def _write_json_report(data: dict, kind: str, lang: str) -> str:
    os.makedirs(USER_DIR, exist_ok=True)
    path = os.path.join(USER_DIR, f"{kind}-{lang}-{time.strftime('%Y%m%d-%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return path


def open_dialog() -> None:
    if not mw.col:
        return
    d = QDialog(mw)
    d.setWindowTitle("Card redesign")
    d.setMinimumWidth(620)
    lay = QVBoxLayout(d)
    layout_box = QGroupBox("Card layout")
    box = QVBoxLayout(layout_box)
    combo = QComboBox()
    for key, label in LANG_LABELS.items():
        combo.addItem(label, key)
    box.addWidget(combo)
    text = QLabel("1. <b>Dry run</b>: checks every note and writes a report. Changes nothing.<br>"
                  "2. <b>Back up and apply</b>: makes a backup, cleans the notes, installs the new layout.<br>"
                  "3. <b>Restore old layout</b>: puts back a saved card layout if you don't like the new one.")
    text.setWordWrap(True)
    box.addWidget(text)
    row = QHBoxLayout()
    for label, fn in (("Dry run", lambda: dry_run(combo.currentData())),
                      ("Back up and apply", lambda: (d.accept(), apply(combo.currentData()))),
                      ("Restore old layout", lambda: restore(d))):
        b = QPushButton(label)
        b.clicked.connect(fn)
        row.addWidget(b)
    box.addLayout(row)
    lay.addWidget(layout_box)
    lay.addWidget(UpdatePanel(d))
    lay.addStretch(1)               # extra height goes below the boxes, not into them
    close = QPushButton("Close")
    close.clicked.connect(d.reject)
    bottom = QHBoxLayout()
    bottom.addStretch(1)
    bottom.addWidget(close)
    lay.addLayout(bottom)
    _exec(d)


action = QAction("Card redesign…", mw)
action.triggered.connect(open_dialog)
mw.form.menuTools.addAction(action)
