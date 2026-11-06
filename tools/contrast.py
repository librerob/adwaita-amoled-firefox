"""Contrast arithmetic for authored colors and resolved Firefox samples."""

import re


def rgba(value):
    if value.startswith("#"):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)) + (1.0,)
    if value == "transparent":
        return (0, 0, 0, 0.0)
    values = [float(v) for v in re.findall(r"[\d.]+", value)]
    if len(values) not in (3, 4):
        raise ValueError(f"Unsupported color: {value}")
    return tuple(values[:3]) + ((values[3] if len(values) == 4 else 1.0),)


def over(foreground, background):
    fg = rgba(foreground) if isinstance(foreground, str) else foreground
    bg = rgba(background) if isinstance(background, str) else background
    assert bg[3] == 1, "Resolve the base surface first"
    return tuple(fg[i] * fg[3] + bg[i] * (1 - fg[3]) for i in range(3)) + (1.0,)


def luminance(color):
    rgb = rgba(color) if isinstance(color, str) else color
    assert rgb[3] == 1, "Composite translucent colors before measuring"
    values = [v / 255 for v in rgb[:3]]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def ratio(foreground, background):
    a, b = sorted((luminance(foreground), luminance(background)))
    return (b + 0.05) / (a + 0.05)

