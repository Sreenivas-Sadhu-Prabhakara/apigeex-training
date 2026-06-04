#!/usr/bin/env python3
"""
build.py — render content/*.md into plain static HTML under docs/.

Usage:
    pip install -r requirements.txt
    python3 build.py

Design goals:
  * Output is self-contained static HTML — GitHub Pages serves docs/ directly,
    no Jekyll, no MkDocs, no CI build required.
  * Content is authored in Markdown (content/day-NN.md) so code blocks don't
    need hand-escaped XML. Fenced code is highlighted with Pygments.
  * The left-hand navigation and prev/next links are generated from
    content/curriculum.json so the table of contents can never drift.
"""

import json
import shutil
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"
DOCS = ROOT / "docs"

PYGMENTS_STYLE = "monokai"

MD_EXTENSIONS = [
    "fenced_code",
    "codehilite",
    "tables",
    "toc",
    "admonition",
    "attr_list",
    "sane_lists",
    "def_list",
    "md_in_html",
]
MD_CONFIG = {
    "codehilite": {"guess_lang": False, "noclasses": False, "pygments_style": PYGMENTS_STYLE},
    "toc": {"permalink": False},
}


def load_curriculum():
    return json.loads((CONTENT / "curriculum.json").read_text(encoding="utf-8"))


def render_markdown(text):
    md = markdown.Markdown(extensions=MD_EXTENSIONS, extension_configs=MD_CONFIG)
    return md.convert(text)


def sidebar_html(curriculum, active_day):
    """Build the week-grouped navigation shared by every page."""
    days = curriculum["days"]
    out = ['<nav class="sidebar" aria-label="Curriculum">']
    out.append('<a class="brand" href="index.html">Apigee&nbsp;X &middot; 30 Days</a>')
    for week in curriculum["weeks"]:
        out.append(f'<div class="nav-week">{week["title"]}</div>')
        out.append("<ul>")
        for d in week["days"]:
            meta = days[str(d)]
            cls = ' class="active"' if d == active_day else ""
            label = f'<span class="daynum">Day {d:02d}</span> {meta["title"]}'
            out.append(f'<li{cls}><a href="day-{d:02d}.html">{label}</a></li>')
        out.append("</ul>")
    out.append("</nav>")
    return "\n".join(out)


def page_shell(title, sidebar, body, *, is_index=False):
    asset_prefix = ""  # docs/ is flat, so assets/ is reachable from every page
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="{asset_prefix}assets/pygments.css">
  <link rel="stylesheet" href="{asset_prefix}assets/style.css">
</head>
<body>
  <button id="navToggle" class="nav-toggle" aria-label="Toggle navigation">&#9776; Menu</button>
  <div class="layout">
    {sidebar}
    <main class="content{' index' if is_index else ''}">
      {body}
    </main>
  </div>
  <script src="{asset_prefix}assets/app.js"></script>
</body>
</html>
"""


def prev_next_html(curriculum, day):
    order = []
    for week in curriculum["weeks"]:
        order.extend(week["days"])
    idx = order.index(day)
    parts = ['<div class="pager">']
    if idx > 0:
        p = order[idx - 1]
        parts.append(f'<a class="prev" href="day-{p:02d}.html">&larr; Day {p:02d}</a>')
    else:
        parts.append('<a class="prev" href="index.html">&larr; Overview</a>')
    if idx < len(order) - 1:
        n = order[idx + 1]
        parts.append(f'<a class="next" href="day-{n:02d}.html">Day {n:02d} &rarr;</a>')
    else:
        parts.append('<a class="next" href="index.html">Finish &rarr;</a>')
    parts.append("</div>")
    return "\n".join(parts)


def build_day(curriculum, day):
    meta = curriculum["days"][str(day)]
    src = CONTENT / f"day-{day:02d}.md"
    if not src.exists():
        raise FileNotFoundError(f"Missing content file: {src}")
    body = render_markdown(src.read_text(encoding="utf-8"))
    body = (
        f'<div class="crumbs">{meta["pillar"]} &middot; '
        f'Week {meta["week"]} &middot; ~{meta["minutes"]} min</div>'
        + body
        + prev_next_html(curriculum, day)
    )
    title = f"Day {day:02d} — {meta['title']} · Apigee X 30-Day Training"
    html = page_shell(title, sidebar_html(curriculum, day), body)
    (DOCS / f"day-{day:02d}.html").write_text(html, encoding="utf-8")


def build_index(curriculum):
    body = render_markdown((CONTENT / "index.md").read_text(encoding="utf-8"))
    html = page_shell(
        f"{curriculum['title']} · {curriculum['subtitle']}",
        sidebar_html(curriculum, active_day=0),
        body,
        is_index=True,
    )
    (DOCS / "index.html").write_text(html, encoding="utf-8")


def write_pygments_css():
    css = HtmlFormatter(style=PYGMENTS_STYLE).get_style_defs(".codehilite")
    (DOCS / "assets" / "pygments.css").write_text(css, encoding="utf-8")


def main():
    curriculum = load_curriculum()
    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "assets").mkdir(parents=True)

    # Static assets
    shutil.copy(ASSETS / "style.css", DOCS / "assets" / "style.css")
    shutil.copy(ASSETS / "app.js", DOCS / "assets" / "app.js")
    write_pygments_css()
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")  # serve files verbatim

    build_index(curriculum)
    count = 0
    for week in curriculum["weeks"]:
        for day in week["days"]:
            build_day(curriculum, day)
            count += 1
    print(f"Built index + {count} day pages into {DOCS}")


if __name__ == "__main__":
    main()
