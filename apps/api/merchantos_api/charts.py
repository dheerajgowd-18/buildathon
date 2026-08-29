"""Server-side SVG chart generator for MerchantOS AI."""

from __future__ import annotations

from typing import Any


def render_divergence_svg(data_dict: dict[str, Any] | None = None) -> str:
    """Generate clean, lightweight inline SVG grouped bar chart for divergence thesis.

    Args:
        data_dict: Parsed evaluation report dictionary containing divergence_buckets.

    Returns:
        String containing <svg> element.
    """
    # Default benchmark values from Phase 05/08 empirical evaluation if report is None
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

    # Dimensions & Plot Area (Remediated with headroom to prevent label/chip collisions)
    svg_w = 720
    svg_h = 340
    plot_x = 70
    plot_y = 64
    plot_w = 600
    plot_h = 210
    baseline_y = plot_y + plot_h  # Y position for 0% (274)

    # Y-Axis Gridlines: 0%, 25%, 50%, 75%, 100%
    gridlines_svg = []
    for pct in (0, 25, 50, 75, 100):
        y_pos = baseline_y - int((pct / 100.0) * plot_h)
        gridlines_svg.append(
            f'<line x1="{plot_x}" y1="{y_pos}" x2="{plot_x + plot_w}" y2="{y_pos}" stroke="#E6E6E0" stroke-width="1" />'
        )
        gridlines_svg.append(
            f'<text x="{plot_x - 12}" y="{y_pos + 4}" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="11" fill="#6E6E76" text-anchor="end" font-variant-numeric="tabular-nums">{pct}%</text>'
        )

    # Grouped Bars
    # 3 groups across plot_w = 600 px. Center positions: 140, 340, 540
    group_width = plot_w / 3.0  # 200 px each
    bar_width = 38
    gap_between_bars = 10
    bars_svg = []

    for i, bucket in enumerate(buckets):
        group_center_x = plot_x + (i * group_width) + (group_width / 2.0)
        rules_x = group_center_x - bar_width - (gap_between_bars / 2.0)
        growth_x = group_center_x + (gap_between_bars / 2.0)

        # Bar heights
        r_height = max(4, int(bucket["rules_conv"] * plot_h))
        g_height = max(4, int(bucket["growth_conv"] * plot_h))
        r_y = baseline_y - r_height
        g_y = baseline_y - g_height

        # Rules Bar (Gray #D9D9D3)
        bars_svg.append(
            f'<rect x="{rules_x:.1f}" y="{r_y:.1f}" width="{bar_width}" height="{r_height}" rx="4" fill="#D9D9D3" />'
        )
        # Rules Percentage Label Above Bar
        bars_svg.append(
            f'<text x="{rules_x + bar_width/2.0:.1f}" y="{r_y - 6:.1f}" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="11" font-weight="500" fill="#6E6E76" text-anchor="middle" font-variant-numeric="tabular-nums">{bucket["rules_conv"]*100:.1f}%</text>'
        )

        # Growth Bar (Cobalt #1F4FD8)
        bars_svg.append(
            f'<rect x="{growth_x:.1f}" y="{g_y:.1f}" width="{bar_width}" height="{g_height}" rx="4" fill="#1F4FD8" />'
        )
        # Growth Percentage Label Above Bar
        bars_svg.append(
            f'<text x="{growth_x + bar_width/2.0:.1f}" y="{g_y - 6:.1f}" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="11" font-weight="600" fill="#17171C" text-anchor="middle" font-variant-numeric="tabular-nums">{bucket["growth_conv"]*100:.1f}%</text>'
        )

        # Delta Chip above group (Fully above value labels with 8px+ clearance)
        chip_y = min(r_y, g_y) - 46
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

        # X-Axis Bucket Label
        bars_svg.append(
            f'<text x="{group_center_x:.1f}" y="{baseline_y + 24}" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="12" font-weight="600" fill="#17171C" text-anchor="middle">{bucket["name"]}</text>'
        )

    # Legend at Top Right
    legend_svg = (
        '<g transform="translate(480, 20)">'
        '<rect x="0" y="0" width="12" height="12" rx="3" fill="#D9D9D3" />'
        '<text x="18" y="10" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="12" fill="#6E6E76">Rules Baseline</text>'
        '<rect x="115" y="0" width="12" height="12" rx="3" fill="#1F4FD8" />'
        '<text x="133" y="10" font-family="ui-sans-serif, system-ui, -apple-system, sans-serif" font-size="12" font-weight="600" fill="#17171C">Growth Agent (AI)</text>'
        '</g>'
    )

    svg_content = f"""<svg viewBox="0 0 {svg_w} {svg_h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Divergence Thesis Benchmark Chart">
    {legend_svg}
    <g id="gridlines">
        {''.join(gridlines_svg)}
    </g>
    <g id="bars">
        {''.join(bars_svg)}
    </g>
</svg>"""
    return svg_content
