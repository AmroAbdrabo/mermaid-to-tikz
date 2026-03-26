# Mermaid to TikZ UML Converter

`mermaid_to_tikz.py` converts a Mermaid `classDiagram` file into a standalone LaTeX/TikZ document.

## Example

<table>
  <tr>
    <td valign="top">
      <pre><code>classDiagram
    direction BT

    class MapsApiAdapter {
        + get_place_name(float, float): str*
        + get_travel_distance_and_time(tuple~[float, float]~, tuple~[float, float]~, str): tuple~[int, timedelta]~*
    }

    class GoogleMapsApiAdapter {
        - _api_key : str
        + __init__(str)
        - _request_json(str, dict~[str, str]~): dict$
    }</code></pre>
      <div><a href="assets/example.mmd"><code>assets/example.mmd</code></a></div>
    </td>
    <td valign="middle" align="center" width="60">
      <strong>&rarr;</strong>
    </td>
    <td valign="top" align="center">
      <a href="assets/example.pdf">
        <img src="assets/example.pdf" alt="Rendered example PDF" width="420">
      </a>
      <div><a href="assets/example.pdf"><code>assets/example.pdf</code></a></div>
    </td>
  </tr>
</table>

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
