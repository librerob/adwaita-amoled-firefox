# Following Firefox changes

[Latest tracking report](https://github.com/librerob/adwaita-amoled-firefox/issues/5)
· [Run history and manual checks](https://github.com/librerob/adwaita-amoled-firefox/actions/workflows/upstream-watch.yml)

The watch runs every Monday at 08:37 UTC (08:37 UK winter time, 09:37 summer
time). GitHub can delay scheduled jobs. For an immediate check, open the workflow
and choose **Run workflow** on `main`. It also runs when its code or baseline
changes. No personal token or extra secret is needed.

## What matters for this theme

This is a static WebExtension theme. Its compatibility boundary is Firefox's
theme API and native rendering. It does not inject GTK styles or replace Nova's
layout. GTK and libadwaita updates belong to the separate desktop theme's watch.

| Area | Why we watch it |
| --- | --- |
| Firefox theme schema and implementation | New, removed or changed color/property keys and fallback behavior |
| ThemeVariableMap, LightweightThemeConsumer/Manager and browser colors | How theme values become native CSS variables, derived colors and fallback themes |
| Tabs, vertical sidebar, address results, menu and popup styles, design tokens | Changes to outlines, surfaces, opacity, selected/hovered text and Nova tokens |
| MDN theme documentation and compatibility data | Documented changes and version requirements |
| Mozilla Release, Beta and Nightly version metadata | New browser versions that need a compatibility review |
| web-ext releases and AMO's minimum-version registry | Linter changes and submission constraints |

Source checks use Mozilla's Firefox repository and MDN's repositories. Each
repository is resolved to one commit before reading its watched files. Directory
checks include child file and subtree SHAs, so new, removed and nested files are
noticed. An unrelated Firefox commit alone does not produce a source alert.
The complete source list and captured SHAs live in `upstream-watch.json`.

The initial baseline was captured on 6 November 2026. It records a comparison
point, not a claim that every line of upstream code has been audited. The native
checks previously recorded in [validation](../docs/validation.md) remain separate
evidence. A source change or a new version means **review-needed**, not that the
theme is broken. A missing source, changed API format, service outage or
incomplete directory listing is an **error**, never an up-to-date result.

## Testing the browser as well as the source

Every run downloads current Release builds on Linux and Windows, plus current
Beta and Nightly on Linux. It runs the existing native Firefox fixture: six
layout/system appearance combinations, selected-tab outline and label, address
placeholder and selected result text, hovered menu label and shortcut, private
window, and theme removal. Linux uses an isolated display with real popup
screenshots; Windows uses headless checks. Actual installed versions, computed
color reports, logs and screenshots are saved as artifacts for 90 days.

Beta and Nightly failures deserve investigation, but can come from upstream
browser bugs, test-selector changes or download/display infrastructure. They do
not automatically establish a theme defect. The pinned Firefox 159.0.1 checks
continue to provide a repeatable release baseline in the regular Checks workflow.
The watch does not automatically edit colors, minimum versions, releases or the
captured baseline.

## Reading the report

The tracking issue is updated in place after runs on `main`. It links to the
latest run, a per-browser result table, source changes and comparison links.
Workflow summaries and the `upstream-source-report` artifact retain the full
Markdown/JSON source report. Pull requests run the checks but cannot update the
public issue. Only the final report job receives issue-write permission; browser
and source jobs have read-only repository access.

No custom email or repeated issue comments are sent. Issue edits do not
guarantee a notification. Use GitHub's Actions notification preferences for
failures, and check the issue for successful runs that found source changes.
The issue can be bookmarked; the README also links to it.

To review an alert:

1. Read the linked source and comparison. Review theme API behavior and the
   affected component's CSS/tokens; a large comparison may include unrelated work.
2. Inspect the browser reports and screenshots. Reproduce a suspected regression
   before changing the palette. Check selected and hovered text, tab outlines,
   horizontal/vertical tabs, focus, private windows and inactive windows.
3. Keep manual macOS, keyboard/screen-reader, forced-colors and physical OLED
   checks in mind. These workflows do not establish those results or cover
   distro-specific patches and every new browser feature.
4. Record the reviewed versions, evidence and remaining limits in validation
   notes. Then update only the relevant baseline entries and commit them for
   review. Directory entries are GitHub child SHAs; file entries are blob SHAs.
   Set that repository's `baseline_commit` to the reviewed commit for useful
   comparison links. Advance the whole repository baseline together, or split
   its path groups if reviewing them at different commits.

For local development, Python 3.12+ is enough for offline tests:

```sh
python -m unittest discover -s tests -p 'test_upstream_watch.py' -v
python tools/upstream_watch.py
```

The live source check uses public GitHub APIs. Set `GH_TOKEN` for their higher
authenticated rate limit; the token is sent only to `api.github.com`. Reports
default to `artifacts/upstream-watch/`. This maintenance tooling is not included
in the installable theme archive, so adding it requires no new theme release.

If reports stop, check Actions: GitHub can disable scheduled workflows after
60 days without repository activity. Nothing here promises uninterrupted
monitoring or automatically declares future Firefox versions supported.
