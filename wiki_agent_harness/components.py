"""Component palette reference — fed into prompts so agents know what
visual building blocks they can use when writing slot content.

Templates supply the page shell; this module documents the inline
components an agent can drop into any slot to make a page visual instead
of a wall of text.

The block is intentionally compact: name + when-to-use + minimal example.
Prompts inject ``render_component_palette()`` into the agent context.
"""
from __future__ import annotations


PALETTE = [
    {
        "name": "stat-grid",
        "when": "Headline numerics: counts, percentages, scores, dates. 2-6 stats per grid.",
        "example": """\
<div class="stat-grid">
  <div class="stat">
    <span class="num">87.6<span class="unit">%</span></span>
    <span class="label">accuracy</span>
    <span class="delta up">+19.2pp</span>
  </div>
  <div class="stat"><span class="num">38</span><span class="label">papers</span></div>
</div>""",
    },
    {
        "name": "card-grid + card",
        "when": "Listing 2-8 children with clickable navigation (subtopics, related pages, options).",
        "example": """\
<div class="card-grid">
  <a href="topic-a/README.html" class="card">
    <h3>▸ Topic A</h3>
    <p>Short blurb, 1-2 sentences.</p>
  </a>
  <a href="topic-b/README.html" class="card"><h3>▸ Topic B</h3></a>
</div>""",
    },
    {
        "name": "page-list + row-link",
        "when": "Compact list of pages with metadata (template, date, tags) on the right.",
        "example": """\
<div class="page-list">
  <a href="paper-x.html" class="row-link">
    <span><span class="icon">·</span><span class="title">Paper X</span></span>
    <span class="meta"><span class="template">source</span><span>2026-05-10</span></span>
  </a>
</div>""",
    },
    {
        "name": "callout",
        "when": "Side-channel info that interrupts the prose: warnings, key insights, cross-links. Variants: info / warn / success / danger.",
        "example": """\
<div class="callout info">Background note or cross-link.</div>
<div class="callout warn">Watch out — non-obvious gotcha.</div>
<div class="callout success">Result confirmed.</div>
<div class="callout danger">Wrong / broken / deprecated.</div>""",
    },
    {
        "name": "timeline",
        "when": "Chronological events: project diary, paper revision history, milestones.",
        "example": """\
<div class="timeline">
  <div class="timeline-item">
    <div class="when">2026-05-13</div>
    <div class="what"><strong>Pilot</strong> — Qwen3-1.7B, EM 68.4%.</div>
  </div>
</div>""",
    },
    {
        "name": "kv (definition list)",
        "when": "Key-value attributes: status, dataset stats, file listings, glossary entries.",
        "example": """\
<dl class="kv">
  <dt>SYNTHESIS.md</dt><dd>38-paper synthesis (design space, gaps)</dd>
  <dt>figures/</dt><dd>lineage + design-matrix figures</dd>
</dl>""",
    },
    {
        "name": "lede",
        "when": "Opening paragraph below H1 — large gray intro setting up the page.",
        "example": '<p class="lede">One- or two-sentence overview that frames the rest.</p>',
    },
    {
        "name": "badge / pill",
        "when": "Inline status / type markers. badge = subtle, pill = gradient prominent.",
        "example": '<span class="badge">draft</span>  <span class="pill">priority</span>',
    },
    {
        "name": "meta-strip",
        "when": "Top-of-page metadata row: status + dates + external links. Used by proposal/source pages.",
        "example": """\
<div class="meta-strip">
  <span class="status">实现已搭好</span>
  <span>updated 2026-05-26</span>
  <a href="https://...">↗ repo</a>
</div>""",
    },
    {
        "name": "mermaid diagram",
        "when": "Flowchart, sequence, state, gantt, mind map, class diagram. Use when 3+ related entities have visual structure.",
        "example": """\
<pre class="mermaid">
flowchart LR
  Input[input] --> Step1[normalise]
  Step1 --> Decision{valid?}
  Decision -->|yes| Out[output]
  Decision -->|no| Reject[reject]
</pre>""",
    },
    {
        "name": "chart (Chart.js)",
        "when": "Numeric data series: benchmark comparisons, training curves, distribution.",
        "example": """\
<canvas data-chart='{"type":"bar","data":{"labels":["A","B","C"],"datasets":[{"label":"score","data":[68,87,52]}]}}' style="max-width:600px;"></canvas>""",
    },
    {
        "name": "math (KaTeX)",
        "when": "Formulas. Inline with $..$, display with $$..$$.",
        "example": """\
Inline: $D_{KL}(P \\| Q) = \\sum_x P(x)\\log\\frac{P(x)}{Q(x)}$
Display:
$$\\mathcal{L} = -\\mathbb{E}_{x\\sim p}[\\log q(x)]$$""",
    },
    {
        "name": "code (highlight.js)",
        "when": "Code snippets — always set the language class.",
        "example": '<pre><code class="language-python">def kl(p, q):\n    return (p * (p / q).log()).sum()</code></pre>',
    },
    {
        "name": "lucide icon",
        "when": "Inline icons in headings or callouts. Any lucide.dev name works.",
        "example": '<h2><i data-lucide="zap"></i> Quick start</h2>',
    },
    {
        "name": "zoomable image",
        "when": "Figures you want click-to-zoom (lightbox).",
        "example": '<figure><a href="figs/big.png" class="zoomable"><img src="figs/big.png" alt="..."></a><figcaption>...</figcaption></figure>',
    },
    {
        "name": "gloss tooltip",
        "when": (
            "An inline definition for a sub-topic term you don't want to "
            "interrupt the prose to explain. Hover shows a small tooltip. "
            "Use this when (a) defining the term inline would derail the "
            "sentence, AND (b) there's no full page worth linking to yet. "
            "The tooltip text must still follow the audience-baseline rule "
            "— only use words the reader already knows."
        ),
        "example": """\
The teacher's <span class="gloss" data-tip="A probability over the
vocabulary at each generation step, the LLM's raw guess for the next
token before sampling.">output distribution</span> drives the loss.

Or with a link to a full page:
<a class="gloss" href="concepts/kl-divergence.html"
   data-tip="A number measuring how different two probability
distributions are; zero means identical.">KL divergence</a>""",
    },
]


WHEN_TO_USE = """\
RULES OF THUMB

  - 3+ numeric metrics                       → stat-grid
  - 2-8 child pages / options to navigate    → card-grid
  - Long-tail list of pages with metadata    → page-list
  - Critical / warning / cross-link aside    → callout
  - Anything chronological                   → timeline
  - Key/value attribute table                → kv
  - 3+ entities with structural relations    → mermaid flowchart
  - Numeric data series with comparisons     → chart
  - Formulas                                 → KaTeX $..$ / $$..$$
  - Code                                     → pre code with language-X
  - Inline jargon you can't gracefully redefine  → <span class="gloss" data-tip="…">

DEFAULT TO RICH. A page that's just <p>/<ul> is the failure case.
If content fits any pattern above, use the component. Plain prose is
fine for explanation paragraphs — but anything structural, numeric,
relational, or chronological should be visual.

Stack components freely: a topic page might open with a stat-grid,
then a mermaid diagram, then card-grid of children, then a callout
about a related cross-cutting concern.
"""


def render_component_palette() -> str:
    """Compact markdown reference of all visual components for the agent."""
    out: list[str] = [
        "## Visual components (use any in any slot)",
        "",
    ]
    for c in PALETTE:
        out.append(f"### {c['name']}")
        out.append(c["when"])
        out.append("```html")
        out.append(c["example"])
        out.append("```")
        out.append("")
    out.append(WHEN_TO_USE)
    return "\n".join(out)
