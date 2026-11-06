# Validation

## Automated checks

The palette suite checks generated output, paired selections, identifying
colors, composited button states, package contents and reproducibility. Its
reference cases include deliberately unsuitable text/fill combinations so an
accidental foreground substitution cannot silently pass.

GitHub Actions also lints the manifest and runs the packaged theme in isolated
Firefox 159.0.1 profiles on Windows and Linux. The native test is in
`tests/firefox_ui.py`; its reports and screenshots are uploaded as workflow
artifacts. A green workflow, rather than this description, records a completed
run.

The browser fixture explicitly enables Nova in its temporary profile. It checks
horizontal tabs, vertical tabs and vertical compact density with simulated
light/dark system appearance. It exercises address-field focus, the main menu,
a private window, and removal. It records computed browser-chrome colors and
measures the selected-tab label against its resolved background.

The fixture uses Firefox's Marionette protocol and system access only in the
throwaway test process. The distributed theme contains neither. No daily
profile is opened or modified.

## Remaining manual checks

- Actual OLED behavior at different brightness levels and ambient lighting.
- macOS and additional Linux desktop environments.
- Windows contrast themes, enlarged system text, keyboard-only navigation and
  screen readers.
- Hover-expanded sidebar, sidebar panels, container/group markers, tab attention
  dots, tooltips, notification panels, and every address-result subtype.
- Browser-derived muted text and compound states beyond the recorded samples.

Color arithmetic is not a guarantee of individual comfort or whole-browser
accessibility. Artwork, favicons, website content and extension-owned surfaces
can supply their own colors.

## Reproduce

```sh
python tools/theme.py --check
python -m unittest discover -s tests -v
python tools/theme.py --check --package
python tests/firefox_ui.py --firefox /path/to/firefox
```

The native run writes `artifacts/firefox/report.json`, screenshots and a Firefox
log. It needs an installed Firefox binary and an environment that permits a
local Marionette connection. It creates and deletes its own temporary profile.

