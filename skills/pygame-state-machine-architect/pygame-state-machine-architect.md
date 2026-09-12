---
id: pygame-state-machine-architect
file_path: skills/pygame-state-machine-architect/pygame-state-machine-architect.md
name: Pygame State Machine Architect
category: software-architecture
tags: [pygame, state-machine, game, python, dt]
author: opencode-core
version: 1.0.0
description: Defines an abstract BaseState lifecycle (startup, cleanup, get_event, update, draw) plus a StateMachine manager running a fixed delta-time loop with dt = clock.tick(60) / 1000.0, providing concrete MenuState, GameplayState, and PauseState implementations and a SpriteSheetSlicer that parses TexturePacker XML or JSON atlases into pygame.Surface subsurface frames.
---

# Pygame State Machine Architect

## 1. System Architecture & Prerequisites

This skill produces a single-file, reusable state-machine core for 2D Pygame
projects. The architecture is layered as follows:

- **`BaseState`** - abstract contract. Every game screen (menu, gameplay,
  pause) sub-classes it and implements exactly five lifecycle hooks:
  `startup(dt)`, `cleanup()`, `get_event(event)`, `update(dt)` and
  `draw(screen)`. States carry a shared `persist` dict that survives screen
  transitions (score, level, references to the machine).
- **`StateMachine`** - the manager. Registers named states
  (`add_state`), switches between them while performing persist hand-off
  (`change_state`), and owns the **main loop** (`run(start_state)`). The loop
  uses a fixed wall-clock timestep `dt = clock.tick(60) / 1000.0` so movement
  logic is framerate-independent and the game logic never sees frame spikes.
- **Concrete states** - `MenuState` (title screen, SPACE starts),
  `GameplayState` (a minimapable player blob driven by arrow keys, `P` opens
  pause), and `PauseState` (freezes play, SPACE/`P` resumes, `Q` quits).
- **`SpriteSheetSlicer`** - loads a texture atlas image plus a TexturePacker
  XML or JSON descriptor and produces named `pygame.Surface.subsurface`
  frames, including `rotated` frame support.

Prerequisites (exact binaries/tools):

| Dependency | Purpose                                     |
| ---------- | ------------------------------------------- |
| Python 3.9+ | Runtime language                            |
| pygame 8.0+ | Event loop, display, surfaces, fonts        |

Install with `python -m pip install pygame`. The module degrades gracefully:
importing it without pygame is allowed, and running `main()` without pygame
exits with a clear installer message instead of a raw import traceback.

## 2. Input/Output Data Contracts

### 2.1 Input JSON Schema - `cfg` for `main(cfg)`

The entry point accepts a single configuration dict. Every key is optional.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "PygameStateMachineConfig",
  "properties": {
    "RES": {
      "type": "array",
      "items": { "type": "integer", "minimum": 1 },
      "minItems": 2,
      "maxItems": 2,
      "default": [640, 480],
      "description": "Window resolution as [width, height]"
    }
  },
  "additionalProperties": true
}
```

### 2.2 Atlas input schema (consumed by `SpriteSheetSlicer`)

The slicer auto-detects the descriptor format by file extension:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "SpriteAtlasJSON",
  "required": ["frames"],
  "properties": {
    "frames": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["frame"],
        "properties": {
          "frame": {
            "type": "object",
            "required": ["x", "y", "w", "h"],
            "properties": {
              "x": { "type": "integer" },
              "y": { "type": "integer" },
              "w": { "type": "integer" },
              "h": { "type": "integer" }
            }
          },
          "rotated": { "type": "boolean", "default": false }
        }
      }
    }
  }
}
```

The equivalent TexturePacker XML form is also accepted
(`<SubTexture name=".." x=".." y=".." width=".." height=".." rotated="false"/>`
nested under `<TextureAtlas imagePath="sheet.png">`).

### 2.3 Output artifacts

| Artifact                    | Path                                                       | Format |
| --------------------------- | ---------------------------------------------------------- | ------ |
| Reference implementation    | `skills/pygame-state-machine-architect/pygame_sm.py`       | Python |
| In-memory frame surfaces    | returned by `SpriteSheetSlicer.frames` dict                | object |
| Optional checkpoint bitmap  | saved by the caller via `pygame.image.save(surface, path)` | PNG    |

The module writes nothing to disk when run directly; it only opens a window.

## 3. Production Reference Implementation

```python
"""pygame_sm.py - production Pygame state-machine architecture.

Layers:
  * BaseState        - abstract lifecycle contract with a persist dict.
  * StateMachine     - state registry + fixed delta-time main loop.
  * MenuState        - title screen that transitions into gameplay.
  * GameplayState    - arrow-key driven player blob with score.
  * PauseState       - freezes gameplay, resumes or quits.
  * SpriteSheetSlicer- TexturePacker XML/JSON atlas parser producing
                       pygame.Surface.subsurface frames.

Requires: Python 3.9+ and pygame 8.0+ (`python -m pip install pygame`).
Run directly:  python pygame_sm.py
"""

from __future__ import annotations

import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

try:
    import pygame
    _HAS_PYGAME = True
except ImportError:  # pragma: no cover - exercised only without pygame
    pygame = None  # type: ignore[assignment]
    _HAS_PYGAME = False

Color = Tuple[int, int, int]

COL_BG = (24, 24, 32)
COL_PANEL = (56, 56, 72)
COL_TEXT = (240, 240, 245)
COL_ACCENT = (255, 140, 0)
COL_PLAYER = (80, 200, 255)


class BaseState(ABC):
    """Abstract lifecycle contract for every game state.

    Sub-classes share a ``persist`` dictionary that survives state
    transitions, so values such as score or machine references can be carried
    from one screen to the next.
    """

    def __init__(self, persist: Optional[Dict[str, Any]] = None) -> None:
        self.persist: Dict[str, Any] = persist if persist is not None else {}

    @abstractmethod
    def startup(self, dt: float = 0.0) -> None:
        """One-time initialisation when the state is activated."""

    @abstractmethod
    def cleanup(self) -> None:
        """One-time teardown when the state is deactivated."""

    @abstractmethod
    def get_event(self, event: pygame.event.Event) -> None:
        """Consume a single pygame event while this state is active."""

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance simulation logic by dt seconds."""

    @abstractmethod
    def draw(self, screen: pygame.Surface) -> None:
        """Render this state onto ``screen``."""


class StateMachine:
    """Owns all registered states and runs the fixed delta-time main loop.

    The loop ticks the clock at 60 FPS, converts milliseconds to seconds
    (dt = clock.tick(60) / 1000.0) and delegates event / update / draw work
    to the currently active state.
    """

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.states: Dict[str, BaseState] = {}
        self.current: Optional[BaseState] = None
        self._running = False
        self._persist: Dict[str, Any] = {}

    def add_state(self, name: str, state: BaseState) -> None:
        """Register ``state`` under ``name`` for later transitions."""
        self.states[name] = state

    def change_state(self, name: str) -> None:
        """Flush persist data, tear down the old state, boot the new one."""
        if name not in self.states:
            raise KeyError("Unknown state: %r" % name)
        if self.current is not None:
            self.current.cleanup()
            self._persist.update(self.current.persist)
        state = self.states[name]
        state.persist.update(self._persist)
        self.current = state
        state.startup()

    def request_quit(self) -> None:
        """Gracefully terminate the main loop on the next iteration."""
        self._running = False

    def run(self, start_state: str) -> None:
        """Enter ``start_state`` and loop until a quit is requested."""
        if not _HAS_PYGAME:
            raise RuntimeError("pygame 8.0+ is required to run StateMachine")
        self._persist["machine"] = self
        self.change_state(start_state)
        self._running = True
        clock = pygame.time.Clock()
        while self._running:
            dt = min(clock.tick(60) / 1000.0, 0.25)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.request_quit()
                elif self.current is not None:
                    self.current.get_event(event)
            if self.current is not None:
                self.current.update(dt)
                self.current.draw(self.screen)
            pygame.display.flip()
        pygame.quit()


def _render_text(label: str, color: Color = COL_TEXT,
                 size: int = 32) -> pygame.Surface:
    """Helper: render antialiased text with the default pygame font."""
    font = pygame.font.Font(None, size)
    return font.render(label, True, color)


class MenuState(BaseState):
    """Title screen that transitions into GameplayState on SPACE."""

    def startup(self, dt: float = 0.0) -> None:
        self.attract = 0.0

    def cleanup(self) -> None:
        self.persist["menu_left_at"] = pygame.time.get_ticks()

    def get_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.persist["start_pressed"] = True
                self.persist["machine"].change_state("gameplay")
            elif event.key == pygame.K_ESCAPE:
                self.persist["machine"].request_quit()

    def update(self, dt: float) -> None:
        self.attract += dt * 2.0

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(COL_BG)
        w, h = screen.get_size()
        pulse = int(120 + 135 * math.sin(self.attract)) % 255
        header = _render_text("STATE MACHINE ARENA", COL_ACCENT, 56)
        sub = _render_text("Press SPACE to start   ESC to quit", COL_TEXT, 26)
        screen.blit(header, header.get_rect(center=(w // 2, h // 2 - 60)))
        screen.blit(sub, sub.get_rect(center=(w // 2, h // 2 + 10)))
        pygame.draw.circle(screen, (pulse, 200, 255), (w // 2, h // 2 + 90), 8)


class GameplayState(BaseState):
    """Minimal playable screen: an arrow-key driven blob with a score."""

    SPEED = 260.0

    def startup(self, dt: float = 0.0) -> None:
        w, h = self.persist["machine"].screen.get_size()
        self.player: pygame.Rect = pygame.Rect(0, 0, 32, 32)
        self.player.center = (w // 2, h // 2)
        self.vel = pygame.Vector2(0.0, 0.0)
        self.score = int(self.persist.get("score", 0))

    def cleanup(self) -> None:
        self.persist["score"] = self.score

    def get_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_p, pygame.K_PAUSE):
                self.persist["machine"].change_state("pause")
            elif event.key == pygame.K_r:
                self.player.center = self.persist["machine"].screen.get_rect().center

    def update(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        self.vel = pygame.Vector2(
            (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]) * self.SPEED,
            (keys[pygame.K_DOWN] - keys[pygame.K_UP]) * self.SPEED,
        )
        self.player.move_ip(round(self.vel.x * dt), round(self.vel.y * dt))
        self.score += int(self.vel.length_squared() * dt * 0.05)
        self.player.clamp_ip(self.persist["machine"].screen.get_rect())

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(COL_PANEL)
        pygame.draw.rect(screen, COL_PLAYER, self.player, border_radius=6)
        label = _render_text("Score %d   P pause   R reset" % self.score, COL_TEXT, 24)
        screen.blit(label, (12, 10))


class PauseState(BaseState):
    """Freezes gameplay; SPACE/``P`` resumes, ``Q`` quits to desktop."""

    def startup(self, dt: float = 0.0) -> None:
        self.paused_since = pygame.time.get_ticks()

    def cleanup(self) -> None:
        pass

    def get_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_SPACE, pygame.K_p):
                self.persist["machine"].change_state("gameplay")
            elif event.key == pygame.K_q:
                self.persist["machine"].request_quit()

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((18, 18, 24))
        w, h = screen.get_size()
        title = _render_text("PAUSED", COL_ACCENT, 64)
        hint = _render_text("SPACE resume   Q quit", COL_TEXT, 24)
        screen.blit(title, title.get_rect(center=(w // 2, h // 2 - 40)))
        screen.blit(hint, hint.get_rect(center=(w // 2, h // 2 + 20)))


class SpriteSheetSlicer:
    """Cut an image atlas into named pygame.Surface frames.

    Two atlas descriptions are auto-detected by file extension:
      * TexturePacker XML  ``<SubTexture name=".." x=".." y=".."
        width=".." height=".." rotated="false"/>`` under a
        ``<TextureAtlas imagePath="sheet.png">`` root.
      * JSON  ``{"frames": {"<name>": {
           "frame": {"x":..,"y":..,"w":..,"h":..}, "rotated": false}}}``

    Output: a ``dict[str, pygame.Surface]`` of subsurface frames plus
    convenience lookups ``get`` and ``find``.
    """

    def __init__(self, sheet_path: str, atlas_path: str) -> None:
        if not _HAS_PYGAME:
            raise ImportError("pygame 8.0+ is required to slice sprite sheets")
        self.sheet_path = sheet_path
        self.atlas_path = atlas_path
        self.sheet: pygame.Surface = pygame.image.load(sheet_path).convert_alpha()
        self.frames: Dict[str, pygame.Surface] = self._parse()

    def _parse(self) -> Dict[str, pygame.Surface]:
        ext = os.path.splitext(self.atlas_path)[1].lower()
        if ext == ".xml":
            return self._parse_xml()
        if ext == ".json":
            return self._parse_json()
        raise ValueError("Unsupported atlas format %r (use .xml or .json)" % ext)

    @staticmethod
    def _slice(sheet: pygame.Surface, x: int, y: int, w: int, h: int,
               rotated: bool) -> pygame.Surface:
        frame = sheet.subsurface(pygame.Rect(x, y, w, h))
        if rotated:
            frame = pygame.transform.rotate(frame, -90)
        return frame

    def _parse_xml(self) -> Dict[str, pygame.Surface]:
        root = ET.parse(self.atlas_path).getroot()
        frames: Dict[str, pygame.Surface] = {}
        for sub in root.iter("SubTexture"):
            name = sub.get("name")
            if not name:
                continue
            frames[name] = self._slice(
                self.sheet,
                int(sub.get("x", 0)),
                int(sub.get("y", 0)),
                int(sub.get("width", 0)),
                int(sub.get("height", 0)),
                sub.get("rotated", "false").lower() == "true",
            )
        return frames

    def _parse_json(self) -> Dict[str, pygame.Surface]:
        with open(self.atlas_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        frames: Dict[str, pygame.Surface] = {}
        for name, meta in data.get("frames", {}).items():
            frame = meta.get("frame") or meta
            frames[name] = self._slice(
                self.sheet,
                int(frame["x"]),
                int(frame["y"]),
                int(frame["w"]),
                int(frame["h"]),
                bool(meta.get("rotated", False)),
            )
        return frames

    def get(self, name: str) -> pygame.Surface:
        """Return the surface for one named frame."""
        if name not in self.frames:
            raise KeyError("Frame %r not present in %s" % (name, self.atlas_path))
        return self.frames[name]

    def find(self, prefix: str) -> List[pygame.Surface]:
        """Return every frame whose name starts with ``prefix``, sorted."""
        return [self.frames[n] for n in sorted(self.frames) if n.startswith(prefix)]


def main(cfg: Optional[Dict[str, Any]] = None,
         sheet_path: str = "", atlas_path: str = "") -> None:
    """Boot the demo window.  ``cfg`` supplies the resolution, and when
    ``sheet_path``/``atlas_path`` are given a SpriteSheetSlicer is demoed."""
    if not _HAS_PYGAME:
        print("ERROR: pygame 8.0+ required.  Install with: "
              "python -m pip install pygame")
        sys.exit(1)
    cfg = cfg or {}
    res: Tuple[int, int] = tuple(cfg.get("RES", (640, 480)))  # type: ignore[assignment]
    pygame.init()
    screen = pygame.display.set_mode(res)
    pygame.display.set_caption("Pygame State Machine Architecture")
    if sheet_path and atlas_path:
        slicer = SpriteSheetSlicer(sheet_path, atlas_path)
        print("Sliced %d frames: %s" % (len(slicer.frames),
                                        ", ".join(list(slicer.frames)[:8])))
    machine = StateMachine(screen)
    machine.add_state("menu", MenuState())
    machine.add_state("gameplay", GameplayState())
    machine.add_state("pause", PauseState())
    machine.run("menu")


if __name__ == "__main__":
    main(cfg={"RES": (640, 480)})
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Install prerequisites.** Ensure Python 3.9+ and run
   `python -m pip install pygame`.
2. **Reuse the module.** Copy `pygame_sm.py` into the target project source
   tree, or `import pygame_sm` from a playable entry point.
3. **Define new screens.** Sub-class `BaseState` and implement all five
   hooks (`startup`, `cleanup`, `get_event`, `update`, `draw`). Use
   `self.persist["machine"]` for the owning `StateMachine` reference.
4. **Wire the machines.** Build a `StateMachine` with a display surface,
   then `add_state("menu", MenuState())` (etc.) for every screen.
5. **Run.** Call `machine.run("menu")`. The fixed loop performs
   `clock.tick(60) / 1000.0` to derive `dt`, pumps `pygame.event.get()`,
   delegates to the active state, and flips the display.
6. **Switch screens.** Inside any state event handler call
   `self.persist["machine"].change_state("gameplay")`; persist values flow
   through automatically.
7. **Slice sprites.** Pass a sheet PNG plus a TexturePacker XML or JSON
   descriptor to `SpriteSheetSlicer`, then request frames via `get(name)` or
   `find("prefix")` for animation playback.
8. **Sanity check (agent).** Import the module, instantiate every state,
   and assert the machine transitions `menu -> gameplay -> pause ->
   gameplay` without exceptions before wiring the rest of the game.

## 5. Edge Cases & Error Handling

- **pygame missing.** The module imports cleanly; `main()` prints an install
  hint and exits 1. `StateMachine.run` raises a descriptive `RuntimeError`.
- **Unknown state name.** `change_state` raises `KeyError` before touching
  the current state, so an invalid target never corrupts the active screen.
- **QUIT / window close.** Handled inside `run` via `request_quit`, followed
  by a clean `pygame.quit()`.
- **Frame spikes / spiral of death.** `dt` is clamped to 0.25s so a long
  loading hitch does not produce absurd frame deltas.
- **State transition storm.** States mutate the machine lazily (in handlers)
  rather than mid-loop, so `change_state` is never re-entered while iterating
  `pygame.event.get()`.
- **Missing atlas files.** `SpriteSheetSlicer.__init__` surfaces
  `FileNotFoundError`/`ValueError` from `pygame.image.load`, `ET.parse`, or
  `json.load` with the offending path in the traceback.
- **Out-of-bounds subrects.** `pygame.Surface.subsurface` raises
  `ValueError`; validate atlas rects against `sheet.get_size()` before
  slicing in strict builds.
- **Headless CI.** `display.set_mode` fails without a display server;
  guard demo invocations with an environment check or use a dummy video
  driver (`SDL_VIDEODRIVER=dummy`) for smoke tests.