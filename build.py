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

Interactive layer (all client-side, CDN libraries, no build step on hosting):
  * ```mermaid fences          → rendered diagrams (Mermaid.js)
  * ```widget {json} fences    → interactive widgets (assets/widgets.js)
  * per-page "On this page" TOC, localStorage progress tracking, answer reveals.
"""

import html as _html
import json
import re
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
    "toc": {"permalink": False, "toc_depth": "2-3"},
}

_MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
_WIDGET_RE = re.compile(r"```widget\s*\n(.*?)```", re.DOTALL)


def load_curriculum():
    return json.loads((CONTENT / "curriculum.json").read_text(encoding="utf-8"))


def _extract_fences(text):
    """Pull ```mermaid and ```widget fences out before Markdown runs.

    Returns (text_with_placeholders, replacements) where replacements maps a
    placeholder token to the final HTML to substitute back in afterwards.
    """
    replacements = {}

    def _mermaid(m):
        token = f"MERMAIDBLOCK{len(replacements)}ENDBLOCK"
        diagram = _html.escape(m.group(1).strip())
        replacements[token] = f'<pre class="mermaid">{diagram}</pre>'
        return f"\n\n{token}\n\n"

    def _widget(m):
        token = f"WIDGETBLOCK{len(replacements)}ENDBLOCK"
        raw = m.group(1).strip()
        # Validate JSON at build time so a typo fails the build, not the browser.
        cfg = json.loads(raw)
        wtype = cfg.get("type", "unknown")
        payload = _html.escape(json.dumps(cfg), quote=False)
        replacements[token] = (
            f'<div class="widget" data-widget="{wtype}">'
            f'<script type="application/json">{payload}</script></div>'
        )
        return f"\n\n{token}\n\n"

    text = _MERMAID_RE.sub(_mermaid, text)
    text = _WIDGET_RE.sub(_widget, text)
    return text, replacements


def render_markdown(text):
    """Return (html, toc_html)."""
    text, replacements = _extract_fences(text)
    md = markdown.Markdown(extensions=MD_EXTENSIONS, extension_configs=MD_CONFIG)
    out = md.convert(text)
    for token, repl in replacements.items():
        # Markdown wraps a bare token line in <p>…</p>; strip that wrapper.
        out = out.replace(f"<p>{token}</p>", repl).replace(token, repl)
    toc = getattr(md, "toc", "") or ""
    return out, toc


def sidebar_html(curriculum, active_day):
    """Build the week-grouped navigation shared by every page."""
    days = curriculum["days"]
    out = ['<nav class="sidebar" aria-label="Curriculum">']
    out.append('<a class="brand" href="index.html">Apigee&nbsp;X &middot; 30 Days</a>')
    out.append('<div class="nav-progress"><div class="nav-progress-bar"><span id="navProgressFill"></span></div>'
               '<span id="navProgressText" class="nav-progress-text">0 / 30 complete</span></div>')
    for week in curriculum["weeks"]:
        out.append(f'<div class="nav-week">{week["title"]}</div>')
        out.append("<ul>")
        for d in week["days"]:
            meta = days[str(d)]
            cls = ' class="active"' if d == active_day else ""
            label = f'<span class="daynum">Day {d:02d}</span> {meta["title"]}'
            out.append(f'<li{cls} data-day="{d}"><a href="day-{d:02d}.html">'
                       f'<span class="done-check" aria-hidden="true">&#10003;</span>{label}</a></li>')
        out.append("</ul>")
    out.append("</nav>")
    return "\n".join(out)


def _scripts(asset_prefix):
    """CDN libraries + local scripts. Mermaid themed to match the site."""
    return f"""
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{
      startOnLoad: true,
      securityLevel: 'loose',
      theme: 'base',
      themeVariables: {{
        primaryColor: '#eef4ff', primaryBorderColor: '#1a73e8', primaryTextColor: '#15233a',
        lineColor: '#5b6b7b', secondaryColor: '#eafaf0', tertiaryColor: '#fff6e6',
        fontFamily: '-apple-system, Segoe UI, Roboto, sans-serif', fontSize: '14px'
      }}
    }});
    window.__mermaidReady = true;
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <script defer src="{asset_prefix}assets/widgets.js"></script>
  <script defer src="{asset_prefix}assets/app.js"></script>
"""


def page_shell(title, sidebar, body, *, toc_html="", day=None, is_index=False):
    asset_prefix = ""  # docs/ is flat, so assets/ is reachable from every page
    main_attrs = f' data-day="{day}"' if day else ""
    main_cls = "content index" if is_index else "content"
    toc_rail = ""
    if toc_html and not is_index:
        toc_rail = (
            '<aside class="toc-rail" aria-label="On this page">'
            '<div class="toc-title">On this page</div>'
            f"{toc_html}</aside>"
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="{asset_prefix}assets/pygments.css">
  <link rel="stylesheet" href="{asset_prefix}assets/style.css">
  <link rel="stylesheet" href="{asset_prefix}assets/widgets.css">
</head>
<body>
  <div id="readingBar"></div>
  <button id="navToggle" class="nav-toggle" aria-label="Toggle navigation">&#9776; Menu</button>
  <div class="layout">
    {sidebar}
    <main class="{main_cls}"{main_attrs}>
      {body}
    </main>
    {toc_rail}
  </div>
{_scripts(asset_prefix)}
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


def complete_toggle(day):
    return (
        f'<div class="day-complete" data-day="{day}">'
        '<button id="markComplete" type="button" class="mark-btn">'
        '<span class="mark-box">&#10003;</span> Mark Day '
        f'{day:02d} complete</button>'
        '<span class="mark-hint">Progress is saved in your browser.</span>'
        "</div>"
    )


def build_day(curriculum, day):
    meta = curriculum["days"][str(day)]
    src = CONTENT / f"day-{day:02d}.md"
    if not src.exists():
        raise FileNotFoundError(f"Missing content file: {src}")
    rendered, toc = render_markdown(src.read_text(encoding="utf-8"))
    body = (
        f'<div class="crumbs">{meta["pillar"]} &middot; '
        f'Week {meta["week"]} &middot; ~{meta["minutes"]} min</div>'
        + rendered
        + complete_toggle(day)
        + prev_next_html(curriculum, day)
    )
    title = f"Day {day:02d} — {meta['title']} · Apigee X 30-Day Training"
    html = page_shell(title, sidebar_html(curriculum, day), body, toc_html=toc, day=day)
    (DOCS / f"day-{day:02d}.html").write_text(html, encoding="utf-8")


def build_index(curriculum):
    rendered, _ = render_markdown((CONTENT / "index.md").read_text(encoding="utf-8"))
    html = page_shell(
        f"{curriculum['title']} · {curriculum['subtitle']}",
        sidebar_html(curriculum, active_day=0),
        rendered,
        is_index=True,
    )
    (DOCS / "index.html").write_text(html, encoding="utf-8")


def write_pygments_css():
    css = HtmlFormatter(style=PYGMENTS_STYLE).get_style_defs(".codehilite")
    (DOCS / "assets" / "pygments.css").write_text(css, encoding="utf-8")


def write_curriculum_json(curriculum):
    """Expose the curriculum to the client (used by the curriculum-map widget)."""
    (DOCS / "assets" / "curriculum.json").write_text(
        json.dumps(curriculum), encoding="utf-8"
    )


def main():
    curriculum = load_curriculum()
    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "assets").mkdir(parents=True)

    # Static assets
    for fname in ("style.css", "app.js", "widgets.js", "widgets.css"):
        shutil.copy(ASSETS / fname, DOCS / "assets" / fname)
    write_pygments_css()
    write_curriculum_json(curriculum)
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
