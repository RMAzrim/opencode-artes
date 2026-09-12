---
name: Procedural Dungeon & Map Generator
description: Implements deterministic 2D tilemap generation with Binary Space Partitioning for rectangular rooms, A* grid pathfinding for corridor carving between room centers, and a Cellular Automata cave smoother using BFS connected-component flood-fill to keep a single reachable region, emitting a grid, ASCII map and JSON statistics.
metadata:
  source: skills/procedural-dungeon-generator/procedural-dungeon-generator.md
---

# Procedural Dungeon & Map Generator

## 1. System Architecture & Prerequisites

This skill is a pure-stdlib procedural tilemap generator. It ships three
independent but composable algorithm families in one module:

- **`BSPTree`** - Binary Space Partitioning. The map rectangle is recursively
  split (axis chosen by aspect ratio, otherwise random; cut point uniform
  within the allowed band) down to a target leaf size. Each leaf stamps one
  `Room`. Sibling subtrees are joined with L-shaped corridors so the room
  graph stays connected.
- **`AStar`** - grid pathfinder with a Manhattan heuristic. Walls are
  traversable at a configurable `wall_cost`, so the search reuses existing
  floor but cuts through rock when needed. Used to carve extra corridors
  between distant rooms in `generate_dungeon`.
- **`cellular_automata_cave`** - organic caves: random noise smoothed by a
  neighbour-majority rule over `iters` generations, then a BFS
  connected-component flood-fill (`connected_components`) converts every
  floor region except the largest into walls, guaranteeing one reachable
  region.

Public API: `generate_dungeon(width, height, seed)`,
`generate_bsp_rooms(width, height, seed)`,
`cellular_automata_cave(width, height, fill, iters, wall_threshold)` and the
`to_ascii(grid)` renderer. Everything is deterministic for a given seed.

Prerequisites: **Python 3.9+** only. Standard library modules used are
`random`, `math`, `collections.deque`, `dataclasses`, `heapq` and `json`.
No third-party packages are required.

## 2. Input/Output Data Contracts

### 2.1 Input JSON Schema - generation options

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "DungeonGeneratorInput",
  "properties": {
    "width": { "type": "integer", "minimum": 8, "default": 44 },
    "height": { "type": "integer", "minimum": 8, "default": 26 },
    "seed": { "type": "integer", "default": 1337 },
    "min_leaf": { "type": "integer", "minimum": 4, "default": 8 },
    "min_room": { "type": "integer", "minimum": 2, "default": 4 },
    "margin": { "type": "integer", "minimum": 0, "default": 1 },
    "fill": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.45 },
    "iters": { "type": "integer", "minimum": 0, "default": 4 },
    "wall_threshold": { "type": "integer", "minimum": 0, "maximum": 8, "default": 5 },
    "connect_all": { "type": "boolean", "default": true }
  }
}
```

### 2.2 Output data contract - `generate_dungeon` return dict

```json
{
  "grid": {
    "description": "2D list of ints, grid[Y][X]; 0=floor, 1=wall, 2=door",
    "type": "array",
    "items": { "type": "array", "items": { "enum": [0, 1, 2] } }
  },
  "rooms": {
    "description": "List of Room dataclass instances (x, y, w, h, center)",
    "type": "array"
  },
  "seed": { "type": "integer" },
  "stats": {
    "type": "object",
    "properties": {
      "width": { "type": "integer" },
      "height": { "type": "integer" },
      "tiles": { "type": "integer" },
      "rooms": { "type": "integer" },
      "floor": { "type": "integer" },
      "walls": { "type": "integer" },
      "doors": { "type": "integer" },
      "connectivity": { "enum": ["verified by BFS", "split"] }
    }
  }
}
```

### 2.3 Output artifacts

| Artifact                 | Path                                                          | Format |
| ------------------------ | ------------------------------------------------------------- | ------ |
| Reference implementation | `skills/procedural-dungeon-generator/dungeon_gen.py`          | Python |
| Console report           | `to_ascii(grid)` text + JSON stats, printed by `main()`       | stdout |

## 3. Production Reference Implementation

```python
"""dungeon_gen.py - deterministic procedural 2D tilemap generator.

Implements three composable algorithm families:

  * BSP room layout   - a binary space partitioning tree subdivides the map,
                        each leaf stamps a Room, sibling subtrees are joined
                        with L-shaped corridors.
  * A* corridor carving - grid search with a Manhattan heuristic and a
                        configurable wall cost for cutting through rock.
  * Cellular automata  - smoothed random noise plus BFS connected-component
                        flood-fill that retains only the largest walkable
                        region.

Grid encoding: 0 = floor, 1 = wall, 2 = door.
Pure stdlib: random, math, collections, dataclasses, heapq, json.
Run directly:  python dungeon_gen.py
"""

from __future__ import annotations

import heapq
import json
import random
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

FLOOR = 0
WALL = 1
DOOR = 2
LEGEND = {FLOOR: ".", WALL: "#", DOOR: "+"}
Point = Tuple[int, int]


@dataclass
class Room:
    """An axis-aligned rectangle of floor tiles."""

    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> Point:
        return (self.x + self.w // 2, self.y + self.h // 2)

    @property
    def area(self) -> int:
        return self.w * self.h

    def contains(self, px: int, py: int) -> bool:
        """True when (px, py) lies strictly inside this room."""
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h

    def intersects(self, other: "Room") -> bool:
        """True when two room bodies overlap by more than a shared edge."""
        ox0 = max(self.x, other.x)
        oy0 = max(self.y, other.y)
        ox1 = min(self.x + self.w, other.x + other.w)
        oy1 = min(self.y + self.h, other.y + other.h)
        return ox1 - ox0 > 1 and oy1 - oy0 > 1


@dataclass
class BSPTree:
    """Binary space partitioning node over a rectangular map region."""

    x: int
    y: int
    w: int
    h: int
    depth: int = 0
    left: Optional["BSPTree"] = None
    right: Optional["BSPTree"] = None
    room: Optional[Room] = None

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None

    def split(self, rng: random.Random, min_leaf: int) -> bool:
        """Recursively subdivide the node until leaves reach ``min_leaf``.

        Returns True when this node itself was split on this call.
        """
        if not self.is_leaf or self.w < min_leaf * 2 or self.h < min_leaf * 2:
            return False
        if self.w > self.h and self.w >= int(self.h * 1.2):
            split_vertical = True
        elif self.h > self.w and self.h >= int(self.w * 1.2):
            split_vertical = False
        else:
            split_vertical = rng.random() < 0.5
        if split_vertical:
            cut = rng.randint(min_leaf, self.w - min_leaf)
            self.left = BSPTree(self.x, self.y, cut, self.h, self.depth + 1)
            self.right = BSPTree(self.x + cut, self.y, self.w - cut, self.h, self.depth + 1)
        else:
            cut = rng.randint(min_leaf, self.h - min_leaf)
            self.left = BSPTree(self.x, self.y, self.w, cut, self.depth + 1)
            self.right = BSPTree(self.x, self.y + cut, self.w, self.h - cut, self.depth + 1)
        self.left.split(rng, min_leaf)
        self.right.split(rng, min_leaf)
        return True

    def create_rooms(self, rng: random.Random, margin: int,
                     min_w: int, min_h: int) -> None:
        """Stamp one random room into every leaf that is big enough."""
        if self.is_leaf:
            inner_w = self.w - 2 * margin
            inner_h = self.h - 2 * margin
            if inner_w < min_w or inner_h < min_h:
                return
            room_w = rng.randint(min_w, inner_w)
            room_h = rng.randint(min_h, inner_h)
            ox = rng.randint(0, inner_w - room_w) + margin
            oy = rng.randint(0, inner_h - room_h) + margin
            self.room = Room(self.x + ox, self.y + oy, room_w, room_h)
            return
        if self.left is not None:
            self.left.create_rooms(rng, margin, min_w, min_h)
        if self.right is not None:
            self.right.create_rooms(rng, margin, min_w, min_h)

    def rooms(self) -> List[Room]:
        """All rooms stamped onto leaves, depth-first."""
        out: List[Room] = []
        self._collect_rooms(out)
        return out

    def _collect_rooms(self, out: List[Room]) -> None:
        if self.room is not None:
            out.append(self.room)
        if self.left is not None:
            self.left._collect_rooms(out)
        if self.right is not None:
            self.right._collect_rooms(out)

    def _pick_room(self) -> Optional[Room]:
        """Deepest room in this subtree, or None when there is none."""
        if self.room is not None:
            return self.room
        for child in (self.left, self.right):
            if child is not None:
                found = child._pick_room()
                if found is not None:
                    return found
        return None

    def carve_corridors(self, grid: List[List[int]]) -> None:
        """Join every sibling subtree pair with an L-corridor (spanning tree)."""
        if self.left is not None and self.right is not None:
            self.left.carve_corridors(grid)
            self.right.carve_corridors(grid)
            a = self.left._pick_room()
            b = self.right._pick_room()
            if a is not None and b is not None:
                carve_l(grid, a.center, b.center)


def carve_h(grid: List[List[int]], x0: int, x1: int, y: int) -> None:
    """Knock out an inclusive horizontal floor run on row ``y``."""
    lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
    for x in range(lo, hi + 1):
        if grid[y][x] == WALL:
            grid[y][x] = FLOOR


def carve_v(grid: List[List[int]], y0: int, y1: int, x: int) -> None:
    """Knock out an inclusive vertical floor run on column ``x``."""
    lo, hi = (y0, y1) if y0 <= y1 else (y1, y0)
    for y in range(lo, hi + 1):
        if grid[y][x] == WALL:
            grid[y][x] = FLOOR


def carve_l(grid: List[List[int]], a: Point, b: Point) -> None:
    """L-shaped corridor: horizontal leg at a's row, vertical leg at b's column."""
    carve_h(grid, a[0], b[0], a[1])
    carve_v(grid, a[1], b[1], b[0])


def stamp_room(grid: List[List[int]], room: Room) -> None:
    """Write every tile of ``room`` into ``grid`` as floor."""
    for y in range(room.y, room.y + room.h):
        for x in range(room.x, room.x + room.w):
            grid[y][x] = FLOOR


def generate_bsp_rooms(
    width: int,
    height: int,
    seed: int,
    min_leaf: int = 8,
    min_room: int = 4,
    margin: int = 1,
    connect_all: bool = True,
) -> Dict[str, object]:
    """BSP rectangular-room layout.

    Splits the map into leaves, stamps a room per leaf, then optionally
    connects all rooms with L-corridors via room centers.  Returns a dict
    with ``grid``, ``rooms``, ``tree`` and ``seed`` keys.
    """
    rng = random.Random(seed)
    grid: List[List[int]] = [[WALL] * width for _ in range(height)]
    tree = BSPTree(0, 0, width, height)
    tree.split(rng, min_leaf)
    tree.create_rooms(rng, margin, min_room, min_room)
    rooms = tree.rooms()
    if connect_all:
        tree.carve_corridors(grid)
    for room in rooms:
        stamp_room(grid, room)
    return {"grid": grid, "rooms": rooms, "tree": tree, "seed": seed}


class AStar:
    """Grid pathfinder used to carve corridors between distant rooms.

    Walls are traversable at a configurable ``wall_cost`` so the search
    prefers existing floor but cuts through rock when required.  Ties on
    the heap are broken by an insertion counter, keeping results fully
    deterministic.
    """

    def __init__(self, grid: List[List[int]], wall_cost: int = 8) -> None:
        self.grid = grid
        self.wall_cost = wall_cost

    @staticmethod
    def _h(a: Point, b: Point) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def cost(self, x: int, y: int) -> int:
        return self.wall_cost if self.grid[y][x] == WALL else 1

    def _neighbors(self, x: int, y: int):
        ht, wt = len(self.grid), len(self.grid[0])
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < wt and 0 <= ny < ht:
                yield nx, ny

    def find(self, start: Point, goal: Point) -> Optional[List[Point]]:
        """Return the optimal path (list of (x, y), start included) or None."""
        if start == goal:
            return [start]
        start_key = (start[0], start[1])
        goal_key = (goal[0], goal[1])
        open_heap = [(self._h(start, goal), 0, start_key)]
        counter = 1
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], int] = {start_key: 0}
        closed: set = set()
        while open_heap:
            _, _, current = heapq.heappop(open_heap)
            if current == goal_key:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return [(x, y) for (x, y) in path]
            if current in closed:
                continue
            closed.add(current)
            cur_g = g_score[current]
            for nx, ny in self._neighbors(*current):
                nxt = (nx, ny)
                if nxt in closed:
                    continue
                tentative = cur_g + self.cost(nx, ny)
                if tentative < g_score.get(nxt, 10 ** 9):
                    came_from[nxt] = current
                    g_score[nxt] = tentative
                    heapq.heappush(open_heap,
                                   (tentative + self._h(nxt, goal_key), counter, nxt))
                    counter += 1
        return None


def _adjacent_to_room(grid: List[List[int]], x: int, y: int,
                      rooms: Sequence[Room]) -> bool:
    ht, wt = len(grid), len(grid[0])
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < wt and 0 <= ny < ht:
            for r in rooms:
                if r.contains(nx, ny):
                    return True
    return False


def carve_astar_corridor(grid: List[List[int]], start: Point, goal: Point,
                         rooms: Sequence[Room], pathfinder: AStar) -> int:
    """Carve an A* corridor from ``start`` to ``goal``; returns door count.

    Wall tiles on the path that sit right before re-entering a room become
    doors instead of plain floor.
    """
    path = pathfinder.find(start, goal)
    if path is None:
        return 0
    doors = 0
    for (x, y) in path:
        if grid[y][x] == WALL:
            inside = any(r.contains(x, y) for r in rooms)
            if not inside and _adjacent_to_room(grid, x, y, rooms):
                grid[y][x] = DOOR
                doors += 1
            else:
                grid[y][x] = FLOOR
    return doors


def cellular_automata_cave(
    width: int,
    height: int,
    fill: float = 0.45,
    iters: int = 4,
    wall_threshold: int = 5,
    seed: int = 0,
) -> List[List[int]]:
    """Organic cave map from smoothed random noise.

    ``fill`` is the initial wall probability, ``iters`` the number of
    smoothing generations and ``wall_threshold`` the neighbour wall count
    needed for a cell to remain wall.  The result then keeps only the
    largest reachable component so the map is never split into islands.
    """
    rng = random.Random(seed)
    grid: List[List[int]] = [
        [WALL if rng.random() < fill else FLOOR for _ in range(width)]
        for _ in range(height)
    ]
    for _ in range(iters):
        grid = _automata_step(grid, wall_threshold)
    _keep_largest_component(grid)
    return grid


def _automata_step(grid: List[List[int]], wall_threshold: int) -> List[List[int]]:
    ht, wt = len(grid), len(grid[0])
    out: List[List[int]] = [[WALL] * wt for _ in range(ht)]
    for y in range(ht):
        for x in range(wt):
            walls = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if nx < 0 or nx >= wt or ny < 0 or ny >= ht:
                        walls += 1
                    elif grid[ny][nx] == WALL:
                        walls += 1
            out[y][x] = WALL if walls >= wall_threshold else FLOOR
    return out


def connected_components(grid: List[List[int]]) -> List[List[Point]]:
    """Orthogonal BFS flood-fill grouping every floor tile into a component."""
    ht, wt = len(grid), len(grid[0])
    seen = [[False] * wt for _ in range(ht)]
    comps: List[List[Point]] = []
    for y in range(ht):
        for x in range(wt):
            if grid[y][x] != FLOOR or seen[y][x]:
                continue
            seen[y][x] = True
            queue = deque([(x, y)])
            cells: List[Point] = []
            while queue:
                cx, cy = queue.popleft()
                cells.append((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if (0 <= nx < wt and 0 <= ny < ht and not seen[ny][nx]
                            and grid[ny][nx] == FLOOR):
                        seen[ny][nx] = True
                        queue.append((nx, ny))
            comps.append(cells)
    return comps


def _keep_largest_component(grid: List[List[int]]) -> None:
    """Convert every floor component except the largest back into walls."""
    comps = connected_components(grid)
    if not comps:
        return
    largest = max(comps, key=len)
    for comp in comps:
        if comp is largest:
            continue
        for (x, y) in comp:
            grid[y][x] = WALL


def _is_single_component(grid: List[List[int]]) -> bool:
    comps = connected_components(grid)
    return sum(1 for c in comps if c) <= 1


def generate_dungeon(width: int, height: int, seed: int) -> Dict[str, object]:
    """Full pipeline entry point.

    Builds a BSP room layout, connects leaves with L-corridors, then uses
    A* to carve extra corridors between several room pairs.  Returns a dict
    with ``grid`` (0 floor, 1 wall, 2 door), ``rooms``, ``tree``, ``seed``
    and ``stats``.
    """
    rng = random.Random(seed)
    base = generate_bsp_rooms(width, height, seed, connect_all=True)
    grid: List[List[int]] = base["grid"]
    rooms: List[Room] = base["rooms"]
    if len(rooms) >= 2:
        pathfinder = AStar(grid, wall_cost=8)
        order = list(rooms)
        rng.shuffle(order)
        for a, b in zip(order, order[1:]):
            carve_astar_corridor(grid, a.center, b.center, rooms, pathfinder)
    floor = sum(row.count(FLOOR) for row in grid)
    walls = sum(row.count(WALL) for row in grid)
    doors = sum(row.count(DOOR) for row in grid)
    stats = {
        "width": width,
        "height": height,
        "tiles": width * height,
        "seed": seed,
        "rooms": len(rooms),
        "floor": floor,
        "walls": walls,
        "doors": doors,
        "connectivity": "verified by BFS" if _is_single_component(grid) else "split",
    }
    return {
        "grid": grid,
        "rooms": rooms,
        "tree": base["tree"],
        "seed": seed,
        "stats": stats,
    }


def to_ascii(grid: List[List[int]]) -> str:
    """Render the grid as text: '.' = floor, '#' = wall, '+' = door."""
    return "\n".join("".join(LEGEND.get(cell, "?") for cell in row) for row in grid)


def main(width: int = 44, height: int = 26, seed: int = 1337) -> None:
    """Print the BSP dungeon, its JSON stats, and the cave variant."""
    dungeon = generate_dungeon(width, height, seed)
    print("BSP + A* dungeon (seed=%d, %dx%d)" % (seed, width, height))
    print(to_ascii(dungeon["grid"]))
    print(json.dumps(dungeon["stats"], indent=2, sort_keys=True))
    cave = cellular_automata_cave(width, height, seed=seed)
    print("\nCellular-automata cave (seed=%d)" % seed)
    print(to_ascii(cave))


if __name__ == "__main__":
    main()
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Copy the module.** Place `dungeon_gen.py` in the project's `scripts` or
   `procedural/` package. No dependency install step is required.
2. **Generate a full dungeon.** Call
   `data = generate_dungeon(44, 26, seed=1337)`. The returned dict contains
   `grid` (0/1/2 tile matrix), `rooms`, `tree`, `seed` and `stats`.
3. **Inspect floors, walls, doors.** Sum the tile counts from `stats` and
   assert `floor + walls + doors == width * height`.
4. **Read the map.** Print `to_ascii(data["grid"])` for a human-readable
   pass; the `+` cells are doors carved by A* near room entrances.
5. **Tune the layout.** Raise `min_leaf` for fewer, larger rooms; raise
   `wall_cost` on `AStar` if corridors should hug rooms instead of tunneling.
6. **Generate caves instead.** Call
   `cave = cellular_automata_cave(width, height, fill=0.45, iters=4,
   wall_threshold=5, seed=seed)`. Raise `fill` for more wall, raise `iters`
   for rounder blobs.
7. **Verify reachability.** Run `connected_components(grid)`; the largest
   component must contain every floor tile on a correctly generated map.
8. **Determinism audit (agent).** Regenerate with the same seed twice and
   `diff` the ASCII outputs; they must be byte-identical.

## 5. Edge Cases & Error Handling

- **Map too small to split.** When `width < min_leaf * 2` (or height), the
  root stays a leaf, `split()` returns False, and a single room is stamped
  if the leaf fits — no crash.
- **Leaf too small for a room.** `create_rooms` returns silently when a leaf
  cannot fit `min_room + 2 * margin`; `_pick_room` walks up the subtree so
  corridor carving always finds a real anchor.
- **Barren grid for caves.** If every tile becomes wall, `comps` is empty,
  `_keep_largest_component` returns early and the map stays all-walls; the
  caller should raise `fill`/re-seed rather than path-find a corpse.
- **A* unreachable goal.** `find` returns `None` and `carve_astar_corridor`
  returns 0 doors; generation continues without corrupting existing rooms.
- **Index safety in carving.** Corridor legs clamp runs with `lo/hi` ordering
  and rooms pre-validate `contains`, so no partial corridor exceeds the grid.
- **Reproductibility guarantees.** A single seeded `random.Random` feeds all
  random draws (split cuts, room offsets/shuffles, noise) and heap ties are
  ordered by insertion counter, so identical seeds always yield identical
  grids and stats.
- **Connectivity contract.** `_is_single_component` uses the same BFS as the
  cave generator; a `"split"` verdict in `stats` flags degenerate input
  (e.g. `min_room` larger than every leaf) for the caller to adjust.
