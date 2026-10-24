#!/usr/bin/env python3
"""
generate_stats.py  —  GitHub profile SVG generator
═══════════════════════════════════════════════════
Renders five self-hosted, auto-updating SVG cards:
  • assets/banner.svg  — hero banner: live status chip, terminal, and a festival
                         or live-weather scene (see scenes.py)
  • assets/stats.svg   — 12-month contribution activity + full heatmap
  • assets/langs.svg   — language breakdown across owned repos
  • assets/recent.svg  — most recently pushed repositories
  • assets/footer.svg  — the secrets folder + egg hunt

GitHub Actions runs this every 30 minutes and commits the results.
No third-party dependencies: only the standard library.

(There are a few things in here that are not strictly "stats".
 If you're reading this, you're already on the hunt. 🥚)
"""

import json, math, os, random, sys, urllib.request
from datetime import date, datetime, timedelta, timezone
from html import escape

import scenes

USERNAME = os.environ.get("GITHUB_USERNAME", "gurukannan22")
TOKEN    = os.environ.get("GITHUB_TOKEN", "")
OUT_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
IST      = timezone(timedelta(hours=5, minutes=30))

# ── Design tokens ────────────────────────────────────────────────────────────
P = {
    "bg":     "#0A0D12", "panel":  "#0D1117", "raise": "#161B22",
    "border": "#21262D", "line":   "#30363D",
    "text":   "#E6EDF3", "soft":   "#C9D1D9", "muted": "#8B949E", "faint": "#484F58",
    "blue":   "#58A6FF", "indigo": "#8FB4FF", "green": "#3FB950", "amber": "#F0B429",
    "pink":   "#FF7B72",
}
HEAT = ["#161B22", "#0E4429", "#006D32", "#26A641", "#39D353"]
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
# Wishes come in Tamil, Malayalam, Telugu, Hindi and Punjabi: name fonts that cover them.
WISH_FONT = ("'Noto Sans Tamil','Tamil Sangam MN','Nirmala UI','Noto Sans Malayalam','Noto Sans Telugu',"
             "'Noto Sans Devanagari','Noto Sans Gurmukhi'," + SANS)
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"

FORTUNES = [
    "It works on my machine. Shipping the machine.",
    "There are 10 kinds of people: those who read binary and those who don't.",
    "A semicolon walks into a bar; the bar compiles.",
    "Weeks of coding can save you hours of planning.",
    "git push --force is a personality, not a strategy.",
    "The best code is no code. The second best is tested code.",
    "99 little bugs in the code. Patch one. 127 little bugs in the code.",
    "Cache invalidation, naming things, and off-by-one errors.",
    "Kafka never forgets. Neither does git blame.",
    "Today's bug is tomorrow's interview story.",
    "Premature optimization is the root of all evil. Mature optimization is just fun.",
    "Any sufficiently advanced bug is indistinguishable from a feature.",
    "Talk is cheap. Show me the code. — Linus Torvalds",
    "First, solve the problem. Then, write the code. — John Johnson",
    "Strong fundamentals scale better than shortcuts.",
    "NullPointerException: motivation not found. Retrying with coffee...",
    "Deleted code is debugged code.",
    "Read the error message. No, the whole error message.",
    "Commit early, commit often, commit with good messages.",
    "Every senior engineer is a junior who didn't quit.",
    "sudo make me a sandwich. Okay.",
]

QUERY = """query($login:String!){user(login:$login){
  followers{totalCount}
  repositories(first:100 ownerAffiliations:OWNER isFork:false
    orderBy:{field:STARGAZERS direction:DESC}){
    totalCount
    nodes{stargazerCount
      languages(first:10 orderBy:{field:SIZE direction:DESC}){
        edges{size node{name color}}}}}
  recent: repositories(first:6 ownerAffiliations:OWNER isFork:false privacy:PUBLIC
    orderBy:{field:PUSHED_AT direction:DESC}){
    nodes{name description pushedAt stargazerCount primaryLanguage{name color}}}
  contributionsCollection{
    totalCommitContributions totalPullRequestContributions
    totalPullRequestReviewContributions restrictedContributionsCount
    contributionCalendar{totalContributions
      weeks{contributionDays{contributionCount date weekday}}}}}}"""


# ═════════════════════════════════════════════════════════════════════════════
# Data
# ═════════════════════════════════════════════════════════════════════════════
def fetch_data() -> dict:
    if not TOKEN:
        print("⚠  No GITHUB_TOKEN — rendering with placeholder data.", file=sys.stderr)
        return _placeholder()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": f"{USERNAME}-profile-generator"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        print(f"GraphQL error: {payload['errors']}", file=sys.stderr)
        return _placeholder()
    return _parse(payload["data"]["user"])


def _parse(u):
    cc   = u["contributionsCollection"]
    days = _days(cc["contributionCalendar"]["weeks"])
    repos = u["repositories"]["nodes"]
    return {
        "total":     cc["contributionCalendar"]["totalContributions"],
        "commits":   cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs":       cc["totalPullRequestContributions"],
        "reviews":   cc["totalPullRequestReviewContributions"],
        "repos":     u["repositories"]["totalCount"],
        "stars":     sum(r["stargazerCount"] for r in repos),
        "followers": u["followers"]["totalCount"],
        "langs":     _languages(repos),
        "recent":    [r for r in u["recent"]["nodes"] if r["name"].lower() != USERNAME.lower()][:4],
        "weeks":     cc["contributionCalendar"]["weeks"],
        **_activity(days),
    }


def _days(weeks):
    return sorted((d for w in weeks for d in w["contributionDays"]), key=lambda d: d["date"])


def _activity(days):
    """Streaks, active days, busiest day/weekday from the contribution calendar."""
    counts = [d["contributionCount"] for d in days]
    # An empty "today" shouldn't break the current streak — the day isn't over.
    tail = counts[:-1] if counts and counts[-1] == 0 else counts
    cur = 0
    for c in reversed(tail):
        if c == 0:
            break
        cur += 1
    lng = run = 0
    for c in counts:
        run = run + 1 if c else 0
        lng = max(lng, run)

    by_wd = [0] * 7
    for d in days:
        by_wd[d.get("weekday", datetime.fromisoformat(d["date"]).isoweekday() % 7)] += d["contributionCount"]
    best = max(days, key=lambda d: d["contributionCount"]) if days else {"date": "", "contributionCount": 0}
    return {
        "cur_streak": cur, "lng_streak": lng,
        "active":     sum(1 for c in counts if c),
        "n_days":     len(counts),
        "best_day":   best["contributionCount"], "best_date": best["date"],
        "top_wd":     ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][by_wd.index(max(by_wd))],
        "last7":      sum(counts[-7:]),
    }


def _languages(repos):
    acc = {}
    for repo in repos:
        for e in (repo.get("languages") or {}).get("edges", []):
            n, s = e["node"]["name"], e["size"]
            acc.setdefault(n, {"size": 0, "color": e["node"]["color"] or "#8B949E"})["size"] += s
    total = sum(v["size"] for v in acc.values()) or 1
    return sorted(
        ({"name": k, "color": v["color"], "percent": v["size"] / total * 100} for k, v in acc.items()),
        key=lambda x: x["percent"], reverse=True,
    )


def _placeholder():
    rng   = random.Random(7)
    today = datetime.now(IST).date()
    start = today - timedelta(days=364 + (today.isoweekday() % 7))
    weeks, week = [], []
    d = start
    while d <= today:
        busy = 0.78 if d.weekday() < 5 else 0.45
        c = rng.choice([1, 2, 3, 4, 5, 6, 8, 11, 14]) if rng.random() < busy else 0
        week.append({"date": d.isoformat(), "contributionCount": c, "weekday": d.isoweekday() % 7})
        if len(week) == 7:
            weeks.append({"contributionDays": week}); week = []
        d += timedelta(days=1)
    if week:
        weeks.append({"contributionDays": week})
    days = _days(weeks)
    now = datetime.now(timezone.utc)
    return {
        "total": sum(x["contributionCount"] for x in days), "commits": 1042, "prs": 38, "reviews": 12,
        "repos": 18, "stars": 9, "followers": 16,
        "langs": [
            {"name": "Java",       "color": "#b07219", "percent": 41.3},
            {"name": "TypeScript", "color": "#3178c6", "percent": 19.6},
            {"name": "JavaScript", "color": "#f1e05a", "percent": 13.2},
            {"name": "Rust",       "color": "#dea584", "percent": 8.9},
            {"name": "Python",     "color": "#3572A5", "percent": 6.4},
            {"name": "HTML",       "color": "#e34c26", "percent": 5.2},
            {"name": "CSS",        "color": "#663399", "percent": 3.1},
            {"name": "C++",        "color": "#f34b7d", "percent": 2.3},
        ],
        "recent": [
            {"name": "connex-app", "description": None, "stargazerCount": 1,
             "pushedAt": (now - timedelta(hours=3)).isoformat(), "primaryLanguage": {"name": "Rust", "color": "#dea584"}},
            {"name": "veltech-career-archive-bca2nd", "description": None, "stargazerCount": 0,
             "pushedAt": (now - timedelta(days=16)).isoformat(), "primaryLanguage": {"name": "JavaScript", "color": "#f1e05a"}},
            {"name": "studentmanager-cpp", "description": "sample cpp project for student management system", "stargazerCount": 1,
             "pushedAt": (now - timedelta(days=117)).isoformat(), "primaryLanguage": {"name": "C++", "color": "#f34b7d"}},
            {"name": "quill", "description": "Save multiple form profiles and fill any web form instantly. Local-first, no cloud.", "stargazerCount": 0,
             "pushedAt": (now - timedelta(days=118)).isoformat(), "primaryLanguage": {"name": "TypeScript", "color": "#3178c6"}},
        ],
        "weeks": weeks,
        **_activity(days),
    }


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════
def fmt(n):
    return f"{n:,}" if n < 100_000 else f"{n/1000:.0f}k"


def ago(iso):
    s = (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds()
    for unit, size in (("y", 31_536_000), ("mo", 2_592_000), ("d", 86_400), ("h", 3_600), ("m", 60)):
        if s >= size:
            return f"{int(s // size)}{unit} ago"
    return "just now"


def clip(text, n):
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def text_w(s, size, mono=False):
    """Rough text width, good enough to size pills."""
    return len(s) * size * (0.6 if mono else 0.55)


def status_for(now: datetime):
    """The banner's status chip on non-festival days. Changes with the hour and weekday."""
    md, h, wd = (now.month, now.day), now.hour, now.weekday()
    yday = now.timetuple().tm_yday
    special = {
        (3, 14):  "π day · 3.14159 commits",
        (4, 1):   "all tests passing (april fools)",
        (5, 4):   "may the --force be with you",
    }
    if yday == 256:  # Programmer's Day: the 256th day of the year
        return "programmer's day · 0x100", P["amber"]
    if md in special:
        return special[md], P["amber"]
    if 0 <= h < 5:
        return "3 a.m. debugging — send coffee", P["amber"]
    if wd == 4 and h >= 15:
        return "friday: no prod deploys, only vibes", P["amber"]
    if wd >= 5:
        return "weekend · side projects compiling", P["green"]
    if h < 9:
        return "early commit club", P["green"]
    if h < 13:
        return "deep work · building backends", P["green"]
    if h < 18:
        return "shipping features", P["green"]
    if h < 22:
        return "reviewing PRs & teaching", P["green"]
    return "one more commit, then sleep", P["green"]


INVADER = [
    "..X.....X..",
    "...X...X...",
    "..XXXXXXX..",
    ".XX.XXX.XX.",
    "XXXXXXXXXXX",
    "X.XXXXXXX.X",
    "X.X.....X.X",
    "...XX.XX...",
]


def _invader(px=3, color=P["green"]):
    return "".join(
        f'<rect x="{x*px}" y="{y*px}" width="{px}" height="{px}" fill="{color}"/>'
        for y, row in enumerate(INVADER) for x, ch in enumerate(row) if ch == "X"
    )


def _card(W, H, inner):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{SANS}">
{inner}
</svg>"""


def _frame(W, H, cid):
    return (
        f'<clipPath id="{cid}"><rect width="{W}" height="{H}" rx="16"/></clipPath>'
        f'<rect width="{W}" height="{H}" rx="16" fill="{P["panel"]}"/>'
        f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="15.5" fill="none" stroke="{P["border"]}"/>'
    )


# ═════════════════════════════════════════════════════════════════════════════
# BANNER  (1200 × 350)
# ═════════════════════════════════════════════════════════════════════════════
def build_banner_svg(d: dict, now: datetime, festival, wx) -> str:
    W, H = scenes.W, scenes.H
    status, s_col = (scenes.festival_status(festival), P["amber"]) if festival else status_for(now)
    scene = scenes.render(now, festival, wx)
    weather = escape(scenes.weather_label(wx)) if wx else ""
    wish    = scenes.festival_wish(festival) if festival else None
    wish_en = scenes.festival_wish_en(festival) if festival else None
    chip_w = text_w(status, 13, mono=True) + 46
    april = (now.month, now.day) == (4, 1)

    secret  = "never stop shipping"
    binary  = " ".join(f"{ord(c):08b}" for c in secret)
    konami  = "↑ ↑ ↓ ↓ ← → ← → B A"

    term_x, term_y, term_w, term_h = 704, 46, 440, 238
    lines = [
        ("$", "whoami"),
        ("", "guru — backend engineer & tech educator"),
        *((("$", "echo $WISHES"), ("wish", wish_en)) if wish_en else
          (("$", "cat ~/.stack"), ("", "java · spring boot · kafka · react · aws"))),
        ("$", "git log -1 --oneline"),
        ("hash", f"feat: {fmt(d['total'])} contributions in 12 months"),
    ]
    term = ""
    for i, (kind, txt) in enumerate(lines):
        y = term_y + 74 + i * 25
        if kind == "$":
            body = f'<tspan fill="{P["green"]}">❯</tspan> <tspan fill="{P["text"]}">{escape(txt)}</tspan>'
        elif kind == "wish":
            body = f'<tspan fill="{P["amber"]}">{escape(clip(txt, 46))}</tspan>'
        elif kind == "hash":
            body = f'<tspan fill="{P["amber"]}">c0ffee5</tspan> <tspan fill="{P["muted"]}">{escape(txt)}</tspan>'
        else:
            body = f'<tspan fill="{P["muted"]}">{escape(txt)}</tspan>'
        term += f'<text x="{term_x+24}" y="{y}" class="mono t">{body}</text>'
    yl = term_y + 74 + len(lines) * 25
    term += (
        f'<text x="{term_x+24}" y="{yl}" class="mono t">'
        f'<tspan fill="{P["green"]}">❯</tspan> <tspan class="cur" fill="{P["blue"]}">▍</tspan></text>'
        f'<text x="{term_x+50}" y="{yl}" class="mono psst" fill="{P["amber"]}" font-size="13">psst… try hovering the images</text>'
    )

    name_tf = f' transform="translate({64*2 + 450} 0) scale(-1 1)"' if april else ""

    return _card(W, H, f"""
<defs>
  <style>
    .mono {{ font-family:{MONO} }}
    .t    {{ font-size:14px }}
    .cur  {{ animation:blink 1.1s step-end infinite }}
    .psst {{ opacity:0; animation:psst 23s 6s linear infinite }}
    .inv  {{ animation:fly 41s 9s linear infinite; transform:translateX(-60px) }}
    .pulse {{ animation:pulse 1.8s ease-in-out infinite }}
    @keyframes blink {{ 50% {{ opacity:0 }} }}
    @keyframes psst  {{ 0%,91% {{ opacity:0 }} 92%,98% {{ opacity:.9 }} 100% {{ opacity:0 }} }}
    @keyframes fly   {{ 0% {{ transform:translateX(-60px) }} 14%,100% {{ transform:translateX({W+60}px) }} }}
    @keyframes pulse {{ 0%,100% {{ opacity:1 }} 50% {{ opacity:.35 }} }}
    {scene["css"]}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation:none !important }} }}
  </style>
  {scene["defs"]}
  <radialGradient id="glow" cx="12%" cy="0%" r="70%">
    <stop offset="0%" stop-color="{P["blue"]}" stop-opacity=".16"/>
    <stop offset="100%" stop-color="{P["blue"]}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="wishG" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="#FFD43B"/>
    <stop offset="100%" stop-color="#FF8787"/>
  </linearGradient>
  <linearGradient id="nameG" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="#FFFFFF"/>
    <stop offset="100%" stop-color="{P["indigo"]}"/>
  </linearGradient>
  <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
    <path d="M32 0H0V32" fill="none" stroke="#fff" stroke-opacity=".035"/>
  </pattern>
</defs>
{_frame(W, H, "bc")}
<g clip-path="url(#bc)">
  <rect width="{W}" height="{H}" fill="url(#grid)"/>
  <rect width="{W}" height="{H}" fill="url(#glow)"/>
  {scene["back"]}
  <g class="inv" opacity=".85"><g transform="translate(0 14)">{_invader()}</g></g>
</g>

<!-- intro -->
<g>
  <text x="64" y="92" class="mono" font-size="13" letter-spacing="2.4" fill="{P["muted"]}">HELLO, WORLD — I'M</text>
</g>
<g{name_tf}>
  <text x="62" y="162" font-size="72" font-weight="700" letter-spacing="-2" fill="url(#nameG)">Guru Kannan</text>
</g>
<g>
  <text x="64" y="204" font-size="22" font-weight="500" fill="{P["soft"]}">Backend engineer · Java · Spring Boot · Kafka</text>
  {f'<text x="64" y="237" font-size="18" font-weight="600" fill="url(#wishG)" font-family="{WISH_FONT}">{escape(wish)}</text>' if wish else
   f'<text x="64" y="236" font-size="16" fill="{P["muted"]}">Building production systems by day, teaching fundamentals by night.</text>'}
</g>
<g>
  <rect x="64" y="258" width="{chip_w:.0f}" height="30" rx="15" fill="{s_col}" fill-opacity=".1" stroke="{s_col}" stroke-opacity=".45"/>
  <circle cx="84" cy="273" r="4.5" fill="{s_col}" class="pulse"/>
  <text x="98" y="277.5" class="mono" font-size="13" fill="{s_col}">{escape(status)}</text>
</g>

<!-- terminal -->
<g>
  <rect x="{term_x}" y="{term_y}" width="{term_w}" height="{term_h}" rx="12" fill="{P["bg"]}" stroke="{P["line"]}"/>
  <path d="M{term_x} {term_y+38}h{term_w}" stroke="{P["border"]}"/>
  <circle cx="{term_x+22}" cy="{term_y+19}" r="5.5" fill="#FF5F57"/>
  <circle cx="{term_x+40}" cy="{term_y+19}" r="5.5" fill="#FEBC2E"/>
  <circle cx="{term_x+58}" cy="{term_y+19}" r="5.5" fill="#28C840"/>
  <text x="{term_x+term_w/2}" y="{term_y+23.5}" text-anchor="middle" class="mono" font-size="12" fill="{P["faint"]}">guru@github: ~</text>
  <text x="{term_x+term_w-18}" y="{term_y+23.5}" text-anchor="end" class="mono" font-size="12" fill="{P["muted"]}">{weather}</text>
</g>
{term}

<!-- festival / weather props that sit in front -->
<g clip-path="url(#bc)">{scene["front"]}</g>

<!-- the fine print -->
<text x="64" y="{H-12}" class="mono" font-size="8" fill="{P["faint"]}" opacity=".55">{binary}</text>
<text x="{W-56}" y="{H-12}" text-anchor="end" class="mono" font-size="9" fill="{P["faint"]}" opacity=".55">{konami}</text>
""")


# ═════════════════════════════════════════════════════════════════════════════
# ACTIVITY  (1200 × 440)
# ═════════════════════════════════════════════════════════════════════════════
def _level(c, peak):
    if c == 0:
        return 0
    r = c / (peak or 1)
    return 1 if r <= .25 else 2 if r <= .5 else 3 if r <= .75 else 4


def build_stats_svg(d: dict, now: datetime) -> str:
    W, H = 1200, 440
    weeks = d["weeks"][-53:]
    synced = now.strftime("%d %b, %H:%M IST")
    fortune = FORTUNES[now.date().toordinal() % len(FORTUNES)]

    metrics = [
        (fmt(d["total"]), "",  "contributions", "last 12 months"),
        (str(d["cur_streak"]), " days" if d["cur_streak"] != 1 else " day", "current streak",
         "and counting" if d["cur_streak"] else "resets never last"),
        (str(d["lng_streak"]), " days", "longest streak", "personal best"),
        (str(d["active"]), " days", "active days", f'{d["active"] / (d["n_days"] or 1):.0%} of the year'),
        (fmt(d["last7"]), "", "this week", "contributions, last 7 days"),
    ]
    col = (W - 96) / len(metrics)
    m_svg = ""
    for i, (val, unit, label, sub) in enumerate(metrics):
        x = 48 + i * col + (0 if i == 0 else 28)
        if i:
            m_svg += f'<path d="M{48 + i*col:.0f} 86v76" stroke="{P["border"]}"/>'
        m_svg += (
            '<g>'
            f'<text x="{x:.0f}" y="128" font-size="40" font-weight="700" letter-spacing="-1" fill="{P["text"]}">{val}'
            f'<tspan font-size="18" font-weight="500" fill="{P["muted"]}" letter-spacing="0">{unit}</tspan></text>'
            f'<text x="{x:.0f}" y="152" font-size="14" font-weight="600" fill="{P["soft"]}">{label}</text>'
            f'<text x="{x:.0f}" y="171" font-size="12" fill="{P["muted"]}">{sub}</text></g>'
        )

    # Heatmap
    x0, y0, cell, step = 96, 232, 15, 19
    peak = max((c["contributionCount"] for w in weeks for c in w["contributionDays"]), default=1)
    cells, months, last_m = "", "", None
    for wi, w in enumerate(weeks):
        first = date.fromisoformat(w["contributionDays"][0]["date"])
        if first.month != last_m:
            if last_m is not None and wi < len(weeks) - 2:
                months += f'<text x="{x0 + wi*step}" y="{y0-12}" font-size="12" fill="{P["muted"]}">{first.strftime("%b")}</text>'
            last_m = first.month
        for c in w["contributionDays"]:
            wd = c.get("weekday", date.fromisoformat(c["date"]).isoweekday() % 7)
            cx, cy = x0 + wi * step, y0 + wd * step
            lv = _level(c["contributionCount"], peak)
            best = c["date"] == d["best_date"] and c["contributionCount"] > 0
            stroke = f' stroke="{P["amber"]}" stroke-width="1.5"' if best else ""
            cells += (
                f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" rx="3.5" fill="{HEAT[lv]}"{stroke} '
                '/>'
            )
    wd_labels = "".join(
        f'<text x="{x0-14}" y="{y0 + i*step + 11.5}" text-anchor="end" font-size="12" fill="{P["muted"]}">{n}</text>'
        for i, n in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    legend = "".join(
        f'<rect x="{x0 + 40 + i*19}" y="{H-50}" width="15" height="15" rx="3.5" fill="{c}"/>' for i, c in enumerate(HEAT)
    )

    return _card(W, H, f"""
<defs>
  <style>
    .mono {{ font-family:{MONO} }}
  </style>
</defs>
{_frame(W, H, "sc")}
<text x="48" y="54" class="mono" font-size="13" letter-spacing="2.4" fill="{P["muted"]}">CONTRIBUTION ACTIVITY</text>
<text x="{W-48}" y="54" text-anchor="end" font-size="13" fill="{P["muted"]}">most active on {d["top_wd"]}s · <tspan fill="{P["faint"]}">synced {synced}</tspan></text>
<path d="M48 72H{W-48}" stroke="{P["border"]}"/>
{m_svg}
<path d="M48 196H{W-48}" stroke="{P["border"]}"/>
{months}{wd_labels}{cells}
<text x="{x0}" y="{H-38}" font-size="12" fill="{P["muted"]}">Less</text>{legend}
<text x="{x0 + 40 + 5*19 + 6}" y="{H-38}" font-size="12" fill="{P["muted"]}">More</text>
<rect x="{x0 + 180}" y="{H-50}" width="15" height="15" rx="3.5" fill="none" stroke="{P["amber"]}" stroke-width="1.5"/>
<text x="{x0 + 203}" y="{H-38}" font-size="12" fill="{P["muted"]}">best day · {d["best_day"]}</text>
<text x="{W-48}" y="{H-38}" text-anchor="end" class="mono" font-size="12" fill="{P["faint"]}">$ fortune → <tspan fill="{P["muted"]}">{escape(fortune)}</tspan></text>
""")


# ═════════════════════════════════════════════════════════════════════════════
# LANGUAGES  (590 × 320)
# ═════════════════════════════════════════════════════════════════════════════
def build_langs_svg(d: dict) -> str:
    W, H = 590, 320
    langs = d["langs"][:8]
    shown = sum(l["percent"] for l in langs) or 1
    bx, bw = 40, W - 80
    bar, x = "", bx
    for l in langs:
        w = l["percent"] / shown * bw
        bar += f'<rect x="{x:.1f}" y="84" width="{max(w - 2, 1):.1f}" height="10" fill="{l["color"] or P["muted"]}"/>'
        x += w
    rows = ""
    for i, l in enumerate(langs):
        cx = 40 + (i // 4) * 265
        cy = 140 + (i % 4) * 38
        rows += (
            '<g>'
            f'<circle cx="{cx+6}" cy="{cy-5}" r="6" fill="{l["color"] or P["muted"]}"/>'
            f'<text x="{cx+22}" y="{cy}" font-size="15" font-weight="500" fill="{P["text"]}">{escape(l["name"])}</text>'
            f'<text x="{cx+240}" y="{cy}" text-anchor="end" class="mono" font-size="13" fill="{P["muted"]}">{l["percent"]:.1f}%</text></g>'
        )
    return _card(W, H, f"""
<defs>
  <style>
    .mono {{ font-family:{MONO} }}
  </style>
  <clipPath id="barc"><rect x="{bx}" y="84" width="{bw}" height="10" rx="5"/></clipPath>
</defs>
{_frame(W, H, "lc")}
<text x="40" y="54" class="mono" font-size="13" letter-spacing="2.4" fill="{P["muted"]}">LANGUAGES</text>
<text x="{W-40}" y="54" text-anchor="end" font-size="13" fill="{P["faint"]}">by code size · {d["repos"]} repos</text>
<g clip-path="url(#barc)">{bar}</g>
{rows}
<text x="40" y="{H-26}" font-size="12" fill="{P["faint"]}">★ {d["stars"]} stars · {d["followers"]} followers · {d["prs"]} PRs &amp; {d["reviews"]} reviews this year</text>
""")


# ═════════════════════════════════════════════════════════════════════════════
# RECENTLY SHIPPED  (590 × 320)
# ═════════════════════════════════════════════════════════════════════════════
def build_recent_svg(d: dict) -> str:
    W, H = 590, 320
    rows = ""
    for i, r in enumerate(d["recent"]):
        y = 104 + i * 52
        lang = r.get("primaryLanguage") or {"name": "Markdown", "color": P["muted"]}
        desc = r.get("description") or ""
        sub = lang["name"] + (f" · {desc}" if desc else "")
        rows += (
            '<g>'
            f'<circle cx="46" cy="{y-5}" r="5" fill="{lang["color"] or P["muted"]}"/>'
            f'<text x="62" y="{y}" font-size="15" font-weight="600" fill="{P["text"]}">{escape(clip(r["name"], 34))}</text>'
            f'<text x="{W-40}" y="{y}" text-anchor="end" class="mono" font-size="12" fill="{P["green"] if i == 0 else P["muted"]}">{ago(r["pushedAt"])}</text>'
            f'<text x="62" y="{y+20}" font-size="12.5" fill="{P["muted"]}">{escape(clip(sub, 68))}</text></g>'
        )
    return _card(W, H, f"""
<defs>
  <style>
    .mono {{ font-family:{MONO} }}
  </style>
</defs>
{_frame(W, H, "rc")}
<text x="40" y="54" class="mono" font-size="13" letter-spacing="2.4" fill="{P["muted"]}">RECENTLY SHIPPED</text>
<text x="{W-40}" y="54" text-anchor="end" font-size="13" fill="{P["faint"]}">last push wins</text>
<path d="M40 72H{W-40}" stroke="{P["border"]}"/>
{rows}
""")


# ═════════════════════════════════════════════════════════════════════════════
# FOOTER  (1200 × 260) — the secrets folder + egg hunt
# ═════════════════════════════════════════════════════════════════════════════
HINTS = [
    "Real engineers read the source.",
    "Point at things. The images talk back.",
    "What is my latest commit hash made of?",
    "Watch the top of the banner for a minute.",
    "The faint 1s and 0s under the banner say something.",
    "A famous cheat code hides in the banner's corner.",
    "No festival today? Check the sky over the terminal.",
    "Come back near Diwali, Pongal, Holi or Eid.",
    "The activity card has a new fortune every day.",
    "You're looking at it: my secrets folder.",
    "Free source code is never free. Click this card.",
    "Switch GitHub between light and dark themes.",
]


def build_footer_svg(now: datetime) -> str:
    W, H = 1200, 260
    tx, ty, tw, th = 32, 32, 680, 196
    today = now.date().toordinal() % len(HINTS)
    lines = [
        ("$", "ls ~/secrets"),
        ("", "free-premium-source-code.zip\u00a0\u00a0\u00a0bugs/\u00a0\u00a0\u00a0blame.log"),
        ("$", "sudo rm -rf ~/secrets/bugs"),
        ("", "rm: cannot remove 'bugs': they are features now"),
        ("$", "git blame production.log"),
        ("", "fatal: it was you. it is always you."),
    ]
    term = ""
    for i, (kind, txt) in enumerate(lines):
        body = (f'<tspan fill="{P["green"]}">❯</tspan> <tspan fill="{P["text"]}">{escape(txt)}</tspan>'
                if kind == "$" else f'<tspan fill="{P["muted"]}">{escape(txt)}</tspan>')
        term += f'<text x="{tx+24}" y="{ty+64 + i*22}" class="mono" font-size="14">{body}</text>'

    eggs = "".join(
        f'<ellipse cx="{752 + i*30}" cy="150" rx="8" ry="10.5" '
        + (f'fill="{P["amber"]}"/>' if i == today else f'fill="none" stroke="{P["line"]}" stroke-width="1.5"/>')
        for i in range(len(HINTS))
    )
    return _card(W, H, f"""
<defs>
  <style>
    .mono {{ font-family:{MONO} }}
    .glow {{ animation:glow 2.4s ease-in-out infinite }}
    @keyframes glow {{ 50% {{ opacity:.45 }} }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation:none !important }} }}
  </style>
</defs>
{_frame(W, H, "fc")}
<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="12" fill="{P["bg"]}" stroke="{P["line"]}"/>
<path d="M{tx} {ty+36}h{tw}" stroke="{P["border"]}"/>
<circle cx="{tx+22}" cy="{ty+18}" r="5.5" fill="#FF5F57"/>
<circle cx="{tx+40}" cy="{ty+18}" r="5.5" fill="#FEBC2E"/>
<circle cx="{tx+58}" cy="{ty+18}" r="5.5" fill="#28C840"/>
<text x="{tx+tw/2}" y="{ty+22.5}" text-anchor="middle" class="mono" font-size="12" fill="{P["faint"]}">~/secrets — do not open</text>
{term}

<text x="752" y="62" class="mono" font-size="13" letter-spacing="2.4" fill="{P["muted"]}">EGG HUNT</text>
<text x="752" y="116" font-size="48" font-weight="700" letter-spacing="-1" fill="{P["text"]}">12<tspan font-size="16" font-weight="400" letter-spacing="0" fill="{P["muted"]}" dx="10">eggs hidden on this page</tspan></text>
<g class="glow">{eggs}</g>
<text x="752" y="196" class="mono" font-size="12" fill="{P["amber"]}">today's hint · #{today + 1}</text>
<text x="752" y="220" font-size="14" fill="{P["soft"]}">{escape(HINTS[today])}</text>
""")


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
def main():
    print(f"[INFO] Fetching @{USERNAME} …")
    data = fetch_data()
    # PROFILE_DATE=2026-11-05T21:00 previews a given moment (festivals, chips).
    now = (datetime.fromisoformat(os.environ["PROFILE_DATE"]).replace(tzinfo=IST)
           if os.environ.get("PROFILE_DATE") else datetime.now(IST))
    festival, wx = scenes.current_festival(now.date()), scenes.fetch_weather()
    print(f"[INFO] festival={festival and festival['key']} weather={wx and wx['desc']}")
    print(f"[INFO] total={data['total']} streak={data['cur_streak']}d "
          f"active={data['active']}/{data['n_days']} langs={len(data['langs'])}")

    os.makedirs(OUT_DIR, exist_ok=True)
    outputs = {
        "banner.svg": build_banner_svg(data, now, festival, wx),
        "stats.svg":  build_stats_svg(data, now),
        "langs.svg":  build_langs_svg(data),
        "recent.svg": build_recent_svg(data),
        "footer.svg": build_footer_svg(now),
    }
    for name, svg in outputs.items():
        path = os.path.join(OUT_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"[OK]  {path}")


if __name__ == "__main__":
    main()
