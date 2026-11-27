"""Draw the catalogue's posters: original typographic art, one per seeded film, in Frontrow's
box-office look (Barlow Condensed on a colour field, a ticket-stub perforation, the cast line).
The films are real, so no studio artwork, stills or logos are used anywhere — only the facts
from `app.seed.content.FILMS` set in type.

    uv run python scripts/make_posters.py --fonts DIR

DIR holds BarlowCondensed-ExtraBold.ttf, -SemiBold.ttf and -Medium.ttf (SIL Open Font Licence,
https://github.com/google/fonts/tree/main/ofl/barlowcondensed). Writes
web/public/img/posters/<poster>.png (800 × 1200) for every film; re-running overwrites them.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.seed.content import FILMS, FilmSpec  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "web" / "public" / "img" / "posters"
W, H = 800, 1200
PAD = 64

# (field, ink, accent) per film — the brand palette (web/src/app/globals.css) and its cousins.
COLOURS: dict[str, tuple[str, str, str]] = {
    "ramayana-part-1": ("#C9711F", "#2A0B1E", "#FFF6EE"),
    "yeh-prem-mol-liya": ("#E63946", "#FFFBF4", "#2A0B1E"),
    "maatrubhumi": ("#2F3B2A", "#F1E7D8", "#D9A42C"),
    "eetha": ("#A3205B", "#FFF6EE", "#F4A261"),
    "king": ("#141014", "#F1E7D8", "#D9A42C"),
    "golmaal-5": ("#F4A261", "#2A0B1E", "#7E1A22"),
    "love-and-war": ("#7E1A22", "#FFF6EE", "#F4A261"),
    "hunger-games-sunrise-on-the-reaping": ("#3A1230", "#F1E7D8", "#E63946"),
    "how-to-rob-a-bank": ("#3FA88A", "#10231D", "#FFFBF4"),
    "avengers-doomsday": ("#1F2A44", "#EEF2F8", "#5E9BD3"),
    "dune-part-three": ("#D9A42C", "#2A0B1E", "#7E1A22"),
}


def _font(fonts: Path, weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(fonts / f"BarlowCondensed-{weight}.ttf"), size)


def _wrap(text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and font.getlength(f"{lines[-1]} {word}") <= width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines


def _title_lines(fonts: Path, title: str) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """The biggest size at which the title fits the width in at most four lines."""
    text = title.upper()
    for size in range(240, 60, -4):
        font = _font(fonts, "ExtraBold", size)
        lines = _wrap(text, font, W - 2 * PAD)
        widest = max(font.getlength(line) for line in lines)
        if len(lines) <= 4 and widest <= W - 2 * PAD and size * 0.9 * len(lines) <= 640:
            return font, lines
    font = _font(fonts, "ExtraBold", 60)
    return font, _wrap(text, font, W - 2 * PAD)


def _date(spec: FilmSpec) -> str:
    return f"{spec.release.day} {spec.release:%b %Y}".upper()


def draw(spec: FilmSpec, fonts: Path) -> Image.Image:
    field, ink, accent = COLOURS[spec.poster]
    img = Image.new("RGB", (W, H), field)
    d = ImageDraw.Draw(img)

    # A spotlight disc behind the title and a stub perforation across the top.
    d.ellipse((W - 520, 150, W + 260, 930), outline=accent, width=6)
    stub_y = 170
    for x in range(PAD // 2, W, 34):
        d.ellipse((x - 7, stub_y - 7, x + 7, stub_y + 7), fill=accent)

    small = _font(fonts, "SemiBold", 30)
    d.text((PAD, 64), " · ".join(spec.languages).upper(), font=small, fill=ink)
    d.text((PAD, 104), f"IN CINEMAS {_date(spec)}", font=_font(fonts, "Medium", 26), fill=ink)

    font, lines = _title_lines(fonts, spec.title)
    step = int(font.size * 0.9)
    y = 980 - step * len(lines)
    for line in lines:
        d.text((PAD - 4, y), line, font=font, fill=ink)
        y += step

    d.rectangle((PAD, 1000, W - PAD, 1006), fill=accent)
    directors = [c["name"] for c in spec.cast_crew if c["role"] == "Director"]
    actors = [c["name"] for c in spec.cast_crew if c["role"] == "Actor"][:3]
    cast = _font(fonts, "SemiBold", 34)
    credit = _font(fonts, "Medium", 26)
    while len(actors) > 1 and cast.getlength("  ·  ".join(actors).upper()) > W - 2 * PAD:
        actors.pop()  # one line of cast: as many top-billed names as fit
    d.text((PAD, 1028), "  ·  ".join(actors).upper(), font=cast, fill=ink)
    d.text(
        (PAD, H - 64 - 26),
        f"DIRECTED BY {' & '.join(directors).upper()}",
        font=credit,
        fill=ink,
    )
    return img


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])  # type: ignore[union-attr]
    parser.add_argument("--fonts", type=Path, required=True, help="folder with the Barlow TTFs")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for spec in FILMS:
        path = OUT / f"{spec.poster}.png"
        draw(spec, args.fonts).save(path, optimize=True)
        print(path.relative_to(OUT.parents[3]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
