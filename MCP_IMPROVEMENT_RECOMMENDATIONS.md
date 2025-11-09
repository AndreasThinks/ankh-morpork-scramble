# MCP Implementation Improvement Recommendations

## Executive Summary

Your MCP implementation is solid and functional, but there are several opportunities to make it more robust, maintainable, and aligned with FastMCP best practices.

---

## Critical Issues

### 1. **Missing Import - CRITICAL BUG** 🔴

**File**: `app/mcp_server.py:781, 837`

**Issue**: `GamePhase` enum is used but not imported.

```python
# Line 8 - Missing import
from app.models.enums import ActionType  # GamePhase is NOT imported
# Lines 781, 837 use GamePhase.DEPLOYMENT but will raise NameError
```

**Impact**: `place_players()` and `ready_to_play()` will crash when called.

**Fix**:
```python
from app.models.enums import ActionType, GamePhase
```

---

## High-Priority Improvements

### 2. **Add Explicit Operation IDs** 🟡

**Reference**: FastMCP docs emphasize "Operation IDs Matter"

**Current**: Tools use default function names
**Recommended**: Add explicit operation IDs for better LLM understanding

```python
@mcp.tool(name="join_game_session")
def join_game(...):
    """Join a game and mark your team as ready to play."""

@mcp.tool(name="get_current_game_state")
def get_game_state(...):
    """Get the complete current state of the game."""
```

**Benefit**: More descriptive names help LLMs understand tool purposes without reading full docstrings.

---

### 3. **Use MCP Resources for Read-Only Operations** 🟡

**Reference**: FastMCP docs - "map GET requests to resources"

**Current**: All 16 operations are Tools
**Recommended**: Convert read-only operations to Resources

**Why**: Resources are semantically correct for read-only data retrieval and help LLMs understand which operations have side effects.

**Candidates for Resource conversion**:
- `get_game_state` → Resource: `game://{game_id}/state`
- `get_valid_actions` → Resource: `game://{game_id}/actions`
- `get_history` → Resource: `game://{game_id}/history`
- `get_messages` → Resource: `game://{game_id}/messages`
- `get_team_budget` → Resource: `game://{game_id}/team/{team_id}/budget`
- `get_available_positions` → Resource: `game://{game_id}/team/{team_id}/positions`

**Implementation Example**:
```python
@mcp.resource("game://{game_id}/state")
def game_state_resource(game_id: str) -> str:
    """Get the complete current state of the game."""
    manager = get_manager()
    game_state = manager.get_game(game_id)

    if not game_state:
        raise ToolError(f"Game '{game_id}' not found.")

    return game_state.model_dump_json()
```

**Tools remain for write operations**: `join_game`, `execute_action`, `end_turn`, `buy_player`, etc.

---

### 4. **Improve Lifespan Management** 🟡

**Reference**: FastMCP docs - "Combining Lifespans"

**Current** (`main.py:68`):
```python
app = FastAPI(lifespan=mcp_app.lifespan)
```

**Issue**: If FastAPI needs its own initialization (database, cache), lifespan combination is needed.

**Recommended**:
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    # FastAPI startup logic
    logger.info("FastAPI app starting...")

    # Nested MCP startup
    async with mcp_app.lifespan(app):
        yield

    # FastAPI shutdown logic
    logger.info("FastAPI app shutting down...")

app = FastAPI(
    title="Ankh-Morpork Scramble API",
    lifespan=combined_lifespan
)
```

**Benefit**: Proper ordering of startup/shutdown, better resource management.

---

### 5. **Add Structured Error Context** 🟡

**Current**: Basic string error messages
**Recommended**: Structured error responses with context

```python
class GameError(ToolError):
    """Game-specific MCP error with context"""
    def __init__(self, message: str, context: dict = None):
        super().__init__(message)
        self.context = context or {}

# Usage
raise GameError(
    f"Not your turn! It's {active_team.id}'s turn.",
    context={
        "active_team": active_team.id,
        "requested_team": team_id,
        "turn_number": game_state.turn.team_turn,
        "phase": game_state.phase.value
    }
)
```

**Benefit**: LLMs can use structured context to make better decisions.

---

### 6. **Standardize Return Types** 🟡

**Current**: Mix of `dict`, `ActionResult`, model objects
**Recommended**: Consistent Pydantic models for all responses

```python
from pydantic import BaseModel

class JoinGameResponse(BaseModel):
    success: bool
    team_id: str
    players_ready: bool
    game_started: bool
    phase: str
    message: str

@mcp.tool
def join_game(...) -> JoinGameResponse:
    # ...
    return JoinGameResponse(
        success=True,
        team_id=team_id,
        players_ready=game_state.players_ready,
        game_started=game_state.game_started,
        phase=game_state.phase.value,
        message=message
    )
```

**Benefit**: Better type safety, automatic validation, clearer API contracts.

---

### 7. **Add Validation Decorator** 🟢

**Current**: Repeated validation code in every tool
**Recommended**: DRY with decorators

```python
from functools import wraps

def require_game(func):
    """Decorator to validate game exists"""
    @wraps(func)
    def wrapper(game_id: str, *args, **kwargs):
        manager = get_manager()
        game_state = manager.get_game(game_id)

        if not game_state:
            raise ToolError(f"Game '{game_id}' not found.")

        # Pass game_state to function
        return func(game_state, *args, **kwargs)
    return wrapper

@mcp.tool
@require_game
def get_game_state(game_state: GameState) -> dict:
    """Get the complete current state of the game."""
    return game_state.model_dump()
```

**Benefit**: Reduces code duplication, cleaner function bodies.

---

### 8. **Use In-Memory Transport for Testing** 🟢

**Reference**: FastMCP docs - "Use in-memory transport for testing"

**Current** (`tests/test_mcp_server.py`): Creates full HTTP client
**Recommended**: Use built-in memory transport

```python
import pytest
from fastmcp.client import Client
from app.mcp_server import mcp

@pytest.mark.asyncio
async def test_join_game_with_memory_transport():
    # Use in-memory transport - much faster
    async with mcp.create_in_memory_client() as client:
        result = await client.call_tool(
            "join_game",
            arguments={"game_id": "test-game", "team_id": "team1"}
        )
        assert result["success"] is True
```

**Benefit**: 10-100x faster tests, no HTTP overhead.

---

### 9. **Add Tool Metadata/Categories** 🟢

**Recommended**: Add metadata to help LLMs understand tool purposes

```python
@mcp.tool(
    name="join_game",
    description="Join a game and mark your team as ready to play.",
    metadata={
        "category": "game_management",
        "phase": "any",
        "side_effects": True,
        "required_for": "starting_game"
    }
)
def join_game(...):
    pass

@mcp.tool(
    name="buy_player",
    metadata={
        "category": "team_setup",
        "phase": "deployment",
        "side_effects": True,
        "requires": ["budget_check"]
    }
)
def buy_player(...):
    pass
```

**Benefit**: LLMs can better understand when to use each tool.

---

### 10. **Add Request Correlation IDs** 🟢

**Recommended**: Track related MCP calls for better debugging

```python
import contextvars
import uuid

# Create context variable for correlation ID
correlation_id_var = contextvars.ContextVar('correlation_id', default=None)

@mcp.tool
def join_game(...):
    """Join a game and mark your team as ready to play."""
    # Generate or retrieve correlation ID
    corr_id = correlation_id_var.get() or str(uuid.uuid4())
    correlation_id_var.set(corr_id)

    logger.info(
        "MCP tool 'join_game' called",
        extra={
            "correlation_id": corr_id,
            "game_id": game_id,
            "team_id": team_id
        }
    )
    # ... rest of function
```

**Benefit**: Easier to trace multi-step agent workflows in logs.

---

### 11. **Add Health Check Resource** 🟢

**Recommended**: Add MCP-specific health check

```python
@mcp.resource("health://check")
def health_check() -> str:
    """Check MCP server health and game manager status"""
    manager = get_manager()
    active_games = len([g for g in manager._games.values() if g.game_started])

    return {
        "status": "healthy",
        "active_games": active_games,
        "total_games": len(manager._games),
        "version": "0.1.0"
    }
```

**Benefit**: Agents can verify MCP server is responsive.

---

## Medium-Priority Improvements

### 12. **Add Input Sanitization** 🟢

**Recommended**: Sanitize all string inputs to prevent injection

```python
import re

def sanitize_game_id(game_id: str) -> str:
    """Ensure game_id is safe"""
    if not re.match(r'^[a-zA-Z0-9_-]+$', game_id):
        raise ToolError("Invalid game_id format. Use only alphanumeric, dash, underscore.")
    return game_id

@mcp.tool
def join_game(game_id: str, team_id: str) -> dict:
    game_id = sanitize_game_id(game_id)
    team_id = sanitize_game_id(team_id)
    # ...
```

---

### 13. **Add Rate Limiting** 🟢

**Recommended**: Prevent abuse with rate limiting

```python
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_calls: int, window: timedelta):
        self.max_calls = max_calls
        self.window = window
        self.calls = defaultdict(list)

    def check(self, key: str):
        now = datetime.now()
        # Clean old calls
        self.calls[key] = [
            call_time for call_time in self.calls[key]
            if now - call_time < self.window
        ]

        if len(self.calls[key]) >= self.max_calls:
            raise ToolError("Rate limit exceeded. Please wait.")

        self.calls[key].append(now)

rate_limiter = RateLimiter(max_calls=100, window=timedelta(minutes=1))

@mcp.tool
def execute_action(...):
    rate_limiter.check(f"execute_action:{game_id}:{player_id}")
    # ... rest of function
```

---

### 14. **Add Retry Logic for Manager Operations** 🟢

**Recommended**: Add retry for transient failures

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def execute_with_retry(manager, game_state, action):
    """Execute action with retry on transient failures"""
    return manager.executor.execute_action(game_state, action)

@mcp.tool
def execute_action(...):
    # ...
    try:
        result = execute_with_retry(manager, game_state, action)
    except Exception as e:
        # ... error handling
```

---

### 15. **Add Tool Versioning** 🟢

**Recommended**: Version your MCP tools for backward compatibility

```python
@mcp.tool(
    name="execute_action_v2",
    description="Execute a game action (v2 - with enhanced error messages)"
)
def execute_action_v2(...):
    pass

# Keep old version for backward compatibility
@mcp.tool(
    name="execute_action",
    deprecated=True,
    description="Execute a game action (DEPRECATED - use execute_action_v2)"
)
def execute_action(...):
    pass
```

---

## Low-Priority / Future Enhancements

### 16. **Enable New OpenAPI Parser** 🔵

**Reference**: FastMCP docs - v2.11+ experimental parser

**Add to environment**:
```bash
FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER=true
```

**Benefit**: Better performance and maintainability (when stable).

---

### 17. **Add Tool Usage Analytics** 🔵

**Recommended**: Track which tools are used most

```python
from collections import Counter

tool_usage_stats = Counter()

@mcp.tool
def join_game(...):
    tool_usage_stats["join_game"] += 1
    # ... rest of function

@mcp.resource("analytics://tool_usage")
def tool_usage() -> str:
    """Get tool usage statistics"""
    return dict(tool_usage_stats)
```

---

### 18. **Add OpenAPI Schema Validation** 🔵

**Recommended**: Validate tool arguments against schema

```python
from pydantic import ValidationError

@mcp.tool
def execute_action(
    game_id: Annotated[str, "Game ID"],
    action_type: Annotated[ActionType, "Action type"],
    ...
) -> ActionResult:
    try:
        # Pydantic handles this automatically, but you can add custom validation
        if action_type not in ActionType:
            raise ToolError(f"Invalid action_type. Must be one of {list(ActionType)}")
    except ValidationError as e:
        raise ToolError(f"Validation error: {e}")
```

---

### 19. **Add Agent Authentication** 🔵

**Recommended**: Authenticate agents if needed

```python
from fastmcp.server import Server

@mcp.tool
def join_game(
    game_id: str,
    team_id: str,
    auth_token: Annotated[str, "Authentication token"] = None
) -> dict:
    # Verify auth_token
    if not verify_token(auth_token, team_id):
        raise ToolError("Authentication failed")
    # ... rest of function
```

---

## Implementation Priority

### Phase 1: Critical (Do First)
1. ✅ Fix `GamePhase` import bug
2. ✅ Add explicit operation IDs
3. ✅ Standardize return types
4. ✅ Add validation decorator

### Phase 2: High Value (Do Soon)
5. ✅ Convert read operations to Resources
6. ✅ Improve lifespan management
7. ✅ Add structured error context
8. ✅ Use in-memory transport for tests

### Phase 3: Polish (Nice to Have)
9. ✅ Add tool metadata/categories
10. ✅ Add correlation IDs
11. ✅ Add health check
12. ✅ Input sanitization
13. ✅ Rate limiting

### Phase 4: Future (When Needed)
14. ✅ Retry logic
15. ✅ Tool versioning
16. ✅ OpenAPI parser experiment
17. ✅ Analytics
18. ✅ Enhanced validation
19. ✅ Authentication

---

## Quick Wins (< 1 hour each)

1. **Fix import bug** (5 min)
2. **Add operation IDs** (15 min)
3. **Add validation decorator** (30 min)
4. **Add health check resource** (15 min)
5. **Update test to use in-memory transport** (20 min)

---

## Testing Recommendations

### Add MCP-Specific Tests

```python
# tests/test_mcp_improvements.py

import pytest
from fastmcp.client import Client

@pytest.mark.asyncio
async def test_all_tools_have_operation_ids():
    """Verify all tools have explicit operation IDs"""
    from app.mcp_server import mcp

    tools = mcp.list_tools()
    for tool in tools:
        assert tool.name, f"Tool missing operation ID: {tool}"
        assert "_" in tool.name, f"Tool should use snake_case: {tool.name}"

@pytest.mark.asyncio
async def test_all_resources_accessible():
    """Verify all resources are accessible"""
    from app.mcp_server import mcp

    async with mcp.create_in_memory_client() as client:
        resources = await client.list_resources()
        assert len(resources) > 0, "Should have at least one resource"

@pytest.mark.asyncio
async def test_error_messages_are_structured():
    """Verify error messages contain helpful context"""
    from app.mcp_server import mcp

    async with mcp.create_in_memory_client() as client:
        try:
            await client.call_tool(
                "join_game",
                arguments={"game_id": "nonexistent", "team_id": "team1"}
            )
        except Exception as e:
            assert "not found" in str(e).lower()
            # Could also check for structured error context
```

---

## References

- [FastMCP FastAPI Integration Docs](https://gofastmcp.com/integrations/fastapi)
- [MCP Protocol Specification](https://spec.modelcontextprotocol.io/)
- Your implementation files:
  - `app/mcp_server.py` - Tool implementations
  - `app/main.py` - FastAPI integration
  - `tests/test_mcp_server.py` - Test suite

---

## Summary

Your MCP implementation is well-structured and functional. The recommended improvements will make it:

- **More robust**: Better error handling, validation, rate limiting
- **More maintainable**: DRY code, standardized patterns, versioning
- **More performant**: In-memory testing, resource caching
- **More LLM-friendly**: Explicit operation IDs, tool metadata, structured errors
- **Better aligned with best practices**: Resources vs tools, lifespan management

Start with Phase 1 (critical fixes), then progressively implement phases 2-4 based on your needs.
