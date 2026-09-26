-- NHL Analytics Hub - analysis queries (MySQL 8, database nhl_db)
-- Season: 2025-26 regular season. Each query answers one business question.
-- A player traded mid-season has one season-stats row per team, so league-wide
-- player totals are summed per player.


-- 1. Who is the top point scorer on each team?
--    (JOIN + correlated subquery)
SELECT t.team_name, p.first_name, p.last_name, ss.goals, ss.assists, ss.points
FROM skater_season_stats ss
JOIN players p ON ss.player_id = p.player_id
JOIN teams t ON ss.team_id = t.team_id
WHERE ss.points = (
    SELECT MAX(ss2.points)
    FROM skater_season_stats ss2
    WHERE ss2.team_id = ss.team_id
)
ORDER BY ss.points DESC, t.team_name;


-- 2. Who are the top 10 point scorers across the league?
--    (JOIN + aggregation + GROUP BY + ORDER BY)
SELECT p.first_name, p.last_name,
       GROUP_CONCAT(t.team_abbrev SEPARATOR '/') AS teams,
       SUM(ss.games_played) AS games_played,
       SUM(ss.goals) AS goals,
       SUM(ss.assists) AS assists,
       SUM(ss.points) AS points
FROM skater_season_stats ss
JOIN players p ON ss.player_id = p.player_id
JOIN teams t ON ss.team_id = t.team_id
GROUP BY p.player_id, p.first_name, p.last_name
ORDER BY points DESC, goals DESC
LIMIT 10;


-- 3. Which goalies have the best save percentage (minimum 20 games played)?
--    (JOIN + WHERE + ORDER BY)
SELECT p.first_name, p.last_name, t.team_abbrev, gs.games_played, gs.wins,
       ROUND(gs.save_pct, 3) AS save_pct,
       ROUND(gs.goals_against_avg, 2) AS goals_against_avg,
       gs.shutouts
FROM goalie_season_stats gs
JOIN players p ON gs.player_id = p.player_id
JOIN teams t ON gs.team_id = t.team_id
WHERE gs.games_played >= 20
ORDER BY gs.save_pct DESC
LIMIT 10;


-- 4. Which teams have the most wins?
--    (JOIN + ORDER BY)
SELECT t.team_name, t.conference_name, s.games_played, s.wins, s.losses, s.ot_losses, s.points
FROM standings s
JOIN teams t ON s.team_id = t.team_id
ORDER BY s.wins DESC, s.points DESC
LIMIT 10;


-- 5. Which teams finished with more points than the league average?
--    (subquery)
SELECT t.team_name, t.division_name, s.points,
       ROUND((SELECT AVG(points) FROM standings), 1) AS league_avg_points
FROM standings s
JOIN teams t ON s.team_id = t.team_id
WHERE s.points > (SELECT AVG(points) FROM standings)
ORDER BY s.points DESC;


-- 6. Which divisions have an average team points total above 90?
--    (GROUP BY + HAVING)
SELECT t.division_name,
       COUNT(*) AS teams,
       ROUND(AVG(s.points), 1) AS avg_points,
       MAX(s.points) AS best_team_points
FROM standings s
JOIN teams t ON s.team_id = t.team_id
GROUP BY t.division_name
HAVING AVG(s.points) > 90
ORDER BY avg_points DESC;


-- 7. Which skaters scored more than 20 goals and recorded more than 30 assists?
--    (WHERE with multiple conditions)
SELECT p.first_name, p.last_name, t.team_abbrev, ss.goals, ss.assists, ss.points
FROM skater_season_stats ss
JOIN players p ON ss.player_id = p.player_id
JOIN teams t ON ss.team_id = t.team_id
WHERE ss.goals > 20 AND ss.assists > 30
ORDER BY ss.points DESC;


-- 8. Which players spent the most time in the penalty box?
--    (JOIN + aggregation + ORDER BY + LIMIT)
SELECT p.first_name, p.last_name, p.position,
       SUM(ss.games_played) AS games_played,
       SUM(ss.penalty_min) AS penalty_min
FROM skater_season_stats ss
JOIN players p ON ss.player_id = p.player_id
GROUP BY p.player_id, p.first_name, p.last_name, p.position
ORDER BY penalty_min DESC
LIMIT 10;


-- 9. How do the two conferences compare on goals scored and goal differential?
--    (aggregation + GROUP BY)
SELECT t.conference_name,
       SUM(s.goals_for) AS goals_for,
       SUM(s.goals_against) AS goals_against,
       SUM(s.goals_for) - SUM(s.goals_against) AS goal_differential,
       ROUND(AVG(s.goals_for), 1) AS avg_goals_per_team
FROM standings s
JOIN teams t ON s.team_id = t.team_id
GROUP BY t.conference_name
ORDER BY goals_for DESC;


-- 10. What were the highest-scoring regular-season games?
--     (teams joined twice for home and away + ORDER BY)
SELECT g.game_date, ht.team_name AS home_team, g.home_score,
       at.team_name AS away_team, g.away_score,
       g.home_score + g.away_score AS total_goals, g.venue_name
FROM games g
JOIN teams ht ON g.home_team_id = ht.team_id
JOIN teams at ON g.away_team_id = at.team_id
WHERE g.game_type = 2 AND g.game_state IN ('OFF', 'FINAL')
ORDER BY total_goals DESC, g.game_date
LIMIT 10;


-- 11. Which teams relied most on home ice (more home wins than road wins)?
--     (calculated column + WHERE + ORDER BY)
SELECT t.team_name, s.home_wins, s.away_wins,
       s.home_wins - s.away_wins AS home_advantage
FROM standings s
JOIN teams t ON s.team_id = t.team_id
WHERE s.home_wins > s.away_wins
ORDER BY home_advantage DESC, s.home_wins DESC;


-- 12. Which teams had at least 3 skaters score 25 or more goals?
--     (GROUP BY + HAVING COUNT)
SELECT t.team_name,
       COUNT(*) AS skaters_with_25_goals,
       GROUP_CONCAT(CONCAT(p.last_name, ' (', ss.goals, ')') ORDER BY ss.goals DESC SEPARATOR ', ') AS scorers
FROM skater_season_stats ss
JOIN players p ON ss.player_id = p.player_id
JOIN teams t ON ss.team_id = t.team_id
WHERE ss.goals >= 25
GROUP BY t.team_id, t.team_name
HAVING COUNT(*) >= 3
ORDER BY skaters_with_25_goals DESC, t.team_name;
