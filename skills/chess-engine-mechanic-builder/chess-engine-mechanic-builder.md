---
id: chess-engine-mechanic-builder
file_path: skills/chess-engine-mechanic-builder/chess-engine-mechanic-builder.md
name: Custom Chess Engine Mechanic Builder
category: core-coding
tags: [chess, python-chess, pygame, game-mechanics, cooldown]
author: opencode-core
version: 1.0.0
description: Wraps python-chess inside a SkillChessBoard that adds turn tracking, per-skill cooldown ticks, a Teleport mechanic and a Freeze Square mechanic with expiry timers, plus rotate_view_180 coordinate mapping, a pygame-free ASCII renderer and an optional pygame renderer, all driven by a runnable demo.
---

# Custom Chess Engine Mechanic Builder

## 1. System Architecture & Prerequisites

This skill builds a variant chess engine on top of `python-chess` while
keeping the logic layer completely pygame-free. The architecture splits into
four parts:

- **`SkillChessBoard`** - a wrapped `chess.Board`. It mirrors the standard
  rule engine (`push_uci`, `legal_moves`, `is_game_over`) and adds
  `turn_player` bookkeeping, a JSON-serialisable `cooldowns` dictionary, and
  a `log` of `MoveEntry` records so gameplay can be replayed/reported.
- **Skill mechanics** - `apply_teleport(sq_from, sq_to)` relocates a friendly
  piece instantly (legal moves route through `board.push_uci`; impossible
  movements use a variant fallback with manual turn advance) and
  `apply_freeze(sq)` marks a square frozen. A frozen square's occupant is
  skipped by `legal_moves()` until its expiry ticks run out.
- **Cooldown scheduler** - `cooldown_ticks` defines honest cooldowns per
  skill; `can_cast(skill)` gates casting, `tick_cooldowns()` decays both skill
  cooldowns and freeze expiries as the turn clock advances.
- **View layer** - `rotate_view_180(board_ui)` maps file/rank indices for a
  180-degree board rotation, `render_ascii()` is a pure-text renderer that
  works without any GUI library, and `render()` draws the same state on a
  pygame surface guarded by an `ImportError` fallback.

Prerequisites:

| Dependency        | Required?            | Install                         |
| ----------------- | -------------------- | ------------------------------- |
| Python 3.9+       | yes                  | -                               |
| `python-chess`    | yes (logic layer)    | `python -m pip install python-chess` |
| `pygame` 8.0+     | only for `render()`  | `python -m pip install pygame`  |

The core module imports cleanly with only `python-chess` installed; scene
rendering degrades to no-ops when pygame is absent.

## 2. Input/Output Data Contracts

### 2.1 Input JSON Schema - `SkillChessBoard` options

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "SkillChessBoardConfig",
  "additionalProperties": false,
  "properties": {
    "start_fen": {
      "type": "string",
      "default": "",
      "description": "Initial FEN; empty string starts the standard game"
    },
    "cooldown_ticks": {
      "type": "object",
      "properties": {
        "teleport": { "type": "integer", "minimum": 0, "default": 6 },
        "freeze": { "type": "integer", "minimum": 0, "default": 9 }
      }
    },
    "freeze_duration": {
      "type": "integer",
      "minimum": 0,
      "default": 3
    }
  }
}
```

### 2.2 Output contracts

- `cooldowns: Dict[str, int]` - remaining ticks per skill after the last cast
  (0 means ready).
- `frozen: Set[int]` - chess square indices currently frozen.
- `frozen_expiry: Dict[int, int]` - remaining freeze ticks per frozen square.
- `log: List[MoveEntry]` - ordered `MoveEntry(kind, detail, turn, cooldowns)`.
- `render_ascii(board, view_rotated=False, frozen=None) -> str` - 8 x 8 text
  board, uppercase = white, lowercase = black, `.` = empty, frozen cells
  shown as `[p]`.
- `render(screen, board, ...)` - optional pygame draw, returns `None` when
  pygame is missing.

### 2.3 Output artifacts

| Artifact                 | Path                                                    | Format |
| ------------------------ | ------------------------------------------------------- | ------ |
| Reference implementation | `skills/chess-engine-mechanic-builder/chess_mechanics.py` | Python |
| Demo transcript          | printed by `main()` (moves, teleport, freeze, cooldowns) | stdout |

## 3. Production Reference Implementation

```python
"""chess_mechanics.py - custom chess engine with skill cooldowns.

Wraps python-chess inside a SkillChessBoard that adds turn tracking,
per-skill cooldown ticks, a Teleport mechanic and a Freeze Square mechanic
with expiry timers.  Rendering ships as a pygame-free ASCII view plus an
optional pygame surface renderer imported lazily, so the logic layer never
requires pygame.

Hard dependency (logic):  python-chess   (pip install python-chess)
Optional dependency:      pygame 8.0+    (used only by render())
Run directly:  python chess_mechanics.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    import chess
    from chess import Board, Piece
except ImportError as exc:  # pragma: no cover - user-facing guard
    raise ImportError(
        "python-chess is required:  python -m pip install python-chess"
    ) from exc

COOLDOWN_TICKS: Dict[str, int] = {"teleport": 6, "freeze": 9}
FREEZE_DURATION_TICKS = 3
SKILL_NAMES = tuple(COOLDOWN_TICKS)

PIECE_GLYPH = {
    chess.PAWN: "p",
    chess.KNIGHT: "n",
    chess.BISHOP: "b",
    chess.ROOK: "r",
    chess.QUEEN: "q",
    chess.KING: "k",
}

try:
    import pygame
    PYGAME_OK = True
except ImportError:  # pragma: no cover - optional dependency
    pygame = None  # type: ignore[assignment]
    PYGAME_OK = False


@dataclass
class MoveEntry:
    """A recorded action for replay / reporting."""

    kind: str
    detail: str
    turn: str
    cooldowns: Dict[str, int] = field(default_factory=dict)


class SkillChessBoard:
    """A chess.Board wrapper with fantasy mechanics.

    Standard chess moves are pushed through ``board.push_uci`` (the rules
    engine stays authoritative).  Skill moves are applied as board-level
    mutations and logged as ``kind in {teleport, freeze}`` entries so the
    flavour never desyncs the main rule book.
    """

    def __init__(
        self,
        start_fen: str = "",
        cooldown_ticks: Optional[Dict[str, int]] = None,
        freeze_duration: int = FREEZE_DURATION_TICKS,
    ) -> None:
        self.board: Board = chess.Board(start_fen) if start_fen else chess.Board()
        self.turn_player: str = "white" if self.board.turn else "black"
        self.cooldown_ticks: Dict[str, int] = dict(COOLDOWN_TICKS)
        if cooldown_ticks:
            self.cooldown_ticks.update(cooldown_ticks)
        self.cooldowns: Dict[str, int] = {name: 0 for name in SKILL_NAMES}
        self.freeze_duration = freeze_duration
        self.frozen: Set[int] = set()
        self.frozen_expiry: Dict[int, int] = {}
        self.log: List[MoveEntry] = []

    # -- turn bookkeeping ----------------------------------------------------

    def increment_turn(self) -> None:
        """Manually advance the player turn (used by variant teleports)."""
        self.turn_player = "black" if self.turn_player == "white" else "white"

    def _sync_turn(self) -> None:
        """Re-derive ``turn_player`` from the authoritative chess board."""
        self.turn_player = "white" if self.board.turn else "black"

    # -- standard moves ------------------------------------------------------

    def push_uci(self, uci: str) -> None:
        """Push a standard move through the rule engine."""
        self.board.push_uci(uci)
        self._sync_turn()
        self.log.append(MoveEntry("move", uci, self.turn_player,
                                  dict(self.cooldowns)))

    def legal_moves(self) -> Iterable[Any]:
        """All legal moves except those whose FROM square is frozen."""
        for move in self.board.legal_moves:
            if move.from_square in self.frozen:
                continue
            yield move

    def can_move_from(self, square: int) -> bool:
        """True when the occupant of ``square`` may legally be moved."""
        return square not in self.frozen

    def piece_at(self, square: int) -> Optional[Piece]:
        return self.board.piece_at(square)

    # -- skill API -----------------------------------------------------------

    def can_cast(self, skill: str) -> bool:
        """A skill is castable while its cooldown is spent and a game lives."""
        if skill not in self.cooldowns:
            return False
        if self.board.is_game_over():
            return False
        return self.cooldowns[skill] <= 0

    def tick_cooldowns(self, ticks: int = 1) -> None:
        """Advance every skill cooldown and freeze expiry by ``ticks``."""
        for _ in range(max(0, ticks)):
            for name in SKILL_NAMES:
                self.cooldowns[name] = max(0, self.cooldowns[name] - 1)
            for sq in list(self.frozen_expiry):
                self.frozen_expiry[sq] -= 1
                if self.frozen_expiry[sq] <= 0:
                    self.frozen.discard(sq)
                    del self.frozen_expiry[sq]

    def apply_teleport(self, sq_from: int, sq_to: int) -> bool:
        """Instantly relocate a friendly piece from ``sq_from`` to ``sq_to``.

        First the move is attempted as a legal chess move via
        ``board.push_uci`` (the turn flips naturally).  When the board
        rejects it as an impossible jump, a variant teleport mutates the
        board directly with ``remove_piece_at`` / ``set_piece_at`` and the
        turn advances manually.  Returns False when the cast cannot happen.
        """
        if not self.can_cast("teleport"):
            return False
        if not (0 <= sq_from < 64 and 0 <= sq_to < 64) or sq_from == sq_to:
            return False
        piece = self.board.piece_at(sq_from)
        if piece is None or piece.color != self.board.turn:
            return False
        target = self.board.piece_at(sq_to)
        if target is not None and target.color == piece.color:
            return False
        actor = self.turn_player
        moved = False
        try:
            uci = chess.square_name(sq_from) + chess.square_name(sq_to)
            candidate = chess.Move.from_uci(uci)
            if candidate in self.board.legal_moves:
                self.board.push_uci(uci)
                moved = True
        except ValueError:
            moved = False
        if moved:
            self._sync_turn()
        else:
            self.board.remove_piece_at(sq_from)
            if target is not None:
                self.board.remove_piece_at(sq_to)
            self.board.set_piece_at(sq_to, piece)
            self.increment_turn()
        self.cooldowns["teleport"] = self.cooldown_ticks["teleport"]
        self.log.append(MoveEntry(
            "teleport",
            "%s->%s" % (chess.square_name(sq_from), chess.square_name(sq_to)),
            actor,
            dict(self.cooldowns),
        ))
        return True

    def apply_freeze(self, square: int) -> bool:
        """Freeze ``square`` so its occupant cannot move for the duration.

        Freezing is a free action: it only costs the skill cooldown, not a
        turn.  The occupant's move options are skipped until the expiry ticks
        elapse (handled by ``tick_cooldowns``).
        """
        if not self.can_cast("freeze"):
            return False
        if not (0 <= square < 64):
            return False
        self.frozen.add(square)
        self.frozen_expiry[square] = self.freeze_duration
        self.cooldowns["freeze"] = self.cooldown_ticks["freeze"]
        self.log.append(MoveEntry("freeze", chess.square_name(square),
                                  self.turn_player, dict(self.cooldowns)))
        return True


def rotate_coords_180(file_: int, rank: int, size: int = 8) -> Tuple[int, int]:
    """Map (file, rank) to its 180-degree rotated position on an 8-rank board."""
    return (size - 1 - file_, size - 1 - rank)


def rotate_view_180(board_ui: Any) -> List[List[Any]]:
    """Rotate a square board view 180 degrees.

    ``board_ui`` is any 8 x 8 nested sequence (list of rows of piece glyphs,
    ASCII grid, pygame colour keys ...).  Rank order is reversed and every
    row is reversed, mapping [file, rank] onto [7 - file, 7 - rank].
    """
    rows: List[Any] = list(board_ui)
    if len(rows) != 8 or any(len(row) != 8 for row in rows):
        raise ValueError("board_ui must be an 8x8 nested sequence")
    return [list(reversed(row)) for row in reversed(rows)]


def _board_rows(board: Any) -> List[List[str]]:
    """Rows of one-char piece symbols with rank 8 on top."""
    if hasattr(board, "board"):
        board = board.board
    rows: List[List[str]] = []
    for rank in range(7, -1, -1):
        row: List[str] = []
        for file_ in range(8):
            piece = board.piece_at(chess.square(file_, rank))
            if piece is None:
                row.append(".")
            elif piece.color == chess.WHITE:
                row.append(PIECE_GLYPH[piece.piece_type].upper())
            else:
                row.append(PIECE_GLYPH[piece.piece_type])
        rows.append(row)
    return rows


def render_ascii(board: Any, view_rotated: bool = False,
                 frozen: Optional[Set[int]] = None) -> str:
    """Text board renderer (pygame-free).

    Uppercase = white, lowercase = black, '.' = empty, frozen cells are
    wrapped as ``[p]``.  ``view_rotated=True`` renders the board from the
    opponent's perspective (180-degree rotation).
    """
    rows = _board_rows(board)
    if view_rotated:
        rows = rotate_view_180(rows)
    lines: List[str] = []
    for i, row in enumerate(rows):
        rank_label = (8 - i) if not view_rotated else (i + 1)
        cells: List[str] = []
        for col, glyph in enumerate(row):
            if frozen:
                file_ = col if not view_rotated else 7 - col
                rank = (7 - i) if not view_rotated else i
                if chess.square(file_, rank) in frozen:
                    glyph = "[%s]" % glyph
            cells.append(glyph)
        lines.append("%d %s" % (rank_label, " ".join(cells)))
    files = "abcdefgh" if not view_rotated else "hgfedcba"
    lines.append("  %s" % " ".join(files))
    return "\n".join(lines)


def render(screen: Any, board: Any, view_rotated: bool = False,
           cell_px: int = 56, square_highlight: Optional[int] = None,
           frozen: Optional[Set[int]] = None) -> None:
    """Optional pygame renderer.  Silently no-ops when pygame is missing.

    Drawing positions follow ``rotate_view_180`` coordinate mapping whenever
    ``view_rotated`` is set, while square lookups keep using real board
    coordinates so pieces stay correct under rotation.
    """
    if pygame is None:
        return
    if hasattr(board, "board"):
        skill_ok = True
        board = board.board
    else:
        skill_ok = False
    palette = {
        "light": (240, 217, 181),
        "dark": (181, 136, 99),
        "frozen": (220, 70, 80),
        "sel": (90, 200, 90),
        "piece": (20, 20, 20),
    }
    board_size = cell_px * 8
    screen.fill((30, 30, 34))
    for rank in range(8):
        for file_ in range(8):
            rx, ry = file_, rank
            if view_rotated:
                rx, ry = rotate_coords_180(file_, rank)
            colour = palette["light"] if ((file_ + rank) % 2 == 0) else palette["dark"]
            sq = chess.square(file_, rank)
            if skill_ok and frozen and sq in frozen:
                colour = palette["frozen"]
            if sq == square_highlight:
                colour = palette["sel"]
            rect = pygame.Rect(rx * cell_px, ry * cell_px, cell_px, cell_px)
            pygame.draw.rect(screen, colour, rect)
            piece = board.piece_at(sq)
            if piece:
                font = pygame.font.Font(None, int(cell_px * 0.8))
                glyph = PIECE_GLYPH[piece.piece_type]
                if piece.color == chess.WHITE:
                    glyph = glyph.upper()
                label = font.render(glyph, True, palette["piece"])
                screen.blit(label, label.get_rect(center=rect.center))
    pygame.display.flip()


def main() -> None:
    """Demo: a short opening line, then Teleport and Freeze casts showing
    the cooldown and freeze-expiry lifecycle, plus both board views."""
    skill = SkillChessBoard()
    print("== Initial position ==")
    print(render_ascii(skill))

    line = ["e2e4", "e7e5", "g1f3", "b8c6"]
    for uci in line:
        skill.push_uci(uci)
    print("\n== After %s ==" % ", ".join(line))
    print(render_ascii(skill))

    e4 = chess.parse_square("e4")
    e7 = chess.parse_square("e7")
    teleported = skill.apply_teleport(e4, e7)
    print("\n== Teleport e4 -> e7 cast %s ==" % ("OK" if teleported else "FAILED"))
    print(render_ascii(skill, frozen=skill.frozen))

    froze = skill.apply_freeze(e7)
    print("\n== Freeze e7 cast %s ==" % ("OK" if froze else "FAILED"))
    print(render_ascii(skill, frozen=skill.frozen))
    if skill.frozen:
        print("Frozen squares: %s"
              % ", ".join(chess.square_name(s) for s in sorted(skill.frozen)))

    print("\n== Cooldowns right after cast ==")
    print(json.dumps(skill.cooldowns, indent=2, sort_keys=True))
    print("can_cast('teleport')=%s can_cast('freeze')=%s"
          % (skill.can_cast("teleport"), skill.can_cast("freeze")))

    frozen_sq = e7
    before = skill.can_move_from(frozen_sq)
    skill.tick_cooldowns(ticks=6)
    after = skill.can_move_from(frozen_sq)
    print("\ncan move from e7 while frozen: %s  ->  after 6 ticks: %s"
          % (before, after))
    print("cooldowns after ticking: teleport=%d freeze=%d"
          % (skill.cooldowns["teleport"], skill.cooldowns["freeze"]))

    print("\n== 180-degree rotated view of the same moment ==")
    print(render_ascii(skill, view_rotated=True, frozen=skill.frozen))

    print("\n== Move log ==")
    for entry in skill.log:
        print("%-10s %-14s %s" % (entry.kind, entry.detail, entry.turn))

    if PYGAME_OK:
        pygame.init()
        screen = pygame.display.set_mode((8 * 56, 8 * 56))
        pygame.display.set_caption("Skill Chess render() demo")
        render(screen, skill, view_rotated=False, frozen=skill.frozen)
        print("\npygame window shown; close it to exit the demo.")


if __name__ == "__main__":
    main()
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Install logic dependency.** Run `python -m pip install python-chess`.
   pygame is optional and only needed for `render()`.
2. **Bring up a skill board.** Create `SkillChessBoard()`, optionally passing
   `start_fen`, custom `cooldown_ticks` and `freeze_duration`.
3. **Play standard moves.** Call `board.push_uci("e2e4")`. The wrapper keeps
   `turn_player` in sync with the authoritative `chess.Board` and appends a
   `MoveEntry` to `log`.
4. **Gate skill use.** Before casting, assert `can_cast(skill)` is True and
   `cooldowns[skill] == 0`; otherwise the cast is rejected and returns False.
5. **Cast Teleport.** `apply_teleport(sq_from, sq_to)` relocates a friendly
   piece. Legal jumps route through `push_uci`; impossible jumps use the
   variant path and manually advance the turn. Verify success via the return
   value and the new `cooldowns["teleport"]`.
6. **Cast Freeze.** `apply_freeze(square)` locks that square; its occupant is
   now skipped by `legal_moves()` and `can_move_from()` returns False.
7. **Advance the clock.** Call `tick_cooldowns(ticks=N)` once per turn. This
   decays skill cooldowns and freeze expiry; squares whose expiry reaches
   zero are removed from `frozen` and unblocked again.
8. **Render.** Use `render_ascii(board, view_rotated=..., frozen=...)` for
   console/debug output. For a GUI, call `render(screen, board, ...)` after
   `pygame.display.set_mode(...)`.
9. **Rotate the view.** Wrap any 8 x 8 board view with
   `rotate_view_180(board_ui)` or pass `view_rotated=True` to the renderers.
10. **Sanity check (agent).** Run `main()` and confirm the transcript shows
    two legal pushes per side, the teleport relocating the e4 pawn, the e7
    square freezing, cooldowns descending from `{"teleport":6,"freeze":9}`,
    and e7 becoming movable again after the ticks.

## 5. Edge Cases & Error Handling

- **Missing `python-chess`.** Module import raises a descriptive
  `ImportError` with the install command; the logic layer cannot run without
  the rule engine.
- **Missing pygame.** `render()` and the GUI demo branch become no-ops;
  `render_ascii` keeps delivering full fidelity, so the demo still runs.
- **Teleport on cooldown or game over.** `can_cast` returns False and
  `apply_teleport` returns False without touching the board.
- **Invalid teleport targets.** Out-of-range squares, self-squares, absent
  source pieces, and destinations holding a friendly piece are all rejected
  before any mutation. `chess.square_name`/`Move.from_uci` failures are
  swallowed and routed to the variant fallback.
- **Frozen occupants.** A frozen piece remains on the board but every move
  whose `from_square` is frozen is omitted from `legal_moves()`, and
  `can_move_from` reports False, splitting the checks cleanly for any AI.
- **Expiry bookkeeping.** `tick_cooldowns` snaps cooldowns at 0 (never
  negative) and removes expired freezes from both `frozen` and
  `frozen_expiry` atomically, so the two structures never disagree.
- **Variant-move legality gap.** Direct board mutation bypasses push-side
  validity (e.g., a teleported king may sit in attack). Callers that need
  strict safety can re-run `board.is_valid()` after a variant cast and undo
  the cast through `log` when it fails.
- **Ragged board views.** `rotate_view_180` and `_board_rows` validate the
  8 x 8 shape and raise `ValueError` instead of producing garbled mirrors.