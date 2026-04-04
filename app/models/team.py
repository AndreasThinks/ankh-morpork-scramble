"""Team models and rosters"""
from typing import Optional
from pydantic import BaseModel, Field
from app.models.enums import TeamType, SkillType
from app.models.player import PlayerPosition


# City Watch Roster
CITY_WATCH_POSITIONS = {
    # Basic positions
    "constable": PlayerPosition(
        role="Constable",
        cost=50000,
        max_quantity=16,
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
        max_quantity=2,
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
        max_quantity=4,
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
        max_quantity=4,
        ma=7,
        st=3,
        ag="3+",
        pa="4+",
        av="9+",
        skills=[SkillType.DRILL_HARDENED],
        primary=["G", "S"],
        secondary=["A", "P"]
    ),

    # NEW: Special positions
    "troll_constable": PlayerPosition(
        role="Troll Constable",
        cost=115000,
        max_quantity=2,
        ma=4,
        st=5,
        ag="5+",
        pa="6+",
        av="10+",
        skills=[SkillType.THICK_AS_A_BRICK, SkillType.ROCK_SOLID, SkillType.REALLY_THICK],
        primary=["S"],
        secondary=["G", "A"]
    ),
    "street_veteran": PlayerPosition(
        role="Street Veteran",
        cost=50000,
        max_quantity=4,
        ma=6,
        st=2,
        ag="3+",
        pa="5+",
        av="8+",
        skills=[SkillType.STREET_FIGHTING, SkillType.SLIPPERY],
        primary=["G", "A"],
        secondary=["S"]
    ),
    "watchdog": PlayerPosition(
        role="Watchdog",
        cost=90000,
        max_quantity=2,
        ma=7,
        st=3,
        ag="3+",
        pa="4+",
        av="9+",
        skills=[SkillType.LUPINE_SPEED, SkillType.KEEN_SENSES, SkillType.REGENERATIVE],
        primary=["G", "A"],
        secondary=["S", "P"]
    ),

    # NEW: Star players (max 1 each)
    "sergeant_detritus": PlayerPosition(
        role="Sergeant Detritus",
        cost=150000,
        max_quantity=1,
        ma=5,
        st=5,
        ag="4+",
        pa="6+",
        av="10+",
        skills=[
            SkillType.COOLING_HELMET,
            SkillType.ROCK_SOLID,
            SkillType.THICK_AS_A_BRICK,
            SkillType.CROSSBOW_TRAINING,
            SkillType.BREAK_HEADS,
            SkillType.KINGLY_PRESENCE  # Using as GUARD
        ],
        primary=["S"],
        secondary=["G"],
        is_star_player=True
    ),
    "captain_carrot": PlayerPosition(
        role="Captain Carrot Ironfoundersson",
        cost=130000,
        max_quantity=1,
        ma=6,
        st=4,
        ag="3+",
        pa="3+",
        av="10+",
        skills=[
            SkillType.TRUE_KING,
            SkillType.KINGLY_PRESENCE,
            SkillType.HONEST_FIGHTER,
            SkillType.WILL_NOT_BACK_DOWN,
            SkillType.DIPLOMATIC_IMMUNITY,
            SkillType.TRUSTED_BY_ALL
        ],
        primary=["G", "P"],
        secondary=["S", "A"],
        is_star_player=True
    )
}

# Unseen University Roster
UNSEEN_UNIVERSITY_POSITIONS = {
    # Basic positions
    "apprentice_wizard": PlayerPosition(
        role="Apprentice Wizard",
        cost=45000,
        max_quantity=12,
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
        max_quantity=6,
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
        max_quantity=1,
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
    ),
    # --- NEW positions ---

    # Fast runner. UU answer to the Fleet Recruit (MA8, AV7+ - fast but fragile).
    # Skills: Sprint + Dodge. Max 2 - magical acceleration is rare.
    "haste_mage": PlayerPosition(
        role="Haste Mage",
        cost=75000,
        max_quantity=2,
        ma=8,
        st=2,
        ag="3+",
        pa="5+",
        av="7+",
        skills=[
            SkillType.HASTE_SPELL,    # Sprint
            SkillType.BLINK_DODGE,    # Dodge
        ],
        primary=["A", "G"],
        secondary=["P"]
    ),

    # Dedicated passer. UU answer to the Clerk-Runner (PA2+, Sure Hands, Safe Pass).
    # Slower and frailer than the Clerk-Runner (MA5, ST2) but equally gifted with the ball.
    "divination_wizard": PlayerPosition(
        role="Divination Wizard",
        cost=85000,
        max_quantity=2,
        ma=5,
        st=2,
        ag="3+",
        pa="2+",
        av="8+",
        skills=[
            SkillType.CALCULATED_TRAJECTORY,  # Pass
            SkillType.HEX_ASSISTED,           # Sure Hands
            SkillType.SAFE_PAIR_OF_HANDS,     # Safe Pass
        ],
        primary=["P", "A"],
        secondary=["G"]
    ),

    # Cheap agile oddity. A wizard who accidentally transformed themselves into an orangutan
    # and has not quite worked out how to change back. Surprisingly strong and very agile
    # (AG2+), but distracted and hard to direct (Loner 4+). Max 2.
    "transformed_wizard": PlayerPosition(
        role="Transformed Wizard",
        cost=60000,
        max_quantity=2,
        ma=5,
        st=3,
        ag="2+",
        pa="6+",
        av="8+",
        skills=[
            SkillType.SIMIAN_AGILITY,  # Leap
            SkillType.FOUR_LIMBS,      # Extra Arms
            SkillType.INDEPENDENT,     # Loner (4+)
        ],
        primary=["A"],
        secondary=["G", "S"]
    ),

    # Star player 1 - The Librarian. ST4, AG2+ (exceptional), Frenzy + Guard + Leap.
    # UU answer to Sergeant Detritus. Ook.
    "the_librarian": PlayerPosition(
        role="The Librarian",
        cost=150000,
        max_quantity=1,
        ma=5,
        st=4,
        ag="2+",
        pa="6+",
        av="9+",
        skills=[
            SkillType.PREHENSILE_EVERYTHING,  # Extra Arms
            SkillType.LIBRARY_SWINGING,       # Leap
            SkillType.PROTECTIVE_INSTINCT,    # Guard
            SkillType.BIBLIOPHILE_RAGE,       # Frenzy
            SkillType.TERRIFYING_GLARE,       # Disturbing Presence
        ],
        primary=["S", "A"],
        secondary=["G"],
        is_star_player=True
    ),

    # Star player 2 - Archchancellor Mustrum Ridcully. Leader + Block + Guard + Pass.
    # UU answer to Captain Carrot. Loud, stubborn, surprisingly effective.
    "archchancellor_ridcully": PlayerPosition(
        role="Archchancellor Ridcully",
        cost=140000,
        max_quantity=1,
        ma=6,
        st=4,
        ag="3+",
        pa="3+",
        av="10+",
        skills=[
            SkillType.ARCHCHANCELLOR,         # Leader
            SkillType.ROBUST_PHYSIQUE,        # Block
            SkillType.BOOMING_VOICE,          # Guard
            SkillType.ARCANE_MASTERY,         # Pass
            SkillType.HEADOLOGY_EXPERT,       # Hypnotic Gaze
            SkillType.STUBBORN,               # Stand Firm
        ],
        primary=["G", "S", "P"],
        secondary=["A"],
        is_star_player=True
    ),
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

    # Budget tracking
    budget_initial: int = 1_000_000  # Standard team treasury
    budget_spent: int = 0
    purchase_history: list[str] = Field(default_factory=list)

    # Re-rolls
    rerolls_total: int = 0
    rerolls_used: int = 0

    # Score
    score: int = 0

    # Players on this team (player_id list)
    player_ids: list[str] = Field(default_factory=list)
    
    @property
    def budget_remaining(self) -> int:
        """Get remaining budget"""
        return max(0, self.budget_initial - self.budget_spent)

    @property
    def rerolls_remaining(self) -> int:
        """Get remaining team re-rolls"""
        return max(0, self.rerolls_total - self.rerolls_used)

    def can_afford(self, cost: int) -> bool:
        """Check if team can afford a purchase"""
        return self.budget_remaining >= cost

    def purchase_item(self, item_name: str, cost: int) -> None:
        """Purchase an item and update budget"""
        if not self.can_afford(cost):
            raise ValueError(
                f"Insufficient funds: need {cost}, have {self.budget_remaining}"
            )
        self.budget_spent += cost
        self.purchase_history.append(f"{item_name} ({cost}g)")

    def purchase_player(self, position_role: str, cost: int) -> None:
        """Purchase a player"""
        self.purchase_item(f"Player: {position_role}", cost)

    def purchase_reroll(self, cost: int) -> None:
        """Purchase a team reroll"""
        roster = TEAM_ROSTERS.get(self.team_type)
        if not roster:
            raise ValueError(f"Unknown team type: {self.team_type}")

        if self.rerolls_total >= roster.max_rerolls:
            raise ValueError(
                f"Cannot exceed maximum of {roster.max_rerolls} rerolls"
            )

        self.purchase_item(f"Team Reroll", cost)
        self.rerolls_total += 1

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
