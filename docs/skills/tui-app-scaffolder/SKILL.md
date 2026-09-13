---
name: Interactive TUI Application Scaffolder
description: Scaffolds a complete reactive Textual terminal Todo application with header, input, DataTable, footer, status label, custom keybindings and CRUD handlers, and includes a fully written Go Bubbletea counter alternative.
metadata:
  source: skills/tui-app-scaffolder/tui-app-scaffolder.md
---

# Interactive TUI Application Scaffolder

## 1. System Architecture & Prerequisites

Scaffolds rich terminal UI applications with **Textual/Rich** (Python) or
**Bubbletea** (Go). The reference implementation is a full Todo app on
Textual: a composable widget tree (Header, Input, DataTable, status Label,
Footer), reactive event handlers, custom keybindings, and an inline CSS
stylesheet. A complete Bubbletea counter is supplied as the cross-language Go
alternative.

Prerequisites:

- **Python 3.9+** and `pip install textual` (Textual ≥ 0.50). Rich is pulled
  in as a Textual dependency; no separate install needed.
- For terminals: Textual needs a real TTY. On Windows use Windows Terminal
  (or `cmd`/PowerShell with VT enabled); on Linux/macOS any modern terminal.
- Optional Bubbletea path: Go 1.21+ and
  `go get github.com/charmbracelet/bubbletea@latest`.

## 2. Input/Output Data Contracts

### Input: application definition (in code)

The scaffolder requires a widget tree specification + interaction contract:

| Element | Contract |
| ------- | -------- |
| `Header`   | app title bar with clock/guidance |
| `Input`    | `id="task-input"`, Submit fires `add_task` |
| `DataTable`| columns `#`, `Task`, `Status`; row cursor selection |
| `Label`    | `id="status"`, user-facing state messages |
| `Footer`   | lists current `BINDINGS` keymap |
| Key bindings | `ctrl+d` delete selected, `ctrl+i` focus input, `ctrl+q` quit |

### Output

- `tui_app.py` — runnable Textual app (`python tui_app.py`).
- Optional `app.tcss` — the same stylesheet in external-file form for
  `App.CSS_PATH` deployment.
- Optional `main.go` — Bubbletea counter (fully written, `go run .`).

No JSON manifests or config files are required — the contract is the widget
tree + bindings above.

## 3. Production Reference Implementation

Save as `tui_app.py`. Complete, importable, and runnable with
`python tui_app.py`.

```python
#!/usr/bin/env python3
"""Textual Todo application — the TUI scaffolder reference implementation.

Features:
  - compose(): Header, Input, DataTable, status Label, Footer
  - reactive handlers: on_input_submitted (add) and on_input_changed (status)
  - custom keybindings: ctrl+d (delete selected row), ctrl+i (focus input)
  - DataTable cursor selection with explicit row keys
Run:  python tui_app.py
"""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Input, Label

# Inline stylesheet. Also works as an external `app.tcss` via CSS_PATH.
CSS = """
Screen {
    background: $surface;
    layout: vertical;
}

#task-input {
    dock: top;
    margin: 1 2 0 2;
    border: tall $primary 30%;
}

DataTable {
    height: 1fr;
    margin: 1 2 0 2;
    border: round $accent;
}

DataTable > .datatable--cursor {
    background: $accent 35%;
}

#status {
    height: 1;
    padding: 0 2;
    background: $panel;
    color: $text-muted;
}

Footer {
    dock: bottom;
}
"""


class TodoApp(App):
    TITLE = "Todo"
    SUB_TITLE = "zero-to-terminal in 60 seconds"
    CSS = CSS

    BINDINGS = [
        Binding("ctrl+d", "delete_task", "Delete selected"),
        Binding("ctrl+i", "focus_input", "Focus input"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._id_counter = 0
        self._task_titles: dict[int, str] = {}

    def compose(self):
        yield Header()
        yield Input(placeholder="Type a task and press Enter", id="task-input")
        yield DataTable(id="tasks")
        yield Label("Ready.", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tasks", DataTable)
        table.add_columns("#", "Task", "Status")
        table.cursor_type = "row"
        table.zebra_stripes = True
        self._set_status("No tasks yet. Type one below and press Enter.")

    # -- reactive handlers ---------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter on the Input widget: add a task row."""
        event.stop()
        text = event.value.strip()
        input_widget = self.query_one("#task-input", Input)
        input_widget.value = ""
        if not text:
            self._set_status("Empty task ignored.")
            return
        self._id_counter += 1
        task_id = self._id_counter
        self._task_titles[task_id] = text
        table = self.query_one("#tasks", DataTable)
        table.add_row(str(task_id), text, "open", key=str(task_id))
        self._set_status(f"Added task #{task_id}: {text}")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Reactive status line while typing (demonstrates state updates)."""
        event.stop()
        length = len(event.value)
        if length:
            self._set_status(f"{length} characters typed.")
        else:
            self._set_status("Ready.")

    # -- actions --------------------------------------------------------

    def action_delete_task(self) -> None:
        table = self.query_one("#tasks", DataTable)
        if table.row_count == 0:
            self._set_status("Nothing to delete.")
            return
        try:
            cell_key = table.coordinate_to_cell_key(table.cursor_coordinate)
        except KeyError:
            self._set_status("No row selected.")
            return
        row_key = cell_key.row_key
        task_id = int(row_key.value)
        title = self._task_titles.pop(task_id, "<unknown>")
        table.remove_row(row_key)
        self._set_status(f"Deleted task #{task_id}: {title}")

    def action_focus_input(self) -> None:
        self.query_one("#task-input", Input).focus()

    # -- helpers ---------------------------------------------------------

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Label).update(message)


def main() -> None:
    TodoApp().run()


if __name__ == "__main__":
    main()
```

### External stylesheet variant — `app.tcss`

```css
Screen {
    background: $surface;
    layout: vertical;
}

#task-input {
    dock: top;
    margin: 1 2 0 2;
    border: tall $primary 30%;
}

DataTable {
    height: 1fr;
    margin: 1 2 0 2;
    border: round $accent;
}

#status {
    height: 1;
    padding: 0 2;
    background: $panel;
    color: $text-muted;
}

Footer {
    dock: bottom;
}
```

Switch with `CSS_PATH = "app.tcss"` and `CSS = None` (or delete the inline
attribute) — Textual merges in reverse priority, so external or inline works
identically.

## 4. Execution Protocol & Step-by-Step Workflow

1. **Bootstrap.** `pip install textual`, then copy `tui_app.py` into the
   project. Run `python tui_app.py` to confirm the toy runs.
2. **Define the widget tree** in `compose()` (top to bottom: Header, Input,
   DataTable, status Label, Footer).
3. **Add bindings** in `BINDINGS` and name private `action_*` methods exactly
   after the binding action ids (`ctrl+d` -> `action_delete_task`).
4. **Wire reactive handlers.** `on_input_submitted` for writes,
   `on_input_changed` for keystroke-level state feedback, `on_mount` for
   one-time table configuration. Prefer Textual's `Subject`/`reactive` for
   data the UI reflects.
5. **Persist.** After each `add`/`delete` call `table.save`-equivalent
   semantics — i.e. write `self._task_titles` to a local JSON file on change
   so restarts are not lost.
6. **Extend** with a `ModalScreen("Confirm delete?")`, worker threads for
   long jobs (`@work`/`run_worker`), and `Input(disabled=True)` while the
   DataTable is dirty.
7. **Package** — wrap in a console script entry point and call
   `TodoApp().run()` from `if __name__ == "__main__"`, exactly as shown.

### Cross-language option — Bubbletea (Go), complete `main.go`

```go
package main

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"
)

type model struct {
	count int
}

func (m model) Init() tea.Cmd { return nil }

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c", "q":
			return m, tea.Quit
		case "up", "k", "+":
			m.count++
		case "down", "j", "-":
			m.count--
		}
	}
	return m, nil
}

func (m model) View() string {
	return fmt.Sprintf(
		"Count: %d\n\n\033[32m+\033[0m/up increase   \033[33m-\033[0m/down decrease   \033[31mq\033[0m/ctrl+c quit\n",
		m.count,
	)
}

func main() {
	program := tea.NewProgram(model{count: 0})
	if _, err := program.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "bubbletea error: %v\n", err)
		os.Exit(1)
	}
}
```

Go build/run: `go mod init tui-counter && go get github.com/charmbracelet/bubbletea@latest && go run .` — the model/update/view triangle maps 1:1 to Textual's `compose`/actions/Screen-render philosophy.

## 5. Edge Cases & Error Handling

- **Textual not installed** — `ModuleNotFoundError: textual` at import;
  the fix is `pip install textual` (stated in Section 1). On a missing TTY,
  Textual raises `TextualError` — run inside a real terminal, not a pipe.
- **DataTable row deletion off-by-one** — the reference stores explicit
  `key=str(task_id)` row keys so `remove_row(row_key)` never deletes the wrong
  row after filtering/ordering; never index by cursor position alone.
- **Delete on empty table** — guarded by `table.row_count == 0`; the
  `KeyError` from `coordinate_to_cell_key` with no selection is also caught.
- **Empty input submit** — `event.value.strip()` guards blank tasks from
  entering the table (a classic scaffold bug in tutorials).
- **`Binding` action name typos** — Textual raises on bad bindings at startup
  (`AttributeError: action_xxx not found`); keep action ids and method names
  welded together.
- **Version drift on `coordinate_to_cell_key`** — older Textual releases used
  `get_cell_at`/`row_key_at`; if the reader's edition differs, prefer the
  stable `DataTable.cursor_coordinate` + `coordinate_to_cell_key` documented
  here (Textual ≥ 0.28).
- **Windows terminal quirks** — use Windows Terminal, set `TERM=xterm-256color`
  if colours misrender, and avoid racing `App.run()` from Jupyter/headless
  shells (run `.run_test()` for headless smoke tests).
- **Resource cleanup** — `on_unmount` should save state; long-running workers
  must be cancelled if the app is dismissed, or the event loop lingers.
- **Bubbletea port** — the Go mirror guards missing dependencies (the
  `go.mod` is created before `go run .`) and quits cleanly on `ctrl+c`,
  matching the Textual esc/quit contract.
