# Leaderboard Benchmark Upgrade Plan

> **For Cline or Hermes:** Four files, implement in order. Each task is a self-contained commit.

---

## Goal

Transform the boring W/L table into a genuine model benchmark. For each model, capture
six dimensions of play style and surface them as visual stat bars on cards. Keep a
traditional table view as a toggle.

**Six dimensions:**

| Dimension | Formula | What it reveals |
|---|---|---|
| 💥 **Aggression** | blocks / game | Contact sport or running game? |
| 🎲 **Recklessness** | turnovers / game | Overcautious or overreaching? |
| 🎯 **Ball Craft** | (pass_completions + pickup_successes) / game | Executes the actual objective? |
| ⚔️ **Lethality** | casualties / game | How dangerous are its blocks? |
| 💬 **Verbosity** | avg strategy message length (chars) | Chatty overthinker or terse? |
| ⚡ **Efficiency** | goals_for per game ÷ max(turnovers per game, 0.5) | Did the risks pay off? |

**Target leaderboard layout:**

```
[📊 Cards]  [📋 Table]          ← view toggle

┌────────────────────────────────────────────┐
│ qwen3.6-plus-preview          3W · 1L · 0D │
│                          GD +4 · 7 scored  │
├────────────────────────────────────────────┤
│ 💥 Aggression   ████████░░  3.2 / game     │
│ 🎲 Recklessness ████░░░░░░  1.4 / game     │
│ 🎯 Ball Craft   ██████░░░░  2.1 / game     │
│ ⚔️ Lethality    ███████░░░  1.8 / game     │
│ 💬 Verbosity    ████░░░░░░  68 chars/msg   │
│ ⚡ Efficiency   █████████░  4.6 ratio      │
└────────────────────────────────────────────┘
```

Bars are normalised relative to the highest value across all models (so the best model
always fills the bar; others are shown proportionally).

---

## Architecture

Four files:

```
app/models/leaderboard.py       — add fields to GameResult + ModelLeaderboardEntry
app/state/game_manager.py       — capture extra stats at record time
app/state/leaderboard_store.py  — aggregate new fields
app/web/templates/leaderboard.html — full UI redesign with cards + table toggle
```

---

## Task 1: Extend `GameResult` and `ModelLeaderboardEntry`

**File:** `app/models/leaderboard.py`

**Replace the entire file with:**

```python
"""Leaderboard data models."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, computed_field


class GameResult(BaseModel):
    """One completed match result written to data/results.jsonl."""
    game_id: str
    played_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Teams and models
    team1_name: str
    team1_model: str = "unknown"
    team1_score: int
    team2_name: str
    team2_model: str = "unknown"
    team2_score: int
    winner_model: Optional[str] = None   # None = draw
    winner_team: Optional[str] = None    # None = draw

    # Combat stats
    team1_casualties: int = 0
    team2_casualties: int = 0
    team1_blocks: int = 0
    team2_blocks: int = 0

    # Ball-handling stats
    team1_passes_attempted: int = 0
    team2_passes_attempted: int = 0
    team1_passes_completed: int = 0
    team2_passes_completed: int = 0
    team1_pickups_attempted: int = 0
    team2_pickups_attempted: int = 0
    team1_pickups_succeeded: int = 0
    team2_pickups_succeeded: int = 0

    # Risk stats
    team1_turnovers: int = 0
    team2_turnovers: int = 0
    team1_failed_dodges: int = 0
    team2_failed_dodges: int = 0

    # Strategy message stats (verbosity proxy)
    team1_messages_sent: int = 0
    team2_messages_sent: int = 0
    team1_total_message_chars: int = 0
    team2_total_message_chars: int = 0


class ModelLeaderboardEntry(BaseModel):
    """Aggregated stats for one model across all games."""
    model_id: str

    # Results
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    goals_for: int = 0
    goals_against: int = 0
    score_diff: int = 0

    # Raw accumulated counts
    casualties_caused: int = 0
    blocks_thrown: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    pickups_attempted: int = 0
    pickups_succeeded: int = 0
    turnovers: int = 0
    failed_dodges: int = 0
    messages_sent: int = 0
    total_message_chars: int = 0

    # ── Computed per-game rates ────────────────────────────────────────────

    @computed_field
    @property
    def win_pct(self) -> float:
        return round(self.wins / self.games, 3) if self.games else 0.0

    @computed_field
    @property
    def aggression(self) -> float:
        """Blocks thrown per game."""
        return round(self.blocks_thrown / self.games, 2) if self.games else 0.0

    @computed_field
    @property
    def recklessness(self) -> float:
        """Turnovers per game."""
        return round(self.turnovers / self.games, 2) if self.games else 0.0

    @computed_field
    @property
    def ball_craft(self) -> float:
        """Successful passes + pickups per game."""
        return round(
            (self.passes_completed + self.pickups_succeeded) / self.games, 2
        ) if self.games else 0.0

    @computed_field
    @property
    def lethality(self) -> float:
        """Casualties caused per game."""
        return round(self.casualties_caused / self.games, 2) if self.games else 0.0

    @computed_field
    @property
    def verbosity(self) -> float:
        """Average strategy message length in characters."""
        return round(self.total_message_chars / self.messages_sent, 1) if self.messages_sent else 0.0

    @computed_field
    @property
    def efficiency(self) -> float:
        """Goals per game divided by turnover rate (higher = scoring despite turnovers)."""
        if not self.games:
            return 0.0
        gf_per_game = self.goals_for / self.games
        to_per_game = self.turnovers / self.games
        return round(gf_per_game / max(to_per_game, 0.5), 2)

    @computed_field
    @property
    def pass_completion_pct(self) -> float:
        """Pass completion percentage (0–100)."""
        return round(
            100 * self.passes_completed / self.passes_attempted, 1
        ) if self.passes_attempted else 0.0


class TeamLeaderboardEntry(BaseModel):
    """Aggregated stats for one team name across all games."""
    team_name: str
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    goals_for: int = 0
    goals_against: int = 0
    score_diff: int = 0


class LeaderboardResponse(BaseModel):
    """Response shape for GET /leaderboard."""
    total_games: int
    by_model: list[ModelLeaderboardEntry]
    by_team: list[TeamLeaderboardEntry]
```

**Commit:** `feat(leaderboard): extend GameResult + ModelLeaderboardEntry with benchmark stats`

---

## Task 2: Capture extra stats in `_record_result_if_concluded`

**File:** `app/state/game_manager.py`

**Find `_record_result_if_concluded`. Replace the stats extraction block:**

Find:
```python
        # Pull casualties + turnovers from StatisticsAggregator
        from app.game.statistics import StatisticsAggregator
        try:
            stats = StatisticsAggregator(game_state).aggregate()
            t1_stats = stats.team_stats.get(game_state.team1.id)
            t2_stats = stats.team_stats.get(game_state.team2.id)
            t1_casualties = t1_stats.casualties_caused if t1_stats else 0
            t2_casualties = t2_stats.casualties_caused if t2_stats else 0
            t1_turnovers = t1_stats.turnovers if t1_stats else 0
            t2_turnovers = t2_stats.turnovers if t2_stats else 0
        except Exception:
            t1_casualties = t2_casualties = t1_turnovers = t2_turnovers = 0
```

Replace with:
```python
        # Pull stats from StatisticsAggregator
        from app.game.statistics import StatisticsAggregator
        t1_casualties = t2_casualties = 0
        t1_blocks = t2_blocks = 0
        t1_passes_attempted = t2_passes_attempted = 0
        t1_passes_completed = t2_passes_completed = 0
        t1_pickups_attempted = t2_pickups_attempted = 0
        t1_pickups_succeeded = t2_pickups_succeeded = 0
        t1_turnovers = t2_turnovers = 0
        t1_failed_dodges = t2_failed_dodges = 0
        try:
            stats = StatisticsAggregator(game_state).aggregate()
            t1_stats = stats.team_stats.get(game_state.team1.id)
            t2_stats = stats.team_stats.get(game_state.team2.id)
            if t1_stats:
                t1_casualties        = t1_stats.casualties_caused
                t1_blocks            = t1_stats.blocks_thrown
                t1_passes_attempted  = t1_stats.passes_attempted
                t1_passes_completed  = t1_stats.passes_completed
                t1_pickups_attempted = t1_stats.pickups_attempted
                t1_pickups_succeeded = t1_stats.pickups_succeeded
                t1_turnovers         = t1_stats.turnovers
                t1_failed_dodges     = t1_stats.failed_dodges
            if t2_stats:
                t2_casualties        = t2_stats.casualties_caused
                t2_blocks            = t2_stats.blocks_thrown
                t2_passes_attempted  = t2_stats.passes_attempted
                t2_passes_completed  = t2_stats.passes_completed
                t2_pickups_attempted = t2_stats.pickups_attempted
                t2_pickups_succeeded = t2_stats.pickups_succeeded
                t2_turnovers         = t2_stats.turnovers
                t2_failed_dodges     = t2_stats.failed_dodges
        except Exception as exc:
            logger.warning("Failed to extract stats for leaderboard: %s", exc)

        # Pull message verbosity stats
        t1_messages_sent = t2_messages_sent = 0
        t1_total_message_chars = t2_total_message_chars = 0
        try:
            for msg in game_state.messages:
                # Only count team strategy messages, not referee commentary
                if msg.sender_id == game_state.team1.id:
                    t1_messages_sent += 1
                    t1_total_message_chars += len(msg.content)
                elif msg.sender_id == game_state.team2.id:
                    t2_messages_sent += 1
                    t2_total_message_chars += len(msg.content)
        except Exception as exc:
            logger.warning("Failed to extract message stats for leaderboard: %s", exc)
```

**Then find the `GameResult(...)` construction. Replace it with:**

```python
        from app.models.leaderboard import GameResult
        result = GameResult(
            game_id=game_state.game_id,
            team1_name=game_state.team1.name,
            team1_model=game_state.team1_model or "unknown",
            team1_score=t1_score,
            team2_name=game_state.team2.name,
            team2_model=game_state.team2_model or "unknown",
            team2_score=t2_score,
            winner_model=winner_model,
            winner_team=winner_team,
            team1_casualties=t1_casualties,
            team2_casualties=t2_casualties,
            team1_blocks=t1_blocks,
            team2_blocks=t2_blocks,
            team1_passes_attempted=t1_passes_attempted,
            team2_passes_attempted=t2_passes_attempted,
            team1_passes_completed=t1_passes_completed,
            team2_passes_completed=t2_passes_completed,
            team1_pickups_attempted=t1_pickups_attempted,
            team2_pickups_attempted=t2_pickups_attempted,
            team1_pickups_succeeded=t1_pickups_succeeded,
            team2_pickups_succeeded=t2_pickups_succeeded,
            team1_turnovers=t1_turnovers,
            team2_turnovers=t2_turnovers,
            team1_failed_dodges=t1_failed_dodges,
            team2_failed_dodges=t2_failed_dodges,
            team1_messages_sent=t1_messages_sent,
            team2_messages_sent=t2_messages_sent,
            team1_total_message_chars=t1_total_message_chars,
            team2_total_message_chars=t2_total_message_chars,
        )
```

**Commit:** `feat(leaderboard): capture blocks, passes, pickups, dodges, message verbosity`

---

## Task 3: Aggregate new fields in `LeaderboardStore`

**File:** `app/state/leaderboard_store.py`

**Find the model aggregation loop inside `get_leaderboard()`:**

```python
            for model_id, score_for, score_against, casualties, turnovers, outcome in [
                (r.team1_model, r.team1_score, r.team2_score, r.team1_casualties, r.team1_turnovers, t1_outcome),
                (r.team2_model, r.team2_score, r.team1_score, r.team2_casualties, r.team2_turnovers, t2_outcome),
            ]:
                if model_id not in model_map:
                    model_map[model_id] = ModelLeaderboardEntry(model_id=model_id)
                entry = model_map[model_id]
                entry.games += 1
                entry.goals_for += score_for
                entry.goals_against += score_against
                entry.score_diff += score_for - score_against
                entry.casualties_caused += casualties
                entry.turnovers += turnovers
                if outcome == "win":
                    entry.wins += 1
                elif outcome == "loss":
                    entry.losses += 1
                else:
                    entry.draws += 1
```

**Replace with:**

```python
            for (model_id, score_for, score_against, outcome,
                 casualties, blocks,
                 passes_att, passes_comp,
                 pickups_att, pickups_succ,
                 turnovers, failed_dodges,
                 messages_sent, total_message_chars) in [
                (
                    r.team1_model, r.team1_score, r.team2_score, t1_outcome,
                    r.team1_casualties, r.team1_blocks,
                    r.team1_passes_attempted, r.team1_passes_completed,
                    r.team1_pickups_attempted, r.team1_pickups_succeeded,
                    r.team1_turnovers, r.team1_failed_dodges,
                    r.team1_messages_sent, r.team1_total_message_chars,
                ),
                (
                    r.team2_model, r.team2_score, r.team1_score, t2_outcome,
                    r.team2_casualties, r.team2_blocks,
                    r.team2_passes_attempted, r.team2_passes_completed,
                    r.team2_pickups_attempted, r.team2_pickups_succeeded,
                    r.team2_turnovers, r.team2_failed_dodges,
                    r.team2_messages_sent, r.team2_total_message_chars,
                ),
            ]:
                if model_id not in model_map:
                    model_map[model_id] = ModelLeaderboardEntry(model_id=model_id)
                entry = model_map[model_id]
                entry.games += 1
                entry.goals_for += score_for
                entry.goals_against += score_against
                entry.score_diff += score_for - score_against
                entry.casualties_caused += casualties
                entry.blocks_thrown += blocks
                entry.passes_attempted += passes_att
                entry.passes_completed += passes_comp
                entry.pickups_attempted += pickups_att
                entry.pickups_succeeded += pickups_succ
                entry.turnovers += turnovers
                entry.failed_dodges += failed_dodges
                entry.messages_sent += messages_sent
                entry.total_message_chars += total_message_chars
                if outcome == "win":
                    entry.wins += 1
                elif outcome == "loss":
                    entry.losses += 1
                else:
                    entry.draws += 1
```

**Commit:** `feat(leaderboard): aggregate all benchmark stats in LeaderboardStore`

---

## Task 4: Redesign `leaderboard.html`

**File:** `app/web/templates/leaderboard.html`

**Replace the entire file** with the implementation below. Key design decisions:
- Default view: Cards (rich, shows stat bars)
- Toggle to Table view (compact, shows all numbers)
- Bars are normalised against the max value across all current models
- Both views are responsive (single-column on mobile)
- `<meta name="viewport">` is included (lesson learned)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Ankh-Morpork Scramble – Season Standings</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Spectral:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #1f160c;
            --panel: #24170c;
            --panel-border: rgba(187, 142, 76, 0.45);
            --panel-shadow: rgba(8, 4, 0, 0.6);
            --accent-gold: #d9b45b;
            --accent-gold-soft: rgba(217, 180, 91, 0.65);
            --accent-orange: #c46d28;
            --text: #f2e3c6;
            --muted: rgba(242, 227, 198, 0.7);
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            font-family: "Spectral", Georgia, serif;
            background: radial-gradient(circle at 22% 16%, rgba(217,180,91,0.12), transparent 55%),
                        radial-gradient(circle at 78% 12%, rgba(106,76,38,0.18), transparent 50%),
                        var(--bg);
            color: var(--text);
            min-height: 100vh;
            padding: 1.5rem clamp(1rem, 4vw, 3rem);
        }

        nav {
            max-width: 1200px;
            margin: 0 auto 1.5rem;
        }

        nav a {
            color: var(--accent-gold);
            text-decoration: none;
            font-family: "Cinzel", serif;
            font-size: 0.85rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        nav a:hover { color: var(--accent-orange); }

        header {
            max-width: 1200px;
            margin: 0 auto 2rem;
            text-align: center;
        }

        header h1 {
            margin: 0 0 0.4rem;
            font-family: "Cinzel", serif;
            font-size: clamp(1.4rem, 3vw, 2rem);
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: var(--accent-gold);
        }

        header p {
            margin: 0;
            color: var(--muted);
            font-size: 0.95rem;
        }

        .container { max-width: 1200px; margin: 0 auto; }

        /* Section */
        .section {
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 24px var(--panel-shadow);
        }

        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
        }

        .section-header h2 {
            margin: 0;
            font-family: "Cinzel", serif;
            font-size: 1.1rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--accent-gold);
        }

        /* View toggle */
        .view-toggle {
            display: flex;
            gap: 0.3rem;
        }

        .view-btn {
            background: rgba(217,180,91,0.06);
            border: 1px solid rgba(217,180,91,0.2);
            color: rgba(242,227,198,0.5);
            font-family: "Cinzel", serif;
            font-size: 0.68rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            padding: 0.3em 0.8em;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s;
        }

        .view-btn:hover { color: rgba(242,227,198,0.85); background: rgba(217,180,91,0.12); }

        .view-btn.active {
            background: rgba(217,180,91,0.2);
            border-color: rgba(217,180,91,0.45);
            color: var(--accent-gold);
        }

        /* ── Model cards ─────────────────────────────────────────────────── */
        .model-cards {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 1rem;
        }

        .model-card {
            background: rgba(30,19,10,0.85);
            border: 1px solid rgba(217,180,91,0.22);
            border-radius: 10px;
            padding: 1rem 1.1rem;
            transition: border-color 0.15s;
        }

        .model-card:hover { border-color: rgba(217,180,91,0.45); }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 0.5rem;
            margin-bottom: 0.6rem;
            padding-bottom: 0.6rem;
            border-bottom: 1px solid rgba(217,180,91,0.15);
        }

        .card-model-name {
            font-family: "Cinzel", serif;
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--accent-gold);
            letter-spacing: 0.04em;
            word-break: break-all;
            flex: 1;
        }

        .card-record {
            font-size: 0.75rem;
            color: var(--muted);
            white-space: nowrap;
            text-align: right;
            flex-shrink: 0;
        }

        .card-record .win { color: #7fb069; font-weight: 600; }
        .card-record .loss { color: #e07856; }
        .card-record .draw { color: var(--muted); }

        .card-meta {
            font-size: 0.72rem;
            color: rgba(242,227,198,0.4);
            margin-bottom: 0.9rem;
        }

        /* Stat bars */
        .stat-row {
            display: grid;
            grid-template-columns: 1.4rem 7rem 1fr 3.5rem;
            align-items: center;
            gap: 0.4rem;
            margin-bottom: 0.45rem;
        }

        .stat-icon {
            font-size: 0.8rem;
            text-align: center;
        }

        .stat-label {
            font-size: 0.68rem;
            color: rgba(242,227,198,0.55);
            font-family: "Cinzel", serif;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .stat-bar-track {
            height: 5px;
            background: rgba(217,180,91,0.1);
            border-radius: 3px;
            overflow: hidden;
        }

        .stat-bar-fill {
            height: 100%;
            border-radius: 3px;
            background: linear-gradient(90deg, rgba(217,180,91,0.6), rgba(217,180,91,0.9));
            transition: width 0.4s ease;
        }

        .stat-value {
            font-size: 0.7rem;
            color: rgba(242,227,198,0.6);
            text-align: right;
            font-variant-numeric: tabular-nums;
        }

        /* ── Table view ──────────────────────────────────────────────────── */
        .table-scroll { overflow-x: auto; }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
            white-space: nowrap;
        }

        th {
            color: var(--accent-gold);
            font-family: "Cinzel", serif;
            font-size: 0.72rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            padding: 0.6rem 0.5rem;
            border-bottom: 2px solid rgba(217,180,91,0.3);
            text-align: center;
        }

        th:first-child { text-align: left; }

        td {
            padding: 0.55rem 0.5rem;
            border-top: 1px solid rgba(217,180,91,0.08);
            color: var(--text);
            text-align: center;
        }

        td:first-child { text-align: left; }

        tr:hover { background: rgba(217,180,91,0.04); }

        .model-name-cell {
            font-family: "Cinzel", serif;
            font-size: 0.75rem;
            color: var(--accent-gold-soft);
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .positive { color: #7fb069; }
        .negative { color: #e07856; }

        th[data-sort] { cursor: pointer; user-select: none; }
        th[data-sort]:hover { color: var(--text); }
        th[data-sort].sorted-asc::after { content: " ▲"; font-size: 0.6em; }
        th[data-sort].sorted-desc::after { content: " ▼"; font-size: 0.6em; }

        /* Team table (always table view) */
        .team-section table { font-size: 0.88rem; }

        /* Shared states */
        .loading, .empty, .error {
            text-align: center;
            padding: 2.5rem;
            color: var(--muted);
            font-style: italic;
        }

        .error { color: var(--accent-orange); }
    </style>
</head>
<body>
    <nav><a href="/ui">← Back to Match</a></nav>

    <header>
        <h1>Season Standings</h1>
        <p id="summary">Loading…</p>
    </header>

    <div class="container">
        <!-- Model benchmark section -->
        <div class="section">
            <div class="section-header">
                <h2>Model Benchmark</h2>
                <div class="view-toggle">
                    <button class="view-btn active" id="btn-cards" onclick="setView('cards')">📊 Cards</button>
                    <button class="view-btn" id="btn-table" onclick="setView('table')">📋 Table</button>
                </div>
            </div>
            <div id="model-cards-view">
                <div class="loading">Loading model data…</div>
            </div>
            <div id="model-table-view" style="display:none;">
                <div class="table-scroll">
                    <div class="loading">Loading model data…</div>
                </div>
            </div>
        </div>

        <!-- Team table section -->
        <div class="section team-section">
            <div class="section-header">
                <h2>Team Standings</h2>
            </div>
            <div class="table-scroll" id="team-table-container">
                <div class="loading">Loading team data…</div>
            </div>
        </div>
    </div>

    <script>
        const STAT_DEFS = [
            { key: 'aggression',   icon: '💥', label: 'Aggression',   unit: '/game',    tip: 'Blocks thrown per game' },
            { key: 'recklessness', icon: '🎲', label: 'Recklessness', unit: '/game',    tip: 'Turnovers per game' },
            { key: 'ball_craft',   icon: '🎯', label: 'Ball Craft',   unit: '/game',    tip: 'Pass completions + pickups per game' },
            { key: 'lethality',    icon: '⚔️', label: 'Lethality',    unit: '/game',    tip: 'Casualties caused per game' },
            { key: 'verbosity',    icon: '💬', label: 'Verbosity',    unit: 'chars/msg',tip: 'Avg strategy message length' },
            { key: 'efficiency',   icon: '⚡', label: 'Efficiency',   unit: 'ratio',    tip: 'Goals per game ÷ turnover rate' },
        ];

        let currentView = 'cards';
        let allModels = [];

        function escapeHtml(str) {
            const d = document.createElement('div');
            d.textContent = str || '';
            return d.innerHTML;
        }

        function shortModelName(id) {
            // strip vendor prefix and :free/:nitro suffix
            return id.split('/').pop().replace(/:(free|nitro|extended|beta)$/, '');
        }

        function setView(v) {
            currentView = v;
            document.getElementById('model-cards-view').style.display = v === 'cards' ? '' : 'none';
            document.getElementById('model-table-view').style.display  = v === 'table' ? '' : 'none';
            document.getElementById('btn-cards').classList.toggle('active', v === 'cards');
            document.getElementById('btn-table').classList.toggle('active', v === 'table');
        }

        function computeMaxes(models) {
            const maxes = {};
            STAT_DEFS.forEach(s => {
                maxes[s.key] = Math.max(1, ...models.map(m => m[s.key] || 0));
            });
            return maxes;
        }

        function renderCards(models) {
            const container = document.getElementById('model-cards-view');
            if (!models.length) {
                container.innerHTML = '<div class="empty">No model data yet — complete a game to populate the benchmark.</div>';
                return;
            }
            const maxes = computeMaxes(models);
            const cards = models.map(m => {
                const short = escapeHtml(shortModelName(m.model_id));
                const full  = escapeHtml(m.model_id);
                const diffSign = m.score_diff > 0 ? '+' : '';
                const diffClass = m.score_diff > 0 ? 'positive' : (m.score_diff < 0 ? 'negative' : '');

                const bars = STAT_DEFS.map(s => {
                    const val = m[s.key] || 0;
                    const pct = maxes[s.key] > 0 ? Math.round(100 * val / maxes[s.key]) : 0;
                    const display = s.key === 'verbosity'
                        ? val.toFixed(0)
                        : val.toFixed(2).replace(/\.00$/, '');
                    return `
                        <div class="stat-row" title="${escapeHtml(s.tip)}">
                            <span class="stat-icon">${s.icon}</span>
                            <span class="stat-label">${s.label}</span>
                            <div class="stat-bar-track">
                                <div class="stat-bar-fill" style="width:${pct}%"></div>
                            </div>
                            <span class="stat-value">${display} <span style="opacity:0.5">${s.unit}</span></span>
                        </div>`;
                }).join('');

                return `
                    <div class="model-card">
                        <div class="card-header">
                            <span class="card-model-name" title="${full}">${short}</span>
                            <div class="card-record">
                                <span class="win">${m.wins}W</span> ·
                                <span class="loss">${m.losses}L</span> ·
                                <span class="draw">${m.draws}D</span>
                            </div>
                        </div>
                        <div class="card-meta">
                            GD <span class="${diffClass}">${diffSign}${m.score_diff}</span>
                            &nbsp;·&nbsp; ${m.goals_for} scored
                            &nbsp;·&nbsp; ${m.games} game${m.games === 1 ? '' : 's'}
                        </div>
                        ${bars}
                    </div>`;
            }).join('');

            container.innerHTML = `<div class="model-cards">${cards}</div>`;
        }

        let sortKey = 'wins';
        let sortAsc = false;

        function renderTable(models) {
            const wrap = document.getElementById('model-table-view').querySelector('.table-scroll') ||
                         document.getElementById('model-table-view');

            if (!models.length) {
                wrap.innerHTML = '<div class="empty">No model data yet.</div>';
                return;
            }

            const sorted = [...models].sort((a, b) => {
                const av = a[sortKey] ?? 0, bv = b[sortKey] ?? 0;
                return sortAsc ? av - bv : bv - av;
            });

            const headers = [
                { key: 'model_id',     label: 'Model' },
                { key: 'games',        label: 'GP' },
                { key: 'wins',         label: 'W' },
                { key: 'losses',       label: 'L' },
                { key: 'draws',        label: 'D' },
                { key: 'goals_for',    label: 'GF' },
                { key: 'goals_against',label: 'GA' },
                { key: 'score_diff',   label: '+/-' },
                { key: 'aggression',   label: '💥/G' },
                { key: 'recklessness', label: '🎲/G' },
                { key: 'ball_craft',   label: '🎯/G' },
                { key: 'lethality',    label: '⚔️/G' },
                { key: 'verbosity',    label: '💬 Chars' },
                { key: 'efficiency',   label: '⚡ Eff' },
            ];

            const ths = headers.map(h => {
                const sortClass = h.key === sortKey ? (sortAsc ? 'sorted-asc' : 'sorted-desc') : '';
                const sortAttr  = h.key !== 'model_id' ? `data-sort="${h.key}"` : '';
                return `<th ${sortAttr} class="${sortClass}" onclick="${h.key !== 'model_id' ? `tableSort('${h.key}')` : ''}">${escapeHtml(h.label)}</th>`;
            }).join('');

            const rows = sorted.map(m => {
                const diffSign  = m.score_diff > 0 ? '+' : '';
                const diffClass = m.score_diff > 0 ? 'positive' : (m.score_diff < 0 ? 'negative' : '');
                const fmt = v => typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(2)) : (v || '—');
                return `<tr>
                    <td class="model-name-cell" title="${escapeHtml(m.model_id)}">${escapeHtml(shortModelName(m.model_id))}</td>
                    <td>${m.games}</td>
                    <td class="positive">${m.wins}</td>
                    <td class="negative">${m.losses}</td>
                    <td>${m.draws}</td>
                    <td>${m.goals_for}</td>
                    <td>${m.goals_against}</td>
                    <td class="${diffClass}">${diffSign}${m.score_diff}</td>
                    <td>${fmt(m.aggression)}</td>
                    <td>${fmt(m.recklessness)}</td>
                    <td>${fmt(m.ball_craft)}</td>
                    <td>${fmt(m.lethality)}</td>
                    <td>${fmt(m.verbosity)}</td>
                    <td>${fmt(m.efficiency)}</td>
                </tr>`;
            }).join('');

            document.getElementById('model-table-view').innerHTML = `
                <div class="table-scroll">
                    <table>
                        <thead><tr>${ths}</tr></thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>`;
        }

        function tableSort(key) {
            if (sortKey === key) {
                sortAsc = !sortAsc;
            } else {
                sortKey = key;
                sortAsc = false;
            }
            renderTable(allModels);
        }

        function renderTeamTable(teams) {
            const container = document.getElementById('team-table-container');
            if (!teams.length) {
                container.innerHTML = '<div class="empty">No team data yet.</div>';
                return;
            }
            const rows = teams.map(t => {
                const diffSign  = t.score_diff > 0 ? '+' : '';
                const diffClass = t.score_diff > 0 ? 'positive' : (t.score_diff < 0 ? 'negative' : '');
                return `<tr>
                    <td class="model-name-cell">${escapeHtml(t.team_name)}</td>
                    <td>${t.games}</td>
                    <td class="positive">${t.wins}</td>
                    <td class="negative">${t.losses}</td>
                    <td>${t.draws}</td>
                    <td>${t.goals_for}</td>
                    <td>${t.goals_against}</td>
                    <td class="${diffClass}">${diffSign}${t.score_diff}</td>
                </tr>`;
            }).join('');
            container.innerHTML = `
                <table>
                    <thead><tr>
                        <th>Team</th><th>GP</th><th>W</th><th>L</th><th>D</th>
                        <th>GF</th><th>GA</th><th>+/-</th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                </table>`;
        }

        async function loadLeaderboard() {
            try {
                const res  = await fetch('/leaderboard');
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();

                document.getElementById('summary').textContent =
                    data.total_games === 0
                        ? 'No completed games yet — check back after the first match concludes.'
                        : `${data.total_games} game${data.total_games === 1 ? '' : 's'} on record`;

                allModels = data.by_model || [];
                renderCards(allModels);
                renderTable(allModels);
                renderTeamTable(data.by_team || []);

            } catch (err) {
                console.error(err);
                document.getElementById('summary').textContent = 'Failed to load data.';
                document.getElementById('model-cards-view').innerHTML =
                    `<div class="error">Error: ${escapeHtml(err.message)}</div>`;
            }
        }

        loadLeaderboard();
    </script>
</body>
</html>
```

**Commit:** `feat(leaderboard): card benchmark view with stat bars, sortable table, view toggle`

---

## Verification

```bash
cd ~/projects/ankh-morpork-scramble && uv run pytest tests/ -q
```

Then:
```bash
# Start server and check leaderboard endpoint returns new fields
uv run uvicorn app.main:app --port 8001 &
sleep 3
curl -s http://localhost:8001/leaderboard | python3 -m json.tool | grep -E "aggression|verbosity|efficiency|blocks"
# Should show the new computed fields (all 0.0 until a game completes)
kill %1
```

Open `http://localhost:8001/leaderboard/ui` in a browser:
- Cards view default, shows 6 stat bars per model
- Toggle to Table: all columns visible, headers clickable to sort
- Team standings section below
- Empty state message shows before first game completes
- Mobile: cards stack to single column, table scrolls horizontally

---

## Notes

- `GameResult` fields default to `0` so old JSONL entries without the new fields will
  still deserialise correctly (Pydantic v2 ignores extra fields and uses defaults for
  missing ones). No migration needed.
- `verbosity` will be 0 until strategy messages are non-empty — this happens from the
  first game that uses `run_simple_game.py` with the messaging system active.
- Bars are normalised against the current dataset's max — a model with 1 game and
  5 blocks/game will show a full bar until more data arrives. This is correct behaviour;
  it self-calibrates as the dataset grows.
