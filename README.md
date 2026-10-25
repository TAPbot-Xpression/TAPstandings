# TAPstandings — University of St. Thomas Athletics

> **Automated conference standings for Tommie Athletics, built for use with TAPbot in Xpression.**

---

## Overview

**TAPstandings** is a Python-based web scraper developed by and for the **University of St. Thomas** athletics department. It automatically collects up-to-date standings from the conferences St. Thomas competes in and publishes them to a structured JSON file used by TAPbot inside the Xpression platform.

Every morning at **9:00 AM**, the bot scans official conference websites and refreshes standings data — so your Xpression workflows always have current information without any manual effort.

---

## Conferences & Sports Covered

TAPstandings tracks standings across **three conferences** and **nine sports**:

### 🏔️ Summit League
| Sport | ID | Points Tracked |
|---|---|---|
| Women's Volleyball | `wvball` | — |
| Men's Soccer | `msoc` | ✅ Conference Points (CPTS) |
| Women's Soccer | `wsoc` | ✅ Conference Points (CPTS) |
| Men's Basketball | `mbball` | — |
| Women's Basketball | `wbball` | — |
| Baseball | `summit_195` | — |
| Softball | `summit_193` | — |

### 🏈 Pioneer Football League (PFL)
| Sport | ID | Points Tracked |
|---|---|---|
| Football | `pfl` | — |

### 🏒 National Collegiate Hockey Conference (NCHC)
| Sport | ID | Points Tracked |
|---|---|---|
| Men's Ice Hockey | `mhockey` | ✅ Conference Points (PTS) |

---

## What Data Is Collected

For every team in every standings table, TAPstandings pulls:

- **Team Name** — Full official name (e.g., *St. Thomas*)
- **Team Acronym** — Short-form identifier for use in Xpression (e.g., `UST`)
- **Conference Record** — Win-Loss (or W-L-T for soccer)
- **Overall Record** — Win-Loss (or W-L-T for soccer)
- **Conference Points** *(where applicable)*:
  - `CPTS` — Summit League Men's Soccer & Women's Soccer
  - `PTS` — NCHC Men's Ice Hockey

> **Note:** Conference points are only tracked for sports where they are an official tiebreaker or ranking metric: MSOC, WSOC, and NCHC Men's Ice Hockey.

---

## Team Acronyms for Xpression

One of TAPstandings' most useful features for Xpression users is its **built-in acronym translation layer**. Every team name scraped from a conference website is automatically converted to a standardized short-form acronym, making it easy to reference teams in TAPbot prompts and workflows.

### Summit League Acronyms
| Team | Acronym |
|---|---|
| University of St. Thomas | **UST** |
| North Dakota | UND |
| North Dakota State | NDSU |
| South Dakota | USD |
| South Dakota State | SDSU |
| Kansas City | UMKC |
| Omaha / Nebraska Omaha | OMA |
| Oral Roberts | ORU |
| UMass | UM |
| Delaware | UD |
| Northern Colorado | UNC |

### Pioneer Football League Acronyms
| Team | Acronym |
|---|---|
| Dayton | DAY |
| Butler | BUT |
| Marist | MARI |
| Presbyterian | PC |
| Valparaiso | VALPO |
| San Diego | SAND |
| Drake | DRA |
| Davidson | DC |
| Morehead State | MOSU |
| Stetson | STET |

### NCHC Men's Ice Hockey Acronyms
| Team | Acronym |
|---|---|
| Arizona State | ASU |
| Colorado College | CC |
| Denver | DU |
| Miami (OH) | MIA |
| Minnesota Duluth | UMD |
| North Dakota | UND |
| Omaha | OMA |
| St. Cloud State | SCSU |
| St. Thomas | **UST** |
| Western Michigan | WMU |

> If a team name is not found in the translation map, the scraper automatically generates an acronym from the capitalized initials of the team name as a fallback.

---

## How It Works

```
GitHub Actions (9:00 AM daily)
        │
        ▼
scraper/scrape.py
        │
        ├── Launches headless Chromium (Playwright)
        ├── Visits each conference standings page
        ├── Parses the HTML standings table
        ├── Extracts: Team, Acronym, Conf Record, Ovr Record, Points
        └── Writes structured output to docs/data.json
                │
                ▼
        TAPbot reads data.json
        and serves standings in Xpression
```

### Resilience & Stale Data Protection

If a conference website is temporarily unavailable or returns an error, TAPstandings does **not** wipe the existing data. Instead, it:

1. Keeps the last successfully scraped data for that sport
2. Marks it as `"status": "stale"` in the JSON
3. Logs the error for review

This ensures the Xpression bot **never goes blank** — it will always have standings to display, even if a source is temporarily down.

---

## Output Format

Standings are written to `docs/data.json` with the following structure:

```json
{
  "generated_at": "2026-10-25T22:53:47+00:00",
  "sports": {
    "msoc": {
      "status": "ok",
      "id": "msoc",
      "name": "Summit League Men's Soccer",
      "source": "https://thesummitleague.org/standings.aspx?path=msoc",
      "updated_at": "2026-10-25T22:53:47+00:00",
      "rows": [
        {
          "rank": 1,
          "team": "Kansas City",
          "acronym": "UMKC",
          "conf": "4-0",
          "ovr": "11-2-2",
          "cpts": "12"
        }
      ]
    }
  }
}
```

---

## Project Structure

```
TAPstandings/
├── .github/                  # GitHub Actions workflow (scheduled scraper)
├── scraper/
│   └── scrape.py             # Main scraper — fetches, parses, and writes standings
├── docs/
│   ├── data.json             # Live standings output (read by TAPbot)
│   └── index.html            # Optional web view of standings
└── requirements.txt          # Python dependencies
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `playwright` | Headless browser for rendering JavaScript-heavy standings pages |
| `beautifulsoup4` | HTML parsing and table extraction |

Install dependencies with:

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## Automated Schedule

The scraper runs automatically via **GitHub Actions** every morning at **9:00 AM**. No manual intervention is required. The `docs/data.json` file is updated in-place and immediately available to TAPbot in Xpression.

To trigger a manual run (e.g., after a late-night game):
1. Go to the **Actions** tab in this repository
2. Select the standings workflow
3. Click **Run workflow**

---

## Built for Tommie Athletics

This tool was built to support the **University of St. Thomas** athletics communications and operations teams. St. Thomas competes in the **Summit League** (most sports), the **Pioneer Football League** (football), and the **NCHC** (men's ice hockey) — and TAPstandings covers all three.



---

*Maintained by the Casey Eakins | TAPbot-Xpression*
