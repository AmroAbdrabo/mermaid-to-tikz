# Mermaid to TikZ UML Converter

`mermaid_to_tikz.py` converts a Mermaid `classDiagram` file into a standalone LaTeX/TikZ document.

## Usage

```bash
python3 mermaid_to_tikz.py INPUT_FILE [options]
```

Example:

```bash
python3 mermaid_to_tikz.py location.mmd -o location.tex --arrow-length 1.5 --row-spacing 1.35
```

## Command Line Options

### Positional arguments

- `input`
  Path to the Mermaid markdown file to convert. Supported inputs are files such as `.mmd` or `.md`.

### Optional arguments

- `-o`, `--output`
  Output `.tex` path. If omitted, the script writes to the input filename with the extension changed to `.tex`.

- `--arrow-length`
  Gap between class-box edges across inheritance levels, measured in centimeters.
  Default: `1.5`

- `--row-spacing`
  Table row spacing multiplier used via LaTeX `\arraystretch`.
  Default: `1.0`

## Notes

- `--arrow-length` must be positive.
- `--row-spacing` must be positive.
- The generated `.tex` file uses `tikz`, `xcolor`, `lmodern`, and the TikZ libraries `arrows.meta` and `positioning`.
