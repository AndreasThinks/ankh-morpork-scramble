"""Extract team roster data from app/models/team.py"""
from app.models.team import CITY_WATCH_POSITIONS, UNSEEN_UNIVERSITY_POSITIONS, TEAM_ROSTERS
from app.models.enums import TeamType


def extract_rosters() -> dict:
    """Extract all team roster data for template rendering.
    
    Returns:
        Dict with team rosters, positions, costs, and metadata
    """
    city_watch_roster = TEAM_ROSTERS[TeamType.CITY_WATCH]
    unseen_roster = TEAM_ROSTERS[TeamType.UNSEEN_UNIVERSITY]
    
    return {
        "city_watch": {
            "name": "City Watch",
            "reroll_cost": city_watch_roster.reroll_cost,
            "max_rerolls": city_watch_roster.max_rerolls,
            "positions": [
                {
                    "key": key,
                    "role": pos.role,
                    "cost": pos.cost,
                    "max_quantity": pos.max_quantity,
                    "ma": pos.ma,
                    "st": pos.st,
                    "ag": pos.ag,
                    "pa": pos.pa,
                    "av": pos.av,
                    "skills": [skill.value for skill in pos.skills],
                    "primary": pos.primary,
                    "secondary": pos.secondary,
                    "is_star_player": pos.is_star_player,
                }
                for key, pos in CITY_WATCH_POSITIONS.items()
            ]
        },
        "unseen_university": {
            "name": "Unseen University",
            "reroll_cost": unseen_roster.reroll_cost,
            "max_rerolls": unseen_roster.max_rerolls,
            "positions": [
                {
                    "key": key,
                    "role": pos.role,
                    "cost": pos.cost,
                    "max_quantity": pos.max_quantity,
                    "ma": pos.ma,
                    "st": pos.st,
                    "ag": pos.ag,
                    "pa": pos.pa,
                    "av": pos.av,
                    "skills": [skill.value for skill in pos.skills],
                    "primary": pos.primary,
                    "secondary": pos.secondary,
                    "is_star_player": pos.is_star_player,
                }
                for key, pos in UNSEEN_UNIVERSITY_POSITIONS.items()
            ]
        },
        "standard_budget": 1_000_000,
    }
