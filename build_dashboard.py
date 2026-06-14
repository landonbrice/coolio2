#!/usr/bin/env python3
"""
Build a self-contained HTML live-rebalancing dashboard from
output/dashboard_state.json. No network, no engine imports, no recomputation —
it renders exactly what the JSON says. Inline CSS, opens anywhere (file://).

    python build_dashboard.py   ->   output/dashboard.html

Mirrors build_report.py's self-contained-HTML style (single TEMPLATE string with
{} placeholders, :root vars with DOUBLED braces because the template is
.format()-ed). Everything is labeled "research / not financial advice."
"""
from __future__ import annotations

import json
import os

OUT = os.environ.get("REBAL_OUTPUT_DIR", "output")


def load():
    """Read the state JSON. Returns None if the file is missing/unreadable."""
    p = os.path.join(OUT, "dashboard_state.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


# ---- formatting helpers (adapted from build_report.py) ----
def pct(x, d=1):
    try:
        return f"{x*100:.{d}f}%"
    except Exception:
        return "—"


def xx(x):
    return f"{x:.2f}×"


def dollars(v):
    try:
        return f"${v:,.0f}"
    except Exception:
        return "—"


def dollars2(v):
    try:
        return f"${v:,.2f}"
    except Exception:
        return "—"


def signed_dollars(v):
    try:
        sign = "+" if v >= 0 else "−"
        return f"{sign}${abs(v):,.0f}"
    except Exception:
        return "—"


def signed_pp(x):
    """Signed percentage-point string, e.g. +7.94pp / −8.05pp."""
    try:
        v = x * 100
        sign = "+" if v >= 0 else "−"
        return f"{sign}{abs(v):.2f}pp"
    except Exception:
        return "—"


def bar(frac, color, w=100):
    frac = max(0.0, min(1.0, frac))
    return (f'<span class="barwrap"><span class="bar" style="width:{frac*w:.0f}%;'
            f'background:{color}"></span></span>')


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ---- error card (missing/broken state, or state carries an "error") ----
def error_html(msg):
    return ERROR_TEMPLATE.format(msg=esc(msg))


def build(d):
    # Catastrophic-failure path: the data layer wrote an "error" key.
    if d.get("error"):
        return error_html(d["error"])

    meta = d.get("meta", {})
    band = meta.get("drift_band", 0.05)
    deploy_cash = meta.get("deploy_cash", 0.0)
    holdings_present = meta.get("holdings_present", d.get("portfolio", {}).get("holdings_present", False))

    # ---------- data_source pill ----------
    src = d.get("data_source", "cached")
    if src == "live":
        src_pill = '<span class="pill live">● LIVE</span>'
    else:
        src_pill = (f'<span class="pill cached">CACHED · offline — prices as of '
                    f'{esc(d.get("price_as_of", "n/a"))}</span>')

    # ---------- drift-alert banner ----------
    if d.get("drift_alert"):
        banner = ('<div class="banner alert">⚠ Portfolio has drifted beyond the '
                  f'{pct(band, 0)} band — rebalance suggested.</div>')
    else:
        banner = (f'<div class="banner ok">✓ Within the {pct(band, 0)} drift band — '
                  'no action required.</div>')

    # ---------- 1. today's ranked top-10 ----------
    top10 = d.get("top10", [])
    max_w = max((r.get("target_weight", 0.0) for r in top10), default=1.0) or 1.0
    top_rows = ""
    for r in top10:
        cap_b = (r.get("market_cap", 0.0) or 0.0) / 1e9
        top_rows += f"""<tr>
          <td class="num">{r.get('rank', '')}</td>
          <td class="tkr">{esc(r.get('ticker', ''))}</td>
          <td class="lbl">{esc(r.get('name', ''))}</td>
          <td class="num">${cap_b:,.1f}B</td>
          <td>{bar(r.get('target_weight', 0.0) / max_w, 'var(--green)')}<span class="num inline">{pct(r.get('target_weight', 0.0), 2)}</span></td>
        </tr>"""
    if not top_rows:
        top_rows = '<tr><td colspan="5" class="empty">No top-10 data in state file.</td></tr>'

    # ---------- 2. deployment plan ----------
    dep = d.get("deployment_plan", [])
    dep_rows = ""
    dep_total = 0.0
    for r in dep:
        dep_total += r.get("dollars", 0.0) or 0.0
        dep_rows += f"""<tr>
          <td class="tkr">{esc(r.get('ticker', ''))}</td>
          <td class="lbl">{esc(r.get('name', ''))}</td>
          <td class="num">{pct(r.get('target_weight', 0.0), 2)}</td>
          <td class="num bold">{dollars2(r.get('dollars', 0.0))}</td>
          <td class="num">{r.get('shares', 0.0):.4f} <span class="muted">@ {dollars2(r.get('price', 0.0))}</span></td>
          <td class="num"><span class="chip buy">BUY</span></td>
        </tr>"""
    if not dep_rows:
        dep_rows = '<tr><td colspan="6" class="empty">No deployment plan in state file.</td></tr>'
    dep_foot = (f"""<tr class="foot-row">
          <td class="lbl bold" colspan="3">Total — deploying from cash</td>
          <td class="num bold">{dollars2(dep_total)}</td>
          <td class="num muted">all BUY</td>
          <td class="num"><span class="chip buy">BUY</span></td>
        </tr>""")

    # ---------- 3. portfolio summary stat cards ----------
    port = d.get("portfolio", {})
    in_band = "No" if d.get("drift_alert") else "Yes"
    in_band_cls = "neg" if d.get("drift_alert") else "pos"
    stat_cards = f"""
      <div class="stat"><div class="sl">Total value</div>
        <div class="sv">{dollars(port.get('total_value', 0.0))}</div>
        <div class="sc">cash + positions</div></div>
      <div class="stat"><div class="sl">Cash</div>
        <div class="sv">{dollars(port.get('cash', 0.0))}</div>
        <div class="sc">uninvested</div></div>
      <div class="stat"><div class="sl"># positions</div>
        <div class="sv">{port.get('num_positions', 0)}</div>
        <div class="sc">held names</div></div>
      <div class="stat"><div class="sl">In drift band?</div>
        <div class="sv {in_band_cls}">{in_band}</div>
        <div class="sc">within {pct(band, 0)} of target</div></div>"""

    # ---------- 4. vs-holdings table ----------
    vs = d.get("vs_holdings", [])
    vs_rows = ""
    for r in vs:
        action = r.get("action", "HOLD")
        act_cls = {"BUY": "buy", "SELL": "sell", "HOLD": "hold"}.get(action, "hold")
        drift = r.get("drift", 0.0) or 0.0
        drift_cls = "drift-hot" if abs(drift) > band else ""
        tag = ""
        if r.get("new_entrant"):
            tag = ' <span class="tag new">← NEW</span>'
        elif r.get("dropped_out"):
            tag = ' <span class="tag dropped">← DROPPED, sell</span>'
        delta = r.get("dollar_delta", 0.0) or 0.0
        delta_cls = "pos" if delta >= 0 else "neg"
        vs_rows += f"""<tr>
          <td class="tkr">{esc(r.get('ticker', ''))}{tag}</td>
          <td class="num">{pct(r.get('current_weight', 0.0), 2)}</td>
          <td class="num">{pct(r.get('target_weight', 0.0), 2)}</td>
          <td class="num {drift_cls}">{signed_pp(drift)}</td>
          <td class="num"><span class="chip {act_cls}">{esc(action)}</span></td>
          <td class="num {delta_cls}">{signed_dollars(delta)}</td>
        </tr>"""
    if not vs_rows:
        vs_rows = '<tr><td colspan="6" class="empty">No vs-holdings rows in state file.</td></tr>'

    holdings_note = ""
    if not holdings_present:
        holdings_note = (f'<div class="note">No <span class="mono">holdings.json</span> found — '
                         f'showing an all-cash {dollars(deploy_cash)} starting portfolio. Every '
                         'target name is a buy.</div>')

    # ---------- 5. benchmark card (hidden if unavailable) ----------
    bench = d.get("benchmark", {})
    if bench.get("available"):
        bench_block = f"""
  <section>
    <div class="snum">05 · BENCHMARK CONTEXT</div>
    <h2>How the index is doing</h2>
    <p class="lede">Frame the strategy as a mega-cap-tech <b>satellite</b> sleeve held against a broad
    index core — not a replacement for it. The dashboard recommends; you decide the sizing.</p>
    <div class="cards">
      <div class="card" style="border-top:3px solid var(--blue)">
        <div class="ct">{esc(bench.get('label', 'Benchmark'))} <span class="muted">({esc(bench.get('symbol', ''))})</span></div>
        <div class="cbig">{bench.get('level', 0.0):,.2f}<span class="cunit"> level</span></div>
        <div class="crow"><span>trailing 1-year return</span><b class="pos">{pct(bench.get('trailing_1y_return', 0.0))}</b></div>
        <div class="crow"><span>as of</span><b>{esc(bench.get('as_of', ''))}</b></div>
        <div class="cnote">A 20–30% concentrated satellite on this core captures part of the mega-cap-tech
        edge at closer-to-index volatility. Size for a −50% drawdown in the satellite sleeve.</div>
      </div>
    </div>
  </section>"""
    else:
        bench_block = ""

    # ---------- notes ----------
    notes = d.get("notes", []) or []
    notes_block = ""
    if notes:
        items = "".join(f"<li>{esc(n)}</li>" for n in notes)
        notes_block = f'<div class="notes"><span class="nh">Notes &amp; caveats</span><ul>{items}</ul></div>'

    # ---------- footer fields ----------
    method_line = ("point-in-time membership, cap-weighted, dividends reinvested via adjusted close")

    return TEMPLATE.format(
        as_of=esc(d.get("as_of", "")),
        price_as_of=esc(d.get("price_as_of", "")),
        src_pill=src_pill,
        banner=banner,
        deploy_cash=dollars(deploy_cash),
        universe=esc(meta.get("universe", "")),
        weighting=esc(meta.get("weighting", "")),
        top_n=meta.get("top_n", ""),
        band_pct=pct(band, 0),
        top_rows=top_rows,
        dep_rows=dep_rows,
        dep_foot=dep_foot,
        stat_cards=stat_cards,
        vs_rows=vs_rows,
        holdings_note=holdings_note,
        bench_block=bench_block,
        notes_block=notes_block,
        next_rebalance_date=esc(d.get("next_rebalance_date", "")),
        days_to_rebalance=d.get("days_to_rebalance", ""),
        cadence=esc(meta.get("cadence", "")),
        method_line=method_line,
    )


# ============================ TEMPLATES ============================
# Braces in CSS are DOUBLED because the whole string is .format()-ed.

_STYLE = """
:root{{
  --ink:#1a2332; --muted:#5b6776; --line:#e4e8ee; --bg:#fbfcfd; --card:#fff;
  --green:#2e7d57; --blue:#1f77b4; --red:#c0392b; --gold:#b07d2b; --accent:#2e7d57;
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}}
.wrap{{max-width:980px;margin:0 auto;padding:0 28px 80px}}
header{{padding:54px 0 22px;border-bottom:1px solid var(--line);margin-bottom:8px}}
.kicker{{letter-spacing:.16em;text-transform:uppercase;font-size:11.5px;color:var(--accent);font-weight:700}}
h1{{font-size:32px;line-height:1.18;margin:10px 0 6px;letter-spacing:-.01em}}
.sub{{color:var(--muted)}}
.meta{{margin-top:16px;font-size:12.5px;color:var(--muted);display:flex;gap:18px;flex-wrap:wrap;align-items:center}}
.meta b{{color:var(--ink)}}
.pill{{display:inline-block;border-radius:999px;padding:3px 11px;font-size:11px;font-weight:800;letter-spacing:.03em}}
.pill.live{{background:#eaf7ef;color:var(--green);border:1px solid #bfe3cd}}
.pill.cached{{background:#eef1f5;color:var(--muted);border:1px solid var(--line)}}
.badge{{display:inline-block;background:#fff4f4;color:var(--red);border:1px solid #f3d3d3;
  border-radius:5px;padding:3px 10px;font-size:11px;font-weight:700;letter-spacing:.03em}}
.banner{{margin:16px 0 2px;border-radius:8px;padding:11px 16px;font-size:13.5px;font-weight:600}}
.banner.alert{{background:#fdf4e3;color:#8a5d12;border:1px solid #f0dcae}}
.banner.ok{{background:#eaf7ef;color:#1f6e46;border:1px solid #bfe3cd}}
section{{margin:44px 0 0;scroll-margin-top:18px}}
.snum{{color:var(--accent);font-weight:800;font-size:13px;letter-spacing:.05em}}
h2{{font-size:22px;margin:6px 0 4px;letter-spacing:-.01em}}
.lede{{color:var(--muted);margin:0 0 16px;max-width:74ch}}
table{{width:100%;border-collapse:collapse;font-size:13.5px;margin:6px 0 4px}}
th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--muted);font-weight:700;padding:6px 9px;border-bottom:2px solid var(--line)}}
td{{padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:middle}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}
.num.inline{{margin-left:8px}}
.lbl{{font-weight:600}}
.tkr{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-weight:800;font-size:13px}}
.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}}
.bold{{font-weight:800}} .neg{{color:var(--red)}} .pos{{color:var(--green)}}
.muted{{color:var(--muted);font-weight:500}}
.drift-hot{{color:var(--red);font-weight:800}}
.empty{{text-align:center;color:var(--muted);padding:18px 9px}}
.foot-row td{{border-top:2px solid var(--line);background:#f7faf8}}
.barwrap{{display:inline-block;width:96px;height:9px;background:#eef1f5;border-radius:5px;vertical-align:middle;overflow:hidden}}
.bar{{display:block;height:100%;border-radius:5px}}
.chip{{display:inline-block;font-size:10.5px;padding:2px 8px;border-radius:5px;font-weight:800;letter-spacing:.02em}}
.chip.buy{{background:#eaf7ef;color:var(--green)}}
.chip.sell{{background:#fdeaea;color:var(--red)}}
.chip.hold{{background:#eef1f5;color:var(--muted)}}
.tag{{font-size:10px;font-weight:700;letter-spacing:.02em}}
.tag.new{{color:var(--green)}} .tag.dropped{{color:var(--red)}}
.cards{{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0 6px}}
.card{{flex:1;min-width:220px;background:var(--card);border:1px solid var(--line);
  border-radius:10px;padding:16px 16px 14px;box-shadow:0 1px 2px rgba(20,30,50,.04)}}
.ct{{font-size:12.5px;color:var(--muted);font-weight:700;min-height:18px}}
.cbig{{font-size:28px;font-weight:800;letter-spacing:-.02em;margin:6px 0 10px}}
.cunit{{font-size:13px;font-weight:600;color:var(--muted)}}
.crow{{display:flex;justify-content:space-between;font-size:12.5px;padding:2px 0;color:var(--muted)}}
.crow b{{color:var(--ink)}}
.cnote{{margin-top:9px;font-size:11.5px;color:var(--muted);border-top:1px dashed var(--line);padding-top:7px}}
.strip{{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0 8px}}
.stat{{flex:1;min-width:150px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.stat .sl{{font-size:11px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.04em}}
.stat .sv{{font-size:25px;font-weight:800;margin-top:4px;letter-spacing:-.01em}}
.stat .sc{{font-size:11.5px;color:var(--muted);margin-top:3px}}
.note{{background:#f4f7fb;border-left:3px solid var(--accent);border-radius:0 8px 8px 0;
  padding:11px 15px;margin:12px 0 2px;font-size:13px;color:var(--muted)}}
.caption{{font-size:12px;color:var(--muted);margin:8px 0 2px}}
.notes{{background:#fbf6ee;border-left:3px solid var(--gold);border-radius:0 8px 8px 0;
  padding:12px 16px;margin:26px 0 2px;font-size:12.5px;color:var(--muted)}}
.notes .nh{{font-weight:800;color:var(--gold);font-size:11px;text-transform:uppercase;
  letter-spacing:.06em;display:block;margin-bottom:6px}}
.notes ul{{margin:0;padding-left:18px}} .notes li{{margin:3px 0}}
.foot{{margin-top:50px;padding-top:20px;border-top:1px solid var(--line);font-size:11.5px;color:var(--muted)}}
"""

TEMPLATE = ("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Top-10 Rebalancer — Live Dashboard</title>
<style>""" + _STYLE + """</style></head><body><div class="wrap">

<header>
  <div class="kicker">Research · Not Financial Advice</div>
  <h1>Top-10 Rebalancer — Live Dashboard</h1>
  <div class="sub">Today's mega-cap leaders, the target cap-weighted portfolio, and a
  recommend-not-execute rebalancing plan vs your holdings. The bot recommends; a human trades.</div>
  <div class="meta">
    <span><b>As of</b> {as_of}</span>
    <span><b>Prices</b> {price_as_of}</span>
    <span>{src_pill}</span>
    <span><b>Universe</b> {universe} · {weighting} · top-{top_n}</span>
  </div>
  <div style="margin-top:14px"><span class="badge">RESEARCH / NOT FINANCIAL ADVICE — THE BOT RECOMMENDS, A HUMAN TRADES</span></div>
  {banner}
</header>

<section>
  <div class="snum">01 · TODAY'S RANKED TOP-10</div>
  <h2>The current mega-cap leaders</h2>
  <p class="lede">Ranked by market capitalization; target weights are cap-weighted over the
  point-in-time {universe} roster and sum to 100%.</p>
  <table>
    <tr><th class="num">Rank</th><th>Ticker</th><th>Name</th><th class="num">Market cap</th><th>Target weight</th></tr>
    {top_rows}
  </table>
</section>

<section>
  <div class="snum">02 · DEPLOYMENT PLAN</div>
  <h2>Deploy {deploy_cash} of fresh cash</h2>
  <p class="lede">Assumes you start in cash — every line is a buy. Dollars and shares per name at the
  prices shown.</p>
  <table>
    <tr><th>Ticker</th><th>Name</th><th class="num">Target wt</th><th class="num">$ to invest</th>
        <th class="num">Shares (@ price)</th><th class="num">Action</th></tr>
    {dep_rows}
    {dep_foot}
  </table>
  <div class="caption">Assumes you start in cash; every line is a buy. Recommend-not-execute.</div>
</section>

<section>
  <div class="snum">03 · PORTFOLIO vs TARGET</div>
  <h2>Where you are vs where the bot wants you</h2>
  <p class="lede">Current weights vs target, the signed drift, and the suggested action when a name is
  beyond the {band_pct} band. + delta = buy, − delta = sell.</p>
  <div class="strip">{stat_cards}</div>
  {holdings_note}
  <table>
    <tr><th>Ticker</th><th class="num">Current wt</th><th class="num">Target wt</th>
        <th class="num">Drift</th><th class="num">Action</th><th class="num">$ delta</th></tr>
    {vs_rows}
  </table>
</section>
{bench_block}

  {notes_block}

<div class="foot">
  <b>Next rebalance</b> {next_rebalance_date} ({days_to_rebalance} days) · cadence {cadence} (quarterly).
  <b>Method:</b> {method_line}. Past performance ≠ future results. Recommend-not-execute: no orders are
  placed — the bot recommends, a human trades. This is a research/curiosity tool and <b>not financial
  advice.</b> Generated by <span class="mono">build_dashboard.py</span> from
  <span class="mono">dashboard_state.json</span> · as of {as_of}.
</div>

</div></body></html>""")

ERROR_TEMPLATE = ("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Top-10 Rebalancer — Live Dashboard</title>
<style>""" + _STYLE + """
.errcard{{background:#fff4f4;border:1px solid #f3d3d3;border-radius:10px;padding:22px 24px;margin:24px 0}}
.errcard h2{{color:var(--red);margin:0 0 8px}}
</style></head><body><div class="wrap">
<header>
  <div class="kicker">Research · Not Financial Advice</div>
  <h1>Top-10 Rebalancer — Live Dashboard</h1>
  <div style="margin-top:14px"><span class="badge">RESEARCH / NOT FINANCIAL ADVICE — THE BOT RECOMMENDS, A HUMAN TRADES</span></div>
</header>
<div class="errcard">
  <h2>Dashboard data unavailable</h2>
  <p>{msg}</p>
  <p class="muted">Run <span class="mono">python dashboard_data.py</span> (or
  <span class="mono">python refresh_dashboard.py</span>) to regenerate
  <span class="mono">output/dashboard_state.json</span>, then rebuild.</p>
</div>
<div class="foot">
  Generated by <span class="mono">build_dashboard.py</span>. Not financial advice.
</div>
</div></body></html>""")


def main():
    d = load()
    if d is None:
        html = error_html("No state file found at output/dashboard_state.json (or it could not "
                          "be parsed).")
    else:
        html = build(d)
    path = os.path.join(OUT, "dashboard.html")
    os.makedirs(OUT, exist_ok=True)
    with open(path, "w") as f:
        f.write(html)
    print(f"Wrote {path} ({len(html)//1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
