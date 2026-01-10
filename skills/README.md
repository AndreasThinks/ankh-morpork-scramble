# Ankh-Morpork Scramble Agent Skills

This directory contains modular Agent Skills following the [agentskills.io](https://agentskills.io) specification, enabling AI agents to play Ankh-Morpork Scramble - a turn-based fantasy sports game.

## Overview

These skills provide strategic guidance for AI agents to understand and play the game effectively. The skills are designed with **progressive disclosure** - lightweight metadata for discovery, comprehensive guidance when activated.

## Skills Structure

### 🎮 Core Orchestrator
**ankh-morpork-scramble** - Main coordination skill
- Game flow management
- Phase transitions (DEPLOYMENT → KICKOFF → PLAYING)
- Turn management and action sequencing
- Complete API reference and game rules

### 🏗️ Specialized Skills (Manual Activation)

**scramble-setup** - Deployment Phase
- Team roster selection and budgeting
- Player positioning strategies
- 11-player lineup optimization

**scramble-movement** - Movement Tactics
- Path planning and dodge mechanics
- Tackle zone navigation
- Rush move decisions

**scramble-combat** - Blocking (Scuffling)
- Strength comparison and dice probabilities
- Block result interpretation
- Injury mechanics

**scramble-ball-handling** - Ball Control
- Pickup, pass, catch strategies
- Risk assessment and turnover avoidance
- Scoring tactics

## How to Use

### For AI Agents

1. **Load orchestrator first**: `ankh-morpork-scramble` provides game context and coordinates other skills

2. **Activate skills as needed**:
   - During DEPLOYMENT → use `scramble-setup`
   - During PLAYING phase:
     - Moving players → `scramble-movement`
     - Blocking enemies → `scramble-combat`
     - Ball actions → `scramble-ball-handling`

3. **Follow progressive disclosure pattern**:
   - SKILL.md provides strategic guidance and decision frameworks
   - references/ contain detailed mechanics and tables

### File Structure

Each skill follows this pattern:
```
skill-name/
├── SKILL.md              # Strategic guidance (basic level)
└── references/           # Detailed mechanics
    └── SPECIFIC-RULES.md # Deep dive on subsystem
```

## Skills Metadata

All SKILL.md files include YAML frontmatter:

```yaml
---
name: skill-name
description: Brief purpose
version: 1.0.0
guidance_level: basic
activation_mode: manual
dependencies: [...]
tags: [...]
---
```

## Game Integration

These skills integrate with the Ankh-Morpork Scramble REST API:

- **Base URL**: `http://localhost:8000` (development)
- **Interactive Docs**: `/docs` endpoint
- **Key Endpoints**:
  - `POST /game/join` - Join game as team
  - `GET /game/{game_id}` - Get current state
  - `POST /game/{game_id}/action` - Execute action
  - `POST /game/{game_id}/end-turn` - End turn

Full API documentation in `ankh-morpork-scramble/references/API-REFERENCE.md`

## Guidance Level

All skills are set to **basic** guidance level:
- Clear strategic frameworks
- Decision trees and patterns
- Risk assessment guidelines
- Tactical tips and common scenarios
- No hand-holding - agents make autonomous decisions

## Dependencies

```
ankh-morpork-scramble (orchestrator)
├── scramble-setup
├── scramble-movement
├── scramble-combat
└── scramble-ball-handling
```

All specialized skills depend on the orchestrator for context.

## Key Concepts

### Game Phases
1. **DEPLOYMENT** - Buy and place 11 players
2. **KICKOFF** - Ball is kicked, random scatter
3. **PLAYING** - Turn-based gameplay until touchdown

### Turn Structure
- Teams alternate turns
- Actions: MOVE, BLOCK, PASS, PICKUP, HAND_OFF
- Turnovers: Failed dodge, failed rush, failed pickup/catch, fumble
- Turn ends: Manual end_turn or automatic on turnover

### Victory Condition
**First team to score a touchdown wins immediately!**

## Quick Start Example

```python
# 1. Agent loads orchestrator skill
load_skill("ankh-morpork-scramble")

# 2. Join game
POST /game/join {"team_name": "Mighty Ducks"}

# 3. During DEPLOYMENT phase, activate setup skill
load_skill("scramble-setup")
# Follow ROSTERS.md to buy players within budget
# Place 11 players according to formation patterns

# 4. During PLAYING phase, activate tactical skills as needed
load_skill("scramble-movement")  # When planning player moves
load_skill("scramble-combat")    # When considering blocks
load_skill("scramble-ball-handling")  # When handling ball

# 5. Execute actions via API
POST /game/{game_id}/action {
  "action_type": "MOVE",
  "player_id": "...",
  "path": [{"x": 10, "y": 7}, {"x": 11, "y": 7}]
}

# 6. End turn when done
POST /game/{game_id}/end-turn
```

## Design Principles

1. **Modular** - Each skill focuses on one game aspect
2. **Progressive** - Light discovery, deep activation
3. **Autonomous** - Guidance, not prescriptive instructions
4. **API-driven** - Direct integration with game server
5. **Risk-aware** - Clear assessment of action consequences

## Version History

- **v1.0.0** (2026-10-01) - Initial release
  - 5 modular skills covering full game flow
  - Basic guidance level
  - REST API integration
  - Complete rule mechanics

## Contributing

When updating skills:
- Maintain YAML frontmatter format
- Keep guidance at basic level (no hand-holding)
- Use progressive disclosure (SKILL.md → references/)
- Test against actual game API
- Update version numbers following semver

## License

These skills are provided as part of the Ankh-Morpork Scramble project. See project LICENSE for details.

---

**For more information**: See project README.md and rules.md in the root directory.
