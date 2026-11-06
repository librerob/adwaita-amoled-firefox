# Design notes

The large surfaces are black, with a short neutral ramp for controls. Blue is
reserved for selection, focus and attention. Ordinary labels stay neutral.

## Tabs

Inactive tabs use `#c0c0c0` labels on black. The current tab has `#e6e6e6` text on
`#141414`, with a `#8ab4f8` native line/outline. Its raised background is subtle;
the outline supplies the stronger identifying cue. The native tab shape makes
selection visible without relying on blue hue alone.

The same colors are used for horizontal and vertical tabs. The inactive window
keeps the black frame and readable labels. Density, tab groups, container
markers, audio icons and private-window indicators remain Firefox's own.

## Surfaces and boundaries

| Role | Color | Use |
| --- | --- | --- |
| Background | `#000000` | Frame, toolbar, sidebar, New Tab |
| Surface | `#0f0f0f` | Address field and New Tab cards |
| Raised | `#141414` | Current tab, focused address field, menus |
| Foreground | `#e6e6e6` | Ordinary labels |
| Secondary | `#c0c0c0` | Inactive tabs and toolbar icons |
| Accent | `#8ab4f8` | Tab outline, themeable focus border, attention icons |
| Selection | `#2d6be0` | Menu/address-result selection with white labels |
| Control border | `#686868` | Address-field boundary |
| Separator | `#2a2a2a` | Decorative divisions |

The field border is quieter than the desktop theme's `#808080`, while exceeding
3:1 against both its idle and focused surfaces. Decorative separators are not
used as the only means of identifying a control or selected state.

Hover and pressed backgrounds use white at 8% and 12%. Their opacity lets the
same paint work over the frame and raised tab. The tests composite both over
each authored surface, then check primary/secondary labels at 7:1 and blue
indicators at 3:1. They also test the opaque selection pairs separately.

The selected blue fill with white text reaches 4.89:1. It is not a 7:1 pair.
Changing its text to the ordinary softened foreground would drop below 4.5:1,
so the selected foreground is explicitly white. Pale-blue text selection has
an explicitly black foreground for the same reason.

## Firefox boundaries

The theme uses a static manifest with no permissions, scripts, remote assets,
experimental theme keys or profile CSS. It requests a dark UI/content scheme;
websites can respond to that preference, and user overrides still apply.

Nova does not expose every paint through the theme API. Some accents follow
the operating system. Focus/link colors, redesigned sidebar highlights and
loading indicators may remain Firefox-controlled. `popup_text` styles panel
text; address results use the field text properties. `ntp_text` does not style
Nova's New Tab search box.

Inactive legacy properties are omitted. There is no background image or
gradient to tile down the vertical sidebar. No rules move or resize controls.

## References

- [Adwaita AMOLED palette](https://github.com/librerob/adwaita-amoled/blob/main/palette/colors.json)
- [Nova theme migration](https://blog.mozilla.org/addons/2026/09/29/nova-is-here-what-changes-for-your-firefox-theme/)
- [Firefox theme reference](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/theme)
- [Text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
- [Non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)

