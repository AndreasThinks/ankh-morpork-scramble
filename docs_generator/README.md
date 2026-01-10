# Documentation Generator

Auto-generates Agent Skills reference documentation from code sources of truth.

## Overview

This package keeps documentation synchronized with code by extracting data from Python modules and rendering it through Jinja2 templates. When you edit team rosters, game mechanics, or API endpoints, simply run `make generate-docs` to update all documentation.

## Architecture

```
docs_generator/
├── extractors/          # Pull data from code
│   ├── roster.py       # Extract team rosters from app/models/team.py
│   ├── api.py          # Extract API schema from FastAPI
│   ├── mechanics.py    # Extract game mechanics constants
│   └── rules.py        # Parse rules.md file
├── templates/           # Jinja2 templates for markdown
│   ├── ROSTERS.md.j2
│   ├── API-REFERENCE.md.j2
│   ├── GAME-RULES.md.j2
│   ├── MOVEMENT-RULES.md.j2
│   ├── BLOCK-DICE.md.j2
│   └── PASS-RULES.md.j2
├── config.py            # Output paths and mappings
└── generate.py          # Main CLI script
```

## Usage

### Generate All Documentation

```bash
make generate-docs
```

This regenerates all 6 reference files in `skills/*/references/`.

### Check if Docs Are Current

```bash
make check-docs
```

Returns exit code 0 if docs are up to date, 1 if they need regeneration. Useful for CI/CD pipelines.

## What Gets Auto-Generated

| File | Source | Template |
|------|--------|----------|
| `skills/scramble-setup/references/ROSTERS.md` | `app/models/team.py` | `ROSTERS.md.j2` |
| `skills/ankh-morpork-scramble/references/API-REFERENCE.md` | FastAPI OpenAPI schema | `API-REFERENCE.md.j2` |
| `skills/ankh-morpork-scramble/references/GAME-RULES.md` | `rules.md` | `GAME-RULES.md.j2` |
| `skills/scramble-movement/references/MOVEMENT-RULES.md` | `app/game/movement.py` | `MOVEMENT-RULES.md.j2` |
| `skills/scramble-combat/references/BLOCK-DICE.md` | `app/game/combat.py` | `BLOCK-DICE.md.j2` |
| `skills/scramble-ball-handling/references/PASS-RULES.md` | `app/game/ball_handling.py` | `PASS-RULES.md.j2` |

## What Stays Hand-Written

The main `SKILL.md` files contain strategic guidance and decision frameworks that aren't derivable from code. These remain manually authored and are not touched by the generator.

## Adding New Generated Documentation

1. **Create extractor function** in `extractors/`:
   ```python
   def extract_new_data() -> dict:
       # Pull data from code
       return {"key": "value"}
   ```

2. **Create Jinja2 template** in `templates/`:
   ```markdown
   # My New Reference
   
   {{ key }}
   ```

3. **Register in config.py**:
   ```python
   OUTPUT_MAPPING = {
       "MY-NEW.md.j2": SKILLS_DIR / "my-skill" / "references" / "MY-NEW.md",
   }
   ```

4. **Add extractor to generate.py**:
   ```python
   data_extractors = {
       "MY-NEW.md.j2": extract_new_data,
   }
   ```

5. **Run**: `make generate-docs`

## Custom Jinja2 Filters

### `format_gold`

Formats integer as gold with thousands separators:
```jinja2
{{ 50000 | format_gold }}  → "50,000gp"
```

Add more filters in `generate.py`'s `setup_jinja_env()` function.

## CI Integration

Add to `.github/workflows/test.yml`:

```yaml
- name: Check docs are current
  run: make check-docs
```

This ensures PRs that change code also update documentation.

## Example Workflow

```bash
# 1. Edit team roster
vim app/models/team.py

# 2. Add new player type with stats
# ... code changes ...

# 3. Regenerate docs
make generate-docs

# 4. Verify changes
git diff skills/scramble-setup/references/ROSTERS.md

# 5. Commit both code and docs
git add app/models/team.py skills/scramble-setup/references/ROSTERS.md
git commit -m "Add new player type"
```

## Benefits

✅ **Single source of truth** - Code defines data, docs reflect code  
✅ **No stale docs** - Always matches actual implementation  
✅ **Type-safe** - Extracts from Pydantic models  
✅ **Fast** - Full regeneration takes ~2 seconds  
✅ **CI-friendly** - Check mode validates docs in pipelines

## Troubleshooting

### "No extractor for template"

The template exists but isn't registered in `generate.py`'s `data_extractors` dict. Add the mapping.

### "Template not found"

Template file missing from `templates/` directory. Check filename and `.j2` extension.

### Import errors

The generator imports from `app.*` modules. Ensure your Python environment has the project installed: `uv pip install -e .`

---

**Version**: 1.0.0  
**Maintainer**: Auto-generated documentation system
