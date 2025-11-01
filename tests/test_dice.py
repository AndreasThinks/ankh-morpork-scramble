"""Tests for dice rolling system"""
import pytest
from app.game.dice import DiceRoller


def test_dice_roller_seeded():
    """Test that seeded dice roller produces deterministic results"""
    roller1 = DiceRoller(seed=42)
    roller2 = DiceRoller(seed=42)
    
    # Same seed should produce same results
    assert roller1.roll_d6() == roller2.roll_d6()
    assert roller1.roll_2d6() == roller2.roll_2d6()


def test_roll_d6_range():
    """Test that d6 rolls are in valid range"""
    roller = DiceRoller(seed=42)
    
    for _ in range(100):
        roll = roller.roll_d6()
        assert 1 <= roll <= 6


def test_roll_2d6_range():
    """Test that 2d6 rolls are in valid range"""
    roller = DiceRoller(seed=42)
    
    for _ in range(100):
        roll = roller.roll_2d6()
        assert 2 <= roll <= 12


def test_roll_target():
    """Test target roll mechanics"""
    roller = DiceRoller(seed=42)
    
    # Roll against target 3+
    result = roller.roll_target(3, "test")
    assert result.type == "test"
    assert result.target == 3
    assert 1 <= result.result <= 6
    assert result.success == (result.result >= 3)


def test_roll_target_with_modifiers():
    """Test target rolls with modifiers"""
    roller = DiceRoller(seed=42)
    
    modifiers = {"skill_bonus": 1, "tackle_zones": -1}
    result = roller.roll_target(4, "test", modifiers)
    
    assert result.modifiers == modifiers
    assert sum(result.modifiers.values()) == 0  # +1 -1 = 0


def test_armor_roll():
    """Test armor break mechanics"""
    roller = DiceRoller(seed=42)
    
    result = roller.roll_armor(9)
    assert result.type == "armor"
    assert result.target == 9
    assert 2 <= result.result <= 12
    assert result.success == (result.result >= 9)


def test_injury_roll():
    """Test injury roll results"""
    roller = DiceRoller(seed=42)
    
    dice_roll, injury_type = roller.roll_injury()
    assert dice_roll.type == "injury"
    assert 2 <= dice_roll.result <= 12
    
    # Check injury type mapping
    assert injury_type in ["stunned", "knocked_out", "casualty"]
    
    if dice_roll.result <= 7:
        assert injury_type == "stunned"
    elif dice_roll.result <= 9:
        assert injury_type == "knocked_out"
    else:
        assert injury_type == "casualty"


def test_scatter():
    """Test ball scatter mechanics"""
    roller = DiceRoller(seed=42)
    
    for _ in range(20):
        dx, dy = roller.scatter()
        
        # Should be adjacent square including diagonals
        assert -1 <= dx <= 1
        assert -1 <= dy <= 1
        # Should not be (0, 0)
        assert not (dx == 0 and dy == 0)
