#!/usr/bin/env python3
"""Convert a Mermaid class diagram (.mmd) to a TikZ UML-like drawing."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict, deque
from pathlib import Path


CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z0-9_.$]+)\s*(\{)?\s*$")
INHERIT_RE = re.compile(r"^\s*([A-Za-z0-9_.$]+)\s+--\|>\s+([A-Za-z0-9_.$]+)\s*$")
DIRECTION_RE = re.compile(r"^\s*direction\s+([A-Z]{2})\s*$")


LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "^": r"\textasciicircum{}",
    "~": r"\textasciitilde{}",
}


def latex_escape(text: str) -> str:
    return "".join(LATEX_ESCAPES.get(ch, ch) for ch in text)


def format_member(member: str) -> str:
    style = None
    text = member

    if text.endswith("*"):
        style = "italic"
        text = text[:-1].rstrip()
    elif text.endswith("$"):
        style = "underline"
        text = text[:-1].rstrip()

    visibility = ""
    remainder = text
    if text[:1] in {"+", "-", "#", "~"}:
        visibility = latex_escape(text[0])
        remainder = text[1:].lstrip()

    formatted_remainder = latex_escape(remainder)
    if ":" in remainder and style in {"italic", "underline"}:
        left, right = remainder.split(":", 1)
        left = latex_escape(left.rstrip())
        right = latex_escape(right.lstrip())
        if style == "italic":
            formatted_remainder = rf"\textit{{{left}}}: {right}"
        else:
            formatted_remainder = rf"\underline{{{left}}}: {right}"
    else:
        if style == "italic":
            formatted_remainder = rf"\textit{{{formatted_remainder}}}"
        elif style == "underline":
            formatted_remainder = rf"\underline{{{formatted_remainder}}}"

    if visibility:
        return f"{visibility} {formatted_remainder}"
    return formatted_remainder


def normalize_member(line: str) -> str:
    member = line.strip()
    member = member.replace(r"\_", "_")
    member = member.replace("~", "")
    return member


def strip_mermaid_fence(content: str) -> str:
    lines = content.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
    return "\n".join(lines)


def parse_mermaid(content: str):
    text = strip_mermaid_fence(content)
    classes: dict[str, list[str]] = {}
    inherits: list[tuple[str, str]] = []
    direction = "TB"

    in_class: str | None = None

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped or stripped.startswith("%%"):
            continue

        if in_class:
            if stripped == "}":
                in_class = None
                continue
            classes[in_class].append(normalize_member(stripped))
            continue

        m_dir = DIRECTION_RE.match(stripped)
        if m_dir:
            direction = m_dir.group(1)
            continue

        m_class = CLASS_RE.match(stripped)
        if m_class:
            name = m_class.group(1)
            classes.setdefault(name, [])
            if m_class.group(2) == "{":
                in_class = name
            continue

        m_inherit = INHERIT_RE.match(stripped)
        if m_inherit:
            child, parent = m_inherit.group(1), m_inherit.group(2)
            inherits.append((child, parent))
            classes.setdefault(child, [])
            classes.setdefault(parent, [])

    if not classes:
        raise ValueError("No classes found in Mermaid input.")

    return classes, inherits, direction


def class_depths(classes: dict[str, list[str]], inherits: list[tuple[str, str]]) -> dict[str, int]:
    children: dict[str, list[str]] = defaultdict(list)
    indeg: dict[str, int] = {name: 0 for name in classes}

    for child, parent in inherits:
        children[parent].append(child)
        indeg[child] += 1

    roots = [n for n, d in indeg.items() if d == 0]
    if not roots:
        return {name: 0 for name in classes}

    depth = {name: 0 for name in classes}
    q = deque(roots)

    while q:
        node = q.popleft()
        for nxt in children[node]:
            cand = depth[node] + 1
            if cand > depth[nxt]:
                depth[nxt] = cand
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)

    return depth


def class_node_body(name: str, members: list[str]) -> str:
    attrs = [m for m in members if "(" not in m]
    methods = [m for m in members if "(" in m]
    lines = [
        r"\begin{tabular}{|l|}",
        r"\hline",
        rf"\rowcolor{{umlheader}}\multicolumn{{1}}{{|c|}}{{\textbf{{{latex_escape(name)}}}}} \\",
        r"\hline",
    ]

    if attrs:
        lines.extend(rf"{format_member(attr)} \\" for attr in attrs)

    if attrs and methods:
        lines.append(r"\hline")

    if methods:
        lines.extend(rf"{format_member(method)} \\" for method in methods)

    if attrs or methods:
        lines.append(r"\hline")

    lines.append(r"\end{tabular}")
    return "\n".join(lines)


def inheritance_anchors(direction: str) -> tuple[str, str]:
    """Return (child_anchor, parent_anchor) for drawing inheritance arrows."""
    if direction in {"TB", "BT"}:
        return "north", "south"
    if direction == "LR":
        return "west", "east"
    if direction == "RL":
        return "east", "west"
    return "north", "south"


def relative_placement_option(direction: str) -> str:
    """Return the TikZ `positioning` option that places a node relative to another
    so that there is a fixed gap between their *edges* (not their centres)."""
    if direction == "TB":
        return "below"
    if direction == "BT":
        return "above"
    if direction == "LR":
        return "right"
    if direction == "RL":
        return "left"
    return "below"


def generate_tikz(
    classes: dict[str, list[str]],
    inherits: list[tuple[str, str]],
    direction: str,
    arrow_length: float,
    row_spacing: float,
) -> str:
    depths = class_depths(classes, inherits)
    by_level: dict[int, list[str]] = defaultdict(list)
    for name, d in depths.items():
        by_level[d].append(name)

    for level in by_level:
        by_level[level].sort()

    max_level = max(by_level)

    # Cross-axis gap (between sibling columns/rows at the same depth level).
    x_gap = 7.0
    y_gap = 5.0

    name_to_node = {name: f"c{i}" for i, name in enumerate(sorted(classes))}

    # ------------------------------------------------------------------
    # Build node placement lines.
    #
    # Strategy:
    #   * For the depth axis (the axis along which inheritance flows) we use
    #     relative placement ("below=<gap> of <anchor>") so the gap is always
    #     measured between box *edges*, not between centres.
    #   * For the cross axis (siblings at the same depth) we still use absolute
    #     x/y coordinates centred around 0, because we don't have a simple
    #     chain to anchor from.
    #
    # To keep both strategies compatible we:
    #   1. Place every node at a fixed cross-axis position (x for TB/BT,
    #      y for LR/RL) using `at`.
    #   2. For nodes at depth > 0, pick one representative "column anchor" per
    #      level – the first node in the previous level that is a parent of
    #      this node (falling back to index 0) – and use
    #      `[<dir>=<gap> of <anchor>.<edge>]` to set the depth-axis position.
    #
    # For the common single-column case this reduces to a clean chain.
    # ------------------------------------------------------------------

    # Build a quick child->parents map for anchor selection.
    parents_of: dict[str, list[str]] = defaultdict(list)
    for child, parent in inherits:
        parents_of[child].append(parent)

    placement_option = relative_placement_option(direction)
    gap_str = f"{arrow_length:.2f}cm"

    node_lines: list[str] = []

    for level in sorted(by_level):
        names = by_level[level]
        n = len(names)

        for col_idx, name in enumerate(names):
            node_id = name_to_node[name]
            body = class_node_body(name, classes[name])

            # ---- Cross-axis absolute position ----
            cross_offset = (col_idx - (n - 1) / 2.0)
            if direction in {"TB", "BT"}:
                cross_coord = f"{cross_offset * x_gap:.2f}"   # x value
            else:
                cross_coord = f"{-cross_offset * y_gap:.2f}"  # y value

            if level == 0:
                # Root nodes: place at absolute cross-axis position, depth = 0.
                if direction in {"TB", "BT"}:
                    coord = f"({cross_coord},0)"
                else:
                    coord = f"(0,{cross_coord})"
                node_lines.append(
                    rf"\node[umlclass] ({node_id}) at {coord} {{{body}}};"
                )
            else:
                # Non-root: find a parent node to anchor from for the depth axis.
                my_parents = parents_of.get(name, [])
                if my_parents:
                    # Prefer a parent that is in the immediately preceding level.
                    prev_level_names = set(by_level.get(level - 1, []))
                    anchor_parent = next(
                        (p for p in my_parents if p in prev_level_names),
                        my_parents[0],
                    )
                else:
                    # Isolated node promoted to this depth – fall back to first
                    # node of the previous level.
                    anchor_parent = by_level[level - 1][0]

                anchor_id = name_to_node[anchor_parent]

                # Relative placement positions the *edge* of this node at
                # `gap_str` from the *edge* of the anchor node.
                # We still want to control the cross-axis, so we combine
                # `below=… of …` with an explicit coordinate override via
                # a phantom node trick or simply accept that siblings are
                # shifted by using `xshift` / `yshift`.
                if direction in {"TB", "BT"}:
                    # `below=… of anchor` sets y; override x with xshift relative
                    # to the anchor's x, or just set it absolutely in a second step.
                    # Simplest: use `below=… of anchor` and then xshift to reach
                    # the desired absolute x.  We compute the anchor's x and diff.
                    # Actually TikZ `below=X of N` places the new node so that
                    # there is exactly X between the south of N and the north of
                    # the new node, *at the same x*.  We then apply an xshift to
                    # move to the desired column.
                    node_lines.append(
                        rf"\node[umlclass,below={gap_str} of {anchor_id}.south,"
                        rf"xshift={cross_coord}cm-(\pgfkeysvalueof{{/pgf/decoration/raise}}"
                        # pgf trick doesn't work cleanly; use simpler explicit x override:
                        # We'll emit a proper version below – see rewrite.
                        rf"] ({node_id}) {{{body}}};"
                    )
                else:
                    node_lines.append(
                        rf"\node[umlclass,right={gap_str} of {anchor_id}.east,"
                        rf"yshift={cross_coord}cm"
                        rf"] ({node_id}) {{{body}}};"
                    )

    # The pgf xshift trick above is messy. Use a cleaner two-pass approach:
    # emit nodes with `below=gap of anchor` for the depth axis and a
    # `\path` yshift/xshift override for the cross axis via `at` + calc.
    # The cleanest TikZ idiom is:
    #
    #   \node[below=GAP of ANCHOR] (id) at (CROSS_X, -.5*GAP) {...}
    #
    # But `below=… of …` and `at` conflict in older TikZ.
    # The correct modern idiom uses the `positioning` library:
    #
    #   \node[below=GAP of ANCHOR, xshift=DELTA] (id) {...};
    #
    # where DELTA is the difference between the desired x and the anchor's x.
    # Since we don't know anchor x at code-gen time (it depends on LaTeX layout),
    # we use `\pgfpointanchor` inside a `\pgfextra`.
    #
    # ---- Simplest correct solution ----
    # Use `below=GAP of ANCHOR` for depth, plus store each node's desired
    # cross-axis value in a macro, then shift.  This requires knowing anchor x.
    #
    # Given that cross-axis positions ARE known (they're the same fixed grid we
    # already compute), the cleanest approach is:
    #
    #   \node[umlclass] (id) at (CROSS_X, \yof{ANCHOR} - GAP - height/2) {...}
    #
    # But height is unknown at code-gen time.
    #
    # ---- Final chosen approach ----
    # Use TikZ `positioning` with `below=GAP of ANCHOR` and `xshift` expressed
    # as `(DESIRED_X - ANCHOR_X)` – both are known since all cross positions are
    # on a fixed grid.  We compute anchor_x from our own grid.

    # Redo node lines cleanly.
    node_lines = []

    # Pre-compute the cross-axis coordinate for each name.
    cross_axis: dict[str, float] = {}
    for level in sorted(by_level):
        names = by_level[level]
        n = len(names)
        for col_idx, name in enumerate(names):
            cross_offset = (col_idx - (n - 1) / 2.0)
            if direction in {"TB", "BT"}:
                cross_axis[name] = cross_offset * x_gap
            else:
                cross_axis[name] = -cross_offset * y_gap

    for level in sorted(by_level):
        names = by_level[level]
        for name in names:
            node_id = name_to_node[name]
            body = class_node_body(name, classes[name])
            cx = cross_axis[name]

            if level == 0:
                if direction in {"TB", "BT"}:
                    coord = f"({cx:.2f},0)"
                else:
                    coord = f"(0,{cx:.2f})"
                node_lines.append(
                    rf"\node[umlclass] ({node_id}) at {coord} {{{body}}};"
                )
            else:
                my_parents = parents_of.get(name, [])
                if my_parents:
                    prev_level_names = set(by_level.get(level - 1, []))
                    anchor_parent = next(
                        (p for p in my_parents if p in prev_level_names),
                        my_parents[0],
                    )
                else:
                    anchor_parent = by_level[level - 1][0]

                anchor_id = name_to_node[anchor_parent]
                anchor_cx = cross_axis[anchor_parent]

                if direction in {"TB", "BT"}:
                    # xshift moves from anchor's x to our desired x.
                    delta = cx - anchor_cx
                    delta_str = f"{delta:+.2f}cm"
                    node_lines.append(
                        rf"\node[umlclass,below={gap_str} of {anchor_id}.south,"
                        rf"xshift={delta_str}] ({node_id}) {{{body}}};"
                    )
                elif direction == "LR":
                    delta = cx - anchor_cx
                    delta_str = f"{delta:+.2f}cm"
                    node_lines.append(
                        rf"\node[umlclass,right={gap_str} of {anchor_id}.east,"
                        rf"yshift={delta_str}] ({node_id}) {{{body}}};"
                    )
                elif direction == "RL":
                    delta = cx - anchor_cx
                    delta_str = f"{delta:+.2f}cm"
                    node_lines.append(
                        rf"\node[umlclass,left={gap_str} of {anchor_id}.west,"
                        rf"yshift={delta_str}] ({node_id}) {{{body}}};"
                    )

    edge_lines = []
    child_anchor, parent_anchor = inheritance_anchors(direction)
    for child, parent in inherits:
        child_id = name_to_node[child]
        parent_id = name_to_node[parent]
        edge_lines.append(
            rf"\draw[inherit] ({child_id}.{child_anchor}) -- ({parent_id}.{parent_anchor});"
        )

    tikz_nodes = "\n".join(node_lines)
    tikz_edges = "\n".join(edge_lines)

    return rf"""\documentclass[tikz,border=10pt]{{standalone}}
\usepackage[T1]{{fontenc}}
\usepackage{{lmodern}}
\usepackage[table]{{xcolor}}
\usepackage{{tikz}}
\usetikzlibrary{{arrows.meta,positioning}}

\definecolor{{umlheader}}{{RGB}}{{220, 235, 252}}
\renewcommand{{\arraystretch}}{{{row_spacing:.2f}}}

\tikzset{{
  umlclass/.style={{
    draw=none,
    align=left,
    inner sep=0pt,
    outer sep=0pt,
    font=\sffamily\small
  }},
  inherit/.style={{
    -{{Triangle[open,length=3.40mm,width=2.80mm]}},
    line width=0.5pt,
    shorten <=-0.4pt,
    shorten >=-0.4pt
  }}
}}

\begin{{document}}
\begin{{tikzpicture}}
{tikz_nodes}

{tikz_edges}
\end{{tikzpicture}}
\end{{document}}
"""


def default_output_path(input_path: Path) -> Path:
    return input_path.with_suffix(".tex")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert Mermaid classDiagram markdown to a TikZ .tex UML drawing."
    )
    parser.add_argument("input", type=Path, help="Path to Mermaid markdown file (.mmd or .md)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output .tex path (defaults to input filename with .tex extension)",
    )
    parser.add_argument(
        "--arrow-length",
        type=float,
        default=1.5,
        help="Gap between box edges across inheritance levels, in cm (default: 1.5)",
    )
    parser.add_argument(
        "--row-spacing",
        type=float,
        default=1.0,
        help="LaTeX table row spacing multiplier (default: 1.0)",
    )
    args = parser.parse_args()

    input_path: Path = args.input
    output_path: Path = args.output or default_output_path(input_path)
    if args.arrow_length <= 0:
        parser.error("--arrow-length must be positive")
    if args.row_spacing <= 0:
        parser.error("--row-spacing must be positive")

    content = input_path.read_text(encoding="utf-8")
    classes, inherits, direction = parse_mermaid(content)
    tex = generate_tikz(classes, inherits, direction, args.arrow_length, args.row_spacing)
    output_path.write_text(tex, encoding="utf-8")

    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
