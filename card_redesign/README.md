# Card Redesign (by Claude)

Tools → **Card redesign…**

## Card layout

1. **Dry run**: checks every note of the chosen language (Chinese CC-CEDICT, Japanese JMdict, Vietnamese v8) and
   writes a report to `user_files/`. Changes nothing.
2. **Back up and apply**: Anki makes a full backup, then the add-on cleans meanings and examples into one simple
   structure and installs the new card layout. Same fields and card types, so no full sync. Review history,
   due dates, Notizen and mnemonics are never touched. Running it again changes nothing.
3. **Restore old layout**: puts back the card layout saved in `user_files/*-templates-*.json`.
   (To also undo the note contents, restore Anki's backup.)

## Deck update

Applies an update file (`*.json.gz`) from the anki-language-decks project: better main meanings, more example
sentences, new words.

1. **Choose file…** and pick the update for your language.
2. **Check** compares it with your notes and changes nothing.
3. **Back up and apply**: Anki makes a full backup, then the fields are updated. A field is only written if it
   still has exactly the content the update was made from, so anything you edited yourself stays as it is.
   Personal fields (PersonalNotes, Notizen, Mnemonic, …), review history and due dates are never touched.
   New words go into the deck chosen in the dialog.
4. **Undo an update…** uses the undo file in `user_files/` (`update-undo-<language>-<time>.json`). Fields you
   changed after the update and new words you already studied are kept.

Running the same update twice changes nothing. Sync afterwards as usual (no full sync needed).
