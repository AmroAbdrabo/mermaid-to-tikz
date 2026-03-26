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

## Example

<table>
  <tr>
    <th width="50%">Mermaid Markdown</th>
    <th width="50%">Rendered Output</th>
  </tr>
  <tr>
    <td valign="top" width="50%">
      <pre><code>classDiagram
    direction BT

    class MapsApiAdapter {
        + get_place_name(float, float): str*
        + get_travel_distance_and_time(..): tuple[int, timedelta]*
    }

    class GoogleMapsApiAdapter {
        - _api_key : str
        + __init__(str)
        - _request_json(str, dict~[str, str]~): dict$
    }
    <td valign="top" width="50%">
  <img src="https://raw.githubusercontent.com/AmroAbdrabo/mermaid-to-tikz/main/assets/example.png" alt="Rendered Output" style="max-width: 100%;">
</td>
  </tr>
</table>