"""Dry-run the cleaners over a whole collection copy and summarise.

Usage: python3 -I tools/corpus_check.py <collection.sqlite> [out.json] [lang]
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "card_redesign"))

from anki.collection import Collection  # noqa: E402

import runner  # noqa: E402


def main(src: str, out: str, lang: str = "cn") -> None:
    col = Collection(src)
    try:
        rep = runner.dry_run(col, lang, sample=40)
    finally:
        col.close()
    d = rep.to_dict()
    pathlib.Path(out).write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
    pct = {f: round(100 * n / rep.notes_total, 3) for f, n in rep.unrecognised_count.items()}
    print(f"notes {rep.notes_total:,}  changed {rep.notes_changed:,}  fields {rep.fields_changed}")
    print(f"unrecognised {rep.unrecognised_count} ({pct} %)")
    print(f"audio in {rep.audio_in:,} out {rep.audio_out:,} dropped {rep.audio_dropped:,}  "
          f"balanced={rep.audio_out == rep.audio_in - rep.audio_dropped}")
    print(f"dropped examples {rep.dropped_examples:,}; first: {rep.dropped_samples[:25]}")
    print(f"template: {rep.template_error or 'ok'} · card check: {rep.card_check} · missing cards: {rep.missing_cards}")
    print(f"{rep.seconds}s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "reports/corpus-cn55.json",
         sys.argv[3] if len(sys.argv) > 3 else "cn")
