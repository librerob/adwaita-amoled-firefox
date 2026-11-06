# Adwaita AMOLED

A black Firefox theme with soft blue accents, based on the default palette of
[Adwaita AMOLED](https://github.com/librerob/adwaita-amoled).

The frame stays black. The current tab has a raised surface and a pale blue
outline. Menus and the address bar use small steps in brightness to keep the
controls distinct. Firefox keeps its own Nova layout, spacing and shapes.

## Try it

This first version is available as source. It has not been signed or listed on
Mozilla Add-ons yet, so the packaged XPI is for temporary testing.

1. Download this repository with **Code → Download ZIP**, then extract it.
2. Open `about:debugging#/runtime/this-firefox` in Firefox 159 or later.
3. Choose **Load Temporary Add-on** and select `theme/manifest.json`.

The theme lasts until Firefox restarts. Switch themes in `about:addons` to remove
it sooner. No profile edits or custom stylesheets are needed.

## Color choices

The palette uses two blues for different jobs. Pale blue is readable on the dark
surfaces; deeper blue gives white text enough contrast in selected menu and
address-bar results. Text selected inside the address field uses pale blue with
black lettering.

| Pair | Contrast |
| --- | ---: |
| Main text on black | 16.83:1 |
| Secondary text on the raised surface | 10.13:1 |
| Pale blue on black | 9.96:1 |
| White on selected blue | 4.89:1 |
| Black on pale blue | 9.96:1 |

These are defined sRGB color pairs. Firefox also derives some colors and uses
the system accent for some controls. The theme does not recolor websites or
extension-owned panels. See [design notes](docs/design.md) for the mapping and
[validation](docs/validation.md) for coverage and remaining checks.

## Development

Python 3.12 or later is enough for generation, palette checks and packaging:

```sh
python tools/theme.py
python -m unittest discover -s tests -v
python tools/theme.py --check --package
```

Archives are written to `dist/`. They contain only the manifest and icon.
`palette.json` is the color source; `theme/manifest.json` is generated from it.

## Credits

The black surfaces and blue accent roles come from
[Adwaita AMOLED](https://github.com/librerob/adwaita-amoled). The Firefox mapping,
icon and tooling live here. Firefox and Nova are Mozilla projects; this theme
is independent of Mozilla.

GPL-3.0-or-later. See [LICENSE](LICENSE).

