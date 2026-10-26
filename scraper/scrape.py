#!/usr/bin/env python3
"""
Fetch standings and national polls from Summit League, PFL, NCHC, WCHA, and USCHO.
Extracts:
  - Sports Standings: Team Name, Acronym, Conference W-L, Overall W-L, CPTS/PTS
  - USCHO Polls: Rank, Team Name, Record, Pts + First-Place Votes formatted as "123 (12)",
    Last Poll rank, and Poll movement (up/down/same/new).

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

# ── Team Acronym Translation Map (for Standings & Polls) ──────────────────────
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

    # ── Default Fallbacks for Other Ice Hockey Programs ───────────────────────
    "Ohio State":               "OSU",
    "Minnesota":                "MINN",
    "Wisconsin":                "WIS",
    "Bemidji State":            "BSU",
    "Minnesota State":          "MSU",
}

# ── WCHA-Specific Acronym Overrides (Applies ONLY to WCHA Standings) ──────────
WCHA_TEAM_ACRONYMS = {
    "Ohio State":       "OHIOST",
    "Minnesota":        "MINNES",
    "St. Cloud State":  "STCLOU",
    "Minnesota Duluth": "MNDULU",
    "St. Thomas":       "STTHMN",
    "Wisconsin":        "WISC",
    "Bemidji State":    "BEMIDJI",
    "Minnesota State":  "MNSTMK",
}

# ── Target Configuration ──────────────────────────────────────────────────────
FEEDS_CONFIG = [
    # ── Fall Sports ───────────────────────────────────────────────────────────
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
    # ── Winter Sports & Polls ─────────────────────────────────────────────────
    {
        "id": "whockey",
        "name": "WCHA Women's Ice Hockey",
        "type": "standings",
        "url": "https://wcha.com/standings.aspx?path=whockey",
        "point_col": "pts",
        "skip_pods": False,
        "acronym_overrides": WCHA_TEAM_ACRONYMS,
    },
    {
        "id": "uscho_womens_poll",
        "name": "USCHO Women's Division I Ice Hockey Poll",
        "type": "poll",
        "url": "https://www.uscho.com/rankings/d-i-womens-poll",
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
        "id": "uscho_mens_poll",
        "name": "USCHO Men's Division I Ice Hockey Poll",
        "type": "poll",
        "url": "https://www.uscho.com/rankings/d-i-mens-poll",
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
        "id": "mbball",
        "name": "Summit League Men's Basketball",
        "type": "standings",
        "url": "https://thesummitleague.org/standings.aspx?path=mbball",
        "point_col": None,
        "skip_pods": False,
    },
    # ── Spring Sports ─────────────────────────────────────────────────────────
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
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

def get_team_acronym(team_name, overrides=None):
    """Translate raw team name into standard acronym with optional feed overrides."""
    cleaned = clean(team_name)
    active_map = {**TEAM_ACRONYMS, **(overrides or {})}

    if cleaned in active_map:
        return active_map[cleaned]

    cleaned_lower = cleaned.lower()
    for full_name, acronym in active_map.items():
        if full_name.lower() == cleaned_lower:
            return acronym

    for full_name, acronym in active_map.items():
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
    overrides      = meta.get("acronym_overrides", None)

    target = None

    # Priority 1: Direct Sidearm divisionless/overall table check
    divisionless = soup.select_one("table.table-divisionless, .table-divisionless table")
    if divisionless:
        target = divisionless

    # Priority 2: Fallback candidate search
    if target is None:
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
            non_pod_tables = [t for t in candidate_tables if not is_pods_table(t)]
            if non_pod_tables:
                target = max(non_pod_tables, key=lambda t: len(body_rows(t)))
            else:
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

    team_idx = exact_idx("team", "school", "member", "institution", "name") or idx("team", "school", "member", "institution", "name")

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
        
        # Skip empty names, header titles, and Pod headers (e.g. "Pod A", "Pod B")
        if not team or team.lower() in ("team", "school", "member", "institution") or team.lower().startswith("pod"):
            continue

        acronym = get_team_acronym(team, overrides=overrides)

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

    # Sort descending by points if sport tracks them
    if point_col_type == "cpts":
        rows.sort(key=lambda r: int(r.get("cpts", 0) or 0), reverse=True)
        for i, row in enumerate(rows, 1):
            row["rank"] = i
    elif point_col_type == "pts":
        rows.sort(key=lambda r: int(r.get("pts", 0) or 0), reverse=True)
        for i, row in enumerate(rows, 1):
            row["rank"] = i

    if not rows:
        raise ValueError(f"No team rows parsed for {meta['name']}")

    return {
        "id":     meta["id"],
        "name":   meta["name"],
        "source": meta["url"],
        "rows":   rows,
    }


# ── USCHO Poll Table Parser (Targets Bootstrap-Vue #btable) ───────────────────

def parse_uscho_poll_table(html, meta):
    soup = BeautifulSoup(html, "html.parser")

    # 1. Extract Poll Date from header (e.g., "USCHO Division I Men's Poll - October 19, 2026")
    poll_date = ""
    for heading in soup.find_all(["h1", "h2", "h3", ".page-title", ".poll-title"]):
        text = clean(heading.get_text())
        m = re.search(r"-\s*([A-Za-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)", text)
        if m:
            poll_date = m.group(1).strip()
            break

    # 2. Locate Main Standings Table
    target = soup.find("table", id="btable")

    if target is None:
        for table in soup.find_all("table"):
            hdrs = [h.lower() for h in header_cells(table)]
            if any("team" in h for h in hdrs) and any("rnk" in h or "rank" in h or "pts" in h for h in hdrs):
                target = table
                break

    if target is None:
        tables = soup.find_all("table")
        if tables:
            target = tables[0]

    if target is None:
        raise ValueError(f"Could not find USCHO table for {meta['name']}")

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

    rank_idx = exact_idx("rnk", "rank", "#", "rk") or idx("rnk", "rank")
    team_idx = exact_idx("team", "school") or idx("team", "school")
    fpv_idx  = idx("first place", "(first place votes)", "fpv", "1st")
    rec_idx  = exact_idx("record", "rec", "w-l-t") or idx("record", "rec")
    pts_idx  = exact_idx("pts", "points", "total") or idx("pts", "point")
    last_idx = exact_idx("last poll", "last", "prev", "last rnk") or idx("last", "prev")

    rows = []
    for tr in body_rows(target):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 4:
            continue

        def cell_text(i):
            if i is None or i >= len(cells):
                return ""
            return clean(cells[i].get_text())

        raw_team = team_text(cells[team_idx]) if team_idx is not None else cell_text(1)
        if not raw_team or raw_team.lower() in ("team", "school", "rnk", "rank", "ranking"):
            continue

        # Extract Rank
        raw_rank = cell_text(rank_idx) if rank_idx is not None else cell_text(0)
        rank_match = re.search(r"(\d+)", raw_rank)
        rank_val = int(rank_match.group(1)) if rank_match else len(rows) + 1

        # Check for first-place votes embedded in team string or separate column
        fpv = None
        m_fpv = re.search(r"\(([\d]+)\)", raw_team)
        if m_fpv:
            fpv = m_fpv.group(1)
            cleaned_team = clean(raw_team[:m_fpv.start()])
        else:
            cleaned_team = raw_team

        if fpv is None and fpv_idx is not None:
            raw_fpv = cell_text(fpv_idx)
            m_col = re.search(r"(\d+)", raw_fpv)
            if m_col:
                fpv = m_col.group(1)

        # Extract Points
        raw_pts = cell_text(pts_idx) if pts_idx is not None else cell_text(4)
        m_pts = re.search(r"(\d+)", raw_pts)
        pts_num = m_pts.group(1) if m_pts else "0"

        # Combine Pts and First Place Votes
        if fpv and int(fpv) > 0:
            formatted_pts = f"{pts_num} ({fpv})"
        else:
            formatted_pts = pts_num

        # Extract Overall Record
        raw_rec = cell_text(rec_idx) if rec_idx is not None else cell_text(3)
        record = raw_rec.replace("–", "-") if raw_rec else "—"

        # Extract Last Poll & calculate movement
        raw_last = cell_text(last_idx) if last_idx is not None else (cell_text(5) if len(cells) > 5 else "")
        last_match = re.search(r"(\d+)", raw_last)

        if last_match:
            last_rank = int(last_match.group(1))
            diff = last_rank - rank_val
            if diff > 0:
                trend = f"+{diff}"
                trend_dir = "up"
            elif diff < 0:
                trend = f"{diff}"
                trend_dir = "down"
            else:
                trend = "="
                trend_dir = "same"
            last_display = str(last_rank)
        else:
            last_rank = None
            last_display = "NR" if ("nr" in raw_last.lower() or not raw_last) else raw_last
            trend = "NEW"
            trend_dir = "new"

        rows.append({
            "rank":      rank_val,
            "team":      cleaned_team,
            "record":    record or "—",
            "pts":       formatted_pts,
            "last_poll": last_display,
            "trend":     trend,
            "trend_dir": trend_dir,
        })

    if not rows:
        raise ValueError(f"No poll rows parsed from table for {meta['name']}")

    return {
        "id":        meta["id"],
        "name":      meta["name"],
        "source":    meta["url"],
        "poll_date": poll_date,
        "rows":      rows,
    }


# ── Playwright Fetch ──────────────────────────────────────────────────────────

def fetch_all_rendered(feeds):
    from playwright.sync_api import sync_playwright

    scraped_data = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=UA)
        page    = context.new_page()

        # Block media/fonts to speed up, keep scripts/styles for dynamic table mounting
        page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ("image", "media", "font")
            else route.continue_(),
        )

        for feed in feeds:
            feed_id   = feed["id"]
            feed_type = feed.get("type", "standings")
            url       = feed["url"]

            print(f"Fetching [{feed['name']}] -> {url} ...")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)

                if feed_type == "poll":
                    try:
                        page.wait_for_selector("#btable tbody tr", timeout=15000)
                    except Exception:
                        page.wait_for_selector("table tbody tr", timeout=10000)
                else:
                    try:
                        page.wait_for_selector("table tbody tr", timeout=15000)
                    except Exception:
                        page.wait_for_selector("table", timeout=5000)

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
