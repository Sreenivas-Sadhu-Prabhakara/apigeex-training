# 30-Day Apigee X Training — API Proxy Development for UK Open Banking (FAPI)

A self-paced, copy-paste-driven course that takes an API developer from "never touched Apigee" to shipping a **FAPI 1.0 Advanced–secured UK Open Banking** API surface on **Apigee X**.

**▶ Read it online:** https://sreenivas-sadhu-prabhakara.github.io/apigeex-training/

## What this is

- **30 atomic days**, each with one objective, a hands-on lab, and runnable code blocks (every block has a copy button on the site).
- **MINTO / pyramid**: each day leads with the bottom line, then supports it.
- **MECE**: five pillars cover "all aspects" of Apigee X relevant to banking, with no topic taught twice.
- **Cumulative**: each day explicitly builds on the previous one.
- **Interactive & visual**: Mermaid diagrams, a request-pipeline animator, step-through OAuth/FAPI/payment sequence diagrams, consent/payment state-machine explorers, a SpikeArrest rate-limit simulator, Chart.js data visualizations, MCQ quizzes, an interactive curriculum map, per-page "on this page" navigation, and browser-saved progress tracking.

## Interactive content (authoring)

Two custom fenced blocks are processed by `build.py` into client-side components (all rendered statically, no server):

~~~
```mermaid
flowchart LR
  A --> B
```

```widget
{"type":"quiz","title":"…","questions":[{"q":"…","options":["a","b"],"answer":0,"explain":"…"}]}
```
~~~

`widget` types: `pipeline`, `sequence`, `statemachine`, `ratelimit`, `chart` (Chart.js), `quiz`, `curriculummap`. Each type's config schema lives in `assets/widgets.js`. Mermaid and Chart.js load from CDN; everything else is local vanilla JS.

| Week | Pillar | Days |
|------|--------|------|
| 1 | Foundations & your first proxy | 1–5 |
| 2 | Core proxy development & mediation | 6–12 |
| 3 | Security & identity (through FAPI) | 13–19 |
| 4 | UK Open Banking domain (consent, AISP, PISP, DCR) | 20–25 |
| 5 | Operations, delivery & production | 26–30 |

## Audience & prerequisites

API developers comfortable with HTTP, REST, JSON, and basic OAuth 2.0. No prior Apigee experience required. You'll need a Google Cloud account with billing enabled — Day 2 provisions a **free** Apigee X evaluation org.

## Repository layout

```text
content/            Markdown source (hand-editable) — one file per day + curriculum.json
assets/             style.css and app.js (copy buttons, mobile nav)
build.py            renders content/ → docs/ (Markdown → plain static HTML)
requirements.txt    build-time deps only (markdown, pygments)
docs/               GENERATED static site that GitHub Pages serves
```

The hosted site is **plain static HTML** — GitHub Pages serves `docs/` directly. No Jekyll, no MkDocs, no CI build required to host. The Python build step is a local convenience for regenerating after you edit content.

## Editing & rebuilding

```bash
pip install -r requirements.txt
# edit content/day-NN.md or assets/*
python3 build.py          # regenerates docs/
```

Then commit the updated `docs/` and push — Pages updates automatically.

## How GitHub Pages is configured

Pages serves from the `main` branch, `/docs` folder. A `.nojekyll` file in `docs/` tells Pages to serve the files verbatim (no Jekyll processing).

## Disclaimer

Independent training material. "Apigee" and "Google Cloud" are trademarks of Google; "Open Banking" specifications belong to the OBIE. Code is illustrative — validate against current official specifications before any production use.

---

Authored as an Apigee X implementation/customer-engineering training. Contributions and forks welcome.
