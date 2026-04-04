# Plan: Pitch State Visuals

**File to edit:** `app/web/templates/dashboard.html` only.
Read it fully before editing. Do not touch any Python files.

---

## Task 1: Player state rendered on token

### Goal
Standing, stunned, and knocked-out players should look visually distinct on the
pitch. Currently all tokens look identical regardless of `player.state`.

### States to handle
| State | Visual treatment |
|-------|-----------------|
| `standing` | Current style — team color fill, initials, solid border |
| `stunned` | Half-opacity fill, yellow-amber stroke ring, label `~` |
| `knocked_out` | Grey fill (#606060), red-tinted dashed border, label `✕` |
| `casualty` | Already removed from pitch — no change needed |

### Changes to `buildPlayerToken(playerId, player, pos, team, isCarrier)`

After building the base circle, apply state-dependent styling:

```js
const playerState = player.state || 'standing';

// Body circle
const circle = document.createElementNS(SVG_NS, 'circle');
circle.setAttribute('cx', pos.x + 0.5);
circle.setAttribute('cy', pos.y + 0.5);
circle.setAttribute('r', 0.42);
circle.dataset.role = 'body';

if (playerState === 'knocked_out') {
    circle.setAttribute('fill', '#555');
    circle.setAttribute('fill-opacity', '0.75');
    circle.setAttribute('stroke', 'rgba(200,70,50,0.8)');
    circle.setAttribute('stroke-width', '0.1');
    circle.setAttribute('stroke-dasharray', '0.25 0.15');
} else if (playerState === 'stunned') {
    circle.setAttribute('fill', `var(${team.color})`);
    circle.setAttribute('fill-opacity', '0.4');
    circle.setAttribute('stroke', 'rgba(255,210,60,0.8)');
    circle.setAttribute('stroke-width', '0.1');
} else {
    // standing — current defaults
    circle.setAttribute('fill', `var(${team.color})`);
    circle.setAttribute('stroke', 'rgba(18,12,7,0.9)');
    circle.setAttribute('stroke-width', '0.08');
}
token.appendChild(circle);

// Label — state-dependent
const label = document.createElementNS(SVG_NS, 'text');
label.setAttribute('x', pos.x + 0.5);
label.setAttribute('y', pos.y + 0.58);
label.setAttribute('text-anchor', 'middle');
label.setAttribute('font-size', '0.38');
label.setAttribute('fill', playerState === 'knocked_out' ? 'rgba(200,100,80,0.9)' : 'rgba(18,12,7,0.92)');
label.setAttribute('font-weight', '700');
label.dataset.role = 'label';

if (playerState === 'knocked_out') {
    label.textContent = '✕';
} else if (playerState === 'stunned') {
    label.textContent = '~';
} else {
    label.textContent = player.position.role.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}
token.appendChild(label);
```

### Changes to `updatePlayerToken(token, playerId, player, pos, team, isCarrier)`

After updating position (cx/cy), also resync body fill/stroke and label text to
match current `player.state`. Find `[data-role=body]` and `[data-role=label]`
and apply the same state-dependent logic as above.

The state can change between polls (e.g. a player gets knocked down mid-turn),
so `updatePlayerToken` must always re-apply state styling, not just position.

---

## Task 2: Event flash on involved players

### Goal
When a block or tackle fires, the involved player tokens briefly glow so the
eye is drawn to the action on the pitch.

### New function: `fireEventFlash(playerId, result, role)`

`role` is `'attacker'` or `'defender'`.

```js
function fireEventFlash(playerId, result, role) {
    const token = tokenElements.get(playerId);
    if (!token) return;
    const body = token.querySelector('[data-role=body]');
    if (!body) return;
    const cx = parseFloat(body.getAttribute('cx'));
    const cy = parseFloat(body.getAttribute('cy'));
    const tokensGroup = document.getElementById('pitch-tokens');
    if (!tokensGroup) return;

    // Color: attacker = warm gold, defender knocked = red, defender pushed = blue
    let color;
    if (role === 'attacker') {
        color = 'rgba(255,220,80,0.9)';
    } else if (result === 'failure' || result === 'turnover') {
        color = 'rgba(255,80,60,0.85)';
    } else {
        color = 'rgba(80,160,255,0.75)';
    }

    const flash = document.createElementNS(SVG_NS, 'circle');
    flash.setAttribute('cx', cx);
    flash.setAttribute('cy', cy);
    flash.setAttribute('r', 0.6);
    flash.setAttribute('fill', 'none');
    flash.setAttribute('stroke', color);
    flash.setAttribute('stroke-width', '0.12');
    flash.classList.add('event-flash');
    tokensGroup.appendChild(flash);
    flash.addEventListener('animationend', () => flash.remove(), { once: true });
}
```

### New CSS keyframe (add near `@keyframes tickerScroll`):

```css
@keyframes eventFlash {
    0%   { opacity: 1; r: 0.6; }
    60%  { opacity: 0.6; }
    100% { opacity: 0; r: 1.1; }
}
.event-flash {
    animation: eventFlash 0.7s ease-out forwards;
    pointer-events: none;
}
```

### Wire into `renderGameLog(events)`

After `lastRenderedEventCount = events.length;`, fire flashes for the most
recent new event (the last item in `newEvents`):

```js
if (newEvents.length > 0) {
    const latest = newEvents[newEvents.length - 1];
    if (latest.player_id) {
        fireEventFlash(latest.player_id, latest.result, 'attacker');
    }
    if (latest.target_player_id) {
        fireEventFlash(latest.target_player_id, latest.result, 'defender');
    }
}
```

---

## Task 3: Active team border on the pitch

### Goal
A thin colored border around the pitch SVG indicates whose turn it is.
Team 1 = blue (`--accent-blue`), Team 2 = orange (`--accent-orange`).
Updates every poll with no extra network calls.

### Implementation in `renderPitch(state)`

Add at the end of the function (after the loose ball logic):

```js
// Active team border
const svg = document.getElementById('pitch-canvas');
const activeTeamId = state.turn?.active_team_id;
const activeColor = activeTeamId === state.team1?.id
    ? 'var(--accent-blue)'
    : activeTeamId === state.team2?.id
    ? 'var(--accent-orange)'
    : 'rgba(217,180,91,0.3)';

let borderRect = svg.querySelector('[data-role="active-border"]');
if (!borderRect) {
    borderRect = document.createElementNS(SVG_NS, 'rect');
    borderRect.dataset.role = 'active-border';
    borderRect.setAttribute('fill', 'none');
    borderRect.setAttribute('stroke-width', '0.18');
    borderRect.setAttribute('rx', '0.15');
    borderRect.setAttribute('pointer-events', 'none');
    svg.appendChild(borderRect);
}
// Match the viewBox bounds — read them from the SVG
const vb = svg.viewBox?.baseVal;
if (vb) {
    borderRect.setAttribute('x', String(vb.x + 0.1));
    borderRect.setAttribute('y', String(vb.y + 0.1));
    borderRect.setAttribute('width',  String(vb.width  - 0.2));
    borderRect.setAttribute('height', String(vb.height - 0.2));
}
borderRect.setAttribute('stroke', activeColor);
borderRect.setAttribute('opacity', '0.55');
```

---

## After implementation

1. `git diff --stat` — confirm only `dashboard.html` changed
2. `git add app/web/templates/dashboard.html`
3. `git commit -m "feat: player state on tokens, event flash, active team pitch border"`
4. `git push origin main`

Do NOT modify any Python files, game logic, or backend routes.
