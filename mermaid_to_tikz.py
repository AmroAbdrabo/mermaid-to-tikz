#!/usr/bin/env python3
"""Convert a Mermaid class diagram (.mmd) to a TikZ UML-like drawing."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict, deque
from pathlib import Path


CLASS_NAME_RE = r"[A-Za-z0-9_.$]+(?:\*)?"
CLASS_RE = re.compile(rf"^\s*class\s+({CLASS_NAME_RE})\s*(\{{)?\s*$")
INHERIT_RE = re.compile(rf"^\s*({CLASS_NAME_RE})\s+--\|>\s+({CLASS_NAME_RE})\s*$")
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


def format_class_name(name: str) -> str:
    # Strip trailing * — it marks the class as abstract (rendered in italics),
    # but is not part of the display name.
    if name.endswith("*"):
        return rf"\textit{{{latex_escape(name[:-1].rstrip())}}}"
    return latex_escape(name)


def prefixed_member(member: str, symbol: str) -> str:
    return rf"{symbol} {format_member(member)}"


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


def canonical_name(name: str) -> str:
    """Return the canonical class name, stripping any trailing '*'.

    In Mermaid a trailing '*' on the class name marks it as abstract.
    The same class may be referenced in inheritance lines *without* the '*',
    so we normalise to the bare name when building the class registry and
    inheritance graph.
    """
    return name.rstrip("*")


def parse_mermaid(content: str):
    text = strip_mermaid_fence(content)
    # classes maps canonical_name -> (members_list, is_abstract)
    classes: dict[str, list[str]] = {}
    abstract: set[str] = set()
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
            raw_name = m_class.group(1)
            name = canonical_name(raw_name)
            if raw_name.endswith("*"):
                abstract.add(name)
            classes.setdefault(name, [])
            if m_class.group(2) == "{":
                in_class = name
            continue

        m_inherit = INHERIT_RE.match(stripped)
        if m_inherit:
            child = canonical_name(m_inherit.group(1))
            parent = canonical_name(m_inherit.group(2))
            inherits.append((child, parent))
            classes.setdefault(child, [])
            classes.setdefault(parent, [])

    if not classes:
        raise ValueError("No classes found in Mermaid input.")

    return classes, abstract, inherits, direction


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


def class_node_body(name: str, members: list[str], is_abstract: bool) -> str:
    attrs = [m for m in members if "(" not in m]
    methods = [m for m in members if "(" in m]
    # Use italic class name for abstract classes
    display_name = rf"\textit{{{latex_escape(name)}}}" if is_abstract else latex_escape(name)
    lines = [
        r"\begin{tabular}{|l|}",
        r"\hline",
        rf"\rowcolor{{umlheader}}\multicolumn{{1}}{{|c|}}{{\customC\ \textbf{{{display_name}}}}} \\",
        r"\hline",
    ]

    if attrs:
        lines.extend(rf"{prefixed_member(attr, r'\customF\ ')} \\" for attr in attrs)

    if attrs and methods:
        lines.append(r"\hline")

    if methods:
        lines.extend(rf"{prefixed_member(method, r'\customM\ ')} \\" for method in methods)

    if attrs or methods:
        lines.append(r"\hline")

    lines.append(r"\end{tabular}")
    return "\n".join(lines)


def inheritance_anchors(direction: str) -> tuple[str, str]:
    """Return (child_anchor, parent_anchor) for drawing inheritance arrows.

    For TB: children are below parents  → arrow goes child.north → parent.south
    For BT: children are above parents  → arrow goes child.south → parent.north
    For LR: children are right of parents → arrow goes child.west → parent.east
    For RL: children are left of parents  → arrow goes child.east → parent.west
    """
    if direction in {"TB", "BT"}:
        # Both TB and BT place superclasses at the top and children below.
        # Arrow runs from child.north up to parent.south.
        return "north", "south"
    if direction == "LR":
        return "west", "east"
    if direction == "RL":
        return "east", "west"
    return "north", "south"


def generate_tikz(
    classes: dict[str, list[str]],
    abstract: set[str],
    inherits: list[tuple[str, str]],
    direction: str,
    arrow_length: float,
    row_spacing: float,
) -> str:
    depths = class_depths(classes, inherits)

    # Raw depths naturally put superclasses (roots) at depth 0 and children
    # at higher depths.  We always want superclasses at the TOP of the diagram
    # (placed first at y=0) with children below — for every direction.
    # render_level == depth for all directions; no inversion needed.
    by_level: dict[int, list[str]] = defaultdict(list)
    for name, d in depths.items():
        by_level[d].append(name)

    for level in by_level:
        by_level[level].sort()

    x_gap = 7.0
    y_gap = 5.0

    name_to_node = {name: f"c{i}" for i, name in enumerate(sorted(classes))}

    parents_of: dict[str, list[str]] = defaultdict(list)
    for child, parent in inherits:
        parents_of[child].append(parent)

    gap_str = f"{arrow_length:.2f}cm"

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

    node_lines: list[str] = []

    for level in sorted(by_level):
        names = by_level[level]
        for name in names:
            node_id = name_to_node[name]
            body = class_node_body(name, classes[name], name in abstract)
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
                my_layout_parents = parents_of.get(name, [])
                if my_layout_parents:
                    prev_level_names = set(by_level.get(level - 1, []))
                    anchor_parent = next(
                        (p for p in my_layout_parents if p in prev_level_names),
                        my_layout_parents[0],
                    )
                else:
                    anchor_parent = by_level[level - 1][0]

                anchor_id = name_to_node[anchor_parent]
                anchor_cx = cross_axis[anchor_parent]
                delta = cx - anchor_cx
                delta_str = f"{delta:+.2f}cm"

                # BT is now treated identically to TB in layout terms: both
                # place higher render_level nodes *below* level-0 nodes.
                if direction in {"TB", "BT"}:
                    node_lines.append(
                        rf"\node[umlclass,below={gap_str} of {anchor_id}.south,"
                        rf"xshift={delta_str}] ({node_id}) {{{body}}};"
                    )
                elif direction == "LR":
                    node_lines.append(
                        rf"\node[umlclass,right={gap_str} of {anchor_id}.east,"
                        rf"yshift={delta_str}] ({node_id}) {{{body}}};"
                    )
                elif direction == "RL":
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

\newcommand{{\customC}}{{%
    \tikz[baseline=(char.base)]{{
        \node[
            shape=circle,
            draw=blue!80!black,
            fill=blue!15,
            text=blue,
            thick,
            inner sep=1pt,
            font=\sffamily\bfseries\footnotesize
        ] (char) {{C}};
    }}%
}}

\newcommand{{\customF}}{{%
    \tikz[baseline=(char.base)]{{
        \node[
            shape=circle,
            draw=orange!80!black,
            fill=orange!15,
            text=orange,
            thick,
            inner sep=1pt,
            font=\sffamily\bfseries\footnotesize
        ] (char) {{f}};
    }}%
}}

\newcommand{{\customM}}{{%
    \tikz[baseline=(char.base)]{{
        \node[
            shape=circle,
            draw=red!80!black,
            fill=red!15,
            text=red,
            thick,
            inner sep=1pt,
            font=\sffamily\bfseries\footnotesize
        ] (char) {{m}};
    }}%
}}

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
    classes, abstract, inherits, direction = parse_mermaid(content)
    tex = generate_tikz(classes, abstract, inherits, direction, args.arrow_length, args.row_spacing)
    output_path.write_text(tex, encoding="utf-8")

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
