"""Write proof diagrams as self-contained HTML files with mermaid.js rendering."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def write_diagram_html(output_path: Path, title: str, diagrams: list[dict]) -> Path:
    """Write an HTML file containing mermaid diagrams.

    Args:
        output_path: File path to write. Parent directory must exist.
        title: Used as the HTML <title> element content.
        diagrams: List of dicts with keys 'mermaid' (str) and 'label' (str or None).

    Returns:
        The output_path written.

    Raises:
        FileNotFoundError: If the parent directory does not exist.
        OSError: On I/O errors.
    """
    sections = []
    for diagram in diagrams:
        mermaid_text = diagram["mermaid"]
        label = diagram.get("label")
        parts = []
        if label is not None:
            parts.append(f"    <h2>{label}</h2>")
        # Use json.dumps to safely embed mermaid text in a JS string literal
        safe_mermaid = json.dumps(mermaid_text)
        parts.append(
            f'    <pre class="mermaid">\n'
            f"    </pre>\n"
            f"    <script>\n"
            f"      document.currentScript.previousElementSibling.textContent = {safe_mermaid};\n"
            f"    </script>"
        )
        sections.append("\n".join(parts))

    body_content = "\n".join(sections)

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <script>
    mermaid.initialize({{ startOnLoad: true, theme: "dark" }});
  </script>
</head>
<body>
{body_content}
</body>
</html>
"""

    output_path.write_text(html)
    return output_path
