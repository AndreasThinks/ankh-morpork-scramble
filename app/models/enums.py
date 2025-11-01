"""Game enumerations"""
from enum import Enum


class PlayerState(str, Enum):
    """Player states during the game"""
    STANDING = "standing"
    PRONE = "prone"
    STUNNED = "stunned"
    KNOCKED_OUT = "knocked_out"
    CASUALTY = "casualty"


class ActionType(str, Enum):
    """Available action types per turn"""
    MOVE = "move"
    BLOCK = "block"
    BLITZ = "blitz"
    PASS = "pass"
    HAND_OFF = "hand_off"
    FOUL = "foul"
    STAND_UP = "stand_up"


class TeamType(str, Enum):
    """Available teams"""
    CITY_WATCH = "city_watch"
    UNSEEN_UNIVERSITY = "unseen_university"


class BlockResult(str, Enum):
    """Block dice outcomes"""
    ATTACKER_DOWN = "attacker_down"
    BOTH_DOWN = "both_down"
    PUSH = "push"
    DEFENDER_STUMBLES = "defender_stumbles"
    DEFENDER_DOWN = "defender_down"


class InjuryResult(str, Enum):
    """Injury roll outcomes"""
    STUNNED = "stunned"
    KNOCKED_OUT = "knocked_out"
    CASUALTY = "casualty"


class PassResult(str, Enum):
    """Pass accuracy outcomes"""
    ACCURATE = "accurate"
    INACCURATE = "inaccurate"
    WILDLY_INACCURATE = "wildly_inaccurate"
    FUMBLE = "fumble"


class SkillType(str, Enum):
    """Themed skill names mapped to their effects"""
    # City Watch skills
    DRILL_HARDENED = "drill_hardened"  # Block
    PIGEON_POST = "pigeon_post"  # Pass
    CHAIN_OF_CUSTODY = "chain_of_custody"  # Sure Hands
    QUICK_GRAB = "quick_grab"  # Catch
    SIDESTEP_SHUFFLE = "sidestep_shuffle"  # Dodge
    
    # Wizard skills
    BLINK = "blink"  # Dodge
    SMALL_AND_SNEAKY = "small_and_sneaky"  # Stunty
    PORTABLE = "portable"  # Right Stuff
    POINTY_HAT_PADDING = "pointy_hat_padding"  # Thick Skull
    REROLL_THE_THESIS = "reroll_the_thesis"  # Brawler
    GRAPPLING_CANTRIP = "grappling_cantrip"  # Grab
    
    # Gargoyle skills
    BOUND_SPIRIT = "bound_spirit"  # Loner (3+)
    STONE_THICK = "stone_thick"  # Mighty Blow (+1)
    PIGEON_PROOF = "pigeon_proof"  # Projectile Vomit
    MINDLESS_MASONRY = "mindless_masonry"  # Really Stupid
    WEATHERED = "weathered"  # Regeneration
    LOB_THE_LACKEY = "lob_the_lackey"  # Throw Team-Mate
    OCCASIONAL_BITE_MARK = "occasional_bite_mark"  # Always Hungry


class GamePhase(str, Enum):
    """Game phases"""
    SETUP = "setup"
    KICKOFF = "kickoff"
    PLAYING = "playing"
    HALF_TIME = "half_time"
    FINISHED = "finished"


class SkillCategory(str, Enum):
    """Skill categories for advancement"""
    GENERAL = "G"
    AGILITY = "A"
    STRENGTH = "S"
    PASSING = "P"
