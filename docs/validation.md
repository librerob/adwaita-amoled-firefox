# Validation

## Current coverage

The offline suite has 16 tests covering palette roles, compound states,
packaging, byte-exact UTF-8/LF generation, and AMO retry/error handling.
The live AMO registry check is a separate CI job. It makes at most three
requests with ten-second timeouts and short backoff delays. An unavailable
service exits with status 2; a rejected minimum version exits with status 1.
Neither an outage nor a cached result is treated as successful validation.

The native fixture also checks the selected-tab outline's color, width and
contrast in every layout. It samples the computed address placeholder,
selected history-result text, and hovered menu labels/shortcut hints, including
opacity and their composed backgrounds. Menu hover is exercised with Firefox's
pseudo-class test API; this checks native paint rather than pointer navigation.

## Earlier validation records

Version 0.1.1 corrects the submission minimum from `159.0.1` to `159.0`.
AMO's application-version registry includes `159.0` but not the patch release.
The upload form checks that registry separately from the lint report. CI now
runs `python tools/check_amo.py` to check this server-side constraint too.

On 6 November 2026, [the validation run](https://github.com/librerob/adwaita-amoled-firefox/actions/runs/42244907800)
passed all eight palette/package tests, manifest lint with warnings treated as
errors, and native Firefox 159.0.1 checks on Windows and Linux. Each browser run
covered six layout/system-appearance combinations and the additional states
described below. The committed previews were captured by that run.

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

Preview captures show browser chrome only. The red remote-control cue is omitted
just while drawing the two `preview-*` images, then restored. It is an automation
indicator rather than part of the theme. Full workflow captures retain it, and
color samples are taken with the cue present. The package contains no such code.

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

