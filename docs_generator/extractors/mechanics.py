"""Extract game mechanics constants from app/game/ modules"""
from app.models.enums import BlockResult, InjuryResult, PassResult


def extract_movement_rules() -> dict:
    """Extract movement mechanics data.
    
    Returns:
        Dict with movement constants and rules
    """
    return {
        "max_rush_moves": 2,
        "rush_target": 2,  # Need 2+ on d6 for rush
        "stand_up_cost": 3,  # MA cost to stand up
        "tackle_zone_range": 1,  # Adjacent squares
        "dodge_penalties": {
            "per_tackle_zone": -1,
        },
        "pitch_dimensions": {
            "width": 26,  # x: 0-25
            "height": 15,  # y: 0-14
        },
    }


def extract_combat_rules() -> dict:
    """Extract combat/blocking mechanics data.
    
    Returns:
        Dict with block dice outcomes, strength comparisons, injury table
    """
    return {
        "block_results": [
            {
                "result": BlockResult.ATTACKER_DOWN.value,
                "symbol": "💀",
                "description": "Attacker Down - Attacker is knocked down",
            },
            {
                "result": BlockResult.BOTH_DOWN.value,
                "symbol": "💥",
                "description": "Both Down - Both players knocked down (unless Block skill)",
            },
            {
                "result": BlockResult.PUSH.value,
                "symbol": "⬅️",
                "description": "Push - Defender pushed back one square",
            },
            {
                "result": BlockResult.DEFENDER_STUMBLES.value,
                "symbol": "😵",
                "description": "Defender Stumbles - Knockdown unless Dodge skill",
            },
            {
                "result": BlockResult.DEFENDER_DOWN.value,
                "symbol": "☠️",
                "description": "Defender Down - Defender knocked down",
            },
        ],
        "block_dice_faces": {
            "1_die": ["attacker_down", "both_down", "push", "push", "defender_stumbles", "defender_down"],
        },
        "strength_comparison": {
            "much_stronger": {"condition": "attacker ST ≥ defender ST + 2", "dice": 3, "choose": "attacker"},
            "stronger": {"condition": "attacker ST = defender ST + 1", "dice": 2, "choose": "attacker"},
            "equal": {"condition": "attacker ST = defender ST", "dice": 1, "choose": "attacker"},
            "weaker": {"condition": "attacker ST = defender ST - 1", "dice": 2, "choose": "defender"},
            "much_weaker": {"condition": "attacker ST ≤ defender ST - 2", "dice": 3, "choose": "defender"},
        },
        "injury_results": [
            {
                "roll": "2-7",
                "result": InjuryResult.STUNNED.value,
                "description": "Stunned - Player stays down until next turn",
            },
            {
                "roll": "8-9",
                "result": InjuryResult.KNOCKED_OUT.value,
                "description": "Knocked Out - Player removed from pitch",
            },
            {
                "roll": "10+",
                "result": InjuryResult.CASUALTY.value,
                "description": "Casualty - Player permanently removed",
            },
        ],
        "armor_roll": {
            "description": "Roll 2d6, if ≥ player's AV, make injury roll",
            "dice": "2d6",
        },
    }


def extract_pass_rules() -> dict:
    """Extract passing/ball handling mechanics data.
    
    Returns:
        Dict with pass ranges, accuracy, scatter mechanics
    """
    return {
        "pass_ranges": [
            {"name": "Quick", "distance": "1-3", "modifier": "+1", "risk": "Low"},
            {"name": "Short", "distance": "4-6", "modifier": "0", "risk": "Medium"},
            {"name": "Long", "distance": "7-12", "modifier": "-1", "risk": "High"},
            {"name": "Long Bomb", "distance": "13+", "modifier": "-2", "risk": "Very High"},
        ],
        "pass_results": [
            {
                "result": PassResult.FUMBLE.value,
                "condition": "Natural 1",
                "scatter": 1,
                "scatter_from": "thrower",
                "turnover": True,
            },
            {
                "result": PassResult.WILDLY_INACCURATE.value,
                "condition": "< Target",
                "scatter": 3,
                "scatter_from": "target",
                "turnover": False,
            },
            {
                "result": PassResult.INACCURATE.value,
                "condition": "Target to Target+2",
                "scatter": 1,
                "scatter_from": "target",
                "turnover": False,
            },
            {
                "result": PassResult.ACCURATE.value,
                "condition": "≥ Target+3",
                "scatter": 0,
                "scatter_from": None,
                "turnover": False,
            },
        ],
        "scatter_directions": {
            "1": {"name": "NE", "dx": 1, "dy": 1},
            "2": {"name": "E", "dx": 1, "dy": 0},
            "3": {"name": "SE", "dx": 1, "dy": -1},
            "4": {"name": "S", "dx": 0, "dy": -1},
            "5": {"name": "SW", "dx": -1, "dy": -1},
            "6": {"name": "W", "dx": -1, "dy": 0},
            "7": {"name": "NW", "dx": -1, "dy": 1},
            "8": {"name": "N", "dx": 0, "dy": 1},
        },
        "catch_rules": {
            "base": "Roll d6 ≥ Agility target",
            "modifiers": "−1 per tackle zone, +1 for Quick Grab skill",
            "failure": "Ball scatters + TURNOVER",
        },
        "pickup_rules": {
            "base": "Roll d6 ≥ Agility target",
            "modifiers": "−1 per tackle zone, +1 for Chain of Custody skill",
            "failure": "Ball scatters + TURNOVER",
        },
        "hand_off_rules": {
            "requirements": "Adjacent teammates only",
            "roll": "None (automatic success)",
            "failure": "Never (if legal)",
        },
    }
