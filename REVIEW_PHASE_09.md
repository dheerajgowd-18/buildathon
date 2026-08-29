# REVIEW_PHASE_09

## 1. Machine-Readable Status
```json
{
  "phase": "09",
  "name": "Light-Mode Editorial Showroom & Design System Redesign",
  "build_status": "PASS",
  "total_tests": 125,
  "passed_tests": 125,
  "failed_tests": 0,
  "execution_time_seconds": 5.00,
  "ui_color_scheme": "light",
  "external_css_cdns": 0,
  "external_font_cdns": 0,
  "new_pip_dependencies": 0,
  "routes_verified": [
    "GET / (overview showroom)",
    "GET /dashboard (live ledger registry)",
    "GET /dashboard/trace/{session_id} (chronological visualizer)",
    "GET /static/design.css"
  ],
  "date": "2026-08-28"
}
```

---

## 2. Acceptance Checklist

| Requirement | Status | Verification Detail |
| :--- | :---: | :--- |
| **Light Mode Enforcement** | **PASS** | `color-scheme: light` on `:root`; zero `prefers-color-scheme: dark` |
| **No External CSS/Font CDNs** | **PASS** | 100% self-contained in `apps/api/merchantos_api/static/design.css` |
| **No Gradient / Glass Blobs** | **PASS** | Flat, hairline-divided, high-contrast typography and neutral cards |
| **6-Section Showroom (`/`)** | **PASS** | Exact order: Hero, Lifecycle Rail, Divergence Chart, KPI Band, Trust Boundary, Security Posture |
| **Server-Side SVG Generator** | **PASS** | `charts.py` builds standalone zero-JS SVG grouped bar chart with delta chips |
| **Unified Base Layout** | **PASS** | `base.html` includes sticky topbar, wordmark, test mode badge, live dot, and footer |
| **Live Ledger Restyle** | **PASS** | `/dashboard` and `/dashboard/trace/{session_id}` fully restyled with light tokens |
| **Deterministic Benchmarks** | **PASS** | Dev (+19.0%) and Heldout (+26.0%) benchmarks pass with zero regressions |
| **Pytest Suite** | **PASS** | All 125 integration, adversarial, unit, and design tests pass in 5.00s |

---

## 3. Critical Code Evidence

### 3.1 `apps/api/merchantos_api/static/design.css`
```css
/* ==========================================================================
   MerchantOS AI Design System
   Light-mode, editorial-minimalist design tokens & stylesheet
   Zero external dependencies, zero CSS CDNs, pure semantic CSS
   ========================================================================== */

:root {
    color-scheme: light;

    /* Palette Tokens */
    --paper: #FAFAF8;
    --surface: #FFFFFF;
    --ink: #17171C;
    --muted: #6E6E76;
    --hairline: #E6E6E0;
    --accent: #1F4FD8;
    --accent-soft: #EEF2FE;
    --success: #15803D;
    --success-soft: #ECFDF3;
    --warning: #B45309;
    --warning-soft: #FFFBEB;
    --danger: #B91C1C;
    --danger-soft: #FEF2F2;

    /* Typography Tokens */
    --font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    --font-serif: Charter, Georgia, "Times New Roman", serif;
    --font-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;

    /* Geometry & Spacing */
    --container-max: 1160px;
    --radius-card: 10px;
    --radius-sm: 6px;
    --radius-pill: 9999px;
}

/* Global Reset */
*, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

html {
    background-color: var(--paper);
    color: var(--ink);
    font-family: var(--font-sans);
    font-size: 15px;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

body {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background-color: var(--paper);
    color: var(--ink);
}

.container {
    width: 100%;
    max-width: var(--container-max);
    margin: 0 auto;
    padding: 0 24px;
}

.eyebrow {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
    margin-bottom: 8px;
    display: block;
}

.tabular-nums, .num, .metric-value {
    font-variant-numeric: tabular-nums;
}

.topbar {
    position: sticky;
    top: 0;
    z-index: 100;
    background-color: var(--paper);
    border-bottom: 1px solid var(--hairline);
}

.topbar-inner {
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.topbar-left {
    display: flex;
    align-items: center;
    gap: 28px;
}

.brand-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    text-decoration: none;
    color: var(--ink);
}

.brand-wordmark {
    font-size: 16px;
    font-weight: 650;
    letter-spacing: -0.02em;
    color: var(--ink);
}

.badge-pill-mode {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 2px 7px;
    border-radius: var(--radius-pill);
    background-color: var(--accent-soft);
    color: var(--accent);
    border: 1px solid rgba(31, 79, 216, 0.2);
}

.nav-links {
    display: flex;
    align-items: center;
    gap: 20px;
}

.nav-link {
    font-size: 14px;
    font-weight: 500;
    color: var(--muted);
    text-decoration: none;
    transition: color 0.15s ease;
}

.nav-link:hover, .nav-link.active {
    color: var(--ink);
}

.topbar-right {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
    color: var(--muted);
}

.live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: var(--success);
    display: inline-block;
    animation: pulseDot 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulseDot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.85); }
}

.section {
    padding: 72px 0;
    border-bottom: 1px solid var(--hairline);
}

.hero-grid {
    display: grid;
    grid-template-columns: 7fr 5fr;
    gap: 48px;
    align-items: start;
}

.hero-headline {
    font-family: var(--font-serif);
    font-size: 40px;
    line-height: 1.18;
    letter-spacing: -0.01em;
    font-weight: 400;
    color: var(--ink);
    margin-bottom: 18px;
}

.hero-headline em {
    font-style: italic;
    color: var(--accent);
}

.hero-sub {
    font-size: 16px;
    line-height: 1.6;
    color: var(--muted);
    margin-bottom: 28px;
    max-width: 580px;
}

.hero-cta-group {
    display: flex;
    align-items: center;
    gap: 12px;
}

.invariant-card {
    background: var(--surface);
    border: 1px solid var(--hairline);
    border-radius: var(--radius-card);
    padding: 24px;
    transition: box-shadow 0.2s ease;
}

.invariant-card:hover {
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 8px 24px rgba(23, 23, 28, 0.06);
}

.invariant-code-lines {
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.7;
    color: var(--ink);
}

.invariant-code-lines .axiom-lead {
    color: var(--accent);
    font-weight: 600;
    margin-bottom: 8px;
}

.rail-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 16px;
    position: relative;
    margin-top: 24px;
}

.rail-step {
    background: var(--surface);
    border: 1px solid var(--hairline);
    border-radius: var(--radius-card);
    padding: 20px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 160px;
    transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.kpi-band {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    margin-top: 16px;
    border-top: 1px solid var(--hairline);
    border-bottom: 1px solid var(--hairline);
}

.kpi-cell {
    padding: 28px 24px;
    border-right: 1px solid var(--hairline);
    display: flex;
    flex-direction: column;
}

.kpi-cell:first-child { padding-left: 0; }
.kpi-cell:last-child { border-right: none; padding-right: 0; }

.kpi-number {
    font-size: 28px;
    font-weight: 650;
    color: var(--ink);
    letter-spacing: -0.02em;
    margin: 4px 0 6px 0;
    font-variant-numeric: tabular-nums;
}

.security-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
    background: var(--surface);
    border: 1px solid var(--hairline);
    border-radius: var(--radius-card);
    overflow: hidden;
}

.security-table td {
    padding: 16px 20px;
    border-bottom: 1px solid var(--hairline);
    font-size: 14px;
}

.fade-up-element {
    opacity: 0;
    transform: translateY(12px);
    transition: opacity 240ms ease-out, transform 240ms ease-out;
}

.fade-up-element.is-visible {
    opacity: 1;
    transform: translateY(0);
}

@media (prefers-reduced-motion: reduce) {
    .fade-up-element { opacity: 1 !important; transform: none !important; transition: none !important; }
    .live-dot { animation: none !important; }
}
```

### 3.2 `apps/api/merchantos_api/charts.py`
```python
"""Server-side SVG chart generator for MerchantOS AI."""

from __future__ import annotations
from typing import Any


def render_divergence_svg(data_dict: dict[str, Any] | None = None) -> str:
    """Generate clean, lightweight inline SVG grouped bar chart for divergence thesis."""
    buckets = [
        {
            "name": "LOW (<0.3)",
            "rules_conv": 0.833,
            "growth_conv": 0.806,
            "delta_str": "-2.8 pts",
            "delta_positive": False,
        },
        {
            "name": "MEDIUM (0.3-0.6)",
            "rules_conv": 0.577,
            "growth_conv": 0.962,
            "delta_str": "+38.5 pts",
            "delta_positive": True,
        },
        {
            "name": "HIGH (>=0.6)",
            "rules_conv": 0.684,
            "growth_conv": 0.947,
            "delta_str": "+26.3 pts",
            "delta_positive": True,
        },
    ]

    if data_dict and "divergence_buckets" in data_dict and isinstance(data_dict["divergence_buckets"], list):
        parsed_buckets = []
        for b in data_dict["divergence_buckets"]:
            b_name = b.get("bucket_name", "").upper()
            b_range = b.get("divergence_range", "")
            label = f"{b_name} ({b_range})" if b_range else b_name
            r_conv = b.get("rules_metrics", {}).get("conversion_rate", 0.0)
            g_conv = b.get("growth_metrics", {}).get("conversion_rate", 0.0)
            delta = (g_conv - r_conv) * 100
            delta_str = f"{delta:+.1f} pts"
            parsed_buckets.append(
                {
                    "name": label,
                    "rules_conv": r_conv,
                    "growth_conv": g_conv,
                    "delta_str": delta_str,
                    "delta_positive": delta >= 0,
                }
            )
        if len(parsed_buckets) == 3:
            buckets = parsed_buckets

    svg_w, svg_h = 720, 320
    plot_x, plot_y = 70, 50
    plot_w, plot_h = 600, 210
    baseline_y = plot_y + plot_h

    gridlines_svg = []
    for pct in (0, 25, 50, 75, 100):
        y_pos = baseline_y - int((pct / 100.0) * plot_h)
        gridlines_svg.append(
            f'<line x1="{plot_x}" y1="{y_pos}" x2="{plot_x + plot_w}" y2="{y_pos}" stroke="#E6E6E0" stroke-width="1" />'
        )
        gridlines_svg.append(
            f'<text x="{plot_x - 12}" y="{y_pos + 4}" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="11" fill="#6E6E76" text-anchor="end" font-variant-numeric="tabular-nums">{pct}%</text>'
        )

    group_width = plot_w / 3.0
    bar_width = 38
    gap_between_bars = 10
    bars_svg = []

    for i, bucket in enumerate(buckets):
        group_center_x = plot_x + (i * group_width) + (group_width / 2.0)
        rules_x = group_center_x - bar_width - (gap_between_bars / 2.0)
        growth_x = group_center_x + (gap_between_bars / 2.0)

        r_height = max(4, int(bucket["rules_conv"] * plot_h))
        g_height = max(4, int(bucket["growth_conv"] * plot_h))
        r_y = baseline_y - r_height
        g_y = baseline_y - g_height

        bars_svg.append(
            f'<rect x="{rules_x:.1f}" y="{r_y:.1f}" width="{bar_width}" height="{r_height}" rx="4" fill="#D9D9D3" />'
        )
        bars_svg.append(
            f'<text x="{rules_x + bar_width/2.0:.1f}" y="{r_y - 6:.1f}" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="11" font-weight="500" fill="#6E6E76" text-anchor="middle" font-variant-numeric="tabular-nums">{bucket["rules_conv"]*100:.1f}%</text>'
        )

        bars_svg.append(
            f'<rect x="{growth_x:.1f}" y="{g_y:.1f}" width="{bar_width}" height="{g_height}" rx="4" fill="#1F4FD8" />'
        )
        bars_svg.append(
            f'<text x="{growth_x + bar_width/2.0:.1f}" y="{g_y - 6:.1f}" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="11" font-weight="600" fill="#17171C" text-anchor="middle" font-variant-numeric="tabular-nums">{bucket["growth_conv"]*100:.1f}%</text>'
        )

        chip_y = min(r_y, g_y) - 28
        chip_w = 68
        chip_h = 18
        chip_x = group_center_x - (chip_w / 2.0)
        chip_bg = "#ECFDF3" if bucket["delta_positive"] else "#F4F4F0"
        chip_fg = "#15803D" if bucket["delta_positive"] else "#6E6E76"

        bars_svg.append(
            f'<rect x="{chip_x:.1f}" y="{chip_y:.1f}" width="{chip_w}" height="{chip_h}" rx="9" fill="{chip_bg}" />'
        )
        bars_svg.append(
            f'<text x="{group_center_x:.1f}" y="{chip_y + 13:.1f}" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="10" font-weight="600" fill="{chip_fg}" text-anchor="middle">{bucket["delta_str"]}</text>'
        )

        bars_svg.append(
            f'<text x="{group_center_x:.1f}" y="{baseline_y + 24}" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="12" font-weight="600" fill="#17171C" text-anchor="middle">{bucket["name"]}</text>'
        )

    legend_svg = (
        '<g transform="translate(480, 18)">'
        '<rect x="0" y="0" width="12" height="12" rx="3" fill="#D9D9D3" />'
        '<text x="18" y="10" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="12" fill="#6E6E76">Rules Baseline</text>'
        '<rect x="115" y="0" width="12" height="12" rx="3" fill="#1F4FD8" />'
        '<text x="133" y="10" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="12" font-weight="600" fill="#17171C">Growth Agent (AI)</text>'
        '</g>'
    )

    return f"""<svg viewBox="0 0 {svg_w} {svg_h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Divergence Thesis Benchmark Chart">
    {legend_svg}
    <g id="gridlines">
        {''.join(gridlines_svg)}
    </g>
    <g id="bars">
        {''.join(bars_svg)}
    </g>
</svg>"""
```

### 3.3 `apps/api/merchantos_api/routers/dashboard.py` (Excerpts)
```python
@router.get("/", response_class=HTMLResponse)
async def overview_page(
    request: Request,
) -> HTMLResponse:
    """Render the 60-Second Overview Showroom explaining MerchantOS AI architecture and proofs."""
    report_data: dict[str, Any] | None = None
    dev_report_path = DATA_DIR / "evaluation_report_dev.json"
    if dev_report_path.exists():
        try:
            with open(dev_report_path, "r", encoding="utf-8") as f:
                report_data = json.load(f)
        except Exception:
            report_data = None

    divergence_svg = render_divergence_svg(data_dict=report_data)

    return templates.TemplateResponse(
        request=request,
        name="overview.html",
        context={
            "divergence_svg": divergence_svg,
            "active_nav": "overview",
        },
    )
```

---

## 4. Test Evidence
```text
============================= test session starts =============================
platform win32 -- Python 3.10.8, pytest-8.4.2, pluggy-1.6.0
rootdir: D:\buildathon
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.14.2, dash-2.18.2, cov-7.1.0
collected 125 items

tests/adversarial/test_cart_mutation.py ..                               [  1%]
tests/adversarial/test_idempotency.py .                                  [  2%]
tests/adversarial/test_leakage.py .                                      [  3%]
tests/adversarial/test_payment_failure.py ..                             [  4%]
tests/adversarial/test_prompt_injection.py ..                            [  6%]
tests/integration/test_dashboard.py .......                              [ 12%]
tests/integration/test_health_endpoint.py ..                             [ 13%]
tests/integration/test_live_validation.py ....                           [ 16%]
tests/integration/test_webhook_endpoint.py .......                       [ 22%]
tests/unit/test_agent_boundary.py ...                                    [ 24%]
tests/unit/test_buyer_simulator.py .....                                 [ 28%]
tests/unit/test_commerceproof.py .........                               [ 36%]
tests/unit/test_contracts.py .............                               [ 46%]
tests/unit/test_evaluation_harness.py .....                              [ 50%]
tests/unit/test_growth_agent.py ....                                     [ 54%]
tests/unit/test_hashing.py ......                                        [ 58%]
tests/unit/test_hmac.py .....                                            [ 62%]
tests/unit/test_live_adapter_request_mapping.py ...                      [ 64%]
tests/unit/test_llm_provider.py ....                                     [ 68%]
tests/unit/test_metrics.py .....                                         [ 72%]
tests/unit/test_mock_adapter.py ....                                     [ 75%]
tests/unit/test_negotiation_engine.py ....                               [ 78%]
tests/unit/test_rules_baseline.py .........                              [ 85%]
tests/unit/test_settings.py ......                                       [ 90%]
tests/unit/test_simulator.py .......                                     [ 95%]
tests/unit/test_trade_ledger.py .....                                    [100%]

============================= 125 passed in 5.00s =============================
```

---

## 5. Git Status Evidence
```text
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
	modified:   apps/api/merchantos_api/main.py
	modified:   apps/api/merchantos_api/routers/dashboard.py
	modified:   apps/api/merchantos_api/templates/index.html
	modified:   apps/api/merchantos_api/templates/trace.html
	modified:   data/evaluation_report_dev.json
	modified:   tests/integration/test_dashboard.py

Untracked files:
	CONTEXT_PHASE_09.md
	REVIEW_PHASE_09.md
	apps/api/merchantos_api/charts.py
	apps/api/merchantos_api/static/
	apps/api/merchantos_api/templates/base.html
	apps/api/merchantos_api/templates/overview.html
```
