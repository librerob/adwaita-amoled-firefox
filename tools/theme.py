"""Generate the Firefox manifest from the small, shared palette."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.1"
THEME_ID = "adwaita-amoled-firefox@librerob"

# Keep text, selection fills and identifying borders as separate roles.
ROLES = {
    "frame": "background", "frame_inactive": "background",
    "toolbar": "background", "toolbar_text": "foreground",
    "tab_background_text": "secondary", "tab_selected": "raised",
    "tab_text": "foreground", "tab_line": "accent",
    "icons": "secondary", "icons_attention": "accent",
    "toolbar_field": "surface", "toolbar_field_text": "foreground",
    "toolbar_field_border": "control_border",
    "toolbar_field_focus": "raised", "toolbar_field_text_focus": "foreground",
    "toolbar_field_border_focus": "accent",
    "toolbar_field_highlight": "accent",
    "toolbar_field_highlight_text": "on_accent",
    "popup": "raised", "popup_text": "foreground", "popup_border": "separator",
    "popup_highlight": "selection", "popup_highlight_text": "on_selection",
    "sidebar": "background", "sidebar_text": "foreground", "sidebar_border": "separator",
    "ntp_background": "background", "ntp_card_background": "surface", "ntp_text": "foreground",
    "button_background_hover": "hover", "button_background_active": "pressed",
    "toolbar_bottom_separator": "separator", "toolbar_vertical_separator": "separator",
}


def manifest():
    palette = json.loads((ROOT / "palette.json").read_text())
    colors = {key: palette[role] for key, role in ROLES.items()}
    colors["toolbar_top_separator"] = "rgba(0, 0, 0, 0)"
    return {
        "manifest_version": 3,
        "name": "Adwaita AMOLED",
        "version": VERSION,
        "description": "True black, soft blue accents, and Firefox's native Nova design.",
        "author": "librerob",
        "homepage_url": "https://github.com/librerob/adwaita-amoled-firefox",
        "browser_specific_settings": {"gecko": {
            "id": THEME_ID, "strict_min_version": "159.0"
        }},
        "icons": {"48": "icon.svg", "96": "icon.svg"},
        "theme": {"colors": colors, "properties": {
            "color_scheme": "dark", "content_color_scheme": "dark"
        }},
    }


def rendered():
    return json.dumps(manifest(), indent=2) + "\n"


def archive_bytes():
    expected = rendered()
    actual = (ROOT / "theme/manifest.json").read_text()
    if actual != expected:
        raise SystemExit("Manifest is stale. Run python tools/theme.py first.")
    # Fixed metadata makes locally and CI-built archives byte-for-byte comparable.
    payloads = {"manifest.json": expected.encode(), "icon.svg": (ROOT / "theme/icon.svg").read_bytes(), "LICENSE": (ROOT / "LICENSE").read_bytes()}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for filename, data in sorted(payloads.items()):
            entry = zipfile.ZipInfo(filename, (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    with zipfile.ZipFile(io.BytesIO(output.getvalue())) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(payloads)
    return output.getvalue()


def package(destination=None):
    data = archive_bytes()
    destination = Path(destination) if destination else ROOT / "dist"
    destination.mkdir(parents=True, exist_ok=True)
    name = f"adwaita-amoled-firefox-{VERSION}"
    for suffix in ("zip", "xpi"):
        (destination / f"{name}.{suffix}").write_bytes(data)
    sums = "".join(f"{hashlib.sha256((destination / f'{name}.{suffix}').read_bytes()).hexdigest()}  {name}.{suffix}\n" for suffix in ("zip", "xpi"))
    (destination / "SHA256SUMS").write_text(sums, encoding="utf-8", newline="\n")
    return destination / f"{name}.xpi"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--package", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    target = ROOT / "theme/manifest.json"
    if args.check:
        if not target.exists() or target.read_text() != rendered():
            raise SystemExit("Manifest is stale. Run python tools/theme.py.")
        print("Manifest matches palette.")
    else:
        target.write_text(rendered(), encoding="utf-8", newline="\n")
    if args.package:
        print(package(args.output))

