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
    SCUFFLE = "scuffle"  # was BLOCK - Discworld street fighting
    CHARGE = "charge"  # was BLITZ - aggressive rush
    HURL = "hurl"  # was PASS - throwing the ball
    QUICK_PASS = "quick_pass"  # was HAND_OFF - short transfer
    BOOT = "boot"  # was FOUL - Ankh-Morpork street tactics
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

    # NEW: City Watch - Troll skills
    THICK_AS_A_BRICK = "thick_as_a_brick"  # Thick Skull
    ROCK_SOLID = "rock_solid"  # Stand Firm
    REALLY_THICK = "really_thick"  # Bone Head
    COOLING_HELMET = "cooling_helmet"  # Bone Head (2+ only) - Detritus special
    CROSSBOW_TRAINING = "crossbow_training"  # Mighty Blow +1
    BREAK_HEADS = "break_heads"  # Break Tackle

    # NEW: City Watch - Street Fighter skills
    STREET_FIGHTING = "street_fighting"  # Dirty Player +1
    SLIPPERY = "slippery"  # Dodge

    # NEW: City Watch - Werewolf skills
    LUPINE_SPEED = "lupine_speed"  # Sure Feet
    KEEN_SENSES = "keen_senses"  # Catch
    REGENERATIVE = "regenerative"  # Regeneration

    # NEW: City Watch - Carrot skills (star player)
    TRUE_KING = "true_king"  # Leader
    KINGLY_PRESENCE = "kingly_presence"  # Guard
    HONEST_FIGHTER = "honest_fighter"  # Block
    WILL_NOT_BACK_DOWN = "will_not_back_down"  # Dauntless
    DIPLOMATIC_IMMUNITY = "diplomatic_immunity"  # Fend
    TRUSTED_BY_ALL = "trusted_by_all"  # Inspiring Presence

    # NEW: Unseen University - Combat skills
    COMBAT_EVOCATION = "combat_evocation"  # Block
    ARCANE_STRIKE = "arcane_strike"  # Mighty Blow +1
    BATTLE_HARDENED = "battle_hardened"  # Thick Skull
    AGGRESSIVE_CASTING = "aggressive_casting"  # Juggernaut

    # NEW: Unseen University - Speed skills
    HASTE_SPELL = "haste_spell"  # Sprint
    BLINK_DODGE = "blink_dodge"  # Dodge
    FLEET_FOOTED = "fleet_footed"  # Sure Feet

    # NEW: Unseen University - Tech skills
    HEX_ASSISTED = "hex_assisted"  # Sure Hands
    CALCULATED_TRAJECTORY = "calculated_trajectory"  # Pass
    SAFE_PAIR_OF_HANDS = "safe_pair_of_hands"  # Safe Pass
    DUMP_OFF_SPELL = "dump_off_spell"  # Dump-Off

    # NEW: Unseen University - Librarian skills (star player)
    PREHENSILE_EVERYTHING = "prehensile_everything"  # Extra Arms
    LIBRARY_SWINGING = "library_swinging"  # Leap
    PROTECTIVE_INSTINCT = "protective_instinct"  # Guard
    BIBLIOPHILE_RAGE = "bibliophile_rage"  # Frenzy
    TERRIFYING_GLARE = "terrifying_glare"  # Disturbing Presence

    # NEW: Unseen University - Ridcully skills (star player)
    ARCHCHANCELLOR = "archchancellor"  # Leader
    ROBUST_PHYSIQUE = "robust_physique"  # Block
    BOOMING_VOICE = "booming_voice"  # Guard
    ARCANE_MASTERY = "arcane_mastery"  # Pass
    HEADOLOGY_EXPERT = "headology_expert"  # Hypnotic Gaze
    STUBBORN = "stubborn"  # Stand Firm

    # NEW: Orangutan skills
    SIMIAN_AGILITY = "simian_agility"  # Leap
    FOUR_LIMBS = "four_limbs"  # Extra Arms
    INDEPENDENT = "independent"  # Loner 4+


class GamePhase(str, Enum):
    """Game phases"""
    DEPLOYMENT = "deployment"  # was SETUP - teams deploy their forces
    OPENING_SCRAMBLE = "opening_scramble"  # was KICKOFF - the match begins
    ACTIVE_PLAY = "active_play"  # was PLAYING - the game in action
    INTERMISSION = "intermission"  # was HALF_TIME - break between halves
    CONCLUDED = "concluded"  # was FINISHED - match over


class SkillCategory(str, Enum):
    """Skill categories for advancement"""
    GENERAL = "G"
    AGILITY = "A"
    STRENGTH = "S"
    PASSING = "P"
