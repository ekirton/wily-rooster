# Diagram File Output

Self-contained HTML file output for proof visualization diagrams — visualization tools write a file the user opens in their browser.

**Stories**: [Epic 5: Diagram File Output](../requirements/stories/proof-visualization-widgets.md#epic-5-diagram-file-output)

---

## Problem

Poule's visualization tools generate Mermaid diagram syntax — text that describes a diagram. In Claude Code's terminal interface, this text is returned to the LLM, which can display it as raw text. But the whole point of visualization is to *see* a rendered graphic. The user needs a visual channel alongside the terminal.

## Solution

Visualization tools write a self-contained HTML file (`proof-diagram.html`) to the project directory as a side effect of each call. The user opens this file in their browser to see the rendered diagram. Since the project directory is bind-mounted at the same host path, the file is directly accessible from the host machine.

The user experience is:
1. Work with Claude: "Visualize the proof tree for `app_nil_r`"
2. Open `proof-diagram.html` in a browser (bookmark it once)
3. Diagram is visible — refresh the browser tab after each new visualization call

The tools still return Mermaid text to Claude Code as before. The HTML file replaces the previous SSE-based live diagram viewer, which has been removed.

## Design Rationale

### Why file output rather than an SSE viewer

A static HTML file works across container boundaries via bind mounts with no server connection needed. It handles multi-diagram sequences naturally (all diagrams in one scrollable page). There is no connection state to manage, no reconnection logic, and no port mapping beyond what MCP already requires.

### Why a single overwritten file

Avoids clutter in the project directory. The user bookmarks the file once. Each visualization call produces fresh content. There is no need for diagram history — the user re-runs the visualization tool to regenerate.

### Why mermaid.js from CDN

No bundling needed, browser caches it after the first load, and the Docker image stays lean. The HTML file remains self-contained (no local assets to manage).

## Scope Boundaries

Provides: self-contained HTML file with CDN mermaid.js, dark theme, multi-diagram support with step labels, client-side `mermaid.render()`.

Does **not** provide: persistent diagram history, image export (PNG/SVG), interactive features (pan, zoom, collapse), offline mermaid.js (CDN required on first load).
