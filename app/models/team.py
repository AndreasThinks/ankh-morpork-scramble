"""Team models and rosters"""
from typing import Optional
from pydantic import BaseModel, Field
from app.models.enums import TeamType, SkillType
from app.models.player import PlayerPosition


# City Watch Roster
CITY_WATCH_POSITIONS = {
    "constable": PlayerPosition(
        role="Constable",
        cost=50000,
        ma=6,
        st=3,
        ag="3+",
        pa="4+",
        av="9+",
        skills=[],
        primary=["G"],
        secondary=["A", "S"]
    ),
    "clerk_runner": PlayerPosition(
        role="Clerk-Runner",
        cost=80000,
        ma=6,
        st=3,
        ag="3+",
        pa="2+",
        av="9+",
        skills=[SkillType.PIGEON_POST, SkillType.CHAIN_OF_CUSTODY],
        primary=["G", "P"],
        secondary=["A", "S"]
    ),
    "fleet_recruit": PlayerPosition(
        role="Fleet Recruit",
        cost=65000,
        ma=8,
        st=2,
        ag="3+",
        pa="5+",
        av="8+",
        skills=[SkillType.QUICK_GRAB, SkillType.SIDESTEP_SHUFFLE],
        primary=["A", "G"],
        secondary=["P", "S"]
    ),
    "watch_sergeant": PlayerPosition(
        role="Watch Sergeant",
        cost=85000,
        ma=7,
        st=3,
        ag="3+",
        pa="4+",
        av="9+",
        skills=[SkillType.DRILL_HARDENED],
        primary=["G", "S"],
        secondary=["A", "P"]
    )
}

# Unseen University Roster
UNSEEN_UNIVERSITY_POSITIONS = {
    "apprentice_wizard": PlayerPosition(
        role="Apprentice Wizard",
        cost=45000,
        ma=6,
        st=2,
        ag="3+",
        pa="4+",
        av="8+",
        skills=[
            SkillType.BLINK,
            SkillType.SMALL_AND_SNEAKY,
            SkillType.PORTABLE,
            SkillType.POINTY_HAT_PADDING
        ],
        primary=["A"],
        secondary=["G", "P", "S"]
    ),
    "senior_wizard": PlayerPosition(
        role="Senior Wizard",
        cost=90000,
        ma=4,
        st=4,
        ag="4+",
        pa="5+",
        av="10+",
        skills=[SkillType.REROLL_THE_THESIS, SkillType.GRAPPLING_CANTRIP],
        primary=["G", "S"],
        secondary=["A", "P"]
    ),
    "animated_gargoyle": PlayerPosition(
        role="Animated Gargoyle",
        cost=115000,
        ma=4,
        st=5,
        ag="5+",
        pa="5+",
        av="10+",
        skills=[
            SkillType.BOUND_SPIRIT,
            SkillType.STONE_THICK,
            SkillType.PIGEON_PROOF,
            SkillType.MINDLESS_MASONRY,
            SkillType.WEATHERED,
            SkillType.LOB_THE_LACKEY,
            SkillType.OCCASIONAL_BITE_MARK
        ],
        primary=["S"],
        secondary=["A", "G", "P"]
    )
}


class TeamRoster(BaseModel):
    """Team roster definition"""
    team_type: TeamType
    positions: dict[str, PlayerPosition]
    reroll_cost: int
    max_rerolls: int = 8


# Pre-defined team rosters
TEAM_ROSTERS = {
    TeamType.CITY_WATCH: TeamRoster(
        team_type=TeamType.CITY_WATCH,
        positions=CITY_WATCH_POSITIONS,
        reroll_cost=50000,
        max_rerolls=8
    ),
    TeamType.UNSEEN_UNIVERSITY: TeamRoster(
        team_type=TeamType.UNSEEN_UNIVERSITY,
        positions=UNSEEN_UNIVERSITY_POSITIONS,
        reroll_cost=60000,
        max_rerolls=8
    )
}


class Team(BaseModel):
    """Team instance in a game"""
    id: str
    name: str
    team_type: TeamType
    
    # Re-rolls
    rerolls_total: int = 0
    rerolls_used: int = 0
    
    # Score
    score: int = 0
    
    # Players on this team (player_id list)
    player_ids: list[str] = Field(default_factory=list)
    
    @property
    def rerolls_remaining(self) -> int:
        """Get remaining team re-rolls"""
        return max(0, self.rerolls_total - self.rerolls_used)
    
    def use_reroll(self) -> None:
        """Use a team re-roll"""
        if self.rerolls_remaining == 0:
            raise ValueError("No team re-rolls remaining")
        self.rerolls_used += 1
    
    def reset_rerolls(self) -> None:
        """Reset re-rolls for new turn"""
        self.rerolls_used = 0
    
    def add_score(self, points: int = 1) -> None:
        """Add to team score"""
        self.score += points
