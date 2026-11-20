"""Zip card_redesign/ into an .ankiaddon. Usage: python3 -I tools/package.py [out.ankiaddon]"""
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "card_redesign"


def main(out: str) -> None:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(SRC.rglob("*")):
            rel = p.relative_to(SRC).as_posix()
            if p.is_dir() or "__pycache__" in rel or rel.startswith("user_files") or rel.endswith(".pyc"):
                continue
            z.write(p, rel)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "card_redesign.ankiaddon"))
