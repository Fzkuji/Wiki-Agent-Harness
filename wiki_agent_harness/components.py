"""Component palette — Tailwind CSS + daisyUI v5.

Templates supply the page shell; this module documents the inline
components an agent can drop into any slot to make a page visual instead
of a wall of text.

**The Tailwind multiplier**: because the base.html shell loads Tailwind
CDN + daisyUI, any Tailwind class string from anywhere on the open web
(shadcn/ui, Vercel templates, Flowbite, Preline, HyperUI, Tailblocks,
daisyUI examples, bento.dev, cruip, tailwindui.com free sections, etc.)
can be copy-pasted directly into a slot and will render. The palette
below is a *starting* vocabulary — not a fence. If you've seen a layout
on a Tailwind site that fits the page better, copy it.

Prompts inject :func:`render_component_palette` into the agent context.
"""
from __future__ import annotations


PALETTE = [
    # ── Hero / page-opening ──────────────────────────────────────
    {
        "name": "hero (wah-hero)",
        "when": "Top of EVERY non-trivial page. Big gradient banner with title, eyebrow tag, lede. Already used by all templates — but you can place a second one inline for a major sub-section.",
        "example": """\
<section class="wah-hero">
  <span class="eyebrow">section · area</span>
  <h1>Page title here</h1>
  <p class="lede">One-or-two-sentence overview that frames the rest of the page.</p>
</section>""",
    },
    # ── Layout primitives (Tailwind) ─────────────────────────────
    {
        "name": "split layout (2-col with sidebar)",
        "when": "Main content + sidebar facts/TOC/CTAs. Use for entity pages, dense docs.",
        "example": """\
<div class="grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
  <article class="prose prose-base max-w-none">... main content ...</article>
  <aside class="lg:sticky lg:top-24 lg:self-start">
    <div class="card bg-base-200 border border-base-300">
      <div class="card-body p-5">... facts / quick links ...</div>
    </div>
  </aside>
</div>""",
    },
    {
        "name": "bento grid (asymmetric feature grid)",
        "when": "Showcase 4-8 features/sub-areas with deliberate visual hierarchy — some cards big, some small. Looks like Apple's bento style.",
        "example": """\
<div class="grid grid-cols-1 md:grid-cols-3 gap-4 auto-rows-[minmax(140px,auto)]">
  <a href="big.html" class="md:col-span-2 md:row-span-2 card bg-gradient-to-br from-brand-500 to-pink-500 text-white border-0 no-underline hover:scale-[1.01] transition-transform">
    <div class="card-body justify-end"><h3 class="text-2xl font-bold m-0">Marquee item</h3><p class="opacity-90 m-0">Bigger, brighter, leading the eye.</p></div>
  </a>
  <a href="b.html" class="card bg-base-200 border border-base-300 no-underline hover:border-brand-400"><div class="card-body p-4"><h4 class="m-0 font-semibold">Item B</h4></div></a>
  <a href="c.html" class="card bg-base-200 border border-base-300 no-underline hover:border-brand-400"><div class="card-body p-4"><h4 class="m-0 font-semibold">Item C</h4></div></a>
  <a href="d.html" class="md:col-span-2 card bg-base-200 border border-base-300 no-underline hover:border-brand-400"><div class="card-body p-4"><h4 class="m-0 font-semibold">Wide item D</h4></div></a>
</div>""",
    },
    # ── daisyUI built-ins ────────────────────────────────────────
    {
        "name": "stats (daisyUI)",
        "when": "Headline numerics: counts, percentages, scores, deltas. 2-6 stats. Use stats-horizontal on desktop, stats-vertical on mobile.",
        "example": """\
<div class="stats stats-vertical sm:stats-horizontal shadow w-full bg-base-100 border border-base-300">
  <div class="stat">
    <div class="stat-figure text-brand-500"><svg xmlns="http://www.w3.org/2000/svg" class="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg></div>
    <div class="stat-title">Baseline EM</div>
    <div class="stat-value text-brand-600">68.4%</div>
    <div class="stat-desc">Qwen3-1.7B · AIME24</div>
  </div>
  <div class="stat">
    <div class="stat-title">After fix</div>
    <div class="stat-value text-success">87.6%</div>
    <div class="stat-desc text-success">↗︎ +19.2pp</div>
  </div>
  <div class="stat">
    <div class="stat-title">Papers</div>
    <div class="stat-value">38</div>
    <div class="stat-desc">in synthesis</div>
  </div>
</div>""",
    },
    {
        "name": "steps (daisyUI vertical)",
        "when": "Numbered procedure / pipeline (3-8 steps). Each step is its own visual block with body underneath the marker.",
        "example": """\
<ul class="steps steps-vertical">
  <li class="step step-primary" data-content="1">
    <div class="text-left ml-4">
      <div class="font-semibold">Reproduce the baseline</div>
      <div class="text-sm text-base-content/70">Run the released eval script unchanged; confirm published numbers within ±0.5pp.</div>
    </div>
  </li>
  <li class="step step-primary" data-content="2">
    <div class="text-left ml-4">
      <div class="font-semibold">Swap in your fix</div>
      <div class="text-sm text-base-content/70">Apply patch; re-run identical eval.</div>
    </div>
  </li>
</ul>""",
    },
    {
        "name": "timeline (daisyUI vertical)",
        "when": "Chronological events: project diary, paper revision history, milestones.",
        "example": """\
<ul class="timeline timeline-snap-icon max-md:timeline-compact timeline-vertical">
  <li>
    <div class="timeline-middle">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5 text-brand-500"><circle cx="10" cy="10" r="6"/></svg>
    </div>
    <div class="timeline-start mb-6 md:text-end">
      <time class="font-mono italic text-sm text-brand-600">2026-05-13</time>
      <div class="text-base font-semibold">Pilot</div>
      <div class="text-sm text-base-content/70">Qwen3-1.7B, EM 68.4%.</div>
    </div>
    <hr/>
  </li>
  <li>
    <hr class="bg-brand-500"/>
    <div class="timeline-middle">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5 text-success"><circle cx="10" cy="10" r="6"/></svg>
    </div>
    <div class="timeline-end mb-6">
      <time class="font-mono italic text-sm text-success">2026-05-20</time>
      <div class="text-base font-semibold">Fix landed</div>
      <div class="text-sm text-base-content/70">EM 87.6% · +19pp.</div>
    </div>
  </li>
</ul>""",
    },
    {
        "name": "card (daisyUI)",
        "when": "Single highlighted unit — used inside card-grids, or standalone as a featured callout. Hover effects baked in below.",
        "example": """\
<a href="topic.html" class="card bg-base-100 border border-base-300 hover:border-brand-400 hover:shadow-lg hover:-translate-y-0.5 transition-all no-underline">
  <div class="card-body p-5">
    <h3 class="card-title text-base m-0">▸ Topic title</h3>
    <p class="text-sm text-base-content/70 m-0">Short blurb, 1-2 sentences.</p>
    <div class="card-actions justify-end mt-2">
      <span class="badge badge-ghost badge-sm">5 pages</span>
      <span class="badge badge-primary badge-sm">new</span>
    </div>
  </div>
</a>""",
    },
    {
        "name": "card-grid",
        "when": "Listing 2-12 children with clickable navigation (subtopics, related pages, options).",
        "example": """\
<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
  <a href="a.html" class="card bg-base-100 border border-base-300 hover:border-brand-400 hover:shadow-lg transition-all no-underline">
    <div class="card-body p-5"><h3 class="card-title text-base m-0">Topic A</h3><p class="text-sm text-base-content/70 m-0">Blurb.</p></div>
  </a>
  <a href="b.html" class="card bg-base-100 border border-base-300 hover:border-brand-400 hover:shadow-lg transition-all no-underline">
    <div class="card-body p-5"><h3 class="card-title text-base m-0">Topic B</h3><p class="text-sm text-base-content/70 m-0">Blurb.</p></div>
  </a>
</div>""",
    },
    {
        "name": "alert / callout (daisyUI)",
        "when": "Side-channel info that interrupts prose: warnings, key insights, cross-links. Variants: alert-info / alert-success / alert-warning / alert-error / bare alert.",
        "example": """\
<div class="alert alert-info">
  <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
  <span><strong>Background:</strong> defined in [linked-page](other.html).</span>
</div>

<div class="alert alert-warning">
  <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>
  <span>Non-obvious gotcha goes here.</span>
</div>""",
    },
    {
        "name": "collapse / accordion (daisyUI)",
        "when": "Optional deep-dive content that would otherwise crowd the page (FAQ, edge cases, derivations).",
        "example": """\
<div class="join join-vertical w-full">
  <div class="collapse collapse-arrow join-item border border-base-300">
    <input type="checkbox"/>
    <div class="collapse-title font-semibold">Why does this loss explode at large T?</div>
    <div class="collapse-content text-sm text-base-content/80"><p>Detailed explanation here, only revealed on click.</p></div>
  </div>
  <div class="collapse collapse-arrow join-item border border-base-300">
    <input type="checkbox"/>
    <div class="collapse-title font-semibold">How does this differ from method X?</div>
    <div class="collapse-content text-sm text-base-content/80"><p>...</p></div>
  </div>
</div>""",
    },
    {
        "name": "tabs (daisyUI)",
        "when": "Same content from multiple angles (e.g. Python / TypeScript / curl examples; before / after).",
        "example": """\
<div role="tablist" class="tabs tabs-lifted">
  <input type="radio" name="t1" role="tab" class="tab" aria-label="Python" checked/>
  <div role="tabpanel" class="tab-content border-base-300 bg-base-100 p-4 rounded-box"><pre><code class="language-python">print("hello")</code></pre></div>
  <input type="radio" name="t1" role="tab" class="tab" aria-label="TypeScript"/>
  <div role="tabpanel" class="tab-content border-base-300 bg-base-100 p-4 rounded-box"><pre><code class="language-typescript">console.log("hello")</code></pre></div>
</div>""",
    },
    {
        "name": "table (daisyUI)",
        "when": "Tabular data, comparisons. Wrap in .overflow-x-auto so mobile scrolls.",
        "example": """\
<div class="overflow-x-auto rounded-xl border border-base-300">
  <table class="table table-zebra m-0">
    <thead><tr><th>Method</th><th>EM ↑</th><th>Notes</th></tr></thead>
    <tbody>
      <tr><td>Baseline</td><td><span class="font-mono">68.4</span></td><td>Qwen3-1.7B</td></tr>
      <tr><td><strong>Ours</strong></td><td><span class="font-mono text-success">87.6</span></td><td>+19.2pp</td></tr>
    </tbody>
  </table>
</div>""",
    },
    {
        "name": "badge / pill (daisyUI)",
        "when": "Inline status / type markers. Variants: badge-primary, badge-success, badge-warning, badge-error, badge-ghost, badge-outline.",
        "example": """\
<span class="badge badge-primary">priority</span>
<span class="badge badge-success badge-outline">verified</span>
<span class="badge badge-ghost">draft</span>""",
    },
    {
        "name": "mockup-browser (daisyUI)",
        "when": "Show a screenshot / wireframe / demo of a UI inside a fake browser chrome — gives it 'this is a real page' weight.",
        "example": """\
<div class="mockup-browser border border-base-300 bg-base-200">
  <div class="mockup-browser-toolbar"><div class="input border border-base-300">https://example.com</div></div>
  <div class="bg-base-100 px-4 py-8 text-center">
    <img src="figs/ui-screenshot.png" alt="..." class="mx-auto rounded">
  </div>
</div>""",
    },
    {
        "name": "mockup-code (daisyUI)",
        "when": "Tutorial / demo code shown as if in a terminal window.",
        "example": """\
<div class="mockup-code">
  <pre data-prefix="$"><code>pip install wiki-agent-harness</code></pre>
  <pre data-prefix=">" class="text-success"><code>installed</code></pre>
  <pre data-prefix="$"><code>wah new --template concept ...</code></pre>
</div>""",
    },
    # ── Rich content (functional libs) ───────────────────────────
    {
        "name": "mermaid diagram",
        "when": "Flowchart / sequence / state / class / gantt / mind map. Use when 3+ entities have visual structure.",
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
        "when": "Numeric series: benchmark comparison, training curves, distribution. Wrap in a card for emphasis.",
        "example": """\
<canvas data-chart='{"type":"bar","data":{"labels":["Baseline","Ours","SOTA"],"datasets":[{"label":"EM (%)","data":[68.4,87.6,89.1],"backgroundColor":["#94a3b8","#6366f1","#10b981"]}]}}' style="max-width:680px;"></canvas>""",
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
        "when": "Code snippets — always set the language class for syntax highlighting.",
        "example": """\
<pre><code class="language-python">def kl(p, q):
    return (p * (p / q).log()).sum()
</code></pre>""",
    },
    {
        "name": "kv (definition list)",
        "when": "Key-value attributes inside an entity sidebar or facts panel.",
        "example": """\
<dl class="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-2 text-sm">
  <dt class="text-base-content/60 font-medium">Authors</dt><dd class="m-0">Smith et al.</dd>
  <dt class="text-base-content/60 font-medium">Venue</dt>  <dd class="m-0">NeurIPS 2025</dd>
  <dt class="text-base-content/60 font-medium">Code</dt>   <dd class="m-0"><a href="https://github.com/...">github</a></dd>
</dl>""",
    },
    {
        "name": "lucide icon",
        "when": "Inline icons in headings / cards / callouts. Any lucide.dev name works.",
        "example": '<h2><i data-lucide="zap" class="inline-block w-5 h-5 align-[-3px] text-brand-500"></i> Quick start</h2>',
    },
    {
        "name": "zoomable image",
        "when": "Figures the reader might want to enlarge (lightbox).",
        "example": """\
<figure class="my-6">
  <a href="figs/big.png" class="zoomable"><img src="figs/big.png" alt="..." class="rounded-xl border border-base-300"></a>
  <figcaption class="text-xs text-base-content/60 text-center mt-2">Caption text.</figcaption>
</figure>""",
    },
    {
        "name": "gloss tooltip",
        "when": (
            "Inline definition for a sub-topic term you don't want to "
            "interrupt the prose to explain. Hover shows a small tooltip. "
            "Use when (a) defining inline would derail the sentence AND "
            "(b) no full page worth linking to. Tooltip text must still "
            "follow the audience-baseline rule — only words the reader "
            "already knows."
        ),
        "example": """\
The teacher's <span class="gloss" data-tip="A probability over the vocabulary at each generation step — the LLM's raw guess for the next token before sampling.">output distribution</span> drives the loss.

Or with a link to a full page:
<a class="gloss" href="concepts/kl-divergence.html" data-tip="A number measuring how different two probability distributions are; zero means identical.">KL divergence</a>""",
    },
]


WHEN_TO_USE = """\
RULES OF THUMB

  - Every non-trivial page opens with a `.wah-hero` (templates do this
    automatically — but a major sub-section can have its own).
  - 3+ numeric metrics                       → daisyUI `stats`
  - 3-8 step procedure                        → daisyUI `steps`
  - Anything chronological                    → daisyUI `timeline`
  - 2-8 child pages / options                 → card-grid of `.card`
  - 4-8 features with visual hierarchy        → bento grid
  - Critical / warning / cross-link aside     → `alert alert-{info|warning|success|error}`
  - Optional deep-dive (FAQ, edge cases)      → `collapse collapse-arrow`
  - Multi-language / multi-angle same content → `tabs tabs-lifted`
  - Tabular data                              → daisyUI `table` in `.overflow-x-auto`
  - Key/value attribute dump                  → `dl` definition list (sidebar pattern)
  - 3+ entities with structural relations     → mermaid flowchart
  - Numeric data series with comparisons      → Chart.js
  - Formulas                                  → KaTeX `$..$` / `$$..$$`
  - Code                                      → `<pre><code class="language-X">`
  - UI screenshot / demo                      → `mockup-browser`
  - Terminal demo                             → `mockup-code`
  - Inline jargon you can't gracefully redefine → `<span class="gloss" data-tip="…">`

DEFAULT TO RICH. A page made of `<p>` and `<ul>` is the FAILURE case.
If content fits any pattern above, use the component. Plain prose is
fine only for genuine *explanation* paragraphs — anything structural,
numeric, relational, chronological, or comparative must be visual.

STACK COMPONENTS FREELY. A topic page might open with a hero, then
stats, then a mermaid diagram, then a bento grid of children, then a
collapse with derivation details, then a callout, then a timeline of
revisions.

YOU ARE NOT LIMITED TO THIS PALETTE. The base shell loads Tailwind
CSS + daisyUI v5 via CDN — meaning any Tailwind-based snippet from
ANYWHERE on the web is valid. If you've seen a layout pattern on
shadcn/ui, Vercel templates, Flowbite, Preline, HyperUI, Tailblocks,
bento.dev, cruip, tailwindui.com, daisyui.com/components — copy the
class strings directly into the slot. The Tailwind atomic class system
makes snippets portable across projects.

TYPOGRAPHY: wrap any chunk of mixed prose/lists/quotes in a
`<div class="prose prose-base max-w-none">` to get nice headings,
spacing, code-tag styling, and bullets. Templates already do this for
known prose slots — only add a fresh `.prose` wrapper if you're
inserting a free-form prose chunk inside a custom layout.

DARK MODE: use `bg-base-100`, `bg-base-200`, `border-base-300`,
`text-base-content`, `text-base-content/70` — these are daisyUI's
theme-aware tokens. Hardcoded `bg-white` / `text-gray-900` will look
wrong in dark mode.
"""


def render_component_palette() -> str:
    """Compact markdown reference of all visual components for the agent."""
    out: list[str] = [
        "## Visual components (Tailwind + daisyUI v5)",
        "",
        ("The base shell loads Tailwind CSS + daisyUI via CDN. The "
         "components below are the *starting* vocabulary — any "
         "Tailwind class string from any open-source Tailwind site "
         "works in any slot."),
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
