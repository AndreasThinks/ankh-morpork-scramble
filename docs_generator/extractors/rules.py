"""Extract and format game rules from rules.md"""
from pathlib import Path


def extract_game_rules() -> dict:
    """Extract game rules from rules.md file.
    
    Returns:
        Dict with formatted rules content
    """
    rules_path = Path(__file__).parent.parent.parent / "rules.md"
    
    if not rules_path.exists():
        return {
            "content": "# Game Rules\n\n*Rules file not found*",
            "has_content": False,
        }
    
    # Read the rules file
    content = rules_path.read_text()
    
    # Extract key sections for summary
    lines = content.split("\n")
    sections = []
    current_section = None
    
    for line in lines:
        if line.startswith("## "):
            if current_section:
                sections.append(current_section)
            current_section = {"title": line[3:].strip(), "content": []}
        elif current_section is not None:
            current_section["content"].append(line)
    
    if current_section:
        sections.append(current_section)
    
    return {
        "full_content": content,
        "sections": sections,
        "has_content": True,
    }
