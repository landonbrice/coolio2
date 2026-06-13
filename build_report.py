#!/usr/bin/env python3
"""
Build a self-contained HTML IC report from output/analysis_data.json + the
sweep/satellite PNGs. Images are base64-inlined so analysis.html opens anywhere
(file://) with no dependencies. Re-run after changing the analysis or styling.

    python build_report.py   ->   output/analysis.html
"""
from __future__ import annotations

import base64
import json
import os

OUT = os.environ.get("REBAL_OUTPUT_DIR", "output")


def load():
    with open(os.path.join(OUT, "analysis_data.json")) as f:
        return json.load(f)


def img(name):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        return ""
    b = base64.b64encode(open(p, "rb").read()).decode()
    return f"data:image/png;base64,{b}"


# ---- formatting helpers ----
def pct(x, d=1):
    return f"{x*100:.{d}f}%"


def xx(x):
    return f"{x:.2f}×"


def bar(frac, color, w=100):
    frac = max(0.0, min(1.0, frac))
    return (f'<span class="barwrap"><span class="bar" style="width:{frac*w:.0f}%;'
            f'background:{color}"></span></span>')


def build(d):
    m = d["meta"]
    bench = d["benchmark"]["full"]
    sat = d["satellite"]
    rv = d["rebalancing_value"]
    uni = d["universe"]
    tax = d["tax"]
    of = d["overfit"]

    # ---------- universe rows ----------
    uni_order = ["nasdaq10", "us10", "global10"]
    max_xsp = max(uni[u]["xsp_median"] for u in uni_order)
    uni_rows = ""
    for u in uni_order:
        g = uni[u]
        hot = " class='hot'" if u == "nasdaq10" else ""
        uni_rows += f"""<tr{hot}>
          <td class="lbl">{u}</td>
          <td class="num">{pct(g['cagr_median'])}</td>
          <td class="num">{pct(g['cagr_best'])}</td>
          <td>{bar(g['xsp_median']/max_xsp, '#2e7d57')}<span class="num inline">{xx(g['xsp_median'])}</span></td>
          <td class="num">{xx(g['xsp_best'])}</td>
          <td class="num">{g['sharpe_best']:.2f}</td>
        </tr>"""

    # ---------- CAGR leaderboard ----------
    lb = d["leaderboard_cagr"][:8]
    maxc = max(r["cagr"] for r in lb)
    lb_rows = ""
    for r in lb:
        conc = "top3" in r["config"] or "top5" in r["config"]
        warn = " <span class='chip risk'>−58% DD</span>" if conc and r["maxdd"] < -0.55 else ""
        lb_rows += f"""<tr>
          <td class="mono">{r['config']}{warn}</td>
          <td>{bar(r['cagr']/maxc, '#2e7d57')}<span class="num inline">{pct(r['cagr'])}</span></td>
          <td class="num">{pct(r['vol'])}</td>
          <td class="num neg">{pct(r['maxdd'])}</td>
          <td class="num">{r['sharpe']:.2f}</td>
          <td class="num">{xx(r['xsp'])}</td>
        </tr>"""

    # ---------- tax flip table (sorted by taxed CAGR) ----------
    taxs = sorted(tax, key=lambda r: -r["cagr_tax"])
    maxdrag = max(r["drag_pts"] for r in tax)
    tax_rows = ""
    for r in taxs:
        rec = "cap-weight top10" in r["config"]
        cls = " class='hot'" if rec else ""
        star = " ⭐" if rec else ""
        tax_rows += f"""<tr{cls}>
          <td class="lbl">{r['config']}{star}</td>
          <td class="num">{pct(r['cagr_notax'])}</td>
          <td class="num bold">{pct(r['cagr_tax'])}</td>
          <td>{bar(r['drag_pts']/maxdrag, '#c0392b')}<span class="num inline">{r['drag_pts']:.1f}pt</span></td>
          <td class="num">{pct(r['turnover'],0)}</td>
          <td class="num neg">{pct(r['maxdd'])}</td>
          <td class="num">{xx(r['xsp_tax'])}</td>
        </tr>"""

    # ---------- cadence / mode matrix ----------
    ce = d["cadence_effect"]
    modes = ["full", "drift_band", "no_sell"]
    ivs = ["M", "Q", "SA", "A"]
    cell = {(c["mode"], c["interval"]): c for c in ce}
    allc = [c["cagr"] for c in ce]
    lo, hi = min(allc), max(allc)
    cad_rows = ""
    for mode in modes:
        tds = ""
        for iv in ivs:
            c = cell.get((mode, iv))
            if not c:
                tds += "<td>—</td>"
                continue
            f = (c["cagr"] - lo) / (hi - lo) if hi > lo else 0.5
            g = int(40 + f * 120)  # green intensity
            tds += (f'<td class="heat" style="background:rgba(46,125,87,{0.12+f*0.55:.2f})">'
                    f'{pct(c["cagr"])}<br><span class="sub">Sh {c["sharpe"]:.2f}</span></td>')
        cad_rows += f"<tr><td class='lbl'>{mode}</td>{tds}</tr>"

    # ---------- satellite cards ----------
    def card(title, s, accent, note=""):
        return f"""<div class="card" style="border-top:3px solid {accent}">
          <div class="ct">{title}</div>
          <div class="cbig">{pct(s['cagr'])}<span class="cunit"> CAGR</span></div>
          <div class="crow"><span>vol</span><b>{pct(s['vol'])}</b></div>
          <div class="crow"><span>max DD</span><b class="neg">{pct(s['maxdd'])}</b></div>
          <div class="crow"><span>Sharpe</span><b>{s['sharpe']:.2f}</b></div>
          <div class="crow"><span>× S&amp;P</span><b>{xx(s['xsp'])}</b></div>
          {f'<div class="cnote">{note}</div>' if note else ''}
        </div>"""

    sat_cards = (card("100% S&amp;P 500 TR", sat["spy"], "#888", "the index core") +
                 card("70% S&amp;P / 30% strategy", sat["blend"], "#2e7d57",
                      f"captures {pct(sat['edge_capture'],0)} of the excess return") +
                 card("100% nasdaq10 strategy", sat["strat"], "#1f77b4", "full concentration"))

    # ---------- rebalancing-value cards ----------
    rb = rv["rebalanced"]
    bh = rv["buy_and_hold"]
    roster = ", ".join(rv["roster_2013"])
    rebal_cards = (card("Rebalanced quarterly", rb, "#2e7d57") +
                   card("Buy 2013 top-10, never touch", bh, "#b07d2b"))

    return TEMPLATE.format(
        start=m["start"], end=m["end"], cost=m["cost_bps"],
        taxl=int(m["tax_long"]*100), taxs=int(m["tax_short"]*100),
        b_cagr=pct(bench["cagr"]), b_vol=pct(bench["vol"]),
        b_sharpe=f"{bench['sharpe']:.2f}", b_dd=pct(bench["maxdd"]),
        uni_rows=uni_rows, lb_rows=lb_rows, tax_rows=tax_rows, cad_rows=cad_rows,
        sat_cards=sat_cards, rebal_cards=rebal_cards,
        sat_img=img("satellite_curve.png"), pareto_img=img("sweep_pareto.png"),
        tt_img=img("sweep_train_test.png"),
        rebal_alpha=f"{rv['rebalancing_alpha_pts']:.1f}",
        bh_cagr=pct(bh["cagr"]), rb_cagr=pct(rb["cagr"]),
        bh_sharpe=f"{bh['sharpe']:.2f}", rb_sharpe=f"{rb['sharpe']:.2f}",
        bh_dd=pct(bh["maxdd"]), rb_dd=pct(rb["maxdd"]),
        roster=roster,
        edge_cap=pct(sat["edge_capture"], 0), blend_cagr=pct(sat["blend"]["cagr"]),
        blend_vol=pct(sat["blend"]["vol"]), strat_vol=pct(sat["strat"]["vol"]),
        strat_dd=pct(sat["strat"]["maxdd"]),
        of_n=of["n"], of_cagr_rank=of["best_train_cagr_test_rank"],
        of_cagr_cfg=of["best_train_cagr_config"],
        of_sh_rank=of["best_train_sharpe_test_rank"], of_sh_cfg=of["best_train_sharpe_config"],
        of_corr=f"{of['corr_cagr_spearman']:.2f}",
    )


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Top-10 Rebalancer — Strategy Analysis</title>
<style>
:root{{
  --ink:#1a2332; --muted:#5b6776; --line:#e4e8ee; --bg:#fbfcfd; --card:#fff;
  --green:#2e7d57; --blue:#1f77b4; --red:#c0392b; --gold:#b07d2b; --accent:#2e7d57;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}}
.wrap{{max-width:980px;margin:0 auto;padding:0 28px 80px}}
header{{padding:54px 0 30px;border-bottom:1px solid var(--line);margin-bottom:8px}}
.kicker{{letter-spacing:.16em;text-transform:uppercase;font-size:11.5px;color:var(--accent);font-weight:700}}
h1{{font-size:32px;line-height:1.18;margin:10px 0 6px;letter-spacing:-.01em}}
.sub{{color:var(--muted)}}
.meta{{margin-top:16px;font-size:12.5px;color:var(--muted);display:flex;gap:18px;flex-wrap:wrap}}
.meta b{{color:var(--ink)}}
.badge{{display:inline-block;background:#fff4f4;color:var(--red);border:1px solid #f3d3d3;
  border-radius:5px;padding:2px 9px;font-size:11px;font-weight:700;letter-spacing:.03em}}
section{{margin:46px 0 0}}
.snum{{color:var(--accent);font-weight:800;font-size:13px;letter-spacing:.05em}}
h2{{font-size:22px;margin:6px 0 4px;letter-spacing:-.01em}}
.lede{{color:var(--muted);margin:0 0 18px;max-width:74ch}}
table{{width:100%;border-collapse:collapse;font-size:13.5px;margin:6px 0 4px}}
th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--muted);font-weight:700;padding:6px 9px;border-bottom:2px solid var(--line)}}
td{{padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:middle}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}
.num.inline{{margin-left:8px}}
.lbl{{font-weight:600}} .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}}
.bold{{font-weight:800}} .neg{{color:var(--red)}}
tr.hot td{{background:#f1f8f4}}
tr.hot td.lbl,tr.hot td:first-child{{box-shadow:inset 3px 0 0 var(--green)}}
.barwrap{{display:inline-block;width:84px;height:9px;background:#eef1f5;border-radius:5px;vertical-align:middle;overflow:hidden}}
.bar{{display:block;height:100%;border-radius:5px}}
.heat{{text-align:center;font-variant-numeric:tabular-nums;font-weight:700;border-radius:4px}}
.heat .sub{{font-weight:500;color:var(--muted);font-size:11px}}
.chip{{font-size:10px;padding:1px 6px;border-radius:4px;font-weight:700;vertical-align:middle}}
.chip.risk{{background:#fdeaea;color:var(--red)}}
.cards{{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0 6px}}
.card{{flex:1;min-width:190px;background:var(--card);border:1px solid var(--line);
  border-radius:10px;padding:16px 16px 14px;box-shadow:0 1px 2px rgba(20,30,50,.04)}}
.ct{{font-size:12.5px;color:var(--muted);font-weight:700;min-height:34px}}
.cbig{{font-size:30px;font-weight:800;letter-spacing:-.02em;margin:2px 0 10px}}
.cunit{{font-size:13px;font-weight:600;color:var(--muted)}}
.crow{{display:flex;justify-content:space-between;font-size:12.5px;padding:2px 0;color:var(--muted)}}
.crow b{{color:var(--ink)}}
.cnote{{margin-top:9px;font-size:11.5px;color:var(--muted);border-top:1px dashed var(--line);padding-top:7px}}
.strip{{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0 4px}}
.stat{{flex:1;min-width:150px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.stat .sl{{font-size:11px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.04em}}
.stat .sv{{font-size:25px;font-weight:800;margin-top:4px;letter-spacing:-.01em}}
.stat .sv .vs{{font-size:13px;color:var(--muted);font-weight:600}}
.stat .sc{{font-size:11.5px;color:var(--muted);margin-top:3px}}
.fig{{margin:14px 0 4px;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff}}
.fig img{{width:100%;display:block}}
.why{{background:#f4f7fb;border-left:3px solid var(--accent);border-radius:0 8px 8px 0;
  padding:13px 16px;margin:14px 0 2px;font-size:13.5px}}
.why b{{color:var(--ink)}} .why .h{{font-weight:800;color:var(--accent);font-size:11.5px;
  text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:3px}}
.tl{{background:#11261c;color:#eafff3;border-radius:12px;padding:22px 24px;margin:18px 0 6px}}
.tl .h{{color:#7fd6a6;font-weight:800;font-size:11.5px;letter-spacing:.08em;text-transform:uppercase}}
.tl p{{margin:8px 0 0;font-size:15px;line-height:1.62}}
.tl b{{color:#fff}}
.foot{{margin-top:54px;padding-top:20px;border-top:1px solid var(--line);font-size:11.5px;color:var(--muted)}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:22px;align-items:start}}
@media(max-width:720px){{.grid2{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">

<header>
  <div class="kicker">Strategy Research · Internal · Not Financial Advice</div>
  <h1>Top-10 Mega-Cap Rebalancing — Structural Analysis</h1>
  <div class="sub">A point-in-time, survivorship-free backtest of the Coatue / Laffont
  "own the biggest companies, rebalance into the new leaders" thesis — read across
  every structural lens, with and without tax.</div>
  <div class="meta">
    <span><b>Window</b> {start} → {end}</span>
    <span><b>Cost</b> {cost} bps/turn</span>
    <span><b>Tax case</b> {taxl}% long / {taxs}% short</span>
    <span><b>Benchmark</b> S&amp;P 500 TR: {b_cagr} CAGR · {b_vol} vol · Sharpe {b_sharpe} · {b_dd} DD</span>
  </div>
  <div style="margin-top:14px"><span class="badge">RESEARCH / CURIOSITY TOOL — NOT FINANCIAL ADVICE</span></div>
</header>

<div class="tl">
  <span class="h">The one-paragraph takeaway</span>
  <p>The thesis <b>works — but only as one specific bet</b>: NASDAQ-listed, top-10,
  cap-weighted. That cell beats the S&amp;P by ~<b>3.2×</b> over 20 years. Every other
  reading dilutes it: owning the 10 biggest <i>US</i> or <i>global</i> companies barely
  beats an index fund. What you've found is a <b>packaged mega-cap-tech factor</b>, not a
  secret — it's more volatile, crashes harder (−51%), and its pre-tax "optimizations"
  (equal-weight, concentration) <b>evaporate after tax</b>. The honest expression is a
  <b>risk-budgeted satellite</b>: a 30% concentration sleeve on an index core captures a
  third of the edge at near-index volatility.</p>
</div>

<section>
  <div class="snum">01 · BY UNIVERSE</div>
  <h2>Where does the edge actually live?</h2>
  <p class="lede">The strategy was run across three readings of "the top 10." They are not
  close. The "beat the market by a multiple" claim is entirely a <b>NASDAQ</b> phenomenon.</p>
  <table>
    <tr><th>Universe</th><th class="num">Median CAGR</th><th class="num">Best CAGR</th>
        <th>Median × S&amp;P</th><th class="num">Best ×</th><th class="num">Best Sharpe</th></tr>
    {uni_rows}
  </table>
  <div class="why"><span class="h">Why it changes</span>
  NASDAQ is the purest container for the mega-cap-tech factor (Apple, Microsoft, Nvidia,
  Amazon, Google). <b>US10</b> dilutes it with NYSE banks, energy, and Berkshire; <b>global10</b>
  adds Aramco, Tencent and a tail of un-priceable delisted ADRs. The median nasdaq10 config
  returns <b>3.2× the index</b>; the median us10/global10 config clusters at ~1.4–1.6×.
  Translation for an IC: "own the 10 biggest companies" is only a market-beater when
  "biggest" resolves to NASDAQ tech.</div>
</section>

<section>
  <div class="snum">02 · BY RETURN</div>
  <h2>The raw-return leaderboard (pre-tax, in-sample)</h2>
  <p class="lede">Sorted by CAGR over the full window. Note what wins — and the warning
  flags. The top of this table is a beauty contest; the later sections are the reality checks.</p>
  <table>
    <tr><th>Config (universe/topN/weight/mode/interval)</th><th>CAGR</th>
        <th class="num">Vol</th><th class="num">Max DD</th><th class="num">Sharpe</th><th class="num">× S&amp;P</th></tr>
    {lb_rows}
  </table>
  <div class="fig"><img src="{pareto_img}" alt="Return vs risk Pareto frontier"></div>
  <div class="why"><span class="h">What it means</span>
  The highest CAGRs come from <b>concentration</b> (top-3 / top-5) and <b>equal-weight</b>.
  But every one of those rows carries a <b>−57% to −59% drawdown</b> — far worse than the
  top-10 line. On the efficient frontier (chart), the sensible names sit where return is high
  <i>and</i> volatility is contained: nasdaq10 / top-10 / equal or cap. Chasing the last point
  of CAGR means buying a much deeper hole.</div>
</section>

<section>
  <div class="snum">03 · BY RISK</div>
  <h2>This is not a safer way to own stocks</h2>
  <p class="lede">It is a higher-octane one. Volatility runs 22–24% (vs the index's 19%), and
  the drawdowns are the real cost of the strategy — not a tail you can engineer away by tuning.</p>
  <div class="strip">
    <div class="stat"><div class="sl">Volatility</div>
      <div class="sv">{strat_vol} <span class="vs">vs {b_vol}</span></div>
      <div class="sc">strategy vs S&amp;P 500</div></div>
    <div class="stat"><div class="sl">Worst year — 2022</div>
      <div class="sv neg">−39.5% <span class="vs">vs −18.6%</span></div>
      <div class="sc">roughly double the index's loss</div></div>
    <div class="stat"><div class="sl">Max drawdown</div>
      <div class="sv neg">{strat_dd}</div>
      <div class="sc">2008 GFC — not avoidable by tuning</div></div>
  </div>
  <div class="why"><span class="h">The number that decides whether you can run it</span>
  The top-10 line drew down <b>−51%</b> (2008) and lost <b>−39.5% in 2022 vs the S&amp;P's −18.6%</b>
  — roughly double the index. Concentrated top-3/5 variants reach <b>−58%</b>. Maximum drawdown is
  not improved by any weighting or cadence choice; it's intrinsic to owning ten names. <b>If a −50%
  paper loss would force you to sell, the strategy fails for you regardless of the backtest.</b>
  Position-size to that number first, optimize second.</div>
</section>

<section>
  <div class="snum">04 · BY TAX</div>
  <h2>Tax quietly inverts the ranking</h2>
  <p class="lede">The sweep is deliberately pre-tax to isolate structure. Layer in a {taxl}%/{taxs}%
  capital-gains case and the pre-tax "winner" falls to the back. Tax drag tracks <b>turnover</b>,
  one-for-one. Sorted below by <b>after-tax</b> CAGR.</p>
  <table>
    <tr><th>Config (nasdaq10)</th><th class="num">CAGR no-tax</th><th class="num">CAGR taxed</th>
        <th>Tax drag</th><th class="num">Turnover/yr</th><th class="num">Max DD</th><th class="num">× S&amp;P taxed</th></tr>
    {tax_rows}
  </table>
  <div class="why"><span class="h">Why it changes</span>
  Equal-weight <b>full</b> trims every winner back to target each period — 27%/yr turnover, and a
  <b>2.0 pt/yr</b> tax bleed that drops it <i>below</i> the plain cap-weight baseline it beat pre-tax.
  Cap-weight is naturally low-turnover (8%/yr): winners are <i>supposed</i> to grow their weight, so it
  barely trades and keeps almost all its return (0.6 pt drag). <b>Account location is a real decision:</b>
  cap-weight in a taxable account; reserve equal-weight / concentration for tax-advantaged.</div>
</section>

<section>
  <div class="snum">05 · BY REBALANCING</div>
  <h2>Cadence barely matters; the <i>rule</i> matters</h2>
  <p class="lede">Holding nasdaq10 / equal / top-10 fixed and varying only how you rebalance.
  Cells are full-period CAGR (greener = higher).</p>
  <table>
    <tr><th>Rebalance mode</th><th class="num">Monthly</th><th class="num">Quarterly</th>
        <th class="num">Semi-ann.</th><th class="num">Annual</th></tr>
    {cad_rows}
  </table>
  <div class="why"><span class="h">Two intuitions for the committee</span>
  <b>(1) Don't obsess over cadence.</b> Monthly → annual moves CAGR by &lt;0.5 pt; less-frequent is if
  anything marginally <i>better</i> and more tax-efficient. <b>(2) Mode is the real lever.</b>
  <b>full</b> &gt; <b>drift_band</b> &gt; <b>no_sell</b>: systematically recycling capital into the
  <i>current</i> leaders captured the baton-pass across tech names (Intel→Apple→Nvidia) better than
  letting old winners ride. The catch — full mode's turnover is exactly what tax (Section 04) punishes.</div>
</section>

<section>
  <div class="snum">06 · BY <i>NOT</i> REBALANCING</div>
  <h2>How much of the edge is the rule vs. the starting roster?</h2>
  <p class="lede">The cleanest honesty test: buy the 2013 top-10 and <b>never touch it</b>, vs.
  rebalancing quarterly into the new leaders. Same window (2013→today), same cap-weight.</p>
  <div class="cards">{rebal_cards}</div>
  <div class="why"><span class="h">The uncomfortable, useful finding</span>
  Buying the 2013 roster (<span class="mono">{roster}</span>) and sitting on your hands returned
  <b>{bh_cagr}/yr</b>. Rebalancing added <b>+{rebal_alpha} pt</b> to {rb_cagr}. So roughly
  <b>~85% of the post-2013 edge was simply <i>owning the 2013 mega-caps</i></b>, not the active rule.
  And on a risk-adjusted basis it's a <b>tie</b> — buy-and-hold Sharpe {bh_sharpe} vs rebalanced
  {rb_sharpe}, with a <i>shallower</i> drawdown ({bh_dd} vs {rb_dd}). The rebalancing rule earns a real
  but modest return premium by rotating into new leaders (Nvidia, Meta); it is not, by itself, the alpha.</div>
</section>

<section>
  <div class="snum">07 · THE SATELLITE</div>
  <h2>The honest way to actually hold this</h2>
  <p class="lede">Most of the single-factor risk comes from going 100% in. A 70% index / 30%
  strategy blend, rebalanced annually, is the "have-your-cake" structure.</p>
  <div class="cards">{sat_cards}</div>
  <div class="fig"><img src="{sat_img}" alt="Satellite blend equity curves"></div>
  <div class="why"><span class="h">What the blend buys you</span>
  At 30% weight the blend earns <b>{blend_cagr}/yr</b> — capturing <b>{edge_cap} of the strategy's
  excess return</b> — while volatility ({blend_vol}) sits right next to the index's, far below the
  strategy's ({strat_vol}). <b>Honest caveat:</b> the blend's <i>maximum</i> drawdown barely improves,
  because 2008 was systemic and hit everything; what it really tames is volatility and the
  <i>tech-specific</i> tails (e.g. 2022). For an IC, this is the difference between a position you can
  hold and one that gets liquidated at the bottom.</div>
</section>

<section>
  <div class="snum">08 · THE META-CHECK</div>
  <h2>Does the "winner" survive out-of-sample?</h2>
  <p class="lede">Every config was scored on train (2006–17) and held-out test (2018–26). If the
  best in-sample config is just curve-fit, it should collapse out-of-sample.</p>
  <div class="fig"><img src="{tt_img}" alt="Train vs test CAGR scatter"></div>
  <div class="why"><span class="h">Read this before trusting any single row</span>
  The best-on-train config by CAGR (<span class="mono">{of_cagr_cfg}</span>) ranked only
  <b>#{of_cagr_rank} of {of_n}</b> out-of-sample — a coin flip. The best-by-Sharpe ranked
  <b>#{of_sh_rank}</b>, far more durable. Train→test rank correlation is <b>{of_corr}</b> (moderate):
  the broad <i>structure</i> (universe, weighting, concentration) carries forward; the specific
  "optimal" cell does not. <b>Trade the structure, never the backtest's #1 row.</b></div>
</section>

<div class="tl">
  <span class="h">Bottom line for the committee</span>
  <p>Run it as <b>nasdaq10 · top-10 · cap-weight · full</b>, quarterly or semiannual, as a
  <b>20–30% risk-budgeted satellite</b> on an index core — in a tax-advantaged account if available.
  That is the configuration that survives all three checks: it's the <b>least overfit</b> (top-10
  structure held up out-of-sample), the <b>most tax-robust</b> (8%/yr turnover, 0.6 pt drag), and it
  sits on the efficient frontier. You are buying a real, well-documented mega-cap-tech factor — not a
  market-beating secret — so size for a <b>−50% drawdown</b> and don't extrapolate the 17.7% CAGR forward.</p>
</div>

<div class="foot">
  <b>Method &amp; caveats.</b> Point-in-time membership (no survivorship bias); dividends reinvested via
  adjusted close; {cost} bps cost on turnover. Membership is curated annual snapshots — global10 pre-2015
  is the priceable subset only. Tax case applies {taxl}% long / {taxs}% short to realized gains at each
  rebalance. Past performance ≠ future results. This is a research/curiosity tool and <b>not financial
  advice.</b> Generated by <span class="mono">build_report.py</span> from <span class="mono">analysis_data.json</span>.
</div>

</div></body></html>"""


def main():
    d = load()
    html = build(d)
    path = os.path.join(OUT, "analysis.html")
    with open(path, "w") as f:
        f.write(html)
    print(f"Wrote {path} ({len(html)//1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
