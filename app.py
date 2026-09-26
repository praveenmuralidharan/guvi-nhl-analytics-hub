import os
import re
from pathlib import Path

import pandas as pd
import pymysql
import streamlit as st
from streamlit_option_menu import option_menu

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3308")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "nhl_db"),
}
QUERIES_FILE = Path(__file__).parent / "sql" / "queries.sql"

GAME_STATES = {"Final": ("OFF", "FINAL"), "Upcoming": ("FUT",)}
STATE_LABELS = {"OFF": "Final", "FINAL": "Final", "FUT": "Upcoming", "LIVE": "In Progress", "CRIT": "In Progress"}
MIN_GOALIE_GAMES = 20

st.set_page_config(page_title="NHL Analytics Hub", layout="wide")


# ---------- database helpers ----------

def get_connection():
    return pymysql.connect(**DB_CONFIG, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def run_query(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columns = [col[0] for col in cur.description] if cur.description else []
            return pd.DataFrame(cur.fetchall(), columns=columns)
    finally:
        conn.close()


def get_data(sql, params=None):
    """Runs a query and shows a readable message instead of a traceback if it fails."""
    try:
        return run_query(sql, params)
    except pymysql.err.OperationalError as err:
        if err.args and err.args[0] == 2003:
            st.error(f"Could not connect to MySQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}. "
                     "Make sure the database server (WAMP) is running.")
        else:
            st.error(f"SQL error: {err.args[-1] if err.args else err}")
    except pymysql.MySQLError as err:
        st.error(f"SQL error: {err.args[-1] if err.args else err}")
    return None


def show_table(df, empty_message="No data found for the selected filters.", **kwargs):
    if df is None:
        return
    if df.empty:
        st.warning(empty_message)
        return
    st.dataframe(df, hide_index=True, **kwargs)


def load_queries(path):
    # each query in queries.sql starts with a numbered comment like "-- 1. Who is ...?"
    queries, title, lines = {}, None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if re.match(r"--\s*\d+\.\s", line):
            title, lines = line.lstrip("- ").strip(), []
        elif title and not line.strip().startswith("--"):
            lines.append(line)
            if line.rstrip().endswith(";"):
                queries[title] = "\n".join(lines).strip().rstrip(";")
                title = None
    return queries


def kpi_card(label, value, caption=None):
    with st.container(border=True):
        st.metric(label, value)
        if caption:
            st.caption(caption)


def team_names():
    df = get_data("SELECT team_name FROM teams ORDER BY team_name")
    return [] if df is None else df["team_name"].tolist()


# ---------- pages ----------

def home_page():
    st.title("NHL Analytics Hub")
    st.caption("2025-26 NHL season, built from the official NHL public API")

    totals = get_data("""
        SELECT (SELECT COUNT(*) FROM teams) AS teams,
               (SELECT COUNT(*) FROM players) AS players,
               (SELECT COUNT(*) FROM games WHERE game_state IN ('OFF', 'FINAL')) AS games,
               (SELECT SUM(goals_for) FROM standings) AS goals
    """)
    if totals is None or totals.empty:
        return
    row = totals.iloc[0]

    cols = st.columns(4)
    with cols[0]:
        kpi_card("Teams", int(row["teams"]))
    with cols[1]:
        kpi_card("Players", f"{int(row['players']):,}")
    with cols[2]:
        kpi_card("Games Played", f"{int(row['games']):,}", "Preseason, regular season and playoffs")
    with cols[3]:
        kpi_card("Goals Scored", f"{int(row['goals'] or 0):,}", "Regular season, all teams")

    st.subheader("Season highlights")
    top_scorer = get_data("""
        SELECT CONCAT(p.first_name, ' ', p.last_name) AS player, SUM(ss.points) AS points,
               SUM(ss.goals) AS goals, SUM(ss.assists) AS assists
        FROM skater_season_stats ss
        JOIN players p ON ss.player_id = p.player_id
        GROUP BY p.player_id, p.first_name, p.last_name
        ORDER BY points DESC, goals DESC
        LIMIT 1
    """)
    best_goalie = get_data("""
        SELECT CONCAT(p.first_name, ' ', p.last_name) AS player, t.team_abbrev,
               gs.save_pct, gs.games_played
        FROM goalie_season_stats gs
        JOIN players p ON gs.player_id = p.player_id
        JOIN teams t ON gs.team_id = t.team_id
        WHERE gs.games_played >= %s
        ORDER BY gs.save_pct DESC
        LIMIT 1
    """, [MIN_GOALIE_GAMES])
    leader = get_data("""
        SELECT t.team_name, s.points, s.wins, s.losses, s.ot_losses
        FROM standings s
        JOIN teams t ON s.team_id = t.team_id
        ORDER BY s.points DESC, s.wins DESC
        LIMIT 1
    """)

    cols = st.columns(3)
    with cols[0]:
        if top_scorer is not None and not top_scorer.empty:
            p = top_scorer.iloc[0]
            kpi_card("Top Scorer", p["player"],
                     f"{int(p['points'])} points ({int(p['goals'])} G, {int(p['assists'])} A)")
    with cols[1]:
        if best_goalie is not None and not best_goalie.empty:
            g = best_goalie.iloc[0]
            kpi_card("Best Goalie", g["player"],
                     f"{g['save_pct']:.3f} save % in {int(g['games_played'])} games ({g['team_abbrev']})")
    with cols[2]:
        if leader is not None and not leader.empty:
            t = leader.iloc[0]
            kpi_card("League Leader", t["team_name"],
                     f"{int(t['points'])} points ({int(t['wins'])}-{int(t['losses'])}-{int(t['ot_losses'])})")


def standings_page():
    st.title("Standings")

    col1, col2 = st.columns(2)
    with col1:
        conference = st.radio("Conference", ["All", "Eastern", "Western"], horizontal=True)
    with col2:
        if conference == "All":
            divisions = get_data("SELECT DISTINCT division_name FROM teams ORDER BY division_name")
        else:
            divisions = get_data("SELECT DISTINCT division_name FROM teams WHERE conference_name = %s "
                                 "ORDER BY division_name", [conference])
        if divisions is None:
            return
        division = st.selectbox("Division", ["All"] + divisions["division_name"].tolist())

    conditions, params = [], []
    if conference != "All":
        conditions.append("t.conference_name = %s")
        params.append(conference)
    if division != "All":
        conditions.append("t.division_name = %s")
        params.append(division)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    df = get_data(f"""
        SELECT RANK() OVER (ORDER BY s.points DESC, s.wins DESC) AS `Rank`,
               t.logo_url AS Logo, t.team_name AS Team, t.conference_name AS Conference,
               t.division_name AS Division, s.games_played AS GP, s.wins AS W, s.losses AS L,
               s.ot_losses AS OTL, s.points AS PTS, s.goals_for AS GF, s.goals_against AS GA,
               s.goals_for - s.goals_against AS DIFF, s.home_wins AS `Home W`, s.away_wins AS `Away W`,
               CONCAT(s.streak_type, s.streak_count) AS Streak
        FROM standings s
        JOIN teams t ON s.team_id = t.team_id
        {where}
        ORDER BY s.points DESC, s.wins DESC
    """, params)
    show_table(df, column_config={"Logo": st.column_config.ImageColumn("", width="small")}, height=38 * 33)


def team_page():
    st.title("Team Info")
    names = team_names()
    if not names:
        st.warning("No teams found in the database.")
        return
    team = st.selectbox("Choose a team", names)

    info = get_data("""
        SELECT team_id, team_name, team_abbrev, conference_name, division_name, logo_url
        FROM teams
        WHERE team_name = %s
    """, [team])
    if info is None or info.empty:
        st.warning("Team not found.")
        return
    t = info.iloc[0]

    col1, col2 = st.columns([1, 4])
    with col1:
        if t["logo_url"]:
            st.image(t["logo_url"], width=140)
    with col2:
        st.header(f"{t['team_name']} ({t['team_abbrev']})")
        st.write(f"{t['conference_name']} Conference, {t['division_name']} Division")

    roster = get_data("""
        SELECT headshot_url AS Photo, jersey_number AS `#`,
               CONCAT(first_name, ' ', last_name) AS Player, position AS Pos,
               shoots_catches AS `Shoots/Catches`, height_cm AS `Height (cm)`, weight_kg AS `Weight (kg)`,
               birth_date AS Born, birth_country AS Country
        FROM players
        WHERE team_id = %s
        ORDER BY jersey_number IS NULL, jersey_number
    """, [int(t["team_id"])])
    if roster is None:
        return
    if roster.empty:
        st.warning("No players found for this team.")
        return

    st.caption("Players linked to this team, including those who played for it in 2025-26.")
    photo = {"Photo": st.column_config.ImageColumn("", width="small")}
    for label, positions in [("Forwards", ["C", "LW", "RW"]), ("Defense", ["D"]), ("Goalies", ["G"])]:
        group = roster[roster["Pos"].isin(positions)]
        st.subheader(f"{label} ({len(group)})")
        show_table(group, f"No {label.lower()} listed.", column_config=photo)


def player_page():
    st.title("Player Search")
    search = st.text_input("Search by player name", placeholder="e.g. MacKinnon or Connor").strip()
    if not search:
        st.info("Type part of a first or last name to find a player.")
        return

    matches = get_data("""
        SELECT p.player_id, CONCAT(p.first_name, ' ', p.last_name) AS player, p.position,
               COALESCE(t.team_abbrev, '-') AS team
        FROM players p
        LEFT JOIN teams t ON p.team_id = t.team_id
        WHERE CONCAT(p.first_name, ' ', p.last_name) LIKE %s
        ORDER BY p.last_name, p.first_name
        LIMIT 50
    """, [f"%{search}%"])
    if matches is None:
        return
    if matches.empty:
        st.warning(f"No players found matching \"{search}\".")
        return

    options = {f"{m.player} ({m.position}, {m.team})": int(m.player_id) for m in matches.itertuples()}
    player_id = options[st.selectbox(f"{len(matches)} player(s) found", list(options))]

    info = get_data("""
        SELECT p.*, t.team_name
        FROM players p
        LEFT JOIN teams t ON p.team_id = t.team_id
        WHERE p.player_id = %s
    """, [player_id])
    if info is None or info.empty:
        return
    p = info.iloc[0]

    col1, col2 = st.columns([1, 4])
    with col1:
        if p["headshot_url"]:
            st.image(p["headshot_url"], width=150)
    with col2:
        number = f"#{int(p['jersey_number'])} " if pd.notna(p["jersey_number"]) else ""
        st.header(f"{number}{p['first_name']} {p['last_name']}")
        st.write(f"{p['position']} | {p['team_name'] or 'No team'}")
        details = [
            f"Born {p['birth_date']}" if p["birth_date"] else None,
            p["birth_country"],
            f"{p['height_cm']:.0f} cm" if pd.notna(p["height_cm"]) else None,
            f"{p['weight_kg']:.0f} kg" if pd.notna(p["weight_kg"]) else None,
            f"Shoots/Catches: {p['shoots_catches']}" if p["shoots_catches"] else None,
        ]
        st.caption(" | ".join(d for d in details if d))

    st.subheader("2025-26 regular season")
    if p["position"] == "G":
        stats = get_data("""
            SELECT t.team_abbrev AS Team, gs.games_played AS GP, gs.wins AS W, gs.losses AS L,
                   gs.ot_losses AS OTL, ROUND(gs.save_pct, 3) AS `SV%%`,
                   ROUND(gs.goals_against_avg, 2) AS GAA, gs.shutouts AS SO, gs.saves AS Saves
            FROM goalie_season_stats gs
            JOIN teams t ON gs.team_id = t.team_id
            WHERE gs.player_id = %s
        """, [player_id])
        if stats is None:
            return
        if stats.empty:
            st.warning("No 2025-26 regular-season stats found for this player.")
            return
        shots_faced = (stats["Saves"] / stats["SV%"]).sum()
        cards = [("Games", int(stats["GP"].sum())), ("Wins", int(stats["W"].sum())),
                 ("Save %", f"{stats['Saves'].sum() / shots_faced:.3f}" if shots_faced else "-"),
                 ("Shutouts", int(stats["SO"].sum())), ("Saves", f"{int(stats['Saves'].sum()):,}")]
    else:
        stats = get_data("""
            SELECT t.team_abbrev AS Team, ss.games_played AS GP, ss.goals AS G, ss.assists AS A,
                   ss.points AS PTS, ss.plus_minus AS `+/-`, ss.penalty_min AS PIM,
                   ss.shots AS Shots, ss.avg_toi AS `Avg TOI`
            FROM skater_season_stats ss
            JOIN teams t ON ss.team_id = t.team_id
            WHERE ss.player_id = %s
        """, [player_id])
        if stats is None:
            return
        if stats.empty:
            st.warning("No 2025-26 regular-season stats found for this player.")
            return
        cards = [("Games", int(stats["GP"].sum())), ("Goals", int(stats["G"].sum())),
                 ("Assists", int(stats["A"].sum())), ("Points", int(stats["PTS"].sum())),
                 ("+/-", int(stats["+/-"].sum()))]

    for col, (label, value) in zip(st.columns(len(cards)), cards):
        with col:
            kpi_card(label, value)
    show_table(stats)


def games_page():
    st.title("Game Results")

    bounds = get_data("SELECT MIN(game_date) AS first_day, MAX(game_date) AS last_day FROM games")
    if bounds is None or bounds.empty or pd.isna(bounds.iloc[0]["first_day"]):
        st.warning("No games found in the database.")
        return
    first_day, last_day = bounds.iloc[0]["first_day"], bounds.iloc[0]["last_day"]

    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        dates = st.date_input("Date range", value=(first_day, last_day),
                              min_value=first_day, max_value=last_day)
    with col2:
        team = st.selectbox("Team", ["All teams"] + team_names())
    with col3:
        state = st.radio("Game state", ["All", "Final", "Upcoming"], horizontal=True)

    conditions, params = [], []
    if isinstance(dates, (list, tuple)) and len(dates) == 2:
        conditions.append("g.game_date BETWEEN %s AND %s")
        params += [dates[0], dates[1]]
    elif isinstance(dates, (list, tuple)) and len(dates) == 1:
        conditions.append("g.game_date = %s")
        params.append(dates[0])
    if team != "All teams":
        conditions.append("(ht.team_name = %s OR at.team_name = %s)")
        params += [team, team]
    if state != "All":
        states = GAME_STATES[state]
        conditions.append(f"g.game_state IN ({', '.join(['%s'] * len(states))})")
        params += list(states)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    df = get_data(f"""
        SELECT g.game_date AS Date,
               CASE g.game_type WHEN 1 THEN 'Preseason' WHEN 2 THEN 'Regular season'
                                WHEN 3 THEN 'Playoffs' ELSE 'Other' END AS Type,
               at.team_name AS Away, g.away_score AS `Away Score`,
               g.home_score AS `Home Score`, ht.team_name AS Home,
               g.game_state AS Status, g.venue_name AS Venue
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.team_id
        JOIN teams at ON g.away_team_id = at.team_id
        {where}
        ORDER BY g.game_date DESC, g.game_id DESC
    """, params)
    if df is not None and not df.empty:
        df["Status"] = df["Status"].map(STATE_LABELS).fillna(df["Status"])
    show_table(df, "No games found for the selected filters.")


def leaderboards_page():
    st.title("Leaderboards")
    st.caption("2025-26 regular season. Players traded mid-season are totalled across teams.")

    skater_board = """
        SELECT CONCAT(p.first_name, ' ', p.last_name) AS Player, p.position AS Pos,
               GROUP_CONCAT(t.team_abbrev SEPARATOR '/') AS Team,
               SUM(ss.games_played) AS GP, SUM(ss.goals) AS G, SUM(ss.assists) AS A,
               SUM(ss.points) AS PTS, SUM(ss.penalty_min) AS PIM
        FROM skater_season_stats ss
        JOIN players p ON ss.player_id = p.player_id
        JOIN teams t ON ss.team_id = t.team_id
        GROUP BY p.player_id, p.first_name, p.last_name, p.position
        ORDER BY {order}
        LIMIT 10
    """
    goalie_board = """
        SELECT CONCAT(p.first_name, ' ', p.last_name) AS Player, t.team_abbrev AS Team,
               gs.games_played AS GP, gs.wins AS W, gs.losses AS L, gs.ot_losses AS OTL,
               ROUND(gs.save_pct, 3) AS `SV%%`, ROUND(gs.goals_against_avg, 2) AS GAA, gs.shutouts AS SO
        FROM goalie_season_stats gs
        JOIN players p ON gs.player_id = p.player_id
        JOIN teams t ON gs.team_id = t.team_id
        WHERE gs.games_played >= %s
        ORDER BY {order}
        LIMIT 10
    """

    tabs = st.tabs(["Top Scorers", "Most Penalty Minutes", "Best Save %", "Most Wins"])
    with tabs[0]:
        show_table(get_data(skater_board.format(order="PTS DESC, G DESC")))
    with tabs[1]:
        show_table(get_data(skater_board.format(order="PIM DESC, GP ASC")))
    with tabs[2]:
        st.caption(f"Minimum {MIN_GOALIE_GAMES} games played")
        show_table(get_data(goalie_board.format(order="gs.save_pct DESC"), [MIN_GOALIE_GAMES]))
    with tabs[3]:
        show_table(get_data(goalie_board.format(order="gs.wins DESC, gs.save_pct DESC"), [0]))


def sql_page():
    st.title("SQL Query")

    queries = load_queries(QUERIES_FILE)
    if not queries:
        st.error(f"No queries found in {QUERIES_FILE.name}.")
        return
    choice = st.selectbox("Pick a pre-built query", list(queries))
    show_table(get_data(queries[choice]), "The query ran but returned no rows.")


PAGES = {
    "Home": home_page,
    "Standings": standings_page,
    "Team Info": team_page,
    "Player Search": player_page,
    "Game Results": games_page,
    "Leaderboards": leaderboards_page,
    "SQL Query": sql_page,
}

with st.sidebar:
    page = option_menu(
        "NHL Analytics Hub",
        list(PAGES),
        icons=["house", "list-ol", "people", "search", "calendar-event", "trophy", "code-square"],
        menu_icon="snow",
        default_index=0,
    )

PAGES[page]()
