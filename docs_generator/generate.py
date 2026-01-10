"""Main documentation generator script.

Usage:
    python -m docs_generator.generate           # Generate all docs
    python -m docs_generator.generate --check   # Check if docs are current (for CI)
"""
import sys
import argparse
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from docs_generator.config import TEMPLATES_DIR, OUTPUT_MAPPING
from docs_generator.extractors import (
    extract_rosters,
    extract_api_schema,
    extract_movement_rules,
    extract_combat_rules,
    extract_pass_rules,
    extract_game_rules,
)


def format_gold(value: int) -> str:
    """Format gold amount with thousand separators."""
    return f"{value:,}gp"


def setup_jinja_env() -> Environment:
    """Set up Jinja2 environment with templates and filters."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    
    # Add custom filters
    env.filters['format_gold'] = format_gold
    
    return env


def generate_all(check_only: bool = False) -> int:
    """Generate all documentation files.
    
    Args:
        check_only: If True, check if files would change (don't write)
    
    Returns:
        0 if successful (or no changes in check mode), 1 otherwise
    """
    env = setup_jinja_env()
    
    # Map templates to their data extractors
    data_extractors = {
        "ROSTERS.md.j2": extract_rosters,
        "API-REFERENCE.md.j2": extract_api_schema,
        "GAME-RULES.md.j2": extract_game_rules,
        "MOVEMENT-RULES.md.j2": extract_movement_rules,
        "BLOCK-DICE.md.j2": extract_combat_rules,
        "PASS-RULES.md.j2": extract_pass_rules,
    }
    
    files_changed = []
    errors = []
    
    for template_name, output_path in OUTPUT_MAPPING.items():
        try:
            print(f"Processing {template_name}...")
            
            # Get the appropriate extractor
            extractor = data_extractors.get(template_name)
            if not extractor:
                print(f"  ⚠️  No extractor for {template_name}, skipping")
                continue
            
            # Extract data
            data = extractor()
            
            # Render template
            template = env.get_template(template_name)
            rendered = template.render(**data)
            
            # Check if file would change
            if output_path.exists():
                current_content = output_path.read_text()
                if current_content == rendered:
                    print(f"  ✓ {output_path.name} is up to date")
                    continue
                else:
                    print(f"  ⚠️  {output_path.name} would change")
                    files_changed.append(output_path.name)
            else:
                print(f"  + {output_path.name} would be created")
                files_changed.append(output_path.name)
            
            # Write file (unless check-only mode)
            if not check_only:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(rendered)
                print(f"  ✓ Generated {output_path.name}")
        
        except Exception as e:
            error_msg = f"Error processing {template_name}: {e}"
            print(f"  ✗ {error_msg}")
            errors.append(error_msg)
    
    # Print summary
    print("\n" + "="*60)
    if errors:
        print(f"❌ Completed with {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    
    if check_only:
        if files_changed:
            print(f"❌ {len(files_changed)} file(s) are out of date:")
            for file in files_changed:
                print(f"  - {file}")
            print("\nRun 'make generate-docs' to update them.")
            return 1
        else:
            print("✅ All documentation is up to date!")
            return 0
    else:
        print(f"✅ Successfully generated {len(OUTPUT_MAPPING)} documentation files")
        if files_changed:
            print(f"   Updated: {', '.join(files_changed)}")
        return 0


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate documentation from code sources"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if docs are current without writing (for CI)",
    )
    
    args = parser.parse_args()
    
    try:
        exit_code = generate_all(check_only=args.check)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
