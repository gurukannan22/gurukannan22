"""
scenes.py  —  festival & weather scenes for the profile banner
═══════════════════════════════════════════════════════════════
Picks what the banner should look like right now:

  1. A festival scene, if one is coming up. Each festival starts showing a few
     days early (up to 10 for the big ones) with a countdown, so the banner
     builds up to the day instead of appearing on it.
  2. Otherwise, the live weather in WEATHER_CITY (Open-Meteo, no API key).

Indian festival dates move every year with the lunar calendar, so they come
from Google's public Indian-holidays calendar, with a built-in fallback table.

Every scene draws into a 1200 × 350 banner. The terminal covers x 704–1144,
y 46–284; the column x 570–690 and the strip y 296–334 are free for props.
"""

import json, math, os, random, re, sys, urllib.request
from datetime import date, datetime, timedelta

W, H = 1200, 350
COL = 630  # centre of the free column between the intro text and the terminal

HOLIDAY_ICS = ("https://calendar.google.com/calendar/ical/"
               "en.indian%23holiday%40group.v.calendar.google.com/public/basic.ics")
CITY = os.environ.get("WEATHER_CITY", "Chennai")
LAT  = float(os.environ.get("WEATHER_LAT", "13.0827"))
LON  = float(os.environ.get("WEATHER_LON", "80.2707"))


# ═════════════════════════════════════════════════════════════════════════════
# Festival calendar
# ═════════════════════════════════════════════════════════════════════════════
# key: (title, scene, lead days, days after, "MM-DD" if fixed else ICS name,
#       countdown flavour, greeting on the day)
FESTIVALS = {
    "diwali":      ("Diwali", "diwali", 10, 1, "diwali/deepavali",
                    "stocking up on diyas", "happy diwali — lamps lit, builds green"),
    "pongal":      ("Pongal", "pongal", 7, 2, "pongal",
                    "sugarcane secured", "pongalo pongal! — kites up, bugs down"),
    "holi":        ("Holi", "holi", 7, 1, "holi",
                    "colours loaded", "happy holi — merging every colour into main"),
    "onam":        ("Onam", "onam", 7, 1, "onam",
                    "pookalam in progress", "happy onam — pookalam compiled"),
    "ganesh":      ("Ganesh Chaturthi", "ganesh", 7, 1, "ganesh chaturthi",
                    "pandal going up", "ganpati bappa morya — obstacles removed"),
    "dussehra":    ("Dussehra", "navratri", 10, 0, "dussehra",
                    "navratri nights on", "happy dussehra — good beats evil (and bugs)"),
    "eid":         ("Eid", "eid", 7, 1, "ramzan id",
                    "moon-watch on", "eid mubarak — peace & clean builds"),
    "bakrid":      ("Bakrid", "eid", 5, 1, "bakrid",
                    "lanterns up", "eid al-adha mubarak"),
    "rakhi":       ("Raksha Bandhan", "petals", 3, 0, "raksha bandhan",
                    "rakhis ready", "happy raksha bandhan"),
    "janmashtami": ("Janmashtami", "petals", 3, 0, "janmashtami",
                    "butter pots hung", "happy janmashtami"),
    "ugadi":       ("Ugadi", "toran", 3, 0, "ugadi",
                    "mango leaves up", "happy ugadi — fresh year, fresh branch"),
    "shivaratri":  ("Maha Shivaratri", "night", 2, 0, "maha shivaratri",
                    "all-nighter planned", "om namah shivaya — all-night build"),
    "gurpurab":    ("Guru Nanak Jayanti", "diyas", 2, 0, "guru nanak jayanti",
                    "lamps ready", "happy gurpurab"),
    "puthandu":    ("Tamil New Year", "toran", 3, 0, "04-14",
                    "kolam drawn", "puthandu vazhthukal!"),
    "republic":    ("Republic Day", "tricolor", 3, 0, "01-26",
                    "flags up", "happy republic day — jai hind"),
    "independence":("Independence Day", "tricolor", 4, 0, "08-15",
                    "flags up", "happy independence day — jai hind"),
    "gandhi":      ("Gandhi Jayanti", "tricolor", 1, 0, "10-02",
                    "be the change", "be the change you wish to see in the codebase"),
    "christmas":   ("Christmas", "christmas", 10, 1, "12-25",
                    "decking the halls", "merry christmas — merging gifts into main"),
    "newyear":     ("New Year", "newyear", 4, 1, "01-01",
                    "final sprint of the year", "happy new year — new year, new bugs"),
    "halloween":   ("Halloween", "halloween", 7, 0, "10-31",
                    "the spiders are moving in", "happy halloween — haunted by legacy code"),
    "valentine":   ("Valentine's Day", "hearts", 1, 0, "02-14",
                    "git commit -m \"♥\"", "in a committed relationship (with git)"),
}

# Used only if the holiday calendar can't be fetched.
FALLBACK_DATES = {
    "diwali/deepavali": ["2026-11-08", "2027-10-29"], "pongal": ["2026-01-14", "2027-01-15"],
    "holi": ["2026-03-04", "2027-03-22"], "onam": ["2026-08-26", "2027-09-12"],
    "ganesh chaturthi": ["2026-09-14", "2027-09-04"], "dussehra": ["2026-10-20", "2027-10-09"],
    "ramzan id": ["2026-03-21", "2027-03-10"], "bakrid": ["2026-05-28", "2027-05-17"],
    "raksha bandhan": ["2026-08-28", "2027-08-17"], "janmashtami": ["2026-09-04", "2027-08-25"],
    "ugadi": ["2026-03-19", "2027-04-07"], "maha shivaratri": ["2026-02-15", "2027-03-06"],
    "guru nanak jayanti": ["2026-11-24", "2027-11-14"],
}


def _holiday_dates() -> dict:
    """{lowercased holiday name: [date, ...]} from the public calendar."""
    try:
        req = urllib.request.Request(HOLIDAY_ICS, headers={"User-Agent": "profile-generator"})
        with urllib.request.urlopen(req, timeout=20) as r:
            ics = r.read().decode("utf-8", "replace").replace("\r\n ", "")
    except Exception as e:  # network hiccup: fall back to the built-in table
        print(f"⚠  Holiday calendar unavailable ({e}); using fallback dates.", file=sys.stderr)
        return {k: [date.fromisoformat(v) for v in vs] for k, vs in FALLBACK_DATES.items()}
    out = {}
    for block in ics.split("BEGIN:VEVENT")[1:]:
        d = re.search(r"DTSTART;VALUE=DATE:(\d{8})", block)
        s = re.search(r"SUMMARY:([^\r\n]*)", block)
        if d and s:
            name = s.group(1).lower().replace(" (tentative)", "").strip()
            out.setdefault(name, []).append(datetime.strptime(d.group(1), "%Y%m%d").date())
    return out


def current_festival(today: date, holidays: dict | None = None):
    """The festival whose window covers today, nearest date first; or None."""
    holidays = _holiday_dates() if holidays is None else holidays
    best = None
    for key, (title, scene, lead, after, when, prep, greet) in FESTIVALS.items():
        if re.fullmatch(r"\d\d-\d\d", when):
            m, d = map(int, when.split("-"))
            dates = [date(y, m, d) for y in (today.year - 1, today.year, today.year + 1)]
        else:
            dates = holidays.get(when, [])
        for day in dates:
            left = (day - today).days
            if -after <= left <= lead:
                rank = (left < 0, abs(left))  # on/before the day beats the day after
                if best is None or rank < best[0]:
                    best = (rank, {"key": key, "title": title, "scene": scene,
                                   "days": left, "prep": prep, "greet": greet})
    return best[1] if best else None


def festival_status(f) -> str:
    n, t = f["days"], f["title"].lower()
    if n == 0:
        return f["greet"]
    if n < 0:
        return f"still celebrating {t}"
    return f"{t} {'tomorrow' if n == 1 else f'in {n} days'} · {f['prep']}"


# ═════════════════════════════════════════════════════════════════════════════
# Weather
# ═════════════════════════════════════════════════════════════════════════════
WMO = {  # code → (description, scene)
    0: ("clear sky", "clear"), 1: ("mostly clear", "clear"), 2: ("partly cloudy", "partly"),
    3: ("overcast", "cloudy"), 45: ("foggy", "fog"), 48: ("foggy", "fog"),
    **{c: ("drizzle", "drizzle") for c in (51, 53, 55, 56, 57)},
    **{c: ("rain", "rain") for c in (61, 63, 66, 80, 81)},
    **{c: ("heavy rain", "rain") for c in (65, 67, 82)},
    **{c: ("snow", "snow") for c in (71, 73, 75, 77, 85, 86)},
    **{c: ("thunderstorm", "storm") for c in (95, 96, 99)},
}
GLYPH = {"clear": "☀", "partly": "⛅", "cloudy": "☁", "fog": "≋", "drizzle": "☂",
         "rain": "☂", "snow": "❄", "storm": "ϟ"}


def fetch_weather():
    """{'city', 'temp', 'desc', 'scene', 'day'} or None if the API is unreachable."""
    override = os.environ.get("PROFILE_WEATHER")  # "code[,is_day]" for previews
    try:
        if override:
            code, *rest = override.split(",")
            cur = {"weather_code": int(code), "is_day": int(rest[0]) if rest else 1, "temperature_2m": 29}
        else:
            url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
                   "&current=temperature_2m,weather_code,is_day&timezone=auto")
            with urllib.request.urlopen(url, timeout=20) as r:
                cur = json.load(r)["current"]
    except Exception as e:
        print(f"⚠  Weather unavailable ({e}).", file=sys.stderr)
        return None
    desc, scene = WMO.get(cur["weather_code"], ("clear sky", "clear"))
    return {"city": CITY, "temp": round(cur["temperature_2m"]), "desc": desc,
            "scene": scene, "day": bool(cur["is_day"])}


def weather_label(wx) -> str:
    glyph = GLYPH[wx["scene"]] if wx["day"] or wx["scene"] != "clear" else "☾"
    return f"{glyph} {wx['temp']}°C · {wx['city'].lower()}"


# ═════════════════════════════════════════════════════════════════════════════
# Drawing primitives
# ═════════════════════════════════════════════════════════════════════════════
# CSS transforms override the transform attribute, so every animated element is
# wrapped: an outer <g transform="translate(...)"> places it, an inner
# <g class="fx-..."> animates it. Negative delays mean the scene is already in
# motion when the image loads.
CSS = """
.fx-fall    { animation:fx-fall linear infinite }
.fx-rise    { animation:fx-rise linear infinite }
.fx-drift   { animation:fx-drift linear infinite }
.fx-twinkle { animation:fx-twinkle ease-in-out infinite }
.fx-pulse   { animation:fx-pulse ease-in-out infinite alternate }
.fx-bob     { animation:fx-bob ease-in-out infinite alternate }
.fx-sway    { transform-box:fill-box; transform-origin:50% 0; animation:fx-sway ease-in-out infinite alternate }
.fx-flicker { transform-box:fill-box; transform-origin:50% 100%; animation:fx-flicker ease-in-out infinite alternate }
.fx-burst   { transform-box:fill-box; transform-origin:center; animation:fx-burst ease-out infinite }
.fx-spin    { transform-box:fill-box; transform-origin:center; animation:fx-spin linear infinite }
.fx-flap    { transform-box:fill-box; transform-origin:center; animation:fx-flap .28s ease-in-out infinite alternate }
.fx-wave    { transform-box:fill-box; transform-origin:0 50%; animation:fx-wave 1.6s ease-in-out infinite alternate }
.fx-flash   { animation:fx-flash 7s linear infinite }
@keyframes fx-fall    { from { transform:translate(0,-40px) rotate(0) } to { transform:translate(var(--dx,0px),390px) rotate(var(--rot,0deg)) } }
@keyframes fx-rise    { 0% { transform:translateY(0); opacity:0 } 15% { opacity:.9 } 100% { transform:translate(var(--dx,0px),-360px); opacity:0 } }
@keyframes fx-drift   { from { transform:translateX(-300px) } to { transform:translateX(1500px) } }
@keyframes fx-twinkle { 50% { opacity:.12 } }
@keyframes fx-pulse   { from { opacity:.35 } to { opacity:1 } }
@keyframes fx-bob     { from { transform:translateY(-7px) } to { transform:translateY(7px) } }
@keyframes fx-sway    { from { transform:rotate(var(--a,-6deg)) } to { transform:rotate(calc(var(--a,-6deg) * -1)) } }
@keyframes fx-flicker { 0% { transform:scale(1,1); opacity:1 } 50% { transform:scale(.86,1.14) } 100% { transform:scale(1.08,.9); opacity:.82 } }
@keyframes fx-burst   { 0% { transform:scale(.05); opacity:0 } 10% { opacity:1 } 65% { opacity:.9 } 100% { transform:scale(1); opacity:0 } }
@keyframes fx-spin    { to { transform:rotate(360deg) } }
@keyframes fx-flap    { from { transform:scaleY(1) } to { transform:scaleY(.25) } }
@keyframes fx-wave    { from { transform:skewY(-4deg) scaleX(.97) } to { transform:skewY(4deg) scaleX(1) } }
@keyframes fx-flash   { 0%,58%,61%,64%,100% { opacity:0 } 59%,62.5% { opacity:1 } }
"""


def _anim(cls, dur, delay=0.0, extra=""):
    return f'class="{cls}" style="animation-duration:{dur:.2f}s;animation-delay:{-delay:.2f}s;{extra}"'


def falling(rng, n, shape, colors, dur=(6, 12), dx=(-60, 60), rot=360, xs=(0, W)):
    out = ""
    for _ in range(n):
        d = rng.uniform(*dur)
        out += (f'<g transform="translate({rng.uniform(*xs):.0f} 0)"><g '
                f'{_anim("fx-fall", d, rng.uniform(0, d), f"--dx:{rng.uniform(*dx):.0f}px;--rot:{rng.uniform(-rot, rot):.0f}deg")}>'
                f'{shape(rng, rng.choice(colors))}</g></g>')
    return out


def rising(rng, n, shape, colors, dur=(5, 9), xs=(0, W), y=(H, H + 20)):
    out = ""
    for _ in range(n):
        d = rng.uniform(*dur)
        out += (f'<g transform="translate({rng.uniform(*xs):.0f} {rng.uniform(*y):.0f})"><g '
                f'{_anim("fx-rise", d, rng.uniform(0, d), f"--dx:{rng.uniform(-40, 40):.0f}px")}>'
                f'{shape(rng, rng.choice(colors))}</g></g>')
    return out


def petal(rng, c):
    return f'<ellipse rx="{rng.uniform(3, 5):.1f}" ry="{rng.uniform(6, 9):.1f}" fill="{c}" opacity=".9"/>'


def confetti(rng, c):
    return f'<rect x="-3" y="-5" width="{rng.uniform(4, 7):.1f}" height="{rng.uniform(8, 12):.1f}" rx="1" fill="{c}"/>'


def flake(rng, c):
    return f'<circle r="{rng.uniform(1.2, 3.2):.1f}" fill="{c}" opacity="{rng.uniform(.5, .95):.2f}"/>'


def heart(rng, c):
    s = rng.uniform(.7, 1.4)
    return (f'<path transform="scale({s:.2f})" d="M0 6 C-10 -2 -8 -12 0 -6 C8 -12 10 -2 0 6Z" '
            f'fill="{c}" opacity=".85"/>')


def stars(rng, n, area=(0, W, 0, 150), color="#FFFFFF"):
    x0, x1, y0, y1 = area
    return "".join(
        f'<circle cx="{rng.uniform(x0, x1):.0f}" cy="{rng.uniform(y0, y1):.0f}" r="{rng.uniform(.7, 1.9):.1f}" '
        f'fill="{color}" {_anim("fx-twinkle", rng.uniform(1.5, 4), rng.uniform(0, 4))}/>'
        for _ in range(n)
    )


def fireworks(rng, n, colors, area=(330, 690, 30, 90)):
    x0, x1, y0, y1 = area
    out = ""
    for _ in range(n):
        c, R, d = rng.choice(colors), rng.uniform(30, 52), rng.uniform(2.2, 3.4)
        rays = "".join(
            f'<line x1="{math.cos(a)*7:.1f}" y1="{math.sin(a)*7:.1f}" x2="{math.cos(a)*R:.1f}" y2="{math.sin(a)*R:.1f}" '
            f'stroke="{c}" stroke-width="2.4" stroke-linecap="round"/>'
            f'<circle cx="{math.cos(a)*(R+5):.1f}" cy="{math.sin(a)*(R+5):.1f}" r="2.6" fill="{c}"/>'
            for a in (i * math.tau / 16 for i in range(16))
        )
        out += (f'<g transform="translate({rng.uniform(x0, x1):.0f} {rng.uniform(y0, y1):.0f})">'
                f'<g {_anim("fx-burst", d, rng.uniform(0, d))}><circle r="{R*.7:.0f}" fill="{c}" opacity=".14"/>{rays}</g></g>')
    return out


def diyas(rng, xs, y=318):
    out = ""
    for x in xs:
        out += (
            f'<g transform="translate({x} {y})">'
            f'<circle cy="-14" r="26" fill="url(#fx-diyaGlow)" {_anim("fx-pulse", rng.uniform(.8, 1.6), rng.uniform(0, 1))}/>'
            f'<path d="M-17 -2 Q0 16 17 -2Z" fill="#B4400E"/><ellipse cy="-2" rx="17" ry="4" fill="#E8691B"/>'
            f'<path d="M-6 9 h12" stroke="#7C2D12" stroke-width="2"/>'
            f'<g {_anim("fx-flicker", rng.uniform(.35, .7), rng.uniform(0, 1))}>'
            f'<path d="M0 -26 C6 -17 7 -10 0 -3 C-7 -10 -6 -17 0 -26Z" fill="url(#fx-flame)"/></g></g>'
        )
    return out


DIYA_DEFS = """
<radialGradient id="fx-diyaGlow"><stop offset="0" stop-color="#FFB020" stop-opacity=".6"/><stop offset="1" stop-color="#FFB020" stop-opacity="0"/></radialGradient>
<linearGradient id="fx-flame" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#FF6A00"/><stop offset=".55" stop-color="#FFB020"/><stop offset="1" stop-color="#FFF6C2"/></linearGradient>
"""


def toran(rng):
    """Marigold garland with mango leaves along the top edge."""
    out, step = "", 100
    for x0 in range(0, W, step):
        flowers = ""
        for i in range(10):
            t = (i + .5) / 10
            x, y = x0 + t * step, 6 + 4 * 30 * t * (1 - t)
            flowers += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{"#FF9F1C" if i % 2 else "#FFD60A"}"/>'
        leaves = "".join(
            f'<ellipse cx="{x0}" cy="14" rx="4.5" ry="13" fill="#2F9E44" transform="rotate({a} {x0} 2)"/>'
            for a in (-22, 0, 22)
        )
        out += (f'<g {_anim("fx-sway", rng.uniform(2.5, 4), rng.uniform(0, 3), "--a:-2deg")}>{flowers}</g>{leaves}'
                f'<circle cx="{x0}" cy="4" r="4" fill="#E03131"/>')
    return out


def kite(rng, x, y, s, c1, c2):
    tail = " ".join(f"Q{(-1)**i*8} {s*1.1 + i*14 + 7} 0 {s*1.1 + (i+1)*14}" for i in range(4))
    bows = "".join(f'<path d="M-5 {s*1.1 + i*14 + 10} l10 -4 v8z" fill="{c2}"/>' for i in range(1, 4))
    return (
        f'<g transform="translate({x} {y})"><g {_anim("fx-bob", rng.uniform(1.6, 2.6), rng.uniform(0, 2))}>'
        f'<g {_anim("fx-sway", rng.uniform(1.8, 3), rng.uniform(0, 2), "--a:-9deg")}>'
        f'<path d="M0 {s*1.1} L-220 400" stroke="#C9D1D9" stroke-opacity=".25" fill="none"/>'
        f'<path d="M0 {-s} L{s*.78} 0 L0 {s*1.1} L{-s*.78} 0Z" fill="{c1}"/>'
        f'<path d="M0 {-s} L{s*.78} 0 L0 0Z" fill="{c2}" opacity=".85"/>'
        f'<path d="M0 {-s} V{s*1.1} M{-s*.78} 0 H{s*.78}" stroke="#fff" stroke-opacity=".5"/>'
        f'<path d="M0 {s*1.1} {tail}" stroke="{c2}" stroke-width="1.5" fill="none"/>{bows}</g></g></g>'
    )


def pookalam(cx, cy, R, dur=70):
    rings = [(1.0, 28, "#2B8A3E", .13), (.82, 24, "#FD7E14", .13), (.66, 20, "#FFD43B", .14),
             (.5, 16, "#E03131", .15), (.35, 12, "#9C36B5", .17), (.22, 10, "#F8F9FA", .2)]
    out = ""
    for f, n, c, w in rings:
        r = R * f
        out += "".join(
            f'<ellipse cy="{-r*.78:.1f}" rx="{r*w*1.6:.1f}" ry="{r*.24:.1f}" fill="{c}" transform="rotate({i*360/n:.1f})"/>'
            for i in range(n)
        )
    out += f'<circle r="{R*.12:.1f}" fill="#FFD43B"/><circle r="{R*.05:.1f}" fill="#E03131"/>'
    return f'<g transform="translate({cx} {cy})"><g {_anim("fx-spin", dur)}>{out}</g></g>'


def lantern(rng, x, length, c="#FFB020"):
    return (
        f'<g {_anim("fx-sway", rng.uniform(2.2, 3.4), rng.uniform(0, 3), "--a:-5deg")}>'
        f'<path d="M{x} 0 V{length}" stroke="#C9D1D9" stroke-opacity=".5"/>'
        f'<circle cx="{x}" cy="{length+24}" r="30" fill="{c}" opacity=".14"/>'
        f'<path d="M{x-9} {length} h18 l6 9 h-30z" fill="#C08A2E"/>'
        f'<rect x="{x-13}" y="{length+9}" width="26" height="30" rx="9" fill="{c}" opacity=".9"/>'
        f'<path d="M{x} {length+9} v30 M{x-6} {length+10} q-4 14 0 28 M{x+6} {length+10} q4 14 0 28" stroke="#8A5A12" stroke-opacity=".6" fill="none"/>'
        f'<path d="M{x-15} {length+39} h30 l-6 7 h-18z" fill="#C08A2E"/>'
        f'<path d="M{x} {length+46} v10" stroke="{c}" stroke-width="2"/></g>'
    )


def moon(cx, cy, r, crescent=True, color="#FFE8A3", mid="fx-moon"):
    mask = (f'<mask id="{mid}"><rect width="{W}" height="{H}" fill="#fff"/>'
            f'<circle cx="{cx + r*.45:.0f}" cy="{cy - r*.25:.0f}" r="{r*.9:.0f}" fill="#000"/></mask>') if crescent else ""
    m = f' mask="url(#{mid})"' if crescent else ""
    return (f'{mask}<circle cx="{cx}" cy="{cy}" r="{r*2.4:.0f}" fill="url(#fx-moonGlow)"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"{m}/>')


MOON_DEFS = """<radialGradient id="fx-moonGlow"><stop offset="0" stop-color="#FFE8A3" stop-opacity=".35"/><stop offset="1" stop-color="#FFE8A3" stop-opacity="0"/></radialGradient>"""


def cloud(rng, y, s, color, opacity, dur):
    puffs = "".join(f'<circle cx="{cx*s:.0f}" cy="{cy*s:.0f}" r="{r*s:.0f}"/>'
                    for cx, cy, r in ((0, 0, 22), (24, -10, 28), (52, -2, 22), (74, 6, 16), (28, 10, 20)))
    return (f'<g transform="translate(0 {y})"><g {_anim("fx-drift", dur, rng.uniform(0, dur))}>'
            f'<g fill="{color}" opacity="{opacity}">{puffs}<rect x="{-10*s:.0f}" y="0" width="{94*s:.0f}" height="{18*s:.0f}" rx="{9*s:.0f}"/></g></g></g>')


def clouds(rng, n, color="#C9D1D9", opacity=(.12, .22), y=(10, 120), s=(.8, 1.6)):
    return "".join(cloud(rng, rng.uniform(*y), rng.uniform(*s), color, rng.uniform(*opacity), rng.uniform(70, 130))
                   for _ in range(n))


def rain(rng, n, heavy=False):
    out = ""
    for _ in range(n):
        d = rng.uniform(.55, .9) if heavy else rng.uniform(.8, 1.3)
        ln = rng.uniform(14, 24) if heavy else rng.uniform(8, 14)
        out += (f'<g transform="translate({rng.uniform(0, W + 80):.0f} 0)"><g {_anim("fx-fall", d, rng.uniform(0, d), "--dx:-40px")}>'
                f'<line x1="0" y1="0" x2="-3" y2="{ln:.0f}" stroke="#8FB4FF" stroke-opacity="{.55 if heavy else .4}" '
                f'stroke-width="{1.6 if heavy else 1.2}" stroke-linecap="round"/></g></g>')
    return out


def sun(rng, cx, cy, r=26):
    rays = "".join(
        f'<line x1="{math.cos(a)*(r+9):.1f}" y1="{math.sin(a)*(r+9):.1f}" x2="{math.cos(a)*(r+22):.1f}" '
        f'y2="{math.sin(a)*(r+22):.1f}" stroke="#FFD166" stroke-width="3.2" stroke-linecap="round"/>'
        for a in (i * math.tau / 12 for i in range(12))
    )
    return (f'<circle cx="{cx}" cy="{cy}" r="{r*3.2:.0f}" fill="url(#fx-sunGlow)"/>'
            f'<g transform="translate({cx} {cy})"><g {_anim("fx-spin", 40)}>{rays}</g>'
            f'<circle r="{r}" fill="url(#fx-sun)"/></g>')


SUN_DEFS = """
<radialGradient id="fx-sunGlow"><stop offset="0" stop-color="#FFB703" stop-opacity=".32"/><stop offset="1" stop-color="#FFB703" stop-opacity="0"/></radialGradient>
<radialGradient id="fx-sun" cx=".4" cy=".35"><stop offset="0" stop-color="#FFF1B8"/><stop offset="1" stop-color="#FFB703"/></radialGradient>
"""


def string_lights(rng, colors=("#FF4D4D", "#40C057", "#FFD43B", "#4DABF7", "#F783AC")):
    out, step = "", 150
    for x0 in range(0, W, step):
        out += f'<path d="M{x0} 4 Q{x0 + step/2} 46 {x0 + step} 4" stroke="#495057" stroke-width="1.5" fill="none"/>'
        for i in range(1, 6):
            t = i / 6
            x, y = x0 + t * step, 4 + 2 * 42 * t * (1 - t) + 6
            c = colors[(x0 // step + i) % len(colors)]
            out += (f'<g {_anim("fx-twinkle", rng.uniform(1, 2.2), rng.uniform(0, 2))}>'
                    f'<circle cx="{x:.0f}" cy="{y:.0f}" r="9" fill="{c}" opacity=".25"/>'
                    f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="3.6" ry="5" fill="{c}"/></g>')
    return out


def tree(rng, cx, top):
    layers = "".join(f'<path d="M{cx} {top + i*26} l{30 + i*10} {38} h{-(60 + i*20)}z" fill="{c}"/>'
                     for i, c in enumerate(("#2F9E44", "#2B8A3E", "#237032")))
    balls = "".join(f'<circle cx="{cx + dx}" cy="{top + dy}" r="3.2" fill="{c}" {_anim("fx-twinkle", rng.uniform(1, 2), rng.uniform(0, 2))}/>'
                    for dx, dy, c in ((-10, 30, "#FF4D4D"), (12, 44, "#FFD43B"), (-20, 70, "#4DABF7"),
                                      (18, 76, "#F783AC"), (0, 58, "#FF4D4D"), (-30, 98, "#FFD43B"), (28, 100, "#40C057")))
    star = (f'<g transform="translate({cx} {top - 4})"><g {_anim("fx-spin", 8)}>'
            f'<path d="M0 -11 L3 -3 L11 -3 L5 2 L7 10 L0 5 L-7 10 L-5 2 L-11 -3 L-3 -3Z" fill="#FFD43B"/></g></g>')
    return (f'<rect x="{cx-6}" y="{top+112}" width="12" height="14" fill="#7C4A1E"/>{layers}{balls}{star}'
            f'<circle cx="{cx}" cy="{top - 4}" r="22" fill="#FFD43B" opacity=".18"/>')


def web(cx, cy, sx, sy, size=150):
    """A cobweb in a corner. sx/sy = ±1 to point it into the banner."""
    angles = [math.radians(a) for a in range(0, 91, 15)]
    pts = lambda r: [(cx + sx * math.cos(a) * r, cy + sy * math.sin(a) * r) for a in angles]
    out = "".join(f'<path d="M{cx} {cy} L{x:.0f} {y:.0f}"/>' for x, y in pts(size))
    for r in range(28, size, 26):
        p = pts(r)
        d = f"M{p[0][0]:.0f} {p[0][1]:.0f}" + "".join(
            f" Q{(a[0] + b[0]) / 2 - sx*4:.0f} {(a[1] + b[1]) / 2 - sy*4:.0f} {b[0]:.0f} {b[1]:.0f}" for a, b in zip(p, p[1:]))
        out += f'<path d="{d}"/>'
    return f'<g stroke="#D0D7DE" stroke-opacity=".38" stroke-width="1.1" fill="none">{out}</g>'


def spider(scale=1.0):
    legs = ""
    for s in (-1, 1):
        for k in range(4):
            legs += (f'<polyline points="{s*6},{-20 + k*4} {s*(26 + k*3)},{-40 + k*13} {s*(40 + k*3)},{-16 + k*15}" '
                     f'fill="none" stroke="#9BA4AE" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>')
    return (
        f'<g transform="scale({scale})">'
        f'<line x1="0" y1="-600" x2="0" y2="-24" stroke="#E6EDF3" stroke-opacity=".6" stroke-width="1.2"/>'
        f'<g class="fx-legs">{legs}</g>'
        f'<ellipse cy="4" rx="15" ry="19" fill="#2B3038" stroke="#768390" stroke-width="1.6"/>'
        f'<path d="M-4 -4 L4 -4 L0 4Z M-4 12 L4 12 L0 4Z" fill="#F03E3E"/>'
        f'<circle cy="-20" r="10" fill="#2B3038" stroke="#768390" stroke-width="1.6"/>'
        f'<g filter="url(#fx-eyeGlow)"><circle cx="-4" cy="-22" r="2.9" fill="#FF3B3B"/><circle cx="4" cy="-22" r="2.9" fill="#FF3B3B"/>'
        f'<circle cx="-8" cy="-18" r="1.4" fill="#FF3B3B"/><circle cx="8" cy="-18" r="1.4" fill="#FF3B3B"/></g></g>'
    )


def bat(rng, y, dur, delay, s):
    return (f'<g transform="translate(0 {y})"><g {_anim("fx-drift", dur, delay)}><g transform="scale({s:.2f})">'
            f'<g class="fx-bob" style="animation-duration:.9s"><g class="fx-flap">'
            f'<path d="M0 0 Q-7 -9 -20 -7 Q-15 -2 -17 5 Q-10 0 -5 5 Q-2 0 0 3 Q2 0 5 5 Q10 0 17 5 Q15 -2 20 -7 Q7 -9 0 0Z" fill="#6E7681"/>'
            f'</g></g></g></g></g>')


def pumpkin(rng, x, y=316, s=1.0):
    face = (f'<g {_anim("fx-pulse", rng.uniform(.4, .9), rng.uniform(0, 1))}>'
            f'<path d="M-9 -5 l4 -6 l4 6z M1 -5 l4 -6 l4 6z M-10 3 l3 3 l3 -3 l3 3 l3 -3 l3 3 l3 -3 l-3 7 h-12z" fill="#FFD43B"/></g>')
    return (f'<g transform="translate({x} {y}) scale({s})">'
            f'<circle r="30" fill="#FF922B" opacity=".14"/>'
            f'<rect x="-2.5" y="-23" width="5" height="9" rx="2" fill="#2F9E44"/>'
            f'<ellipse rx="21" ry="16" fill="#E8590C"/><ellipse rx="10" ry="16" fill="none" stroke="#C2410C" stroke-width="1.5"/>'
            f'<ellipse rx="17" ry="16" fill="none" stroke="#C2410C" stroke-width="1"/>{face}</g>')


def flag(cx, top):
    chakra = "".join(f'<line x1="0" y1="0" x2="{math.cos(a)*7.5:.1f}" y2="{math.sin(a)*7.5:.1f}"/>'
                     for a in (i * math.tau / 24 for i in range(24)))
    return (f'<path d="M{cx} {top - 4} V{top + 210}" stroke="#ADB5BD" stroke-width="3" stroke-linecap="round"/>'
            f'<circle cx="{cx}" cy="{top - 6}" r="4" fill="#FFD43B"/>'
            f'<g transform="translate({cx + 2} {top})"><g class="fx-wave">'
            f'<rect width="96" height="21" fill="#FF9933"/><rect y="21" width="96" height="21" fill="#FFFFFF"/>'
            f'<rect y="42" width="96" height="21" fill="#138808"/>'
            f'<g transform="translate(48 31.5)" stroke="#000080" stroke-width=".8"><circle r="8.5" fill="none" stroke-width="1.4"/>{chakra}</g>'
            f'</g></g>')


# ═════════════════════════════════════════════════════════════════════════════
# Scenes
# ═════════════════════════════════════════════════════════════════════════════
MARIGOLD = ("#FF9F1C", "#FFD60A", "#F76707", "#E03131", "#FCC419")
HOLI = ("#FF3D7F", "#FFC400", "#00C853", "#2979FF", "#AA00FF", "#FF6D00", "#00E5FF")
SPARK = ("#FFD43B", "#FF6B6B", "#63E6BE", "#74C0FC", "#F783AC", "#FFA94D", "#B197FC")


def _festival_scene(name, rng):
    """Returns (defs, back, front)."""
    defs, back, front = "", "", ""
    strip = list(range(48, 700, 58))  # bottom strip for diyas, pumpkins, ...
    if name == "diwali":
        defs = DIYA_DEFS
        back = (f'<rect width="{W}" height="{H}" fill="url(#fx-warm)"/>' + stars(rng, 40, (0, W, 0, 170), "#FFE8A3")
                + fireworks(rng, 6, SPARK, (330, 690, 30, 90)) + fireworks(rng, 3, SPARK, (1150, 1190, 20, 300)))
        defs += """<radialGradient id="fx-warm" cx=".3" cy="1" r=".9"><stop offset="0" stop-color="#FF8C00" stop-opacity=".22"/><stop offset="1" stop-color="#FF8C00" stop-opacity="0"/></radialGradient>"""
        front = toran(rng) + diyas(rng, strip)
    elif name == "pongal":
        defs = SUN_DEFS
        back = (sun(rng, COL, 250, 30)
                + kite(rng, 360, 50, 22, "#FF3D7F", "#FFD43B") + kite(rng, 600, 70, 26, "#4DABF7", "#FF922B")
                + kite(rng, 1168, 60, 18, "#40C057", "#F783AC") + kite(rng, 470, 26, 15, "#FFD43B", "#E03131"))
        cane = "".join(f'<g transform="translate({x} 334) rotate({a})"><rect x="-3" y="-60" width="6" height="60" rx="2" fill="#7B4F9D"/>'
                       + "".join(f'<rect x="-3.5" y="{-60 + j*12}" width="7" height="2" fill="#4A2F63"/>' for j in range(5))
                       + f'<path d="M0 -60 q-14 -10 -20 -24 M0 -60 q12 -12 22 -20" stroke="#2F9E44" stroke-width="3" fill="none"/></g>'
                       for x, a in ((40, -8), (60, 10), (660, -10), (680, 8)))
        pot = ('<g transform="translate(360 318)"><ellipse rx="24" ry="17" fill="#B45309"/>'
               '<rect x="-14" y="-24" width="28" height="10" rx="3" fill="#92400E"/>'
               '<path d="M-16 -24 q4 -8 8 0 q4 -8 8 0 q4 -8 8 0 q4 -8 8 0" fill="#FFF9DB"/>'
               '<path d="M-24 -2 h48" stroke="#FCC419" stroke-width="3"/></g>')
        back += rising(rng, 14, flake, ("#FFF9DB",), (2, 4), (340, 380), (290, 296))
        front = cane + pot
    elif name == "holi":
        defs = '<filter id="fx-blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="22"/></filter>'
        blobs = "".join(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" filter="url(#fx-blur)" {_anim("fx-pulse", rng.uniform(2, 4), rng.uniform(0, 3))}/>'
            for (x, y, r), c in zip(((40, 40, 90), (330, 0, 80), (640, 120, 70), (20, 330, 90), (420, 350, 80),
                                     (1180, 20, 80), (1190, 330, 90), (900, 345, 70)), HOLI))
        splats = "".join(
            f'<g transform="translate({x} {y})" fill="{c}" opacity=".55"><circle r="{r}"/>'
            + "".join(f'<circle cx="{math.cos(a)*r*1.5:.0f}" cy="{math.sin(a)*r*1.5:.0f}" r="{r*.25:.1f}"/>'
                      for a in (rng.uniform(0, math.tau) for _ in range(6))) + '</g>'
            for (x, y, r), c in zip(((610, 60, 14), (660, 190, 10), (1172, 150, 12), (540, 320, 9)), HOLI[2:]))
        back = blobs + splats + rising(rng, 60, flake, HOLI, (3, 6))
    elif name == "onam":
        back = (pookalam(0, 0, 95) + pookalam(W, H, 140) + pookalam(COL, 230, 52, 50)
                + falling(rng, 40, petal, MARIGOLD + ("#FFFFFF",)))
    elif name in ("ganesh", "navratri", "toran", "petals"):
        defs = DIYA_DEFS
        back = falling(rng, 45 if name != "toran" else 25, petal, MARIGOLD + ("#F06595",))
        front = toran(rng)
        if name == "navratri":
            back += fireworks(rng, 4, SPARK, (360, 690, 30, 90))
            front += diyas(rng, strip[::2])
        if name == "ganesh":
            back += pookalam(COL, 230, 50, 60)
    elif name == "eid":
        defs = MOON_DEFS
        back = stars(rng, 70, (0, W, 0, 200), "#FFE8A3") + moon(COL, 80, 30)
        front = lantern(rng, 580, 60) + lantern(rng, 690, 120, "#FF922B") + lantern(rng, 1172, 90) + lantern(rng, 22, 20, "#63E6BE")
    elif name == "christmas":
        back = tree(rng, COL, 90) + falling(rng, 90, flake, ("#FFFFFF",), (7, 14), (-30, 30), 0)
        front = string_lights(rng)
    elif name == "newyear":
        back = (fireworks(rng, 7, SPARK, (330, 690, 30, 90)) + fireworks(rng, 3, SPARK, (1150, 1190, 20, 320))
                + falling(rng, 70, confetti, SPARK, (5, 10)))
    elif name == "tricolor":
        back = flag(596, 52) + falling(rng, 70, confetti, ("#FF9933", "#FFFFFF", "#138808", "#FF9933", "#138808", "#000080"), (6, 11))
        front = (f'<rect width="{W}" height="4" fill="#FF9933"/><rect y="4" width="{W}" height="3" fill="#FFFFFF"/>'
                 f'<rect y="7" width="{W}" height="4" fill="#138808"/>')
    elif name == "halloween":
        defs = (MOON_DEFS + '<filter id="fx-eyeGlow" x="-1" y="-1" width="3" height="3"><feGaussianBlur stdDeviation="1.6" result="b"/>'
                '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
                '<radialGradient id="fx-spooky" cx=".25" cy="1" r=".9"><stop offset="0" stop-color="#FF6B00" stop-opacity=".22"/>'
                '<stop offset="1" stop-color="#7B2FBE" stop-opacity="0"/></radialGradient>')
        back = (f'<rect width="{W}" height="{H}" fill="url(#fx-spooky)"/>' + moon(COL - 6, 62, 30, False, "#FFC078")
                + web(0, 0, 1, 1, 165) + web(W, 0, -1, 1, 150))
        front = ("".join(bat(rng, y, d, dl, s) for y, d, dl, s in
                         ((40, 13, 2, 1.2), (78, 17, 9, .9), (24, 21, 15, 1.4), (110, 15, 6, .8)))
                 + "".join(pumpkin(rng, x, 316, s) for x, s in ((40, .9), (470, 1.0), (560, .8), (660, 1.1)))
                 # The big one: drops into the free column, bounces, swings, climbs back up.
                 + f'<g transform="translate({COL} 0)"><g class="fx-drop"><g class="fx-swing">{spider(1.35)}</g></g></g>'
                 # A smaller one keeps bobbing at the right edge, next to the terminal.
                 + f'<g transform="translate(1172 112)"><g class="fx-bob" style="animation-duration:1.7s">{spider(.75)}</g></g>')
    elif name == "hearts":
        back = rising(rng, 40, heart, ("#FF6B81", "#F03E3E", "#F783AC", "#FFC9D6"), (5, 9))
    elif name == "night":
        defs = MOON_DEFS + DIYA_DEFS
        back = stars(rng, 90, (0, W, 0, 260)) + moon(COL, 80, 28)
        front = diyas(rng, strip[::2])
    elif name == "diyas":
        defs = DIYA_DEFS
        back = stars(rng, 40, (0, W, 0, 170), "#FFE8A3")
        front = diyas(rng, strip)
    return defs, back, front


def _weather_scene(wx, rng):
    s, day = wx["scene"], wx["day"]
    defs = SUN_DEFS + MOON_DEFS
    sky = sun(rng, COL, 84) if day else moon(COL, 80, 28) + stars(rng, 60, (0, W, 0, 220))
    if s == "clear":
        return defs, sky, ""
    if s == "partly":
        return defs, sky + clouds(rng, 5, opacity=(.14, .24)), ""
    if s == "cloudy":
        return defs, clouds(rng, 10, opacity=(.14, .26)), ""
    if s == "fog":
        bands = "".join(f'<g transform="translate(0 {y})"><g {_anim("fx-drift", rng.uniform(40, 70), rng.uniform(0, 60))}>'
                        f'<rect x="-200" width="{rng.uniform(500, 800):.0f}" height="{rng.uniform(16, 30):.0f}" rx="15" '
                        f'fill="#C9D1D9" opacity="{rng.uniform(.06, .12):.2f}" filter="url(#fx-fog)"/></g></g>'
                        for y in range(20, H, 38))
        return defs + '<filter id="fx-fog"><feGaussianBlur stdDeviation="8"/></filter>', bands, ""
    if s == "drizzle":
        return defs, clouds(rng, 7, opacity=(.14, .24)) + rain(rng, 60), ""
    if s == "rain":
        return defs, clouds(rng, 9, "#ADB5BD", (.16, .28)) + rain(rng, 140, heavy=wx["desc"] == "heavy rain"), ""
    if s == "snow":
        return defs, clouds(rng, 6, opacity=(.12, .2)) + falling(rng, 110, flake, ("#FFFFFF",), (7, 14), (-30, 30), 0), ""
    if s == "storm":
        bolt = (f'<g class="fx-flash"><rect width="{W}" height="{H}" fill="#E7F5FF" opacity=".08"/>'
                f'<path d="M{COL+10} 40 L{COL-16} 120 H{COL+4} L{COL-14} 200 L{COL+30} 104 H{COL+8} L{COL+26} 40Z" fill="#FFF3BF"/></g>')
        return defs, clouds(rng, 11, "#868E96", (.2, .32)) + rain(rng, 170, heavy=True) + bolt, ""
    return defs, "", ""


def render(now: datetime, festival, wx):
    """{'css', 'defs', 'back', 'front'} for the banner."""
    rng = random.Random(now.date().toordinal())
    if festival:
        defs, back, front = _festival_scene(festival["scene"], rng)
    elif wx:
        defs, back, front = _weather_scene(wx, rng)
    else:
        defs = back = front = ""
    css = CSS + """
.fx-drop  { animation:fx-drop 11s .6s cubic-bezier(.3,.7,.4,1) infinite; transform:translateY(-120px) }
.fx-swing { transform-box:fill-box; transform-origin:50% 0; animation:fx-swing 2.6s ease-in-out infinite alternate }
.fx-legs  { animation:fx-legs .5s ease-in-out infinite alternate }
@keyframes fx-drop  { 0% { transform:translateY(-120px) } 9% { transform:translateY(178px) } 12% { transform:translateY(150px) }
                      15% { transform:translateY(165px) } 72% { transform:translateY(165px) } 86%,100% { transform:translateY(-120px) } }
@keyframes fx-swing { from { transform:rotate(-1.6deg) } to { transform:rotate(1.6deg) } }
@keyframes fx-legs  { to { transform:scale(1.05,.94) } }
"""
    return {"css": css, "defs": defs, "back": back, "front": front}
