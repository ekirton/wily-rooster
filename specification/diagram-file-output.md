# Diagram File Output

Write self-contained HTML files that render Mermaid diagrams in a browser, as a side effect of visualization MCP tool calls.

**Architecture**: [diagram-file-output.md](../doc/architecture/diagram-file-output.md)

---

## 1. Purpose

Define the `write_diagram_html` function, its HTML template structure, and the integration contract with visualization tool handlers.

## 2. Scope

**In scope**: `write_diagram_html` function signature and behavior, HTML template requirements, handler integration contract, error handling.

**Out of scope**: Mermaid diagram generation logic (owned by mermaid-renderer), MCP protocol handling (owned by mcp-server), browser-side rendering behavior beyond template structure.

## 3. Definitions

| Term | Definition |
|------|-----------|
| `write_diagram_html` | Pure function that writes a self-contained HTML file rendering one or more Mermaid diagrams |
| diagram dict | A dictionary with keys `mermaid: str` (Mermaid syntax text) and `label: str \| None` (optional heading for the diagram section) |

## 4. Behavioral Requirements

### 4.1 Function Signature

```
write_diagram_html(output_path: Path, title: str, diagrams: list[dict]) -> Path
```

- `output_path`: file path to write. Parent directory must exist (the function does not create directories).
- `title`: used as the HTML `<title>` element content.
- `diagrams`: list of diagram dicts. Each dict has keys `mermaid` (str, required) and `label` (str or None).
- Returns: the `output_path` written.

### 4.2 HTML Output

The written file is a valid HTML document:
- Starts with `<!DOCTYPE html>` declaration
- Contains `<html>`, `<head>`, `<body>` elements
- `<title>` element matches the `title` parameter
- Loads mermaid.js from CDN (`cdn.jsdelivr.net/npm/mermaid`)
- Configures mermaid with dark theme
- Renders each diagram via client-side `mermaid.render()` or equivalent initialization

### 4.3 Single Diagram

When `diagrams` contains one entry, the HTML contains one diagram section. No heading is rendered if `label` is None.

### 4.4 Multiple Diagrams

When `diagrams` contains multiple entries, the HTML contains one section per entry, in order. Each section with a non-None `label` renders the label as a heading. Sections with `label: None` have no heading.

### 4.5 Overwrite Behavior

When a file already exists at `output_path`, the function overwrites it with the new content. No merge, append, or backup.

### 4.6 Special Character Safety

Mermaid text containing `"`, `<`, `>`, `&`, or other HTML-sensitive characters must not break the HTML structure. The embedding mechanism must escape or encode these characters appropriately.

### 4.7 No Server Dependencies

The HTML file must not contain references to `/viewer/events`, `EventSource`, SSE endpoints, or any server-side resources beyond the mermaid.js CDN.

## 5. Handler Integration

Each visualization handler calls `write_diagram_html` when `diagram_dir is not None`:

- Constructs `output_path` as `diagram_dir / "proof-diagram.html"`
- Passes the appropriate title and diagram list (see architecture document for per-tool formats)
- Call is fire-and-forget: exceptions are caught and logged at WARNING, not propagated to the MCP response

When `diagram_dir is None`, the handler skips the file write entirely.

## 6. Error Specification

| Condition | Behavior |
|-----------|----------|
| `IOError` on write (permissions, disk full) | Logged at WARNING; not propagated to caller |
| Parent directory does not exist | Raise error (do not create parent directories) |
| Empty `diagrams` list | Write valid HTML with no diagram sections |
| `mermaid` value is empty string | Write section with empty diagram (no error) |

## 7. Language-Specific Notes (Python)

- Module: `src/poule/server/diagram_writer.py` (provisional)
- `output_path` parameter: `pathlib.Path`
- HTML template: f-string or equivalent string construction
- Mermaid text embedding: `json.dumps` for safe JavaScript string escaping
- Logging: `logging.getLogger(__name__).warning(...)` for caught I/O errors
