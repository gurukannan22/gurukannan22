#!/usr/bin/env python3
"""
generate_stats.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetches live GitHub data via GraphQL and generates two SVG files:
  • assets/stats.svg      — Terminal-style stats dashboard card
  • assets/langs.svg      — Language breakdown donut + bar chart
Run via GitHub Actions every 6 hours.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import math
import requests
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────
USERNAME  = os.environ.get("GITHUB_USERNAME", "gurukannan22")
TOKEN     = os.environ.get("GITHUB_TOKEN", "")
OUT_DIR   = os.path.join(os.path.dirname(__file__), "..", "..", "assets")

# ── Palette ─────────────────────────────────────────────────────
C = {
    "bg":       "#010409",
    "bg2":      "#0D1117",
    "bg3":      "#161B22",
    "border":   "#21262D",
    "blue":     "#58A6FF",
    "blue2":    "#1F6FEB",
    "amber":    "#F0B429",
    "green":    "#3FB950",
    "purple":   "#BC8CFF",
    "pink":     "#FF7B72",
    "text":     "#E6EDF3",
    "dim":      "#7D8590",
    "white":    "#F0F6FC",
}

# ── GitHub GraphQL Query ─────────────────────────────────────────
QUERY = """
query ($login: String!) {
  user(login: $login) {
    name
    bio
    followers    { totalCount }
    following    { totalCount }
    repositories(
      first: 100
      ownerAffiliations: OWNER
      isFork: false
      orderBy: { field: STARGAZERS, direction: DESC }
    ) {
      totalCount
      nodes {
        name
        stargazerCount
        forkCount
        primaryLanguage { name color }
        languages(
          first: 10
          orderBy: { field: SIZE, direction: DESC }
        ) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { contributionCount date }
        }
      }
    }
    pullRequests(states: MERGED) { totalCount }
    issues(states: OPEN)         { totalCount }
  }
}
"""

# ────────────────────────────────────────────────────────────────
# Data Fetching
# ────────────────────────────────────────────────────────────────

def fetch_data() -> dict:
    if not TOKEN:
        print("⚠  No GITHUB_TOKEN found — using placeholder data.", file=sys.stderr)
        return _placeholder()

    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": QUERY, "variables": {"login": USERNAME}},
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type":  "application/json",
        },
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()

    if "errors" in payload:
        print(f"GraphQL errors: {payload['errors']}", file=sys.stderr)
        return _placeholder()

    return _parse(payload["data"]["user"])


def _parse(u: dict) -> dict:
    repos  = u["repositories"]["nodes"]
    cc     = u["contributionsCollection"]
    cal    = cc["contributionCalendar"]
    weeks  = cal["weeks"]

    stars  = sum(r["stargazerCount"] for r in repos)
    forks  = sum(r["forkCount"]      for r in repos)
    commits = cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
    prs    = u["pullRequests"]["totalCount"]
    issues = u["issues"]["totalCount"]
    repos_count = u["repositories"]["totalCount"]
    followers   = u["followers"]["totalCount"]
    total_c     = cal["totalContributions"]

    cur_streak, lng_streak = _streaks(weeks)
    langs = _languages(repos)

    return {
        "username":   USERNAME,
        "name":       u.get("name") or USERNAME,
        "commits":    commits,
        "stars":      stars,
        "forks":      forks,
        "prs":        prs,
        "issues":     issues,
        "repos":      repos_count,
        "followers":  followers,
        "total_c":    total_c,
        "cur_streak": cur_streak,
        "lng_streak": lng_streak,
        "langs":      langs,
        "weeks":      weeks,
    }


def _streaks(weeks: list) -> tuple:
    days = []
    for w in weeks:
        for d in w["contributionDays"]:
            days.append(d)
    days.sort(key=lambda x: x["date"])

    cur = lng = tmp = 0
    found_today = False

    for d in reversed(days):
        if d["contributionCount"] > 0:
            if not found_today:
                found_today = True
            tmp += 1
            lng = max(lng, tmp)
        else:
            if not found_today:
                continue     # Skip trailing empty days
            tmp = 0

    cur = tmp
    return cur, max(lng, cur)


def _languages(repos: list) -> list:
    acc = {}
    for repo in repos:
        for edge in repo.get("languages", {}).get("edges", []):
            name  = edge["node"]["name"]
            color = edge["node"]["color"] or "#858585"
            size  = edge["size"]
            if name in acc:
                acc[name]["size"] += size
            else:
                acc[name] = {"size": size, "color": color}

    total = sum(v["size"] for v in acc.values()) or 1
    result = [
        {
            "name":    k,
            "color":   v["color"],
            "size":    v["size"],
            "percent": round(v["size"] / total * 100, 1),
        }
        for k, v in acc.items()
    ]
    result.sort(key=lambda x: x["size"], reverse=True)
    return result[:10]


def _placeholder() -> dict:
    return {
        "username":   USERNAME, "name": "Guru Kannan",
        "commits":    1200,     "stars": 45,
        "forks":      12,       "prs":   88,
        "issues":     15,       "repos": 30,
        "followers":  80,       "total_c": 800,
        "cur_streak": 14,       "lng_streak": 42,
        "langs": [
            {"name":"Java",       "color":"#b07219","percent":45.2},
            {"name":"JavaScript", "color":"#f1e05a","percent":22.1},
            {"name":"Python",     "color":"#3572A5","percent":14.3},
            {"name":"HTML",       "color":"#e34c26","percent":9.8},
            {"name":"CSS",        "color":"#563d7c","percent":5.1},
            {"name":"TypeScript", "color":"#2b7489","percent":3.5},
        ],
        "weeks": [],
    }


# ────────────────────────────────────────────────────────────────
# Number formatter
# ────────────────────────────────────────────────────────────────

def fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


# ────────────────────────────────────────────────────────────────
# Mini Contribution Calendar (last 18 weeks)
# ────────────────────────────────────────────────────────────────

def _calendar_cells(weeks: list, x0: int, y0: int, cell: int = 9, gap: int = 2) -> str:
    if not weeks:
        return ""

    recent = weeks[-18:] if len(weeks) >= 18 else weeks
    pieces = []
    for wi, week in enumerate(recent):
        for di, day in enumerate(week["contributionDays"]):
            c = day["contributionCount"]
            if   c == 0:   fill = "#21262D"
            elif c <= 3:   fill = "#0e4429"
            elif c <= 6:   fill = "#006d32"
            elif c <= 9:   fill = "#26a641"
            else:           fill = "#39d353"

            cx = x0 + wi * (cell + gap)
            cy = y0 + di * (cell + gap)
            pieces.append(
                f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" '
                f'rx="2" fill="{fill}" opacity="0.95"/>'
            )
    return "\n    ".join(pieces)


# ────────────────────────────────────────────────────────────────
# SVG 1 — Stats Terminal Card (900 × 300)
# ────────────────────────────────────────────────────────────────

def build_stats_svg(d: dict) -> str:
    W, H = 900, 300
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M UTC")

    # Stat items: (label, value, sub-label, color, x, y)
    STATS = [
        ("COMMITS",   fmt(d["commits"]),    "all time",          C["blue"],   60,  145),
        ("STREAK",    f"{d['cur_streak']}d","current",           C["amber"],  210, 145),
        ("STARS",     fmt(d["stars"]),       "earned",            C["purple"], 360, 145),
        ("PRs",       fmt(d["prs"]),         "merged",            C["green"],  510, 145),
        ("REPOS",     fmt(d["repos"]),       "public",            C["pink"],   60,  235),
        ("FOLLOWERS", fmt(d["followers"]),   "github",            C["blue"],   210, 235),
        ("ISSUES",    fmt(d["issues"]),      "open",              C["amber"],  360, 235),
        ("BEST",      f"{d['lng_streak']}d","longest streak",    C["green"],  510, 235),
    ]

    # Calendar
    cal = _calendar_cells(d["weeks"], x0=650, y0=105, cell=8, gap=2)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "<defs>",
        # ── Styles ──
        """<style>
  @keyframes fadeUp   { from { opacity:0; transform:translateY(8px)} to {opacity:1; transform:translateY(0)} }
  @keyframes blink    { 0%,100%{opacity:1} 50%{opacity:0} }
  @keyframes pulseBdr { 0%,100%{stroke-opacity:.6} 50%{stroke-opacity:1} }
  @keyframes scanline { from{transform:translateY(-10px)} to{transform:translateY(310px)} }
  @keyframes shimmer  { 0%{stop-color:#58A6FF;stop-opacity:.1} 50%{stop-color:#58A6FF;stop-opacity:.25} 100%{stop-color:#58A6FF;stop-opacity:.1} }

  .label   { font:700 10px 'Courier New',monospace; letter-spacing:.12em; fill:#7D8590; }
  .val     { font:800 28px 'Segoe UI',sans-serif; }
  .sub     { font:400 10px 'Courier New',monospace; fill:#7D8590; }
  .prompt  { font:600 13px 'Courier New',monospace; }
  .ts      { font:400 10px 'Courier New',monospace; fill:#7D8590; }
  .cursor  { animation: blink 1.1s step-end infinite; }
  .border  { animation: pulseBdr 2.5s ease-in-out infinite; }
  .stat    { animation: fadeUp .6s ease both; }
</style>""",
        # ── Gradients ──
        '<linearGradient id="bgG" x1="0" y1="0" x2="1" y2="1">',
        f'  <stop offset="0%"   stop-color="{C["bg2"]}"/>',
        f'  <stop offset="100%" stop-color="{C["bg3"]}"/>',
        '</linearGradient>',
        '<linearGradient id="topBar" x1="0" y1="0" x2="1" y2="0">',
        f'  <stop offset="0%"   stop-color="{C["blue"]}"/>',
        f'  <stop offset="50%"  stop-color="{C["purple"]}"/>',
        f'  <stop offset="100%" stop-color="{C["amber"]}"/>',
        '</linearGradient>',
        # ── Glow filter ──
        '<filter id="glow" x="-20%" y="-20%" width="140%" height="140%">',
        '  <feGaussianBlur stdDeviation="3.5" result="blur"/>',
        '  <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        '</filter>',
        '<clipPath id="clip"><rect width="900" height="300" rx="14"/></clipPath>',
        "</defs>",

        # ── Background ──
        f'<rect width="{W}" height="{H}" rx="14" fill="url(#bgG)"/>',

        # ── Grid overlay ──
        '<g clip-path="url(#clip)" opacity=".03">',
        " ".join(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke="{C["blue"]}" stroke-width=".8"/>' for x in range(0, W, 28)),
        " ".join(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{C["blue"]}" stroke-width=".8"/>' for y in range(0, H, 28)),
        "</g>",

        # ── Scan-line animation ──
        f'<g clip-path="url(#clip)" opacity=".06">',
        f'  <rect x="0" y="0" width="{W}" height="6" rx="0" fill="{C["blue"]}">',
        f'    <animateTransform attributeName="transform" type="translate" from="0 -6" to="0 306" dur="3.5s" repeatCount="indefinite"/>',
        f'  </rect>',
        f'</g>',

        # ── Outer border (glow) ──
        f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="13" fill="none" '
        f'stroke="{C["blue"]}" stroke-width="1.2" class="border" filter="url(#glow)"/>',

        # ── Top rainbow bar ──
        f'<rect x="0" y="0" width="{W}" height="4" rx="0" fill="url(#topBar)"/>',

        # ── Vertical separator ──
        f'<line x1="640" y1="20" x2="640" y2="{H-20}" stroke="{C["border"]}" stroke-width="1"/>',

        # ── Terminal prompt ──
        f'<text x="26" y="42" class="prompt">',
        f'  <tspan fill="{C["green"]}">guru</tspan>',
        f'  <tspan fill="{C["dim"]}">@github</tspan>',
        f'  <tspan fill="{C["dim"]}">:</tspan>',
        f'  <tspan fill="{C["blue"]}">~/stats</tspan>',
        f'  <tspan fill="{C["dim"]}"> $ </tspan>',
        f'  <tspan fill="{C["text"]}">live --fetch --render</tspan>',
        f'  <tspan class="cursor" fill="{C["blue"]}">█</tspan>',
        f'</text>',

        # ── Separator line ──
        f'<line x1="26" y1="56" x2="620" y2="56" stroke="{C["border"]}" stroke-width="1"/>',

        # ── Section labels ──
        f'<text x="26"  y="76" class="label">// ACTIVITY METRICS</text>',
        f'<text x="26"  y="168" class="label">// REPOSITORY METRICS</text>',

        # ── Stats ──
    ]

    for i, (label, val, sub, color, x, y) in enumerate(STATS):
        delay = i * 0.1
        svg_parts += [
            f'<g class="stat" style="animation-delay:{delay:.1f}s">',
            f'  <text x="{x}" y="{y-20}" class="label">{label}</text>',
            f'  <text x="{x}" y="{y+4}"  class="val" fill="{color}" filter="url(#glow)">{val}</text>',
            f'  <text x="{x}" y="{y+18}" class="sub">{sub}</text>',
            f'</g>',
        ]

    # ── Calendar section ──
    svg_parts += [
        f'<text x="658" y="76" class="label">// CONTRIBUTION CALENDAR  (18w)</text>',
        f'<g class="stat" style="animation-delay:.4s">',
        cal,
        f'</g>',
    ]

    # ── Timestamp footer ──
    svg_parts += [
        f'<line x1="26" y1="{H-38}" x2="{W-26}" y2="{H-38}" stroke="{C["border"]}" stroke-width="1"/>',
        f'<text x="26" y="{H-18}" class="ts">⟳ AUTO-UPDATED: {now}</text>',
        f'<text x="{W-26}" y="{H-18}" class="ts" text-anchor="end">github.com/{USERNAME}</text>',
        "</svg>",
    ]

    return "\n".join(svg_parts)


# ────────────────────────────────────────────────────────────────
# SVG 2 — Language Chart (440 × 300)
# ────────────────────────────────────────────────────────────────

def _donut_path(cx: float, cy: float, r: float, r_inner: float,
                start_deg: float, end_deg: float) -> str:
    """Return SVG path for a donut arc segment."""
    def polar(deg: float):
        rad = math.radians(deg - 90)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    def polar_i(deg: float):
        rad = math.radians(deg - 90)
        return cx + r_inner * math.cos(rad), cy + r_inner * math.sin(rad)

    large = 1 if (end_deg - start_deg) > 180 else 0
    x1, y1 = polar(start_deg)
    x2, y2 = polar(end_deg)
    xi1, yi1 = polar_i(end_deg)
    xi2, yi2 = polar_i(start_deg)

    return (
        f"M {x1:.2f} {y1:.2f} "
        f"A {r:.2f} {r:.2f} 0 {large} 1 {x2:.2f} {y2:.2f} "
        f"L {xi1:.2f} {yi1:.2f} "
        f"A {r_inner:.2f} {r_inner:.2f} 0 {large} 0 {xi2:.2f} {yi2:.2f} Z"
    )


def build_langs_svg(d: dict) -> str:
    langs = d["langs"][:8]
    W, H  = 440, 300
    now   = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M UTC")

    CX, CY = 145, 155
    R, RI  = 85, 50

    # Build donut arcs
    donut_parts = []
    angle = 0.0
    for i, lang in enumerate(langs):
        sweep = lang["percent"] / 100 * 360
        end   = angle + sweep
        path  = _donut_path(CX, CY, R, RI, angle, end)
        color = lang.get("color") or "#858585"
        delay = i * 0.08
        donut_parts.append(
            f'<path d="{path}" fill="{color}" opacity=".9" '
            f'style="animation:fadeUp .5s {delay:.2f}s both ease"/>'
        )
        angle = end

    # Center text
    top_lang = langs[0]["name"] if langs else "Java"
    top_pct  = langs[0]["percent"] if langs else 0

    # Bar rows
    bar_parts = []
    bar_x0, bar_y0 = 250, 90
    bar_w_max = 165
    for i, lang in enumerate(langs):
        by = bar_y0 + i * 26
        color  = lang.get("color") or "#858585"
        bw     = round(lang["percent"] / 100 * bar_w_max)
        delay  = i * 0.07
        bar_parts += [
            # dot
            f'<circle cx="{bar_x0 - 10}" cy="{by - 4}" r="4" fill="{color}" '
            f'style="animation:fadeUp .4s {delay:.2f}s both ease"/>',
            # name
            f'<text x="{bar_x0}" y="{by}" '
            f'font-family="Courier New,monospace" font-size="10" fill="{C["text"]}" '
            f'style="animation:fadeUp .4s {delay:.2f}s both ease">{lang["name"]}</text>',
            # pct
            f'<text x="{bar_x0 + bar_w_max + 5}" y="{by}" text-anchor="start" '
            f'font-family="Courier New,monospace" font-size="10" fill="{color}" font-weight="700" '
            f'style="animation:fadeUp .4s {delay:.2f}s both ease">{lang["percent"]}%</text>',
            # track
            f'<rect x="{bar_x0}" y="{by+3}" width="{bar_w_max}" height="3" rx="2" fill="{C["border"]}"/>',
            # fill
            f'<rect x="{bar_x0}" y="{by+3}" width="{bw}" height="3" rx="2" fill="{color}" '
            f'style="animation:fadeUp .4s {delay:.2f}s both ease"/>',
        ]

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <style>
    @keyframes fadeUp {{ from{{opacity:0;transform:translateY(8px)}} to{{opacity:1;transform:translateY(0)}} }}
    @keyframes pulseBdr {{ 0%,100%{{stroke-opacity:.6}} 50%{{stroke-opacity:1}} }}
    @keyframes spin {{ from{{transform:rotate(0deg)}} to{{transform:rotate(360deg)}} }}
  </style>
  <linearGradient id="langBg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%"   stop-color="{C['bg2']}"/>
    <stop offset="100%" stop-color="{C['bg3']}"/>
  </linearGradient>
  <linearGradient id="langTop" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%"   stop-color="{C['purple']}"/>
    <stop offset="100%" stop-color="{C['pink']}"/>
  </linearGradient>
  <filter id="glow2" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur stdDeviation="3" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <clipPath id="clip2"><rect width="{W}" height="{H}" rx="14"/></clipPath>
</defs>

<!-- Background -->
<rect width="{W}" height="{H}" rx="14" fill="url(#langBg)"/>

<!-- Grid -->
<g clip-path="url(#clip2)" opacity=".03">
  {"".join(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke="{C["purple"]}" stroke-width=".8"/>' for x in range(0,W,28))}
  {"".join(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{C["purple"]}" stroke-width=".8"/>' for y in range(0,H,28))}
</g>

<!-- Border -->
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="13" fill="none"
      stroke="{C['purple']}" stroke-width="1.2"
      style="animation:pulseBdr 2.5s ease-in-out infinite" filter="url(#glow2)"/>

<!-- Top bar -->
<rect x="0" y="0" width="{W}" height="4" fill="url(#langTop)"/>

<!-- Title -->
<text x="26" y="40"
  font-family="Courier New,monospace" font-size="11" font-weight="700"
  fill="{C['dim']}" letter-spacing=".12em">// LANGUAGE MATRIX</text>

<!-- Divider -->
<line x1="26" y1="52" x2="{W-26}" y2="52" stroke="{C['border']}" stroke-width="1"/>

<!-- Donut arcs -->
{"".join(donut_parts)}

<!-- Donut center -->
<circle cx="{CX}" cy="{CY}" r="{RI-3}" fill="{C['bg2']}"/>
<text x="{CX}" y="{CY-10}" text-anchor="middle"
  font-family="Courier New,monospace" font-size="9" fill="{C['dim']}">TOP LANG</text>
<text x="{CX}" y="{CY+8}" text-anchor="middle"
  font-family="Courier New,monospace" font-size="13" font-weight="800"
  fill="{C['white']}">{top_lang[:8]}</text>
<text x="{CX}" y="{CY+24}" text-anchor="middle"
  font-family="Courier New,monospace" font-size="11" font-weight="700"
  fill="{C['purple']}">{top_pct}%</text>

<!-- Bars -->
{"".join(bar_parts)}

<!-- Vertical separator -->
<line x1="236" y1="65" x2="236" y2="{H-35}" stroke="{C['border']}" stroke-width="1"/>

<!-- Footer -->
<line x1="26" y1="{H-30}" x2="{W-26}" y2="{H-30}" stroke="{C['border']}" stroke-width="1"/>
<text x="26" y="{H-13}"
  font-family="Courier New,monospace" font-size="9" fill="{C['dim']}">
  ⟳ {now}
</text>
</svg>"""
    return svg


# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────

def main():
    print(f"[INFO] Fetching data for @{USERNAME} …")
    data = fetch_data()
    print(f"[INFO] Commits={data['commits']}  Stars={data['stars']}  "
          f"Streak={data['cur_streak']}d  Langs={len(data['langs'])}")

    os.makedirs(OUT_DIR, exist_ok=True)

    stats_path = os.path.join(OUT_DIR, "stats.svg")
    langs_path = os.path.join(OUT_DIR, "langs.svg")

    with open(stats_path, "w", encoding="utf-8") as f:
        f.write(build_stats_svg(data))
    print(f"[OK]   Written: {stats_path}")

    with open(langs_path, "w", encoding="utf-8") as f:
        f.write(build_langs_svg(data))
    print(f"[OK]   Written: {langs_path}")

    print("[DONE] SVGs generated successfully.")


if __name__ == "__main__":
    main()
