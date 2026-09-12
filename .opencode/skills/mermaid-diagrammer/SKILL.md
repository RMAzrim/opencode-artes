---
name: Mermaid Diagrammer
description: Convert code logic, database structures, or system architectures into valid Mermaid.js visual diagrams.
metadata:
  source: skills/mermaid-diagrammer/mermaid-diagrammer.md
---

# Mermaid Diagrammer

## Prerequisites & Dependencies
- Node.js 18+ with npm or pnpm (for Mermaid CLI or Vite/Webpack plugin)
- Mandatory package: `npm i mermaid` or enable Mermaid syntax in your Markdown renderer (Obsidian, VS Code, GitHub Pages)
- Optional: `npm i @mermaid-js/prettier` for code formatting, or `mermaid-live-editor` for online preview

## Execution Steps
1. Choose the diagram type based on the structure you want to visualize:
   - **Flowchart**: process flows, decision points, and arrows
   - **Sequence diagram**: lifelines and messages between objects
   - **Class diagram**: classes, attributes, methods, and relationships
   - **Gantt chart**: project timelines and tasks
   - **Entity-Relationship (ER) diagram**: tables and foreign key relationships
2. Write the Mermaid source syntax using the appropriate block type
3. Render the diagram:
   - In VS Code: install the `Mermaid Markdown Preview` extension and press `Cmd+Shift+V`
   - In Obsidian: enable `Mermaid` preview in settings
   - In web apps: import `mermaid.initialize({ startOnLoad: true, svg: true })` or use the `@mermaid-js/renderer` package
4. Customize styling: adjust colors, fonts, and padding via Mermaid's theme CSS or `theme` configuration
5. Export as SVG/PNG for documentation: `mermaid.cli` or browser `window.mermaid.exportSVG()`

```mermaid
%% Flowchart: user onboarding process
flowchart TD
    A[Start] --> B{Has account?}
    B -->|Yes| C[Dashboard]
    B -->|No| D[Sign-up Form]
    D --> E[Verify Email]
    E --> C[Dashboard]
    C --> F[Complete Profile]
    F --> G[Welcome Modal]

%% Sequence diagram: API request flow
sequenceDiagram
    participant User
    participant Client
    participant Server
    User->>Client: Send request
    Client->>Server: Process request
    Server-->>Client: Return response
    Client-->>User: Update UI
```

```bash
# Install Mermaid CLI globally (optional)
npm i -g mermaid.cli

# Render a Mermaid file to SVG
mmdc -i diagram.mmd -o diagram.svg
```
