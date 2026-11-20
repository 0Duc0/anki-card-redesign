"""Render cards of a (redesigned) collection copy to PNG for visual review.

Usage: python3 -I tools/render.py <collection> <out_dir> <word> [<word> …]
Writes <out_dir>/<word>-c<ord>-<side>-<width>-<theme>.png and one contact sheet per word.
"""
import asyncio
import pathlib
import re
import sys

from anki.collection import Collection
from PIL import Image, ImageDraw, ImageFont
from playwright.async_api import async_playwright

PLAY = ('<a class="replay-button soundLink" href="#"><svg class="playImage" viewBox="0 0 64 64" version="1.1">'
        '<circle cx="32" cy="32" r="29"></circle><path d="M56.502,32.301l-37.502,20.101l0.329,-40.804l37.173,20.703Z">'
        '</path></svg></a>')
CHROME = "/usr/bin/google-chrome"


def page(html: str, ord_: int, dark: bool, open_all: bool) -> str:
    html = re.sub(r"\[anki:play:[qa]:\d+\]", PLAY, html)
    cls = f"card card{ord_ + 1}" + (" nightMode" if dark else "")
    script = "<script>document.querySelectorAll('details').forEach(d=>d.open=true)</script>" if open_all else ""
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>a.replay-button svg{{width:30px;height:30px}}'
            f'</style></head><body class="{cls}">{html}{script}</body></html>')


async def shoot(jobs, out: pathlib.Path):
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME)
        for name, html, width in jobs:
            pg = await browser.new_page(viewport={"width": width, "height": 400}, device_scale_factor=1)
            await pg.set_content(html, wait_until="load")
            await pg.screenshot(path=str(out / name), full_page=True)
            await pg.close()
        await browser.close()


def sheet(files: list[pathlib.Path], dest: pathlib.Path, title: str):
    ims = [Image.open(f) for f in files]
    pad, label_h = 16, 22
    w = sum(i.width for i in ims) + pad * (len(ims) + 1)
    h = max(i.height for i in ims) + pad * 2 + label_h
    canvas = Image.new("RGB", (w, h), (200, 200, 200))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    x = pad
    for f, im in zip(files, ims):
        draw.text((x, pad // 2), f.stem.replace(title + "-", ""), fill=(20, 20, 20), font=font)
        canvas.paste(im, (x, pad + label_h))
        x += im.width + pad
    canvas.save(dest)


def main(src: str, out_dir: str, words: list[str], widths=(420,), themes=("light",), open_all=False, field="Simplified"):
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    col = Collection(src)
    jobs, per_word = [], {}
    try:
        for word in words:
            nids = col.find_notes(f'"{field}:{word}"')
            notes = sorted((col.get_note(n) for n in nids), key=lambda n: -len(n.joined_fields()))
            note = notes[0]
            for card in sorted(note.cards(), key=lambda c: c.ord):
                for side, html in (("front", card.question()), ("back", card.answer())):
                    for width in widths:
                        for theme in themes:
                            name = f"{word}-c{card.ord + 1}-{side}-{width}-{theme}{'-open' if open_all else ''}.png"
                            jobs.append((name, page(html, card.ord, theme == "dark", open_all), width))
                            per_word.setdefault(word, []).append(out / name)
    finally:
        col.close()
    asyncio.run(shoot(jobs, out))
    for word, files in per_word.items():
        sheet(files, out / f"sheet-{word}{'-open' if open_all else ''}-{widths[0]}-{themes[0]}.png", word)


if __name__ == "__main__":
    args = sys.argv[1:]
    opts = {"widths": (420,), "themes": ("light",), "open_all": False, "field": "Simplified"}
    while args and args[0].startswith("--"):
        flag = args.pop(0)
        if flag == "--wide":
            opts["widths"] = (900,)
        elif flag == "--dark":
            opts["themes"] = ("dark",)
        elif flag == "--open":
            opts["open_all"] = True
        elif flag.startswith("--field="):
            opts["field"] = flag.split("=", 1)[1]
    main(args[0], args[1], args[2:], **opts)
