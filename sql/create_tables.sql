-- NHL Analytics Hub - table definitions (MySQL 8)
-- Run against the nhl_db database. Parent tables come first so the foreign keys resolve.
-- MySQL needs FOREIGN KEY constraints as separate table-level clauses, not inline on the column.

CREATE TABLE IF NOT EXISTS teams (
    team_id          INT AUTO_INCREMENT,
    team_abbrev      VARCHAR(10)  NOT NULL,
    team_name        VARCHAR(100) NOT NULL,
    conference_name  VARCHAR(50),
    division_name    VARCHAR(50),
    logo_url         TEXT,
    PRIMARY KEY (team_id),
    UNIQUE KEY uq_team_abbrev (team_abbrev)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS standings (
    standing_id    INT AUTO_INCREMENT,
    team_id        INT         NOT NULL,
    season         VARCHAR(20) NOT NULL,
    games_played   INT,
    wins           INT,
    losses         INT,
    ot_losses      INT,
    points         INT,
    goals_for      INT,
    goals_against  INT,
    home_wins      INT,
    away_wins      INT,
    streak_type    VARCHAR(20),
    streak_count   INT,
    PRIMARY KEY (standing_id),
    UNIQUE KEY uq_standing (team_id, season),
    CONSTRAINT fk_standings_team FOREIGN KEY (team_id) REFERENCES teams (team_id)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS players (
    player_id       BIGINT       NOT NULL,
    team_id         INT,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    position        VARCHAR(10),
    jersey_number   INT,
    birth_date      DATE,
    birth_country   VARCHAR(10),
    height_cm       REAL,
    weight_kg       REAL,
    shoots_catches  VARCHAR(5),
    headshot_url    TEXT,
    PRIMARY KEY (player_id),
    CONSTRAINT fk_players_team FOREIGN KEY (team_id) REFERENCES teams (team_id)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS games (
    game_id       BIGINT      NOT NULL,
    season        VARCHAR(20) NOT NULL,
    game_type     INT         NOT NULL,
    game_date     DATE        NOT NULL,
    home_team_id  INT         NOT NULL,
    away_team_id  INT         NOT NULL,
    home_score    INT,
    away_score    INT,
    game_state    VARCHAR(20),
    venue_name    VARCHAR(150),
    PRIMARY KEY (game_id),
    CONSTRAINT fk_games_home_team FOREIGN KEY (home_team_id) REFERENCES teams (team_id),
    CONSTRAINT fk_games_away_team FOREIGN KEY (away_team_id) REFERENCES teams (team_id)
) ENGINE = InnoDB;

-- skaters only (forwards and defensemen)
CREATE TABLE IF NOT EXISTS game_stats (
    stat_id        INT AUTO_INCREMENT,
    game_id        BIGINT NOT NULL,
    player_id      BIGINT NOT NULL,
    team_id        INT    NOT NULL,
    goals          INT,
    assists        INT,
    points         INT,
    shots_on_goal  INT,
    penalty_min    INT,
    toi            VARCHAR(10),
    plus_minus     INT,
    PRIMARY KEY (stat_id),
    UNIQUE KEY uq_game_player (game_id, player_id),
    CONSTRAINT fk_game_stats_game   FOREIGN KEY (game_id)   REFERENCES games (game_id),
    CONSTRAINT fk_game_stats_player FOREIGN KEY (player_id) REFERENCES players (player_id),
    CONSTRAINT fk_game_stats_team   FOREIGN KEY (team_id)   REFERENCES teams (team_id)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS skater_season_stats (
    stat_id       INT AUTO_INCREMENT,
    player_id     BIGINT      NOT NULL,
    season        VARCHAR(20) NOT NULL,
    team_id       INT         NOT NULL,
    games_played  INT,
    goals         INT,
    assists       INT,
    points        INT,
    plus_minus    INT,
    penalty_min   INT,
    shots         INT,
    avg_toi       VARCHAR(10),
    PRIMARY KEY (stat_id),
    UNIQUE KEY uq_skater_season (player_id, season, team_id),
    CONSTRAINT fk_skater_stats_player FOREIGN KEY (player_id) REFERENCES players (player_id),
    CONSTRAINT fk_skater_stats_team   FOREIGN KEY (team_id)   REFERENCES teams (team_id)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS goalie_season_stats (
    stat_id            INT AUTO_INCREMENT,
    player_id          BIGINT      NOT NULL,
    season             VARCHAR(20) NOT NULL,
    team_id            INT         NOT NULL,
    games_played       INT,
    wins               INT,
    losses             INT,
    ot_losses          INT,
    save_pct           FLOAT,
    goals_against_avg  FLOAT,
    shutouts           INT,
    saves              INT,
    PRIMARY KEY (stat_id),
    UNIQUE KEY uq_goalie_season (player_id, season, team_id),
    CONSTRAINT fk_goalie_stats_player FOREIGN KEY (player_id) REFERENCES players (player_id),
    CONSTRAINT fk_goalie_stats_team   FOREIGN KEY (team_id)   REFERENCES teams (team_id)
) ENGINE = InnoDB;
