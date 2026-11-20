#!/usr/bin/env python3
"""Rebuild only Step 8 of the main notebook from src/event_level_simulation.py.

The script preserves Steps 1-7 and Step 9 onward. It replaces the cells from
"## Step 8 — Event-level spatiotemporal simulation" up to the next "## Step N"
section with cells parsed from the percent-format Step 8 source file.

Usage from the repository root:
    python build_notebook.py

By default it updates notebooks/metro_manila_traffic_simulation.ipynb in place.
Use --output to write a separate file instead.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

STEP8_HEADING = "## Step 8 — Event-level spatiotemporal simulation"


def repo_root() -> Path:
    here = Path(__file__).resolve().parent
    candidates = [here, *here.parents, Path.cwd(), *Path.cwd().parents]
    for candidate in candidates:
        if (candidate / "notebooks").is_dir() and (candidate / "src").is_dir():
            return candidate
    raise FileNotFoundError("Could not find repository root containing notebooks/ and src/.")


def parse_percent_file(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    cells: list[dict] = []
    kind = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, kind
        if kind is None:
            buf = []
            return
        if kind == "markdown":
            md = []
            for line in buf:
                if line.startswith("# "):
                    md.append(line[2:])
                elif line.startswith("#"):
                    md.append(line[1:])
                else:
                    md.append(line)
            cells.append({"cell_type": "markdown", "metadata": {}, "source": md})
        else:
            cells.append({
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": buf.copy(),
            })
        buf = []

    for line in lines:
        marker = line.strip()
        if marker == "# %% [markdown]":
            flush()
            kind = "markdown"
        elif marker == "# %%":
            flush()
            kind = "code"
        else:
            if kind is not None:
                buf.append(line)
    flush()

    if not cells:
        raise ValueError(f"No '# %%' cells found in {path}")
    first_text = "".join(cells[0].get("source", []))
    if STEP8_HEADING not in first_text:
        raise ValueError(f"First parsed Step 8 cell does not contain expected heading: {STEP8_HEADING}")
    return cells


def step8_bounds(cells: list[dict]) -> tuple[int, int]:
    start = None
    for i, cell in enumerate(cells):
        text = "".join(cell.get("source", []))
        if start is None and STEP8_HEADING in text:
            start = i
            continue
        if start is not None and i > start and cell.get("cell_type") == "markdown":
            stripped = text.lstrip()
            if re.match(r"^## Step\s+(?!8\b)", stripped):
                return start, i
    if start is None:
        raise ValueError("Could not find Step 8 in the notebook.")
    return start, len(cells)


def main() -> None:
    root = repo_root()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--notebook",
        type=Path,
        default=root / "notebooks" / "metro_manila_traffic_simulation.ipynb",
    )
    parser.add_argument(
        "--step8",
        type=Path,
        default=root / "src" / "event_level_simulation.py",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    notebook_path = args.notebook.resolve()
    step8_path = args.step8.resolve()
    output_path = args.output.resolve() if args.output else notebook_path

    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    new_step8 = parse_percent_file(step8_path)
    start, end = step8_bounds(notebook["cells"])

    notebook["cells"] = notebook["cells"][:start] + new_step8 + notebook["cells"][end:]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"Rebuilt Step 8 from: {step8_path}")
    print(f"Wrote notebook:      {output_path}")
    print(f"Replaced cells:      {start}..{end - 1}")
    print(f"New Step 8 cells:    {len(new_step8)}")


if __name__ == "__main__":
    main()
