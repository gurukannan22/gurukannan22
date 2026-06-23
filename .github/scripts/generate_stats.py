#!/usr/bin/env python3
"""
generate_stats.py  —  Ultra-Modern GitHub Profile SVG Generator
════════════════════════════════════════════════════════════════
Generates three custom animated SVG assets:
  • assets/banner.svg   — Particle-field animated name banner
  • assets/stats.svg    — Cyberpunk terminal stats dashboard
  • assets/langs.svg    — Animated donut + bar language chart

GitHub Actions runs this every 6 hours and commits the results.
"""

import os, sys, math, random, requests
from datetime import datetime, timezone

USERNAME = os.environ.get("GITHUB_USERNAME", "gurukannan22")
TOKEN    = os.environ.get("GITHUB_TOKEN", "")
OUT_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "assets")

# ── Palette ──────────────────────────────────────────────────────────────────
P = {
    "bg":     "#010409", "bg2": "#0D1117", "bg3":    "#161B22",
    "border": "#21262D", "blue": "#58A6FF", "blue2":  "#1F6FEB",
    "amber":  "#F0B429", "green": "#3FB950", "purple": "#BC8CFF",
    "pink":   "#FF7B72", "teal":  "#39C5BB", "text":   "#E6EDF3",
    "dim":    "#7D8590", "white": "#F0F6FC",
}

QUERY = """query($login:String!){user(login:$login){
  name followers{totalCount}
  repositories(first:100 ownerAffiliations:OWNER isFork:false
    orderBy:{field:STARGAZERS direction:DESC}){
    totalCount
    nodes{stargazerCount forkCount
      languages(first:10 orderBy:{field:SIZE direction:DESC}){
        edges{size node{name color}}}}}
  contributionsCollection{
    totalCommitContributions restrictedContributionsCount
    contributionCalendar{totalContributions
      weeks{contributionDays{contributionCount date}}}}
  pullRequests(states:MERGED){totalCount}
  issues(states:OPEN){totalCount}}}"""

# ─────────────────────────────────────────────────────────────────────────────
def fetch_data() -> dict:
    if not TOKEN:
        print("⚠  No GITHUB_TOKEN — using placeholder.", file=sys.stderr)
        return _placeholder()
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": QUERY, "variables": {"login": USERNAME}},
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        timeout=20,
    )
    r.raise_for_status()
    p = r.json()
    if "errors" in p:
        print(f"GraphQL error: {p['errors']}", file=sys.stderr)
        return _placeholder()
    return _parse(p["data"]["user"])

def _parse(u):
    repos   = u["repositories"]["nodes"]
    cc      = u["contributionsCollection"]
    cal     = cc["contributionCalendar"]
    commits = cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
    stars   = sum(r["stargazerCount"] for r in repos)
    cur, lng = _streaks(cal["weeks"])
    return {
        "commits": commits, "stars": stars,
        "forks":   sum(r["forkCount"] for r in repos),
        "prs":     u["pullRequests"]["totalCount"],
        "issues":  u["issues"]["totalCount"],
        "repos":   u["repositories"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "total_c": cal["totalContributions"],
        "cur_streak": cur, "lng_streak": lng,
        "langs": _languages(repos),
        "weeks": cal["weeks"],
    }

def _streaks(weeks):
    days = sorted([d for w in weeks for d in w["contributionDays"]], key=lambda x: x["date"])
    cur = lng = tmp = 0
    for d in reversed(days):
        if d["contributionCount"] > 0:
            tmp += 1; lng = max(lng, tmp)
        else:
            if cur == 0: cur = tmp
            tmp = 0
    if cur == 0: cur = tmp
    return cur, max(lng, cur)

def _languages(repos):
    acc = {}
    for repo in repos:
        for e in repo.get("languages", {}).get("edges", []):
            n = e["node"]["name"]; c = e["node"]["color"] or "#858585"; s = e["size"]
            acc[n] = {"size": acc.get(n, {"size": 0})["size"] + s, "color": c}
    total = sum(v["size"] for v in acc.values()) or 1
    return sorted([
        {"name": k, "color": v["color"], "size": v["size"],
         "percent": round(v["size"] / total * 100, 1)}
        for k, v in acc.items()
    ], key=lambda x: x["size"], reverse=True)[:9]

def _placeholder():
    return {
        "commits": 1242, "stars": 48, "forks": 15, "prs": 92,
        "issues": 8, "repos": 18, "followers": 94, "total_c": 842,
        "cur_streak": 0, "lng_streak": 6,
        "langs": [
            {"name": "Java",       "color": "#b07219", "percent": 52.3},
            {"name": "JavaScript", "color": "#f1e05a", "percent": 18.4},
            {"name": "Python",     "color": "#3572A5", "percent": 11.2},
            {"name": "HTML",       "color": "#e34c26", "percent": 8.7},
            {"name": "CSS",        "color": "#563d7c", "percent": 5.1},
            {"name": "TypeScript", "color": "#2b7489", "percent": 2.8},
            {"name": "Shell",      "color": "#89e051", "percent": 1.5},
        ],
        "weeks": [],
    }

def fmt(n):
    return f"{n/1_000_000:.1f}M" if n >= 1_000_000 else f"{n/1_000:.1f}k" if n >= 1_000 else str(n)

# ════════════════════════════════════════════════════════════════════════════════
# Shared SVG primitives
# ════════════════════════════════════════════════════════════════════════════════
def _corner_brackets(W, H, size=22, gap=10, color="#58A6FF", t=2.5):
    g, s = gap, size
    return (
        f'<path d="M {g+s} {g} L {g} {g} L {g} {g+s}" stroke="{color}" stroke-width="{t}" fill="none" stroke-linecap="round" opacity=".85"/>'
        f'<path d="M {W-g-s} {g} L {W-g} {g} L {W-g} {g+s}" stroke="{color}" stroke-width="{t}" fill="none" stroke-linecap="round" opacity=".85"/>'
        f'<path d="M {g} {H-g-s} L {g} {H-g} L {g+s} {H-g}" stroke="{color}" stroke-width="{t}" fill="none" stroke-linecap="round" opacity=".85"/>'
        f'<path d="M {W-g-s} {H-g} L {W-g} {H-g} L {W-g} {H-g-s}" stroke="{color}" stroke-width="{t}" fill="none" stroke-linecap="round" opacity=".85"/>'
    )

def _dot_bg(W, H, step=22, color="#58A6FF"):
    dots = "".join(
        f'<circle cx="{x}" cy="{y}" r=".9" fill="{color}"/>'
        for x in range(step, W, step) for y in range(step, H, step)
    )
    return f'<g opacity=".05">{dots}</g>'

def _animated_border(W, H, color):
    return (
        f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="14" fill="none" stroke="{color}" stroke-width="1.2">'
        f'<animate attributeName="stroke-opacity" values=".3;.95;.3" dur="2.8s" repeatCount="indefinite"/>'
        f'</rect>'
    )

def _scanline(W, H, color):
    return (
        f'<rect x="0" y="0" width="{W}" height="5" fill="{color}" opacity=".07">'
        f'<animateTransform attributeName="transform" type="translate" '
        f'from="0 -5" to="0 {H+5}" dur="4s" repeatCount="indefinite" calcMode="linear"/>'
        f'</rect>'
    )

def _clip_bar(uid, bx, by, bw, bh, fill, delay=0, dur=1.3, rx=2):
    """Animated progress bar via SVG clipPath — grows left→right."""
    return (
        f'<clipPath id="cp{uid}"><rect x="{bx}" y="{by}" width="0" height="{bh}">'
        f'<animate attributeName="width" from="0" to="{bw}" dur="{dur}s" begin="{delay}s" fill="freeze" '
        f'calcMode="spline" keyTimes="0;1" keySplines=".22 1 .36 1"/>'
        f'</rect></clipPath>'
        f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="{rx}" fill="{fill}" clip-path="url(#cp{uid})"/>'
    )

# ════════════════════════════════════════════════════════════════════════════════
# BANNER SVG  (900 × 200) — Particle field + gradient name
# ════════════════════════════════════════════════════════════════════════════════
def build_banner_svg() -> str:
    W, H = 900, 200
    random.seed(42)

    # 35 animated glowing particles
    particles = ""
    for _ in range(35):
        px  = random.randint(20, W - 20)
        py  = random.randint(10, H - 10)
        pr  = round(random.uniform(1.0, 3.0), 1)
        dl  = round(random.uniform(0, 5), 2)
        dr  = round(random.uniform(1.8, 4.5), 2)
        col = random.choice([P["blue"], P["purple"], P["amber"], P["teal"], P["green"]])
        particles += (
            f'<circle cx="{px}" cy="{py}" r="{pr}" fill="{col}">'
            f'<animate attributeName="opacity" values=".12;.9;.12" dur="{dr}s" begin="{dl}s" repeatCount="indefinite"/>'
            f'<animate attributeName="r" values="{pr};{pr*1.7:.1f};{pr}" dur="{dr*1.3:.1f}s" begin="{dl}s" repeatCount="indefinite"/>'
            f'</circle>'
        )

    # Horizontal scan lines (decorative background)
    hlines = "".join(
        f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{P["blue"]}" stroke-width=".4" opacity=".05"/>'
        for y in range(0, H, 8)
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <style>
    @keyframes nameIn  {{ from{{opacity:0;transform:translateY(-16px)}} to{{opacity:1;transform:translateY(0)}} }}
    @keyframes subIn   {{ from{{opacity:0;transform:translateY(16px)}}  to{{opacity:1;transform:translateY(0)}} }}
    @keyframes glowN   {{ 0%,100%{{filter:drop-shadow(0 0 6px {P["blue"]}90)}} 50%{{filter:drop-shadow(0 0 24px {P["blue"]})}} }}
    @keyframes chipIn  {{ from{{opacity:0;transform:scale(.7)}} to{{opacity:1;transform:scale(1)}} }}
    @keyframes pulseGr {{ 0%,100%{{opacity:1;r:3.5}} 50%{{opacity:.3;r:5.5}} }}
  </style>
  <linearGradient id="nameG" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%"   stop-color="{P["blue"]}"/>
    <stop offset="44%"  stop-color="{P["purple"]}"/>
    <stop offset="100%" stop-color="{P["amber"]}"/>
  </linearGradient>
  <linearGradient id="bgB" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%"   stop-color="{P["bg"]}"/>
    <stop offset="100%" stop-color="{P["bg3"]}"/>
  </linearGradient>
  <linearGradient id="topG" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%"   stop-color="{P["blue"]}"/>
    <stop offset="50%"  stop-color="{P["purple"]}"/>
    <stop offset="100%" stop-color="{P["amber"]}"/>
  </linearGradient>
  <filter id="gN" x="-10%" y="-40%" width="120%" height="180%">
    <feGaussianBlur stdDeviation="5" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <clipPath id="bClip"><rect width="{W}" height="{H}" rx="16"/></clipPath>
</defs>

<rect width="{W}" height="{H}" rx="16" fill="url(#bgB)"/>

<!-- Scan lines -->
<g clip-path="url(#bClip)">{hlines}</g>

<!-- Particles -->
<g clip-path="url(#bClip)">{particles}</g>

<!-- Corner brackets -->
{_corner_brackets(W, H, size=20, gap=10, color=P["amber"], t=2.2)}

<!-- Top gradient bar -->
<rect x="0" y="0" width="{W}" height="3.5" fill="url(#topG)"/>

<!-- Name -->
<text x="{W//2}" y="98" text-anchor="middle"
  font-family="'Segoe UI',Ubuntu,'Helvetica Neue',sans-serif"
  font-size="58" font-weight="800" letter-spacing="-1"
  fill="url(#nameG)" filter="url(#gN)"
  style="animation:nameIn .9s cubic-bezier(.16,1,.3,1) both, glowN 3.5s 1.8s ease-in-out infinite">
  GURU KANNAN
</text>

<!-- Subtitle -->
<text x="{W//2}" y="130" text-anchor="middle"
  font-family="'Courier New',Courier,monospace"
  font-size="12.5" font-weight="500" letter-spacing=".24em" fill="{P["dim"]}"
  style="animation:subIn 1s .5s ease both">
  SYSTEM ENGINEER  ·  FULL STACK DEVELOPER  ·  TECH EDUCATOR
</text>

<!-- Growing accent bar -->
<rect x="{W//2}" y="148" width="0" height="2" rx="1" fill="url(#topG)">
  <animate attributeName="width" from="0" to="190" dur=".9s" begin=".9s" fill="freeze"
    calcMode="spline" keyTimes="0;1" keySplines=".22 1 .36 1"/>
  <animate attributeName="x" from="{W//2}" to="{W//2 - 95}" dur=".9s" begin=".9s" fill="freeze"
    calcMode="spline" keyTimes="0;1" keySplines=".22 1 .36 1"/>
</rect>

<!-- Status chip -->
<rect x="{W//2 - 52}" y="158" width="104" height="22" rx="11"
  fill="{P["green"]}18" stroke="{P["green"]}" stroke-width=".9"
  style="animation:chipIn .7s 1.3s cubic-bezier(.34,1.56,.64,1) both"/>
<circle cx="{W//2 - 32}" cy="169" r="0" fill="{P["green"]}">
  <animate attributeName="r"       values="3.5;5.5;3.5" dur="1.5s" repeatCount="indefinite"/>
  <animate attributeName="opacity" values="1;.2;1"       dur="1.5s" repeatCount="indefinite"/>
</circle>
<text x="{W//2 - 20}" y="174" text-anchor="start"
  font-family="'Courier New',monospace" font-size="10" font-weight="700" fill="{P["green"]}"
  style="animation:chipIn .7s 1.3s cubic-bezier(.34,1.56,.64,1) both">
  ONLINE · SHIPPING
</text>

</svg>"""


# ════════════════════════════════════════════════════════════════════════════════
# STATS SVG  (900 × 340) — Cyberpunk stat cards + heatmap
# ════════════════════════════════════════════════════════════════════════════════
def build_stats_svg(d: dict) -> str:
    W, H   = 900, 340
    now    = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M UTC")
    CW, CH = 138, 90   # card width / height

    # 8 stat cards: (label, value, sub, color, card_x, card_y, raw_val)
    STATS = [
        ("COMMITS",    fmt(d["commits"]),     "all time",      P["blue"],   32,  76,  d["commits"]),
        ("STREAK",     f'{d["cur_streak"]}d', "current",       P["amber"],  186, 76,  d["cur_streak"]),
        ("STARS",      fmt(d["stars"]),        "earned",        P["purple"], 340, 76,  d["stars"]),
        ("PRs MERGED", fmt(d["prs"]),          "merged",        P["green"],  494, 76,  d["prs"]),
        ("REPOS",      fmt(d["repos"]),        "public",        P["pink"],   32,  196, d["repos"]),
        ("FOLLOWERS",  fmt(d["followers"]),    "github",        P["blue"],   186, 196, d["followers"]),
        ("ISSUES",     fmt(d["issues"]),       "open",          P["amber"],  340, 196, d["issues"]),
        ("BEST STREAK",f'{d["lng_streak"]}d', "all time",      P["teal"],   494, 196, d["lng_streak"]),
    ]

    max_raw = max(s[6] for s in STATS) or 1
    clip_defs = ""
    cards     = ""

    for i, (label, val, sub, color, cx, cy, raw) in enumerate(STATS):
        delay = i * 0.11
        bar_w = max(4, int(raw / max_raw * (CW - 22)))
        bx, by = cx + 11, cy + CH - 20
        uid = f"s{i}"
        clip_defs += _clip_bar(uid, bx, by, bar_w, 4, color, delay=round(delay + 0.55, 2), rx=2)

        cards += f"""
<g style="animation:cardUp .5s {delay:.2f}s cubic-bezier(.16,1,.3,1) both">
  <rect x="{cx}" y="{cy}" width="{CW}" height="{CH}" rx="10" fill="{P["bg3"]}"/>
  <rect x="{cx}" y="{cy}" width="{CW}" height="{CH}" rx="10" fill="none" stroke="{color}" stroke-width=".7" opacity=".4"/>
  <rect x="{cx+11}" y="{cy}" width="32" height="2.5" rx="0" fill="{color}" opacity=".9"/>
  <text x="{cx+11}" y="{cy+17}" font-family="'Courier New',monospace" font-size="9" font-weight="700"
    letter-spacing=".13em" fill="{P["dim"]}">{label}</text>
  <text x="{cx+11}" y="{cy+53}" font-family="'Segoe UI',Ubuntu,sans-serif" font-size="30" font-weight="800"
    fill="{color}">{val}
    <animate attributeName="opacity" values="0;1" dur=".35s" begin="{delay:.2f}s" fill="freeze"/>
  </text>
  <text x="{cx+11}" y="{cy+66}" font-family="'Courier New',monospace" font-size="9" fill="{P["dim"]}">{sub}</text>
  <rect x="{bx}" y="{by}" width="{CW-22}" height="4" rx="2" fill="{P["border"]}"/>
</g>"""

    # 18-week heatmap with animated cell fade-in
    recent = d["weeks"][-18:] if len(d["weeks"]) >= 18 else d["weeks"]
    CELL, GAP = 9, 2
    hx0, hy0  = 656, 82
    cells = ""
    for wi, week in enumerate(recent):
        for di, day in enumerate(week["contributionDays"]):
            c = day["contributionCount"]
            fill = ("#0e4429" if c <= 3 else "#006d32" if c <= 6 else
                    "#26a641" if c <= 9 else "#39d353") if c > 0 else P["border"]
            d_s = round((wi * 7 + di) * 0.008, 3)
            cells += (
                f'<rect x="{hx0 + wi*(CELL+GAP)}" y="{hy0 + di*(CELL+GAP)}" '
                f'width="{CELL}" height="{CELL}" rx="2" fill="{fill}">'
                f'<animate attributeName="opacity" values="0;1" dur=".3s" begin="{d_s}s" fill="freeze"/>'
                f'</rect>'
            )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <style>
    @keyframes cardUp  {{ from{{opacity:0;transform:translateY(14px)}} to{{opacity:1;transform:translateY(0)}} }}
    @keyframes blinkC  {{ 0%,100%{{opacity:1}} 50%{{opacity:0}} }}
  </style>
  <linearGradient id="topSt" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%"   stop-color="{P["blue"]}"/>
    <stop offset="42%"  stop-color="{P["purple"]}"/>
    <stop offset="100%" stop-color="{P["amber"]}"/>
  </linearGradient>
  <linearGradient id="bgSt" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%"   stop-color="{P["bg2"]}"/>
    <stop offset="100%" stop-color="#090d14"/>
  </linearGradient>
  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur stdDeviation="3" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <clipPath id="stClip"><rect width="{W}" height="{H}" rx="15"/></clipPath>
  {clip_defs}
</defs>

<rect width="{W}" height="{H}" rx="15" fill="url(#bgSt)"/>
{_dot_bg(W, H, step=22, color=P["blue"])}
<g clip-path="url(#stClip)">{_scanline(W, H, P["blue"])}</g>
{_animated_border(W, H, P["blue"])}
{_corner_brackets(W, H, size=20, gap=10, color=P["blue"], t=2.3)}
<rect x="0" y="0" width="{W}" height="3.5" fill="url(#topSt)"/>

<!-- terminal prompt -->
<text x="32" y="48" font-family="'Courier New',monospace" font-size="13" font-weight="600">
  <tspan fill="{P["green"]}">guru</tspan><tspan fill="{P["dim"]}">@github:</tspan>
  <tspan fill="{P["blue"]}">~/profile/stats</tspan>
  <tspan fill="{P["dim"]}"> $ </tspan>
  <tspan fill="{P["text"]}">./live --fetch --all-metrics</tspan>
  <tspan fill="{P["blue"]}" style="animation:blinkC 1.1s step-end infinite">█</tspan>
</text>

<!-- LIVE chip -->
<rect x="824" y="32" width="50" height="22" rx="11"
  fill="{P["green"]}15" stroke="{P["green"]}" stroke-width=".8"/>
<circle cx="837" cy="43" r="0" fill="{P["green"]}">
  <animate attributeName="r"       values="3;4.8;3" dur="1.4s" repeatCount="indefinite"/>
  <animate attributeName="opacity" values="1;.2;1"  dur="1.4s" repeatCount="indefinite"/>
</circle>
<text x="845" y="48" font-family="'Courier New',monospace" font-size="10" font-weight="700" fill="{P["green"]}">LIVE</text>

<line x1="32" y1="60" x2="{W-32}" y2="60" stroke="{P["border"]}" stroke-width="1"/>
<text x="32"  y="73" font-family="'Courier New',monospace" font-size="9" font-weight="700" letter-spacing=".13em" fill="{P["dim"]}">// METRICS</text>
<text x="656" y="73" font-family="'Courier New',monospace" font-size="9" font-weight="700" letter-spacing=".13em" fill="{P["dim"]}">// CONTRIBUTION HEATMAP (18 WEEKS)</text>
<line x1="642" y1="62" x2="642" y2="{H-42}" stroke="{P["border"]}" stroke-width="1"/>

{cards}
{cells}

<!-- heatmap legend -->
<text x="656" y="250" font-family="'Courier New',monospace" font-size="8" fill="{P["dim"]}">Less</text>
<rect x="684" y="243" width="9" height="9" rx="2" fill="{P["border"]}"/>
<rect x="696" y="243" width="9" height="9" rx="2" fill="#0e4429"/>
<rect x="708" y="243" width="9" height="9" rx="2" fill="#006d32"/>
<rect x="720" y="243" width="9" height="9" rx="2" fill="#26a641"/>
<rect x="732" y="243" width="9" height="9" rx="2" fill="#39d353"/>
<text x="745" y="250" font-family="'Courier New',monospace" font-size="8" fill="{P["dim"]}">More</text>

<!-- total contributions pill -->
<rect x="656" y="261" width="{W-32-656}" height="28" rx="8"
  fill="{P["green"]}0F" stroke="{P["green"]}" stroke-width=".7"/>
<text x="{656 + (W-32-656)//2}" y="280" text-anchor="middle"
  font-family="'Segoe UI',sans-serif" font-size="13" font-weight="800" fill="{P["green"]}">
  {fmt(d["total_c"])} contributions this year
</text>

<line x1="32" y1="{H-36}" x2="{W-32}" y2="{H-36}" stroke="{P["border"]}" stroke-width="1"/>
<text x="32"      y="{H-16}" font-family="'Courier New',monospace" font-size="9" fill="{P["dim"]}">⟳ AUTO-UPDATED · {now}</text>
<text x="{W-32}"  y="{H-16}" font-family="'Courier New',monospace" font-size="9" fill="{P["dim"]}" text-anchor="end">github.com/{USERNAME}</text>

</svg>"""


# ════════════════════════════════════════════════════════════════════════════════
# LANGS SVG  (440 × 340) — Animated donut ring + staggered bars
# ════════════════════════════════════════════════════════════════════════════════
def _donut_seg(cx, cy, R, Ri, a0, a1):
    def pt(deg, r):
        rad = math.radians(deg - 90)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)
    large = 1 if (a1 - a0) > 180 else 0
    x1, y1 = pt(a0, R);  x2, y2 = pt(a1, R)
    xi1,yi1 = pt(a1, Ri); xi2,yi2 = pt(a0, Ri)
    return (f"M {x1:.2f} {y1:.2f} A {R} {R} 0 {large} 1 {x2:.2f} {y2:.2f} "
            f"L {xi1:.2f} {yi1:.2f} A {Ri} {Ri} 0 {large} 0 {xi2:.2f} {yi2:.2f} Z")

def build_langs_svg(d: dict) -> str:
    W, H  = 440, 340
    langs = d["langs"][:8]
    now   = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M UTC")
    CX, CY, R, Ri = 126, 168, 88, 52

    # Donut segments — fade + scale in staggered
    segs  = ""
    angle = -90.0
    for i, lang in enumerate(langs):
        sweep = lang["percent"] / 100 * 360
        path  = _donut_seg(CX, CY, R, Ri, angle, angle + sweep)
        color = lang.get("color") or "#858585"
        delay = i * 0.10
        segs += (
            f'<path d="{path}" fill="{color}" opacity="0">'
            f'<animate attributeName="opacity" values="0;.95" dur=".4s" begin="{delay:.2f}s" fill="freeze"/>'
            f'</path>\n'
        )
        angle += sweep

    # Outer ring that draws itself
    circ = 2 * math.pi * (R + 6)
    segs += (
        f'<circle cx="{CX}" cy="{CY}" r="{R+6}" fill="none" '
        f'stroke="{P["purple"]}" stroke-width="1.8" opacity=".22" '
        f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}">'
        f'<animate attributeName="stroke-dashoffset" from="{circ:.1f}" to="0" '
        f'dur="1.6s" begin=".15s" fill="freeze" '
        f'calcMode="spline" keyTimes="0;1" keySplines=".22 1 .36 1"/>'
        f'</circle>'
    )

    # Donut center
    top  = langs[0]["name"][:8] if langs else "Java"
    tpct = langs[0]["percent"]  if langs else 0.0
    segs += (
        f'<circle cx="{CX}" cy="{CY}" r="{Ri-4}" fill="{P["bg2"]}"/>'
        f'<text x="{CX}" y="{CY-14}" text-anchor="middle" '
        f'font-family="\'Courier New\',monospace" font-size="8.5" fill="{P["dim"]}">TOP LANG</text>'
        f'<text x="{CX}" y="{CY+8}" text-anchor="middle" '
        f'font-family="\'Segoe UI\',Ubuntu,sans-serif" font-size="15" font-weight="800" '
        f'fill="{P["white"]}">{top}</text>'
        f'<text x="{CX}" y="{CY+26}" text-anchor="middle" '
        f'font-family="\'Courier New\',monospace" font-size="13" font-weight="700" '
        f'fill="{P["purple"]}">{tpct}%</text>'
    )

    # Language bars (clip-path animated)
    bx0, by0, bmax = 248, 84, 163
    clip_defs = ""
    bars      = ""
    for i, lang in enumerate(langs):
        by    = by0 + i * 30
        color = lang.get("color") or "#858585"
        bw    = max(4, int(lang["percent"] / 100 * bmax))
        delay = i * 0.10
        uid   = f"L{i}"
        clip_defs += _clip_bar(uid, bx0, by + 15, bw, 5, color, delay=round(delay + 0.5, 2), dur=1.0, rx=2)
        bars += (
            f'<g style="animation:cardUp .45s {delay:.2f}s cubic-bezier(.16,1,.3,1) both">'
            f'<circle cx="{bx0-11}" cy="{by+8}" r="4.5" fill="{color}"/>'
            f'<text x="{bx0}" y="{by+13}" font-family="\'Courier New\',monospace" '
            f'font-size="11" font-weight="600" fill="{P["text"]}">{lang["name"]}</text>'
            f'<text x="{bx0+bmax+8}" y="{by+13}" font-family="\'Courier New\',monospace" '
            f'font-size="10" font-weight="800" fill="{color}">{lang["percent"]}%</text>'
            f'<rect x="{bx0}" y="{by+15}" width="{bmax}" height="5" rx="2" fill="{P["border"]}"/>'
            f'</g>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <style>
    @keyframes cardUp {{ from{{opacity:0;transform:translateY(12px)}} to{{opacity:1;transform:translateY(0)}} }}
  </style>
  <linearGradient id="topLg" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%"   stop-color="{P["purple"]}"/>
    <stop offset="100%" stop-color="{P["pink"]}"/>
  </linearGradient>
  <linearGradient id="bgLg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%"   stop-color="{P["bg2"]}"/>
    <stop offset="100%" stop-color="#090d14"/>
  </linearGradient>
  <clipPath id="lgClip"><rect width="{W}" height="{H}" rx="15"/></clipPath>
  {clip_defs}
</defs>

<rect width="{W}" height="{H}" rx="15" fill="url(#bgLg)"/>
{_dot_bg(W, H, step=22, color=P["purple"])}
<g clip-path="url(#lgClip)">{_scanline(W, H, P["purple"])}</g>
{_animated_border(W, H, P["purple"])}
{_corner_brackets(W, H, size=20, gap=10, color=P["purple"], t=2.3)}
<rect x="0" y="0" width="{W}" height="3.5" fill="url(#topLg)"/>

<text x="32" y="40" font-family="'Courier New',monospace" font-size="9.5" font-weight="700"
  letter-spacing=".14em" fill="{P["dim"]}">// LANGUAGE MATRIX</text>
<line x1="32" y1="50" x2="{W-32}" y2="50" stroke="{P["border"]}" stroke-width="1"/>
<line x1="228" y1="58" x2="228" y2="{H-40}" stroke="{P["border"]}" stroke-width="1"/>
<text x="{CX}" y="68" text-anchor="middle" font-family="'Courier New',monospace"
  font-size="8.5" fill="{P["dim"]}">// SHARE</text>
<text x="{bx0}" y="68" font-family="'Courier New',monospace" font-size="8.5" fill="{P["dim"]}">// BREAKDOWN</text>

{segs}
{bars}

<line x1="32" y1="{H-34}" x2="{W-32}" y2="{H-34}" stroke="{P["border"]}" stroke-width="1"/>
<text x="32" y="{H-16}" font-family="'Courier New',monospace" font-size="8" fill="{P["dim"]}">⟳ {now}</text>

</svg>"""


# ════════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════════
def main():
    print(f"[INFO] Fetching @{USERNAME} …")
    data = fetch_data()
    print(f"[INFO] commits={data['commits']} stars={data['stars']} "
          f"streak={data['cur_streak']}d langs={len(data['langs'])}")

    os.makedirs(OUT_DIR, exist_ok=True)

    outputs = {
        "banner.svg": build_banner_svg(),
        "stats.svg":  build_stats_svg(data),
        "langs.svg":  build_langs_svg(data),
    }
    for name, svg in outputs.items():
        path = os.path.join(OUT_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"[OK]  {path}")

    print("[DONE] All SVGs generated.")

if __name__ == "__main__":
    main()
