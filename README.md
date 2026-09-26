# NHL Analytics Hub

An end-to-end hockey data pipeline built on the official NHL public API. Raw JSON from several API endpoints is parsed and normalized into a 7-table relational database, analysed with SQL, and presented in a multi-page Streamlit dashboard.

**Database:** MySQL 8.0 (tested on MySQL 8.0.18 from WAMP)
**Connector library:** PyMySQL
**Season covered:** 2025-26 (`20252026`)

## Project structure

```
.
├── notebooks/
│   ├── 01_explore_api.ipynb       # calls each endpoint and inspects the raw JSON structure
│   └── 02_fetch_and_load.ipynb    # loops over the API and inserts every response straight into MySQL
├── sql/
│   ├── create_tables.sql          # CREATE TABLE statements (PK, FK, NOT NULL, UNIQUE)
│   └── queries.sql                # 12 analysis queries, each answering a business question
├── app.py                         # Streamlit dashboard (7 pages)
├── requirements.txt
└── README.md
```

No JSON files are written to disk. The loader fetches each response, flattens it into a pandas DataFrame, cleans it and inserts it directly into the database.

## Data sources

All endpoints are on `https://api-web.nhle.com/v1` and need no API key. A short delay is added before every request.

| Table | Endpoint |
|---|---|
| `teams`, `standings` | `/standings/now` |
| `players` | `/roster/{team_abbrev}/current` (forwards, defensemen and goalies flattened into one list) |
| `games` | `/club-schedule-season/{team_abbrev}/20252026` |
| `game_stats` | `/gamecenter/{game_id}/boxscore` (skaters only) |
| `skater_season_stats`, `goalie_season_stats` | `/club-stats/{team_abbrev}/20252026/2` (position `G` goes to the goalie table) |

Because the data was collected in the off-season, `/roster/{team}/current` no longer lists some players who played in 2025-26 (trades, retirements, preseason prospects). Those players are added to `players` from `/player/{player_id}/landing`, so every stats row has a matching player.

## Database schema

| Table | Primary key | Foreign keys | Rows |
|---|---|---|---|
| `teams` | `team_id` (AUTO_INCREMENT) | - | 32 |
| `standings` | `standing_id` | `team_id` -> teams | 32 |
| `players` | `player_id` (from the API) | `team_id` -> teams | 1,545 |
| `games` | `game_id` (from the API) | `home_team_id`, `away_team_id` -> teams | 1,498 |
| `game_stats` | `stat_id` | `game_id` -> games, `player_id` -> players, `team_id` -> teams | 53,927 |
| `skater_season_stats` | `stat_id` | `player_id` -> players, `team_id` -> teams | 1,023 |
| `goalie_season_stats` | `stat_id` | `player_id` -> players, `team_id` -> teams | 100 |

Row counts are from the load run in September 2026. The 1,498 games cover preseason, regular season and playoffs. Of the 1,545 players, 979 came from the current rosters and 566 were added from the landing endpoint.

Several endpoints return the same record more than once (every game is in both teams' schedules), so unique keys are defined on each table's natural key and rows are loaded with `INSERT IGNORE`. Running the load a second time inserts nothing.

## Setup

### 1. Prerequisites

- Python 3.9 or newer
- A running MySQL 8 server (WAMP, XAMPP, a standalone install, etc.)

### 2. Install the Python packages

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

### 3. Database connection settings

The notebooks and `app.py` read the connection from environment variables. The defaults are:

| Variable | Default |
|---|---|
| `DB_HOST` | `127.0.0.1` |
| `DB_PORT` | `3308` |
| `DB_USER` | `root` |
| `DB_PASSWORD` | *(empty)* |
| `DB_NAME` | `nhl_db` |

The default port is 3308 because WAMP runs MySQL 8 on 3308 and MariaDB on 3306. On a standard MySQL install, set `DB_PORT=3306`. For example, in PowerShell:

```powershell
$env:DB_PORT = "3306"
$env:DB_PASSWORD = "your_password"
```

You don't need to create the database yourself. The loader notebook creates `nhl_db` if it doesn't exist and then runs `sql/create_tables.sql`.

### 4. Load the data

Open Jupyter from the `notebooks/` folder:

```bash
jupyter notebook
```

1. `01_explore_api.ipynb` (optional, about 1 minute) makes a sample call to each endpoint and shows the JSON structure the loader is built around.
2. `02_fetch_and_load.ipynb` calls the API in a loop and inserts into MySQL table by table: teams, standings, players, games, season stats, then game stats. The first run takes about 35-40 minutes, mostly the one boxscore call per finished game and the lookups for players missing from the current rosters. It ends with checks: row counts, orphan checks and re-inserting the same data (which should add 0 rows).

Re-running the loader is safe and quick (about 2 minutes). `INSERT IGNORE` skips rows that are already there, and the boxscore loop skips games that already have stats, so an interrupted run carries on where it stopped.

### 5. Start the dashboard

From the project root:

```bash
streamlit run app.py
```

## Dashboard pages

Navigation uses `streamlit-option-menu` in the sidebar.

| Page | What it shows |
|---|---|
| Home | KPI cards (teams, players, games played, goals) and season highlights (top scorer, best goalie, league leader) |
| Standings | Full league table with team logos, filtered by conference (`st.radio`) and division (`st.selectbox`) |
| Team Info | Pick a team (`st.selectbox`) to see its logo, conference, division and players grouped into forwards, defense and goalies |
| Player Search | Search by name (`st.text_input`), then see the headshot, bio and season stats as metric cards |
| Game Results | Filter games by date range (`st.date_input`), team and game state (Final / Upcoming) |
| Leaderboards | Tabs for top scorers, most penalty minutes, best save percentage and most wins |
| SQL Query | Dropdown of the 12 pre-built queries from `sql/queries.sql`; the results of the selected query are shown |

Filters are applied in SQL: each page builds its `WHERE` clause from only the filters the user picked, using parameterized queries. Invalid SQL, a stopped database server and empty results all show a clear message instead of an error trace.

## Analysis queries

`sql/queries.sql` contains 12 queries covering aggregations, JOINs, subqueries, GROUP BY, ORDER BY and HAVING:

1. Top point scorer on each team (correlated subquery)
2. Top 10 point scorers in the league
3. Goalies with the best save percentage (minimum 20 games)
4. Teams with the most wins
5. Teams with more points than the league average (subquery)
6. Divisions with an average of more than 90 points (GROUP BY + HAVING)
7. Skaters with more than 20 goals and more than 30 assists
8. Most penalty minutes
9. Goals for and goal differential by conference
10. Highest-scoring regular-season games
11. Teams with more home wins than road wins
12. Teams with at least 3 skaters scoring 25+ goals (GROUP BY + HAVING COUNT)
