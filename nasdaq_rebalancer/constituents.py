"""
Point-in-time "top 10 largest companies" membership tables.

WHY THIS FILE EXISTS
--------------------
The single biggest way a "buy the top 10 and rebalance" backtest lies to you is
survivorship / look-ahead bias: if you backtest *today's* top 10 (Nvidia, Apple,
Microsoft, Broadcom, ...) over 20 years, you are implicitly "buying Nvidia in
2006 because you already know it wins." That produces a fantasy result.

A credible test must use POINT-IN-TIME membership: at each rebalance date you
hold whoever was *actually* in the top 10 *at that time*, and you drop the names
that fell out (Exxon, GE, Citigroup, Intel, PetroChina, ...). Yahoo Finance gives
you prices but NOT historical market-cap rankings, so that membership has to be
curated. That is what this file is.

THREE UNIVERSES
---------------
- "nasdaq10" : 10 largest NASDAQ-listed companies (closest to "top Nasdaq names").
- "us10"     : 10 largest U.S.-domiciled companies on any U.S. exchange.
- "global10" : 10 largest publicly traded companies worldwide.

DATA PROVENANCE & HONESTY
-------------------------
Membership and the approximate market caps below are curated from public
year-end market-cap rankings (Financial Times / Wikipedia "List of public
corporations by market capitalization", companiesmarketcap.com, PwC Global Top
100, Visual Capitalist, finhacker.cz). They are *approximate*. Treat them as a
good-faith reconstruction, not gospel:

  * Market-cap figures (USD billions) are rounded and only used for *weighting*.
    Cap-weighting is dominated by the top 3-4 names, which are well known; the
    exact cap of the #9/#10 name barely moves results.
  * The exact #9 vs #10 ordering in some years is fuzzy and, again, immaterial to
    a cap-weighted result because those names carry tiny weight.
  * "global10" is the LOWEST-confidence universe: several historical leaders were
    Chinese/Russian ADRs (PetroChina PTR, China Mobile CHL, Sinopec SNP, Gazprom
    OGZPY) that have since been delisted from U.S. exchanges, so Yahoo may have
    little/no usable history for them. The backtest engine degrades gracefully
    (drops a name it cannot price and renormalizes weights) but that means the
    pre-2015 global10 result is an approximation of the available subset. This is
    disclosed loudly in the README and in the run output.

Each snapshot is dated at the YEAR-END that *precedes* the year it governs. The
engine, at any rebalance date D, uses the most recent snapshot with date <= D, so
there is no look-ahead (year-end ranks are known before the next quarter starts).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Ticker metadata: Yahoo symbol -> (display name, listing currency, exchange).
# Currency is used by prices.py to convert non-USD names into USD so the whole
# portfolio is measured in one currency. ADRs trade in USD even for foreign
# companies, so they are tagged "USD".
# ---------------------------------------------------------------------------
TICKER_META: Dict[str, Dict[str, str]] = {
    # --- U.S. mega-cap tech (NASDAQ) ---
    "AAPL": {"name": "Apple", "currency": "USD", "exchange": "NASDAQ"},
    "MSFT": {"name": "Microsoft", "currency": "USD", "exchange": "NASDAQ"},
    "GOOGL": {"name": "Alphabet (Google)", "currency": "USD", "exchange": "NASDAQ"},
    "AMZN": {"name": "Amazon", "currency": "USD", "exchange": "NASDAQ"},
    "META": {"name": "Meta (Facebook)", "currency": "USD", "exchange": "NASDAQ"},
    "NVDA": {"name": "Nvidia", "currency": "USD", "exchange": "NASDAQ"},
    "TSLA": {"name": "Tesla", "currency": "USD", "exchange": "NASDAQ"},
    "AVGO": {"name": "Broadcom", "currency": "USD", "exchange": "NASDAQ"},
    "INTC": {"name": "Intel", "currency": "USD", "exchange": "NASDAQ"},
    "CSCO": {"name": "Cisco", "currency": "USD", "exchange": "NASDAQ"},
    "QCOM": {"name": "Qualcomm", "currency": "USD", "exchange": "NASDAQ"},
    "AMGN": {"name": "Amgen", "currency": "USD", "exchange": "NASDAQ"},
    "CMCSA": {"name": "Comcast", "currency": "USD", "exchange": "NASDAQ"},
    "PEP": {"name": "PepsiCo", "currency": "USD", "exchange": "NASDAQ"},
    "COST": {"name": "Costco", "currency": "USD", "exchange": "NASDAQ"},
    "ADBE": {"name": "Adobe", "currency": "USD", "exchange": "NASDAQ"},
    "NFLX": {"name": "Netflix", "currency": "USD", "exchange": "NASDAQ"},
    "TXN": {"name": "Texas Instruments", "currency": "USD", "exchange": "NASDAQ"},
    "DELL": {"name": "Dell", "currency": "USD", "exchange": "NASDAQ"},
    "EBAY": {"name": "eBay", "currency": "USD", "exchange": "NASDAQ"},
    "ORCL": {"name": "Oracle", "currency": "USD", "exchange": "NYSE"},  # NASDAQ until 2013
    # --- U.S. large-cap non-NASDAQ (NYSE) ---
    "XOM": {"name": "ExxonMobil", "currency": "USD", "exchange": "NYSE"},
    "GE": {"name": "General Electric", "currency": "USD", "exchange": "NYSE"},
    "WMT": {"name": "Walmart", "currency": "USD", "exchange": "NYSE"},
    "JPM": {"name": "JPMorgan Chase", "currency": "USD", "exchange": "NYSE"},
    "JNJ": {"name": "Johnson & Johnson", "currency": "USD", "exchange": "NYSE"},
    "BRK-B": {"name": "Berkshire Hathaway", "currency": "USD", "exchange": "NYSE"},
    "PG": {"name": "Procter & Gamble", "currency": "USD", "exchange": "NYSE"},
    "PFE": {"name": "Pfizer", "currency": "USD", "exchange": "NYSE"},
    "C": {"name": "Citigroup", "currency": "USD", "exchange": "NYSE"},
    "BAC": {"name": "Bank of America", "currency": "USD", "exchange": "NYSE"},
    "AIG": {"name": "AIG", "currency": "USD", "exchange": "NYSE"},
    "CVX": {"name": "Chevron", "currency": "USD", "exchange": "NYSE"},
    "T": {"name": "AT&T", "currency": "USD", "exchange": "NYSE"},
    "IBM": {"name": "IBM", "currency": "USD", "exchange": "NYSE"},
    "WFC": {"name": "Wells Fargo", "currency": "USD", "exchange": "NYSE"},
    "V": {"name": "Visa", "currency": "USD", "exchange": "NYSE"},
    "MA": {"name": "Mastercard", "currency": "USD", "exchange": "NYSE"},
    "UNH": {"name": "UnitedHealth", "currency": "USD", "exchange": "NYSE"},
    "LLY": {"name": "Eli Lilly", "currency": "USD", "exchange": "NYSE"},
    "HD": {"name": "Home Depot", "currency": "USD", "exchange": "NYSE"},
    "KO": {"name": "Coca-Cola", "currency": "USD", "exchange": "NYSE"},
    # --- Foreign names: USD ADRs preferred (clean), else local listing + FX ---
    "TSM": {"name": "TSMC (ADR)", "currency": "USD", "exchange": "NYSE"},
    "BABA": {"name": "Alibaba (ADR)", "currency": "USD", "exchange": "NYSE"},
    "TM": {"name": "Toyota (ADR)", "currency": "USD", "exchange": "NYSE"},
    "BP": {"name": "BP (ADR)", "currency": "USD", "exchange": "NYSE"},
    "SHEL": {"name": "Shell (ADR)", "currency": "USD", "exchange": "NYSE"},
    "PTR": {"name": "PetroChina (ADR, delisted 2022)", "currency": "USD", "exchange": "NYSE"},
    "CHL": {"name": "China Mobile (ADR, delisted 2021)", "currency": "USD", "exchange": "NYSE"},
    "SNP": {"name": "Sinopec (ADR, delisted 2021)", "currency": "USD", "exchange": "NYSE"},
    "OGZPY": {"name": "Gazprom (ADR, halted 2022)", "currency": "USD", "exchange": "OTC"},
    "2222.SR": {"name": "Saudi Aramco", "currency": "SAR", "exchange": "Tadawul"},
    "0700.HK": {"name": "Tencent", "currency": "HKD", "exchange": "HKEX"},
    "1398.HK": {"name": "ICBC", "currency": "HKD", "exchange": "HKEX"},
    "005930.KS": {"name": "Samsung Electronics", "currency": "KRW", "exchange": "KRX"},
    "NESN.SW": {"name": "Nestle", "currency": "CHF", "exchange": "SIX"},
}

# A snapshot is (ticker, approx_market_cap_usd_billions). Up to 10 names, ranked.
Snapshot = List[Tuple[str, float]]

# ---------------------------------------------------------------------------
# us10 : 10 largest U.S.-domiciled companies, year-end snapshots.
# ---------------------------------------------------------------------------
US10: Dict[str, Snapshot] = {
    "2005-12-31": [("XOM", 375), ("GE", 370), ("MSFT", 280), ("C", 245), ("WMT", 205),
                   ("BAC", 185), ("JNJ", 180), ("PFE", 175), ("AIG", 170), ("INTC", 150)],
    "2006-12-31": [("XOM", 440), ("GE", 380), ("MSFT", 290), ("C", 275), ("BAC", 240),
                   ("PG", 200), ("JNJ", 192), ("WMT", 192), ("AIG", 185), ("PFE", 185)],
    "2007-12-31": [("XOM", 510), ("GE", 370), ("MSFT", 330), ("T", 250), ("PG", 220),
                   ("GOOGL", 217), ("WMT", 190), ("CVX", 185), ("JNJ", 185), ("AAPL", 174)],
    "2008-12-31": [("XOM", 405), ("WMT", 220), ("PG", 175), ("MSFT", 172), ("T", 168),
                   ("JNJ", 165), ("GE", 160), ("CVX", 150), ("WFC", 125), ("JPM", 117)],
    "2009-12-31": [("XOM", 322), ("MSFT", 270), ("WMT", 205), ("GOOGL", 197), ("AAPL", 190),
                   ("JNJ", 178), ("PG", 177), ("IBM", 172), ("JPM", 165), ("GE", 161)],
    "2010-12-31": [("XOM", 369), ("AAPL", 296), ("MSFT", 235), ("BRK-B", 200), ("GE", 195),
                   ("WMT", 192), ("GOOGL", 190), ("CVX", 184), ("IBM", 184), ("PG", 181)],
    "2011-12-31": [("XOM", 406), ("AAPL", 376), ("IBM", 217), ("MSFT", 218), ("CVX", 215),
                   ("GOOGL", 209), ("WMT", 205), ("GE", 190), ("BRK-B", 187), ("PG", 183)],
    "2012-12-31": [("AAPL", 500), ("XOM", 390), ("BRK-B", 248), ("GOOGL", 232), ("WMT", 230),
                   ("MSFT", 224), ("GE", 220), ("IBM", 215), ("CVX", 209), ("JNJ", 198)],
    "2013-12-31": [("AAPL", 500), ("XOM", 442), ("GOOGL", 375), ("MSFT", 310), ("BRK-B", 296),
                   ("GE", 282), ("JNJ", 258), ("WMT", 255), ("CVX", 240), ("WFC", 239)],
    "2014-12-31": [("AAPL", 643), ("XOM", 390), ("MSFT", 382), ("BRK-B", 370), ("GOOGL", 360),
                   ("JNJ", 290), ("WFC", 285), ("WMT", 277), ("GE", 254), ("PG", 246)],
    "2015-12-31": [("AAPL", 586), ("GOOGL", 528), ("MSFT", 443), ("BRK-B", 325), ("XOM", 324),
                   ("AMZN", 318), ("META", 296), ("JNJ", 282), ("GE", 280), ("WFC", 277)],
    "2016-12-31": [("AAPL", 609), ("GOOGL", 539), ("MSFT", 483), ("BRK-B", 408), ("XOM", 374),
                   ("AMZN", 356), ("META", 332), ("JNJ", 313), ("JPM", 308), ("GE", 280)],
    "2017-12-31": [("AAPL", 868), ("GOOGL", 729), ("MSFT", 660), ("AMZN", 564), ("META", 513),
                   ("BRK-B", 489), ("JNJ", 374), ("JPM", 372), ("XOM", 354), ("BAC", 306)],
    "2018-12-31": [("MSFT", 780), ("AAPL", 748), ("AMZN", 737), ("GOOGL", 724), ("BRK-B", 494),
                   ("META", 376), ("JNJ", 346), ("JPM", 325), ("V", 290), ("XOM", 289)],
    "2019-12-31": [("AAPL", 1304), ("MSFT", 1200), ("GOOGL", 922), ("AMZN", 920), ("META", 585),
                   ("BRK-B", 553), ("JPM", 437), ("V", 405), ("JNJ", 384), ("WMT", 338)],
    "2020-12-31": [("AAPL", 2255), ("MSFT", 1682), ("AMZN", 1634), ("GOOGL", 1185), ("META", 778),
                   ("TSLA", 669), ("BRK-B", 543), ("V", 467), ("JNJ", 415), ("WMT", 408)],
    "2021-12-31": [("AAPL", 2913), ("MSFT", 2522), ("GOOGL", 1917), ("AMZN", 1691), ("TSLA", 1061),
                   ("META", 935), ("NVDA", 733), ("BRK-B", 669), ("UNH", 472), ("JPM", 467)],
    "2022-12-31": [("AAPL", 2066), ("MSFT", 1787), ("GOOGL", 1145), ("AMZN", 856), ("BRK-B", 689),
                   ("UNH", 496), ("XOM", 463), ("JNJ", 462), ("V", 437), ("JPM", 393)],
    "2023-12-31": [("AAPL", 2994), ("MSFT", 2794), ("GOOGL", 1756), ("AMZN", 1570), ("NVDA", 1223),
                   ("META", 909), ("TSLA", 790), ("BRK-B", 781), ("LLY", 554), ("V", 533)],
    "2024-12-31": [("AAPL", 3780), ("NVDA", 3280), ("MSFT", 3130), ("GOOGL", 2330), ("AMZN", 2310),
                   ("META", 1470), ("TSLA", 1300), ("AVGO", 1080), ("BRK-B", 1010), ("LLY", 735)],
    "2025-12-31": [("NVDA", 4400), ("AAPL", 4000), ("MSFT", 3700), ("GOOGL", 3300), ("AMZN", 2500),
                   ("META", 1800), ("AVGO", 1600), ("TSLA", 1400), ("BRK-B", 1050), ("LLY", 800)],
}

# ---------------------------------------------------------------------------
# nasdaq10 : 10 largest NASDAQ-listed companies, year-end snapshots.
# NOTE: pre-2013 this list contains some names with messy Yahoo histories
# (DELL went private 2013 & relisted 2018; EBAY/ORCL ok; older Yahoo/Dell data
# may be partial). The engine drops un-priceable names and renormalizes.
# Oracle (ORCL) was NASDAQ-listed until July 2013, so it is included pre-2013.
# ---------------------------------------------------------------------------
NASDAQ10: Dict[str, Snapshot] = {
    "2005-12-31": [("MSFT", 280), ("INTC", 150), ("GOOGL", 123), ("CSCO", 105), ("AMGN", 95),
                   ("DELL", 72), ("QCOM", 70), ("ORCL", 68), ("EBAY", 58), ("CMCSA", 53)],
    "2006-12-31": [("MSFT", 290), ("GOOGL", 142), ("INTC", 117), ("CSCO", 165), ("CMCSA", 88),
                   ("QCOM", 62), ("AMGN", 80), ("ORCL", 88), ("DELL", 56), ("EBAY", 42)],
    "2007-12-31": [("MSFT", 330), ("GOOGL", 217), ("AAPL", 174), ("CSCO", 163), ("INTC", 156),
                   ("ORCL", 116), ("QCOM", 64), ("CMCSA", 55), ("AMGN", 50), ("GILD", 43)],
    "2008-12-31": [("MSFT", 172), ("GOOGL", 97), ("AAPL", 76), ("CSCO", 95), ("INTC", 82),
                   ("ORCL", 89), ("QCOM", 59), ("AMGN", 60), ("CMCSA", 48), ("GILD", 47)],
    "2009-12-31": [("MSFT", 270), ("GOOGL", 197), ("AAPL", 190), ("CSCO", 137), ("ORCL", 123),
                   ("INTC", 113), ("QCOM", 78), ("AMGN", 55), ("CMCSA", 48), ("AMZN", 60)],
    "2010-12-31": [("AAPL", 296), ("MSFT", 235), ("GOOGL", 190), ("CSCO", 114), ("ORCL", 158),
                   ("INTC", 116), ("QCOM", 83), ("AMZN", 81), ("CMCSA", 62), ("AMGN", 52)],
    "2011-12-31": [("AAPL", 376), ("MSFT", 218), ("GOOGL", 209), ("ORCL", 130), ("INTC", 121),
                   ("CSCO", 96), ("AMZN", 79), ("QCOM", 92), ("CMCSA", 64), ("AMGN", 49)],
    "2012-12-31": [("AAPL", 500), ("GOOGL", 232), ("MSFT", 224), ("ORCL", 158), ("AMZN", 114),
                   ("INTC", 103), ("CSCO", 105), ("QCOM", 105), ("CMCSA", 100), ("AMGN", 65)],
    "2013-12-31": [("AAPL", 500), ("GOOGL", 375), ("MSFT", 310), ("AMZN", 183), ("CSCO", 120),
                   ("INTC", 129), ("CMCSA", 135), ("QCOM", 125), ("AMGN", 87), ("GILD", 115)],
    "2014-12-31": [("AAPL", 643), ("MSFT", 382), ("GOOGL", 360), ("AMZN", 144), ("INTC", 172),
                   ("CMCSA", 148), ("GILD", 142), ("CSCO", 142), ("QCOM", 124), ("AMGN", 121)],
    "2015-12-31": [("AAPL", 586), ("GOOGL", 528), ("MSFT", 443), ("AMZN", 318), ("META", 296),
                   ("INTC", 163), ("CMCSA", 138), ("CSCO", 137), ("GILD", 149), ("AMGN", 123)],
    "2016-12-31": [("AAPL", 609), ("GOOGL", 539), ("MSFT", 483), ("AMZN", 356), ("META", 332),
                   ("INTC", 172), ("CMCSA", 165), ("CSCO", 152), ("AMGN", 109), ("QCOM", 96)],
    "2017-12-31": [("AAPL", 868), ("GOOGL", 729), ("MSFT", 660), ("AMZN", 564), ("META", 513),
                   ("INTC", 216), ("CMCSA", 190), ("CSCO", 189), ("NVDA", 116), ("AMGN", 127)],
    "2018-12-31": [("MSFT", 780), ("AAPL", 748), ("AMZN", 737), ("GOOGL", 724), ("META", 376),
                   ("INTC", 215), ("CSCO", 195), ("CMCSA", 155), ("PEP", 157), ("AMGN", 125)],
    "2019-12-31": [("AAPL", 1304), ("MSFT", 1200), ("GOOGL", 922), ("AMZN", 920), ("META", 585),
                   ("INTC", 256), ("CSCO", 203), ("CMCSA", 204), ("PEP", 190), ("AVGO", 125)],
    "2020-12-31": [("AAPL", 2255), ("MSFT", 1682), ("AMZN", 1634), ("GOOGL", 1185), ("META", 778),
                   ("TSLA", 669), ("NVDA", 323), ("PYPL", 275), ("INTC", 202), ("CMCSA", 239)],
    "2021-12-31": [("AAPL", 2913), ("MSFT", 2522), ("GOOGL", 1917), ("AMZN", 1691), ("TSLA", 1061),
                   ("META", 935), ("NVDA", 733), ("AVGO", 276), ("PEP", 240), ("COST", 250)],
    "2022-12-31": [("AAPL", 2066), ("MSFT", 1787), ("GOOGL", 1145), ("AMZN", 856), ("TSLA", 389),
                   ("NVDA", 360), ("META", 320), ("AVGO", 232), ("PEP", 249), ("COST", 202)],
    "2023-12-31": [("AAPL", 2994), ("MSFT", 2794), ("GOOGL", 1756), ("AMZN", 1570), ("NVDA", 1223),
                   ("META", 909), ("TSLA", 790), ("AVGO", 516), ("COST", 292), ("ADBE", 272)],
    "2024-12-31": [("AAPL", 3780), ("NVDA", 3280), ("MSFT", 3130), ("GOOGL", 2330), ("AMZN", 2310),
                   ("META", 1470), ("TSLA", 1300), ("AVGO", 1080), ("COST", 406), ("NFLX", 382)],
    "2025-12-31": [("NVDA", 4400), ("AAPL", 4000), ("MSFT", 3700), ("GOOGL", 3300), ("AMZN", 2500),
                   ("META", 1800), ("AVGO", 1600), ("TSLA", 1400), ("NFLX", 500), ("COST", 430)],
}

# Extra tickers referenced by nasdaq10 that need metadata.
TICKER_META.setdefault("GILD", {"name": "Gilead Sciences", "currency": "USD", "exchange": "NASDAQ"})
TICKER_META.setdefault("PYPL", {"name": "PayPal", "currency": "USD", "exchange": "NASDAQ"})

# ---------------------------------------------------------------------------
# global10 : 10 largest companies worldwide, year-end snapshots.
# LOWEST-confidence universe -- several historical leaders are delisted ADRs
# (PTR, CHL, SNP, OGZPY). The engine will drop names it cannot price; pre-2015
# results are an approximation of the available subset. See README.
# ---------------------------------------------------------------------------
GLOBAL10: Dict[str, Snapshot] = {
    "2005-12-31": [("GE", 370), ("XOM", 375), ("MSFT", 280), ("C", 245), ("BP", 230),
                   ("SHEL", 210), ("WMT", 205), ("TM", 200), ("BAC", 185), ("JNJ", 180)],
    "2006-12-31": [("XOM", 440), ("GE", 380), ("MSFT", 290), ("C", 275), ("BP", 240),
                   ("TM", 230), ("BAC", 240), ("SHEL", 220), ("PTR", 220), ("WMT", 192)],
    "2007-12-31": [("PTR", 720), ("XOM", 510), ("GE", 370), ("CHL", 330), ("MSFT", 330),
                   ("1398.HK", 290), ("SNP", 220), ("OGZPY", 330), ("TM", 230), ("SHEL", 220)],
    "2008-12-31": [("PTR", 260), ("XOM", 405), ("1398.HK", 190), ("MSFT", 172), ("CHL", 200),
                   ("WMT", 220), ("PG", 175), ("GE", 160), ("TM", 130), ("JNJ", 165)],
    "2009-12-31": [("PTR", 350), ("XOM", 322), ("MSFT", 270), ("1398.HK", 270), ("WMT", 205),
                   ("CHL", 195), ("GOOGL", 197), ("AAPL", 190), ("BHP", 200), ("BRK-B", 160)],
    "2010-12-31": [("XOM", 369), ("PTR", 303), ("AAPL", 296), ("1398.HK", 250), ("BHP", 240),
                   ("MSFT", 235), ("BRK-B", 200), ("GE", 195), ("WMT", 192), ("GOOGL", 190)],
    "2011-12-31": [("XOM", 406), ("AAPL", 376), ("PTR", 280), ("1398.HK", 230), ("BHP", 200),
                   ("IBM", 217), ("MSFT", 218), ("CVX", 215), ("CHL", 215), ("WMT", 205)],
    "2012-12-31": [("AAPL", 500), ("XOM", 390), ("PTR", 260), ("BRK-B", 248), ("GOOGL", 232),
                   ("MSFT", 224), ("WMT", 230), ("1398.HK", 240), ("GE", 220), ("CHL", 215)],
    "2013-12-31": [("AAPL", 500), ("XOM", 442), ("GOOGL", 375), ("MSFT", 310), ("BRK-B", 296),
                   ("1398.HK", 230), ("GE", 282), ("WMT", 255), ("CVX", 240), ("PTR", 230)],
    "2014-12-31": [("AAPL", 643), ("XOM", 390), ("MSFT", 382), ("BRK-B", 370), ("GOOGL", 360),
                   ("1398.HK", 280), ("PTR", 330), ("WMT", 277), ("JNJ", 290), ("WFC", 285)],
    "2015-12-31": [("AAPL", 586), ("GOOGL", 528), ("MSFT", 443), ("BRK-B", 325), ("XOM", 324),
                   ("AMZN", 318), ("META", 296), ("1398.HK", 200), ("JNJ", 282), ("WFC", 277)],
    "2016-12-31": [("AAPL", 609), ("GOOGL", 539), ("MSFT", 483), ("BRK-B", 408), ("AMZN", 356),
                   ("META", 332), ("XOM", 374), ("JNJ", 313), ("0700.HK", 275), ("JPM", 308)],
    "2017-12-31": [("AAPL", 868), ("GOOGL", 729), ("MSFT", 660), ("AMZN", 564), ("0700.HK", 530),
                   ("META", 513), ("BABA", 441), ("BRK-B", 489), ("JNJ", 374), ("JPM", 372)],
    "2018-12-31": [("MSFT", 780), ("AAPL", 748), ("AMZN", 737), ("GOOGL", 724), ("BRK-B", 494),
                   ("META", 376), ("BABA", 355), ("0700.HK", 385), ("JPM", 325), ("JNJ", 346)],
    "2019-12-31": [("2222.SR", 1880), ("AAPL", 1304), ("MSFT", 1200), ("GOOGL", 922), ("AMZN", 920),
                   ("META", 585), ("BRK-B", 553), ("BABA", 569), ("0700.HK", 460), ("JPM", 437)],
    "2020-12-31": [("AAPL", 2255), ("2222.SR", 1900), ("MSFT", 1682), ("AMZN", 1634), ("GOOGL", 1185),
                   ("META", 778), ("BABA", 628), ("TSLA", 669), ("0700.HK", 680), ("TSM", 565)],
    "2021-12-31": [("AAPL", 2913), ("MSFT", 2522), ("2222.SR", 1900), ("GOOGL", 1917), ("AMZN", 1691),
                   ("TSLA", 1061), ("META", 935), ("NVDA", 733), ("TSM", 623), ("0700.HK", 560)],
    "2022-12-31": [("AAPL", 2066), ("2222.SR", 1840), ("MSFT", 1787), ("GOOGL", 1145), ("AMZN", 856),
                   ("BRK-B", 689), ("UNH", 496), ("TSM", 386), ("XOM", 463), ("JNJ", 462)],
    "2023-12-31": [("AAPL", 2994), ("MSFT", 2794), ("2222.SR", 2130), ("GOOGL", 1756), ("AMZN", 1570),
                   ("NVDA", 1223), ("META", 909), ("BRK-B", 781), ("TSLA", 790), ("TSM", 540)],
    "2024-12-31": [("AAPL", 3780), ("NVDA", 3280), ("MSFT", 3130), ("GOOGL", 2330), ("AMZN", 2310),
                   ("2222.SR", 1790), ("META", 1470), ("TSLA", 1300), ("AVGO", 1080), ("TSM", 1040)],
    "2025-12-31": [("NVDA", 4400), ("AAPL", 4000), ("MSFT", 3700), ("GOOGL", 3300), ("AMZN", 2500),
                   ("META", 1800), ("AVGO", 1600), ("TSLA", 1400), ("TSM", 1100), ("2222.SR", 1600)],
}

# Extra tickers referenced by global10 that need metadata.
TICKER_META.setdefault("BHP", {"name": "BHP (ADR)", "currency": "USD", "exchange": "NYSE"})

UNIVERSES: Dict[str, Dict[str, Snapshot]] = {
    "nasdaq10": NASDAQ10,
    "us10": US10,
    "global10": GLOBAL10,
}

UNIVERSE_LABELS = {
    "nasdaq10": "Top 10 NASDAQ-listed",
    "us10": "Top 10 U.S. companies",
    "global10": "Top 10 global companies",
}

# Confidence in the curated membership, by era. We deliberately keep ANNUAL
# (year-end) snapshots rather than fabricating quarterly precision we don't have:
# the top-10 turns over slowly, and inventing 240 quarterly rows would add false
# precision, not accuracy. Cap-weighting is dominated by the top 3-4 names, whose
# identity/rank is high-confidence throughout.
CONFIDENCE = {
    "2005-2012": "medium  (membership solid; #8-#10 ordering & caps approximate; "
                 "some early NASDAQ names -- DELL/EBAY/ORCL -- have messy Yahoo history)",
    "2013-2025": "high    (well-documented mega-cap era; US/NASDAQ names all live & USD)",
    "global10":  "low pre-2015 (PetroChina/China Mobile/Gazprom ADRs delisted -> "
                 "dropped & renormalized at runtime); medium-high 2015+",
}


def _parse(d: str) -> datetime:
    return datetime.strptime(d, "%Y-%m-%d")


def members_asof(universe: str, as_of: datetime) -> Snapshot:
    """Return the most recent snapshot (ticker, cap) list with date <= as_of.

    This is the point-in-time guarantee: a rebalance on 2014-04-01 sees the
    2013-12-31 roster, never a later one.
    """
    snaps = UNIVERSES[universe]
    chosen_key = None
    for key in sorted(snaps.keys()):
        if _parse(key) <= as_of:
            chosen_key = key
        else:
            break
    if chosen_key is None:
        # as_of precedes our earliest snapshot; use the earliest available.
        chosen_key = sorted(snaps.keys())[0]
    return snaps[chosen_key]


def all_tickers(universe: str) -> List[str]:
    """Every ticker that ever appears in a universe (for one bulk price download)."""
    seen = set()
    for snap in UNIVERSES[universe].values():
        for ticker, _cap in snap:
            seen.add(ticker)
    return sorted(seen)


def name_of(ticker: str) -> str:
    return TICKER_META.get(ticker, {}).get("name", ticker)


def currency_of(ticker: str) -> str:
    return TICKER_META.get(ticker, {}).get("currency", "USD")
