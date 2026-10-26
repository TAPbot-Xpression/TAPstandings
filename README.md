# TAPstandings — Tommie Athletic Productions
> **Automated conference standings and national polls pipeline for Tommie Athletic Productions broadcast graphics and Ross XPression.**

---

## 💜 Overview

As the **University of St. Thomas** competes across multiple NCAA Division I conferences—and frequently appears in national rankings—keeping broadcast graphics up-to-date with live records, conference points, and national poll rankings can quickly become a manual headache.

**TAPstandings** solves this by automating the entire data gathering pipeline. Every morning, an automated bot scans official conference sites and national poll boards, cleans and standardizes the records, and outputs a single structured `data.json` file. 

This data feeds directly into **Ross XPression via Datalinq / TAPbot** for on-air graphics, while also powering a web dashboard for fast visual verification by production staff before showtime.

---

## 🎯 What This System Does

- **Eliminates Manual Stat Entry:** No more manually re-typing win-loss records, conference points, or poll movements into XPression graphics on game day.
- **Multi-Conference Coverage:** Automatically pulls data from every conference where the Tommies compete:
  - **Summit League** (Men's & Women's Soccer, Volleyball, Basketball, Baseball, Softball)
  - **Pioneer Football League (PFL)** (Football)
  - **WCHA** (Women's Ice Hockey)
  - **NCHC** (Men's Ice Hockey)
- **National Poll Tracking:** Scrapes weekly **USCHO Men's and Women's D-I Ice Hockey Polls**, including ranks, records, total points, first-place votes, and trend direction.
- **Broadcast-Ready Formatting:** Team names are automatically paired with standardized on-screen acronyms (`UST`, `UND`, `SDSU`, etc.) so XPression text boxes and bug graphics populate cleanly.
- **Fail-Safe Reliability:** If a conference website goes down, the system preserves the last good data and marks it as "stale" rather than wiping out your broadcast graphics.

---

## 📺 Connecting to Ross XPression (Using `data.json`)

For production and broadcast crew members setting up graphics templates in **Ross XPression Studio**:

1. **Live Data Endpoint:**  
   `https://tapbot-xpression.github.io/TAPstandings/data.json`
2. **XPression Setup:**
   - Open **Datalinq Server** and add a **JSON Data Source**.
   - Point the URL to the live `data.json` link above (or use a local mirror synced via TAPbot).
   - Link your table and text objects in XPression to the relevant sport key (e.g., `sports.msoc.rows` or `sports.uscho_mens_poll.rows`).
3. **Data Fields Available per Row:**
   - **Standings:** `rank`, `team`, `acronym`, `conf` (W-L or W-L-T), `ovr`, and `cpts` / `pts` (points).
   - **Polls:** `rank`, `team`, `record`, `pts` (points & 1st-place votes), `last_poll`, `trend` (+1, -2, =), and `trend_dir` (up, down, same, new).

---

## 🌐 The Live Web Dashboard

Production staff can check current data anytime from any device at:

🔗 **[https://tapbot-xpression.github.io/TAPstandings/](https://tapbot-xpression.github.io/TAPstandings/)**

### Dashboard Features:
- **Season Filtering:** Toggle quickly between **Fall**, **Winter**, **Spring**, or **All** sports.
- **Tommie Pride Highlight:** University of St. Thomas rows are automatically highlighted in purple across all conference tables and national polls.
- **USCHO Poll Badges:** Shows the published date of the latest poll and color-coded movement badges (green ▲ for climbing, red ▼ for dropping, gold for NEW).
- **Scan Status Indicators:** Green **Live** badge for fresh daily data; yellow **Stale** badge if a source website had an issue.

---

## 🏆 Covered Sports & Conferences

| Sport / Feed | Organization / League | Season | Points Tracked |
|---|---|---|---|
| **Women's Soccer** | Summit League | Fall | CPTS |
| **Men's Soccer** | Summit League | Fall | CPTS |
| **Football** | Pioneer Football League (PFL) | Fall | Conf / Overall W-L |
| **Women's Volleyball** | Summit League | Fall | Conf / Overall W-L |
| **Women's Ice Hockey** | WCHA | Winter | PTS |
| **Women's DI Hockey Poll** | USCHO National Poll | Winter | Poll Pts & 1st Votes |
| **Men's Ice Hockey** | NCHC | Winter | PTS |
| **Men's DI Hockey Poll** | USCHO National Poll | Winter | Poll Pts & 1st Votes |
| **Women's Basketball** | Summit League | Winter | Conf / Overall W-L |
| **Men's Basketball** | Summit League | Winter | Conf / Overall W-L |
| **Softball** | Summit League | Spring | Conf / Overall W-L |
| **Baseball** | Summit League | Spring | Conf / Overall W-L |

---

## ⚙️ How It Works (Under the Hood)

1. **Automated Daily Trigger:** A GitHub Actions workflow runs every day at **9:00 AM UTC**, **12:00 PM UTC**, and **4:00 PM UTC**  (or can be manually triggered on demand after games).
2. **Headless Browser Scraping:** Python using Playwright and BeautifulSoup renders live JavaScript pages on Sidearm Sports and USCHO to capture full tables.
3. **Data Normalization:** Filters out group/pod artifacts, extracts conference vs. overall records, calculates poll trends, and maps school acronyms.
4. **JSON Emission & Publishing:** Writes a clean `data.json` to GitHub Pages, instantly updating both XPression graphics feeds and the web interface.

---

## 🚀 Running on Demand

Need an instant refresh after a Friday night game without waiting for the scheduled 9 AM run?

1. Go to the **Actions** tab in this GitHub repository.
2. Select **Scrape Standings & Polls** from the left sidebar.
3. Click **Run workflow** → **Run workflow**.
4. Within 60 seconds, `data.json` and the website will reflect the newest numbers.

---

*University of St. Thomas Athletics • Broadcast & Video Production • Maintained by Casey Eakins*
