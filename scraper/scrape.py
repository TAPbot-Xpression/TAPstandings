#!/usr/bin/env python3
"""
Fetch standings and national polls from Summit League, PFL, NCHC, WCHA, and USCHO.
Extracts:
  - Sports Standings: Team Name, Acronym, Conference W-L, Overall W-L, CPTS/PTS
  - USCHO Polls: Rank, Team Name, Record, Pts + First-Place Votes formatted as "123 (12)"

Writes structured output to docs/data.json.

Safe by design: if any individual source fails, the last good data for that
sport/poll stays in the file marked "stale", so the website never goes blank.

Usage:
    python scraper/scrape.py
    python scraper/scrape.py --out docs/data.json
"""

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ── Team Acronym Translation Map (for Standings) ──────────────────────────────
TEAM_ACRONYMS = {
    # ── Summit League ─────────────────────────────────────────────────────────
    "North Dakota":             "UND",
    "North Dakota State":       "NDSU",
    "South Dakota":             "USD",
    "South Dakota State":       "SDSU",
    "Kansas City":              "UMKC",
    "Omaha":                    "OMA",
    "Nebraska Omaha":           "OMA",
    "St. Thomas":               "UST",
    "St. Thomas (MN)":          "UST",
    "St. Thomas (Minn.)":       "UST",
    "University of St. Thomas": "UST",
    "Oral Roberts":             "ORU",

    # ── Other Summit League / Common Opponents ────────────────────────────────
    "UMass":                    "UM",
    "Massachusetts":            "UM",
    "Delaware":                 "UD",
    "Northern Colorado":        "UNC",

    # ── Pioneer Football League (PFL) ─────────────────────────────────────────
    "Dayton":                   "DAY",
    "Butler":                   "BUT",
    "Marist":                   "MARI",
    "Presbyterian":             "PC",
    "Valparaiso":               "VALPO",
    "San Diego":                "SAND",
    "Drake":                    "DRA",
    "Davidson":                 "DC",
    "Morehead State":           "MOSU",
    "Stetson":                  "STET",

    # ── NCHC Men's Ice Hockey ─────────────────────────────────────────────────
    "Arizona State":            "ASU",
    "Colorado College":         "CC",
    "Denver":                   "DU",
    "Miami":                    "MIA",
    "Miami (OH)":               "MIA",
    "Minnesota Duluth":         "UMD",
    "St. Cloud State":          "SCSU",
    "Western Michigan":         "WMU",

    # ── WCHA Women's Ice Hockey ───────────────────────────────────────────────
    "Ohio State":               "OSU",
    "Minnesota":                "MINN",
    "Wisconsin":                "WIS",
    "Bemidji State":            "BSU",
    "Minnesota State":          "MSU",
}

# ── Target Configuration ──────────────────────────────────────────────────────
# Includes conference standings and USCHO national polls
FEEDS_CONFIG = [
    # ── Standings ─────────────────────────────────────────────────────────────
    {
        "id": "wsoc",
        "name": "Summit League Women's Soccer",
        "type": "standings",
        "url": "https://thesummitleague.org/standings.aspx?path=wsoc",
        "point_col": "cpts",
        "skip_pods": True,
    },
    {
        "id": "msoc",
        "name": "Summit League Men's Soccer",
        "type": "standings",
        "url": "https://thesummitleague.org/standings.aspx?path=msoc",
        "point_col": "cpts",
        "skip_pods": False,
    },
    {
        "id": "pfl",
        "name": "Pioneer Football League",
        "type": "standings",
        "url": "https://pioneer-football.org/standings.aspx?standings=19",
        "point_col": None,
        "skip_pods": False,
    },
    {
        "id": "wvball",
        "name": "Summit League Women's Volleyball",
        "type": "standings",
        "url": "https://thesummitleague.org/standings.aspx?path=wvball",
        "point_col": None,
        "skip_pods": False,
    },
    {
        "id": "whockey",
        "name": "WCHA Women's Ice Hockey",
        "type": "standings",
        "url": "https://wcha.com/standings.aspx?path=whockey",
        "point_col": "pts",
        "skip_pods": False,
    },
    {
        "id": "mhockey",
        "name": "NCHC Men's Ice Hockey",
        "type": "standings",
        "url": "https://nchchockey.com/standings.aspx?path=mhockey",
        "point_col": "pts",
        "skip_pods": False,
    },
    {
        "id": "mbball",
        "name": "Summit League Men's Basketball",
        "type": "standings",
        "url": "https://thesummitleague.org/standings.aspx?path=mbball",
        "point_col": None,
        "skip_pods": False,
    },
    {
        "id": "wbball",
        "name": "Summit League Women's Basketball",
        "type": "standings",
        "url": "https://thesummitleague.org/standings.aspx?path=wbball",
        "point_col": None,
        "skip_pods": False,
    },
    {
        "id": "summit_193",
        "name": "Summit League Softball",
        "type": "standings",
        "url": "https://thesummitleague.org/standings.aspx?standings=193",
        "point_col": None,
        "skip_pods": False,
    },
    {
        "id": "summit_195",
        "name": "Summit League Baseball",
        "type": "standings",
        "url": "https://thesummitleague.org/standings.aspx?standings=195",
        "point_col": None,
        "skip_pods": False,
    },
    # ── USCHO National Polls ──────────────────────────────────────────────────
    {
        "id": "uscho_mens_poll",
        "name": "USCHO Men's Division I Ice Hockey Poll",
        "type": "poll",
        "url": "https://www.uscho.com/rankings/d-i-mens-poll",
    },
    {
        "id": "uscho_womens_poll",
        "name": "USCHO Women's Division I Ice Hockey Poll",
        "type": "poll",
        "url": "https://www.uscho.com/rankings/d-i-womens-poll",
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

def get_team_acronym(team_name):
    """Translate raw team name into standard acronym."""
    cleaned = clean(team_name)

    if cleaned in TEAM_ACRONYMS:
        return TEAM_ACRONYMS[cleaned]

    cleaned_lower = cleaned.lower()
    for full_name, acronym in TEAM_ACRONYMS.items():
        if full_name.lower() == cleaned_lower:
            return acronym

    for full_name, acronym in TEAM_ACRONYMS.items():
        if full_name.lower() in cleaned_lower:
            return acronym

    words = [w for w in re.split(r"[\s\-\.]+", cleaned) if w and w[0].isupper()]
    if words:
        return "".join(w[0] for w in words).upper()
    return cleaned[:4].upper()

def header_cells(table):
    row = table.select_one("thead tr:last-of-type") or table.find("tr")
    return [clean(c.get_text()) for c in row.find_all(["th", "td"])] if row else []

def body_rows(table):
    rows = table.select("tbody tr") or table.find_all("tr")[1:]
    return [r for r in rows if r.find_all(["td", "th"])]

def team_text(cell):
    link = cell.find("a")
    return clean((link or cell).get_text())

def is_pods_table(table):
    """Returns True if this table is a Pods/group sub-table rather than full standings."""
    hdrs = [h.lower() for h in header_cells(table)]
    if any("pod" in h or "group" in h for h in hdrs):
        return True
    prev = table.find_previous(["h2", "h3", "h4", "caption", "th"])
    if prev and "pod" in prev.get_text().lower():
        return True
    if len(body_rows(table)) < 6:
        return True
    return False


# ── Sidearm Standings Table Parser ────────────────────────────────────────────

def parse_standings_table(html, meta):
    soup = BeautifulSoup(html, "html.parser")
    point_col_type = meta.get("point_col")
    skip_pods      = meta.get("skip_pods", False)

    candidate_tables = [
        t for t in soup.find_all("table")
        if any(
            "team" in h.lower() or "school" in h.lower() or "member" in h.lower()
            for h in header_cells(t)
        )
    ]

    if not candidate_tables:
        raise ValueError(f"No standings table found for {meta['name']}")

    if skip_pods:
        target = next((t for t in candidate_tables if not is_pods_table(t)), None)
        if target is None:
            target = max(candidate_tables, key=lambda t: len(body_rows(t)))
    else:
        target = candidate_tables[0]

    if target is None:
        raise ValueError(f"Could not identify standings table for {meta['name']}")

    headers    = header_cells(target)
    hdrs_lower = [h.lower() for h in headers]

    def idx(*candidates):
        for c in candidates:
            for i, h in enumerate(hdrs_lower):
                if c in h:
                    return i
        return None

    def exact_idx(*candidates):
        for c in candidates:
            for i, h in enumerate(hdrs_lower):
                if h == c:
                    return i
        return None

    team_idx = idx("team", "school", "member", "institution", "name")

    conf_combined = exact_idx("conf", "conference", "league", "wcha", "nchc")
    if conf_combined is None:
        conf_combined = idx("conf record", "conference record", "wcha record", "nchc record")
    conf_w_idx = idx("conf w", "cw", "conference w", "wcha w") if conf_combined is None else None
    conf_l_idx = idx("conf l", "cl", "conference l", "wcha l") if conf_combined is None else None

    ovr_combined = exact_idx("overall", "ovr", "total")
    if ovr_combined is None:
        ovr_combined = idx("overall record", "ovr record", "total record")
    ovr_w_idx = idx("overall w", "ow", "ovr w") if ovr_combined is None else None
    ovr_l_idx = idx("overall l", "ol", "ovr l") if ovr_combined is None else None

    pts_idx = None
    if point_col_type == "cpts":
        pts_idx = exact_idx("cpts", "conf pts", "pts", "points") or idx("cpts", "conf pts")
    elif point_col_type == "pts":
        pts_idx = exact_idx("pts", "points", "total pts", "tp", "wcha pts", "nchc pts") or idx("pts", "point")

    rows = []
    for tr in body_rows(target):
        cells = tr.find_all(["td", "th"])

        def cell_text(i):
            if i is None or i >= len(cells):
                return ""
            return clean(cells[i].get_text())

        team = team_text(cells[team_idx]) if team_idx is not None else ""
        if not team or team.lower() in ("team", "school", "member", "institution"):
            continue

        acronym = get_team_acronym(team)

        if conf_combined is not None:
            conf = cell_text(conf_combined).replace("–", "-") or "0-0"
        elif conf_w_idx is not None and conf_l_idx is not None:
            conf = f"{cell_text(conf_w_idx)}-{cell_text(conf_l_idx)}"
        else:
            conf = "—"

        if ovr_combined is not None:
            ovr = cell_text(ovr_combined).replace("–", "-") or "0-0"
        elif ovr_w_idx is not None and ovr_l_idx is not None:
            ovr = f"{cell_text(ovr_w_idx)}-{cell_text(ovr_l_idx)}"
        else:
            ovr = "—"

        row_data = {
            "rank":    len(rows) + 1,
            "team":    team,
            "acronym": acronym,
            "conf":    conf,
            "ovr":     ovr,
        }

        if point_col_type == "cpts" and pts_idx is not None:
            row_data["cpts"] = cell_text(pts_idx) or "0"
        elif point_col_type == "pts" and pts_idx is not None:
            row_data["pts"] = cell_text(pts_idx) or "0"

        rows.append(row_data)

    if not rows:
        raise ValueError(f"No team rows parsed for {meta['name']}")

    return {
        "id":     meta["id"],
        "name":   meta["name"],
        "source": meta["url"],
        "rows":   rows,
    }


# ── USCHO Poll Table Parser ───────────────────────────────────────────────────

def parse_uscho_poll_table(html, meta):
    soup = BeautifulSoup(html, "html.parser")

    target = None
    for table in soup.find_all("table"):
        hdrs = [h.lower() for h in header_cells(table)]
        if any("team" in h or "school" in h for h in hdrs) and any("pts" in h or "point" in h for h in hdrs):
            target = table
            break

    if target is None:
        tables = soup.find_all("table")
        if tables:
            target = tables[0]

    if target is None:
        raise ValueError(f"Could not find USCHO poll table for {meta['name']}")

    headers = header_cells(target)
    hdrs_lower = [h.lower() for h in headers]

    def idx(*candidates):
        for c in candidates:
            for i, h in enumerate(hdrs_lower):
                if c in h:
                    return i
        return None

    def exact_idx(*candidates):
        for c in candidates:
            for i, h in enumerate(hdrs_lower):
                if h == c:
                    return i
        return None

    rank_idx = exact_idx("rank", "#", "rk") or idx("rank", "#")
    team_idx = idx("team", "school", "institution", "college")
    pts_idx  = exact_idx("pts", "points", "total") or idx("pts", "point")
    fpv_idx  = exact_idx("1st", "(1st)", "fpv", "first", "1st place") or idx("1st", "fpv", "first")
    rec_idx  = idx("record", "rec", "w-l-t", "overall")

    rows = []
    for tr in body_rows(target):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue

        def cell_text(i):
            if i is None or i >= len(cells):
                return ""
            return clean(cells[i].get_text())

        raw_team = team_text(cells[team_idx]) if team_idx is not None else ""
        if not raw_team or raw_team.lower() in ("team", "school", "rank", "ranking"):
            continue

        # Check for first-place votes embedded in team string (e.g. "Boston College (45)")
        fpv_embedded = None
        m_fpv = re.search(r"\(([\d]+)\)", raw_team)
        if m_fpv:
            fpv_embedded = m_fpv.group(1)
            cleaned_team = clean(raw_team[:m_fpv.start()])
        else:
            cleaned_team = raw_team

        # Rank
        rank_val = cell_text(rank_idx) if rank_idx is not None else str(len(rows) + 1)
        rank_val = re.sub(r"[^\d]", "", rank_val) or str(len(rows) + 1)

        # Points and First Place Votes
        raw_pts = cell_text(pts_idx) if pts_idx is not None else "0"
        raw_pts = re.sub(r"[^\d]", "", raw_pts) or "0"

        fpv = fpv_embedded
        if fpv is None and fpv_idx is not None:
            fpv_text = cell_text(fpv_idx)
            m_col = re.search(r"(\d+)", fpv_text)
            if m_col:
                fpv = m_col.group(1)

        # Format combined Points and FPV: "123 (12)" or "123"
        if fpv and int(fpv) > 0:
            formatted_pts = f"{raw_pts} ({fpv})"
        else:
            formatted_pts = raw_pts

        # Record
        record = cell_text(rec_idx).replace("–", "-") if rec_idx is not None else "—"

        rows.append({
            "rank":   int(rank_val),
            "team":   cleaned_team,
            "pts":    formatted_pts,
            "record": record or "—",
        })

    if not rows:
        raise ValueError(f"No poll rows parsed for {meta['name']}")

    return {
        "id":     meta["id"],
        "name":   meta["name"],
        "source": meta["url"],
        "rows":   rows,
    }


# ── Playwright Fetch ──────────────────────────────────────────────────────────

def fetch_all_rendered(feeds):
    from playwright.sync_api import sync_playwright

    scraped_data = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=UA)
        page    = context.new_page()

        page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ("image", "media", "font", "stylesheet")
            else route.continue_(),
        )

        for feed in feeds:
            feed_id   = feed["id"]
            feed_type = feed.get("type", "standings")
            url       = feed["url"]

            print(f"Fetching [{feed['name']}] -> {url} ...")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_selector("table", timeout=15000)
                except Exception:
                    print(f"  ⚠ No table selector found within timeout for {feed_id}")

                html = page.content()

                if feed_type == "poll":
                    data = parse_uscho_poll_table(html, feed)
                else:
                    data = parse_standings_table(html, feed)

                scraped_data[feed_id] = {"status": "ok", **data}
                pts_note = f" (with {feed['point_col'].upper()})" if feed.get("point_col") else ""
                print(f"  ✓ Parsed {len(data['rows'])} rows{pts_note}.")
            except Exception as exc:
                print(f"  ✗ Error [{feed_id}]: {exc}", file=sys.stderr)
                scraped_data[feed_id] = {
                    "status": "error",
                    "error":  str(exc)[:300],
                    "rows":   [],
                }

        browser.close()

    return scraped_data


# ── Main ──────────────────────────────────────────────────────────────────────

def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/data.json", help="Path to output data.json")
    args = ap.parse_args()

    out_path = Path(args.out)

    old_sports = {}
    if out_path.exists():
        try:
            old_sports = json.loads(out_path.read_text(encoding="utf-8")).get("sports", {})
        except Exception:
            pass

    new_scraped       = fetch_all_rendered(FEEDS_CONFIG)
    current_timestamp = now_iso()
    final_sports      = {}

    for feed in FEEDS_CONFIG:
        s_id = feed["id"]
        res  = new_scraped.get(s_id)
        old  = old_sports.get(s_id)

        if res and res.get("status") == "ok":
            res["updated_at"] = current_timestamp
            final_sports[s_id] = res
        elif old and old.get("rows"):
            print(f"[{s_id}] Scrape failed — keeping previous data as stale.")
            final_sports[s_id] = {
                **old,
                "status": "stale",
                "error":  res.get("error") if res else "Fetch failed",
            }
        else:
            final_sports[s_id] = res or {
                "id":     s_id,
                "name":   feed["name"],
                "source": feed["url"],
                "status": "error",
                "rows":   [],
            }

    payload = {
        "generated_at": current_timestamp,
        "sports":       final_sports,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\n✓ Successfully wrote {len(final_sports)} feeds to {out_path}")


if __name__ == "__main__":
    main()
