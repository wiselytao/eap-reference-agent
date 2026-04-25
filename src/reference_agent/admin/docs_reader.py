from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
import re


DOCS_ROOTS = ("README.md", "CHANGELOG.md", "VERSION.md")
DOCS_DIRECTORIES = ("PRD", "Reference", "doc")


def build_docs_page_model(selected_doc: str | None) -> dict[str, Any]:
    available = list_available_docs()
    selected_name = selected_doc or "README.md"
    selected_entry = next((item for item in available if item["name"] == selected_name), None)
    if selected_entry is None and available:
        selected_entry = available[0]
        selected_name = selected_entry["name"]

    for entry in available:
        entry["is_selected"] = entry["name"] == selected_name

    if selected_entry is None:
        return {
            "selected_doc": None,
            "available_docs": available,
            "error": "No allowlisted project docs are available.",
        }

    return {
        "selected_doc": {
            "name": selected_entry["name"],
            "path": selected_entry["path"],
            "html": render_markdown(selected_entry["file_path"].read_text(encoding="utf-8")),
        },
        "available_docs": available,
        "error": None,
    }


def list_available_docs() -> list[dict[str, Any]]:
    repo = repo_root()
    paths: list[Path] = []

    for relative_name in DOCS_ROOTS:
        path = repo / relative_name
        if path.is_file():
            paths.append(path)

    for relative_dir in DOCS_DIRECTORIES:
        directory = repo / relative_dir
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.md")):
            if any(part.startswith(".") for part in path.parts):
                continue
            paths.append(path)

    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        name = path.relative_to(repo).as_posix()
        if name in seen:
            continue
        seen.add(name)
        docs.append(
            {
                "name": name,
                "path": str(path),
                "href": f"/admin/docs?doc={name}",
                "file_path": path,
                "is_selected": False,
            }
        )
    return docs


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def render_markdown(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_kind: str | None = None
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(f"<p>{render_inline(' '.join(paragraph).strip())}</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if list_items:
            tag = "ol" if list_kind == "ordered" else "ul"
            blocks.append(f"<{tag}>" + "".join(list_items) + f"</{tag}>")
            list_items.clear()
        list_kind = None

    def flush_code() -> None:
        if code_lines:
            blocks.append(
                '<pre class="admin-code-block"><code>'
                + escape("\n".join(code_lines))
                + "</code></pre>"
            )
            code_lines.clear()

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            if in_code:
                flush_code()
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        if stripped.startswith("#"):
            flush_paragraph()
            flush_list()
            level = min(len(stripped) - len(stripped.lstrip("#")), 6)
            heading = stripped[level:].strip()
            blocks.append(f"<h{level}>{render_inline(heading)}</h{level}>")
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_paragraph()
            if list_kind not in (None, "unordered"):
                flush_list()
            list_kind = "unordered"
            list_items.append(f"<li>{render_inline(stripped[2:].strip())}</li>")
            continue

        match = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if match:
            flush_paragraph()
            if list_kind not in (None, "ordered"):
                flush_list()
            list_kind = "ordered"
            list_items.append(f"<li>{render_inline(match.group(1).strip())}</li>")
            continue

        paragraph.append(stripped)

    flush_paragraph()
    flush_list()
    if in_code:
        flush_code()

    return "\n".join(blocks)


def render_inline(text: str) -> str:
    escaped = escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    return escaped
