"""Configuration for documentation generator."""
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Source directories
TEMPLATES_DIR = PROJECT_ROOT / "docs_generator" / "templates"
SKILLS_DIR = PROJECT_ROOT / "skills"

# Output file mappings: template -> output path
OUTPUT_MAPPING = {
    "ROSTERS.md.j2": SKILLS_DIR / "scramble-setup" / "references" / "ROSTERS.md",
    "API-REFERENCE.md.j2": SKILLS_DIR / "ankh-morpork-scramble" / "references" / "API-REFERENCE.md",
    "GAME-RULES.md.j2": SKILLS_DIR / "ankh-morpork-scramble" / "references" / "GAME-RULES.md",
    "MOVEMENT-RULES.md.j2": SKILLS_DIR / "scramble-movement" / "references" / "MOVEMENT-RULES.md",
    "BLOCK-DICE.md.j2": SKILLS_DIR / "scramble-combat" / "references" / "BLOCK-DICE.md",
    "PASS-RULES.md.j2": SKILLS_DIR / "scramble-ball-handling" / "references" / "PASS-RULES.md",
}
