#!/usr/bin/env python3
"""
Generate light.svg, dark.svg (profile card) and snake.svg.
Run:  GH_TOKEN=$(gh auth token) python3 generate.py
"""

import json
import os
import sys
import urllib.request

# ── config ────────────────────────────────────────────────────────────────────

USERNAME = "danbuildss"
ROLE     = "Founder"
STATUS   = "Currently building Luca & CORTX"
TOOLS    = ["TypeScript", "Next.js", "Python", "Claude API"]
PROJECTS = [
    ("Luca",    "financial agent onchain"),
    ("CORTX",   "reliability infra for x402"),
    ("SOMEHOW", "text & voice note convos"),
    ("OFFLINE", "IRL gathering for builders"),
]
CONTACT  = "x.com/danbuildss"

# card dimensions
CW, CH = 680, 392
PAD    = 28
FZ     = 13
LH     = 22
HH     = 38
FONT   = "'Courier New',Courier,monospace"
CW_CH  = 7.8   # monospace char width at FZ=13 (Courier New)
KEY_COL = 18   # key + dots padded to this many chars

THEMES = {
    "dark": dict(
        bg="#0d1117", border="#30363d", header="#161b22",
        text="#e6edf3", muted="#8b949e", accent="#58a6ff",
        pill_bg="#21262d", pill_fg="#7d8590",
        dot_col="#3d444d", tile_bg="#161b22",
        cursor="#58a6ff",
        red="#ff5f57", yellow="#febc2e", green="#28c840",
        sn0="#161b22", sn1="#0e4429", sn2="#006d32",
        sn3="#26a641", sn4="#39d353",
    ),
    "light": dict(
        bg="#ffffff", border="#d0d7de", header="#f6f8fa",
        text="#24292f", muted="#656d76", accent="#0969da",
        pill_bg="#eaeef2", pill_fg="#57606a",
        dot_col="#d0d7de", tile_bg="#f6f8fa",
        cursor="#0969da",
        red="#ff5f57", yellow="#febc2e", green="#28c840",
        sn0="#ebedf0", sn1="#9be9a8", sn2="#40c463",
        sn3="#30a14e", sn4="#216e39",
    ),
}

# ── github api ────────────────────────────────────────────────────────────────

GQL = """query($login:String!){user(login:$login){
  repositories(first:100 privacy:PUBLIC ownerAffiliations:OWNER
    orderBy:{field:STARGAZERS direction:DESC}){
    totalCount nodes{stargazerCount}
  }
  contributionsCollection{contributionCalendar{
    totalContributions
    weeks{contributionDays{contributionCount date weekday}}
  }}
}}"""


def query_github(token: str) -> dict:
    payload = json.dumps({"query": GQL, "variables": {"login": USERNAME}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{USERNAME}-profile-gen",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
    except Exception as e:
        print(f"ERROR: GitHub API request failed: {e}", file=sys.stderr)
        sys.exit(1)
    if "errors" in result:
        print(f"ERROR: GitHub API returned errors:\n{result['errors']}", file=sys.stderr)
        sys.exit(1)
    if not result.get("data", {}).get("user"):
        print("ERROR: No user data returned. Check GH_TOKEN and username.", file=sys.stderr)
        sys.exit(1)
    return result["data"]["user"]


def calc_stats(user: dict) -> dict:
    cal   = user["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    # flatten + sort newest first for streak
    all_days = sorted(
        [d for w in weeks for d in w["contributionDays"]],
        key=lambda d: d["date"],
        reverse=True,
    )
    streak, found_gap = 0, False
    for day in all_days:
        if day["contributionCount"] > 0:
            streak += 1
            found_gap = False
        else:
            if found_gap:
                break
            found_gap = True  # allow one trailing zero (today not over yet)

    stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    return {
        "contribs": cal["totalContributions"],
        "streak":   streak,
        "repos":    user["repositories"]["totalCount"],
        "stars":    stars,
        "weeks":    weeks,
    }

# ── svg helpers ───────────────────────────────────────────────────────────────

def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def dotted(key: str) -> str:
    """Pad key with dots to KEY_COL chars."""
    s = key + " "
    return s + "." * max(0, KEY_COL - len(s))


def pill(text: str, x: float, y: float, t: dict) -> tuple[str, float]:
    """Return (svg_fragment, width_used). y is baseline of surrounding text."""
    ph, ppx = 18, 8
    tw = len(text) * CW_CH
    pw = tw + ppx * 2
    rx_top = y - FZ * 0.85 - 1   # top of pill
    svg = (
        f'<rect x="{x:.1f}" y="{rx_top:.1f}" width="{pw:.1f}" height="{ph}" rx="3" '
        f'fill="{t["pill_bg"]}"/>'
        f'<text x="{x + ppx:.1f}" y="{y}" '
        f'font-family="{FONT}" font-size="{FZ}" fill="{t["pill_fg"]}">{esc(text)}</text>'
    )
    return svg, pw + 6  # 6px gap between pills


def tile(x: float, y: float, w: float, h: float, val: str, label: str, t: dict) -> str:
    mid_x = x + w / 2
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="5" '
        f'fill="{t["tile_bg"]}" stroke="{t["border"]}" stroke-width="1"/>'
        f'<text x="{mid_x:.1f}" y="{y + h * 0.44:.1f}" text-anchor="middle" '
        f'font-family="{FONT}" font-size="18" font-weight="600" fill="{t["text"]}">{esc(val)}</text>'
        f'<text x="{mid_x:.1f}" y="{y + h * 0.78:.1f}" text-anchor="middle" '
        f'font-family="{FONT}" font-size="10" fill="{t["muted"]}">{esc(label)}</text>'
    )

# ── card svg ──────────────────────────────────────────────────────────────────

def card_svg(stats: dict, theme: str) -> str:
    t   = THEMES[theme]
    cx  = PAD        # content left x
    vx  = PAD + KEY_COL * CW_CH + 4  # value column x
    row_delay = 0.15  # seconds between row fade-ins

    rows: list[tuple[int, str]] = []  # (row_index, svg_fragment)
    ri = 0
    y  = HH + 28  # first content row y (baseline)

    def add(svg_frag: str):
        nonlocal ri
        rows.append((ri, svg_frag))
        ri += 1

    def kv(key: str, val: str) -> str:
        return (
            f'<text x="{cx}" y="{{Y}}" font-family="{FONT}" font-size="{FZ}" '
            f'fill="{t["dot_col"]}">{esc(dotted(key))}</text>'
            f'<text x="{vx:.1f}" y="{{Y}}" font-family="{FONT}" font-size="{FZ}" '
            f'fill="{t["text"]}">{esc(val)}</text>'
        )

    # role
    add(kv("role", ROLE).replace("{Y}", f"{y}"))
    y += LH

    # status
    add(kv("status", STATUS).replace("{Y}", f"{y}"))
    y += LH

    # tools (pills)
    pills_svg = (
        f'<text x="{cx}" y="{y}" font-family="{FONT}" font-size="{FZ}" '
        f'fill="{t["dot_col"]}">{esc(dotted("tools"))}</text>'
    )
    px = vx
    for tool in TOOLS:
        frag, pw = pill(tool, px, y, t)
        pills_svg += frag
        px += pw
    add(pills_svg)
    y += LH + 10

    # projects header
    add(
        f'<text x="{cx}" y="{y}" font-family="{FONT}" font-size="{FZ}" '
        f'fill="{t["muted"]}">projects</text>'
    )
    y += LH

    # project rows
    for name, desc in PROJECTS:
        row = (
            f'<text x="{cx}" y="{y}" font-family="{FONT}" font-size="{FZ}" '
            f'fill="{t["accent"]}">→</text>'
            f'<text x="{cx + 16}" y="{y}" font-family="{FONT}" font-size="{FZ}" '
            f'font-weight="600" fill="{t["text"]}">{esc(name)}</text>'
            f'<text x="{cx + 16 + (len(name) + 1) * CW_CH:.1f}" y="{y}" '
            f'font-family="{FONT}" font-size="{FZ}" fill="{t["muted"]}">{esc(desc)}</text>'
        )
        add(row)
        y += LH

    y += 8
    # contact
    add(kv("contact", CONTACT).replace("{Y}", f"{y}"))
    y += LH + 10

    # stat tiles
    tile_w = (CW - 2 * PAD - 3 * 8) / 4
    tile_h = 56
    tiles_svg = ""
    for i, (val, label) in enumerate([
        (f"{stats['contribs']:,}", "this year"),
        (f"{stats['streak']}d", "streak"),
        (str(stats["repos"]), "repos"),
        (str(stats["stars"]), "stars"),
    ]):
        tx = PAD + i * (tile_w + 8)
        tiles_svg += tile(tx, y, tile_w, tile_h, val, label, t)
    add(tiles_svg)
    y += tile_h + 16

    # cursor
    cursor_svg = (
        f'<text x="{cx}" y="{y}" font-family="{FONT}" font-size="{FZ}" '
        f'fill="{t["cursor"]}" class="cursor">▋</text>'
    )
    add(cursor_svg)

    # build CSS
    css_parts = [
        "@keyframes fadein{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}",
        "@keyframes blink{50%{opacity:0}}",
        f".cursor{{animation:blink 1s step-end infinite}}",
    ]
    for i in range(len(rows)):
        delay = i * row_delay
        css_parts.append(
            f".r{i}{{opacity:0;animation:fadein 0.4s ease {delay:.2f}s forwards}}"
        )
    css = "\n".join(css_parts)

    # build row groups
    groups = ""
    for i, frag in rows:
        groups += f'<g class="r{i}">{frag}</g>\n'

    # header dots + prompt
    header = (
        f'<rect width="{CW}" height="{HH}" rx="8 8 0 0" fill="{t["header"]}"/>'
        f'<circle cx="18" cy="19" r="6" fill="{t["red"]}"/>'
        f'<circle cx="36" cy="19" r="6" fill="{t["yellow"]}"/>'
        f'<circle cx="54" cy="19" r="6" fill="{t["green"]}"/>'
        f'<text x="76" y="23" font-family="{FONT}" font-size="12" fill="{t["muted"]}">'
        f'{esc(USERNAME)}@github ~ whoami</text>'
        f'<line x1="0" y1="{HH}" x2="{CW}" y2="{HH}" stroke="{t["border"]}" stroke-width="1"/>'
    )

    actual_h = y + 8
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CW}" height="{actual_h}" viewBox="0 0 {CW} {actual_h}">
<defs><style>{css}</style></defs>
<rect width="{CW}" height="{actual_h}" rx="8" fill="{t["bg"]}" stroke="{t["border"]}" stroke-width="1"/>
{header}
{groups}
</svg>"""

# ── snake svg ─────────────────────────────────────────────────────────────────

CELL  = 11
GAP   = 2
STEP  = CELL + GAP  # 13px per cell
OX    = 24          # left offset for day labels
OY    = 18          # top offset for month labels

LEVEL_THRESHOLDS = [0, 1, 3, 6, 10]  # contributions → level 0-4


def contrib_level(n: int) -> int:
    for lv, thr in enumerate(LEVEL_THRESHOLDS):
        if n <= thr:
            return lv
    return 4


def build_snake_path(weeks: list) -> list[tuple[float, float, int]]:
    """
    Return boustrophedon path as list of (cx, cy, contrib_count).
    cx/cy = center of each cell.
    """
    path = []
    for wi, week in enumerate(weeks):
        days = week["contributionDays"]
        if wi % 2 == 1:
            days = list(reversed(days))
        for day in days:
            x = OX + wi * STEP + CELL / 2
            # weekday: 0=Sun, so y = weekday * STEP
            y = OY + day["weekday"] * STEP + CELL / 2
            path.append((x, y, day["contributionCount"]))
    return path


def snake_svg(weeks: list, theme: str) -> str:
    t   = THEMES[theme]
    nw  = len(weeks)
    sw  = OX + nw * STEP + 4
    sh  = OY + 7 * STEP + 4

    # draw contribution cells
    cells_svg = ""
    month_labels: dict[str, float] = {}
    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            lv = contrib_level(day["contributionCount"])
            color = t[f"sn{lv}"]
            cx = OX + wi * STEP
            cy = OY + day["weekday"] * STEP
            cells_svg += (
                f'<rect x="{cx}" y="{cy}" width="{CELL}" height="{CELL}" rx="2" '
                f'fill="{color}"/>'
            )
            # month label: first day of each month
            if day["date"][8:10] == "01":
                month_abbr = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                mo = int(day["date"][5:7])
                month_labels[month_abbr[mo]] = OX + wi * STEP

    # month labels
    month_svg = ""
    for name, mx in month_labels.items():
        month_svg += (
            f'<text x="{mx}" y="{OY - 4}" font-family="{FONT}" font-size="9" '
            f'fill="{t["muted"]}">{name}</text>'
        )

    # day labels (Mon, Wed, Fri)
    day_labels = {1: "Mon", 3: "Wed", 5: "Fri"}
    day_svg = ""
    for wd, label in day_labels.items():
        dy = OY + wd * STEP + CELL / 2 + 3
        day_svg += (
            f'<text x="0" y="{dy}" font-family="{FONT}" font-size="9" '
            f'fill="{t["muted"]}">{label}</text>'
        )

    # snake path (boustrophedon polyline)
    path = build_snake_path(weeks)
    if not path:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{sw}" height="{sh}"></svg>'

    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in path)
    total_cells = len(path)
    total_len   = total_cells * STEP
    body_len    = 7 * STEP  # 7-cell body

    # CSS animation: stroke-dasharray keeps a fixed snake length visible
    snake_css = (
        "@keyframes snake{"
        f"from{{stroke-dashoffset:{total_len + body_len}}}"
        f"to{{stroke-dashoffset:{-body_len}}}"
        "}"
        ".snake{"
        f"stroke-dasharray:{body_len} {total_len};"
        f"stroke-dashoffset:{total_len + body_len};"
        "animation:snake 12s linear infinite;"
        "}"
    )

    snake_path = (
        f'<polyline class="snake" points="{pts}" fill="none" '
        f'stroke="#39d353" stroke-width="{CELL}" stroke-linecap="round" '
        f'stroke-linejoin="round"/>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{sw}" height="{sh}" '
        f'viewBox="0 0 {sw} {sh}">\n'
        f'<defs><style>{snake_css}</style></defs>\n'
        f'<rect width="{sw}" height="{sh}" fill="{t["bg"]}" rx="6"/>\n'
        f'{month_svg}\n{day_svg}\n{cells_svg}\n{snake_path}\n'
        f'</svg>'
    )

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    token = os.environ.get("GH_TOKEN", "").strip()
    if not token:
        print("ERROR: GH_TOKEN environment variable is not set.", file=sys.stderr)
        print("Run:  GH_TOKEN=$(gh auth token) python3 generate.py", file=sys.stderr)
        sys.exit(1)

    print("Querying GitHub API...", flush=True)
    user  = query_github(token)
    stats = calc_stats(user)

    print(
        f"  contributions: {stats['contribs']}  "
        f"streak: {stats['streak']}d  "
        f"repos: {stats['repos']}  "
        f"stars: {stats['stars']}"
    )

    out_dir = os.path.dirname(os.path.abspath(__file__))

    for theme in ("light", "dark"):
        path = os.path.join(out_dir, f"{theme}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(card_svg(stats, theme))
        print(f"  wrote {path}")

    for theme in ("light", "dark"):
        path = os.path.join(out_dir, f"snake-{theme}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(snake_svg(stats["weeks"], theme))
        print(f"  wrote {path}")

    print("Done.")


if __name__ == "__main__":
    main()
