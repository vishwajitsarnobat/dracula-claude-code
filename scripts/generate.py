#!/usr/bin/env python3
"""Generate Dracula and Alucard themes for Claude Code from the Dracula spec.

The palette in palette.json is copied verbatim from https://draculatheme.com/spec.
Each colour token takes the spec colour that plays the same role in Claude
Code's built-in themes. Most tokens are exact spec values:

  accents     the classic palette (Foreground, Comment, Red, Orange, ...)
  shimmers    the spec's bright ANSI colours, e.g. Red #ff5555 -> #ff6e6e
  surfaces    the spec's UI palette (Background Light, Background Dark, ...)

Three things the spec does not define are derived, deterministically:

  bright orange and bright comment  the spec has no bright variant of either,
              so they take the average lightness step of the six it does have
  diff and message backgrounds      the accent's hue, with its lightness solved
              against a WCAG contrast floor

Usage:  python3 scripts/generate.py [--check]
"""

from __future__ import annotations

import argparse
import colorsys
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
PALETTE = json.loads((HERE / "palette.json").read_text())

# The complete set of colour tokens Claude Code accepts in a custom theme.
# Keys outside this set are silently discarded by the application.
KEYS = [
    "autoAccept", "autoAcceptShimmer", "skill", "bashBorder", "claude",
    "claudeShimmer", "claudeBlue_FOR_SYSTEM_SPINNER",
    "claudeBlueShimmer_FOR_SYSTEM_SPINNER", "permission", "permissionShimmer",
    "planMode", "ide", "promptBorder", "promptBorderShimmer", "text",
    "inverseText", "inactive", "inactiveShimmer", "subtle", "suggestion",
    "remember", "background", "success", "error", "warning", "merged",
    "warningShimmer", "diffAdded", "diffRemoved", "diffAddedDimmed",
    "diffRemovedDimmed", "diffAddedWord", "diffRemovedWord",
    "red_FOR_SUBAGENTS_ONLY", "blue_FOR_SUBAGENTS_ONLY",
    "green_FOR_SUBAGENTS_ONLY", "yellow_FOR_SUBAGENTS_ONLY",
    "purple_FOR_SUBAGENTS_ONLY", "orange_FOR_SUBAGENTS_ONLY",
    "pink_FOR_SUBAGENTS_ONLY", "cyan_FOR_SUBAGENTS_ONLY", "professionalBlue",
    "chromeYellow", "clawd_body", "clawd_background", "userMessageBackground",
    "userMessageBackgroundHover", "composerSidebarBackground", "selectionBg",
    "bashMessageBackgroundColor", "memoryBackgroundColor", "rate_limit_fill",
    "rate_limit_empty", "fastMode", "fastModeShimmer", "effortUltra",
    "briefLabelYou", "briefLabelClaude", "rainbow_red", "rainbow_orange",
    "rainbow_yellow", "rainbow_green", "rainbow_blue", "rainbow_indigo",
    "rainbow_violet", "rainbow_red_shimmer", "rainbow_orange_shimmer",
    "rainbow_yellow_shimmer", "rainbow_green_shimmer", "rainbow_blue_shimmer",
    "rainbow_indigo_shimmer", "rainbow_violet_shimmer",
]

# Which spec colour plays each role. Dracula has no blue: its ANSI palette uses
# Purple for blue and Pink for magenta, and Claude Code's own ANSI themes put
# each token in one of those families, so the same shift carries over here.
# Periwinkle UI (permission, suggestions, the system spinner) becomes Purple and
# violet UI (auto-accept, skills, bash mode) becomes Pink. Sky blues that sit
# closer to Cyan than to Purple (IDE, the "you" label) become Cyan.
#
# `background` is not the screen background. Claude Code uses it as a cyan
# accent for background tasks and several dialog borders, so it must be visible.
ROLES = {
    "text": "foreground", "inverseText": "background",
    "clawd_background": "background",
    "inactive": "comment", "subtle": "comment", "promptBorder": "comment",

    "claude": "orange", "clawd_body": "orange", "briefLabelClaude": "orange",
    "fastMode": "orange",

    "claudeBlue_FOR_SYSTEM_SPINNER": "purple", "permission": "purple",
    "suggestion": "purple", "remember": "purple", "rate_limit_fill": "purple",

    "autoAccept": "pink", "skill": "pink", "bashBorder": "pink",
    "merged": "pink", "effortUltra": "pink",

    "planMode": "cyan", "background": "cyan", "ide": "cyan",
    "professionalBlue": "cyan", "briefLabelYou": "cyan",

    "success": "green", "error": "red", "warning": "yellow",
    "chromeYellow": "yellow",

    "selectionBg": "selection", "rate_limit_empty": "selection",

    # Eight subagent colours from seven accents: blue takes Comment, the one
    # blue in the palette, so no two subagents share a colour.
    "red_FOR_SUBAGENTS_ONLY": "red", "orange_FOR_SUBAGENTS_ONLY": "orange",
    "yellow_FOR_SUBAGENTS_ONLY": "yellow", "green_FOR_SUBAGENTS_ONLY": "green",
    "cyan_FOR_SUBAGENTS_ONLY": "cyan", "blue_FOR_SUBAGENTS_ONLY": "comment",
    "purple_FOR_SUBAGENTS_ONLY": "purple", "pink_FOR_SUBAGENTS_ONLY": "pink",

    "rainbow_red": "red", "rainbow_orange": "orange", "rainbow_yellow": "yellow",
    "rainbow_green": "green", "rainbow_blue": "cyan", "rainbow_indigo": "purple",
    "rainbow_violet": "pink",
}

# Shimmer tokens and the colour whose bright variant each one uses.
SHIMMERS = {
    "claudeShimmer": "orange", "fastModeShimmer": "orange",
    "claudeBlueShimmer_FOR_SYSTEM_SPINNER": "purple",
    "permissionShimmer": "purple", "autoAcceptShimmer": "pink",
    "warningShimmer": "yellow",
    "inactiveShimmer": "comment", "promptBorderShimmer": "comment",
    "rainbow_red_shimmer": "red", "rainbow_orange_shimmer": "orange",
    "rainbow_yellow_shimmer": "yellow", "rainbow_green_shimmer": "green",
    "rainbow_blue_shimmer": "cyan", "rainbow_indigo_shimmer": "purple",
    "rainbow_violet_shimmer": "pink",
}

# Surfaces from the spec's UI palette, ordered by distance from the background
# so the same step means the same thing in both variants. Alucard's UI colours
# are all darker than its background; Dracula's lighter ones sit above it and
# Background Dark below it.
SURFACES = {
    "dracula": {
        "userMessageBackground": "background_light",
        "userMessageBackgroundHover": "background_lighter",
        "composerSidebarBackground": "background_dark",
    },
    "alucard": {
        "userMessageBackground": "background_lighter",
        "userMessageBackgroundHover": "background_light",
        "composerSidebarBackground": "floating",
    },
}

# Derived backgrounds.
#
# `lum` is a target relative luminance, not an HSL lightness, so the green and
# red bands come out equally prominent. `against` names what the band must stay
# distinguishable from: the editor background, or for a word highlight the band
# it is painted inside. Entries resolve in order. On a light theme red needs far
# more saturation than green to look as strong at the same luminance, so the
# light values differ per accent.
BACKGROUNDS = {
    "diffAdded": dict(accent="green", lum_dark=0.055, lum_light=0.50,
                      sat_dark=0.60, sat_light=0.50, sep=1.45, against="background"),
    "diffRemoved": dict(accent="red", lum_dark=0.055, lum_light=0.50,
                        sat_dark=0.60, sat_light=1.20, sep=1.45, against="background"),
    "diffAddedDimmed": dict(accent="green", lum_dark=0.034, lum_light=0.74,
                            sat_dark=0.35, sat_light=0.40, sep=1.15,
                            against="background"),
    "diffRemovedDimmed": dict(accent="red", lum_dark=0.034, lum_light=0.74,
                              sat_dark=0.35, sat_light=0.90, sep=1.15,
                              against="background"),
    "diffAddedWord": dict(accent="green", lum_dark=0.130, lum_light=0.36,
                          sat_dark=0.65, sat_light=0.60, sep=1.25,
                          against="diffAdded"),
    "diffRemovedWord": dict(accent="red", lum_dark=0.130, lum_light=0.36,
                            sat_dark=0.65, sat_light=1.20, sep=1.25,
                            against="diffRemoved"),
    "bashMessageBackgroundColor": dict(accent="pink", lum_dark=0.036,
                                       lum_light=0.80, sat_dark=0.20,
                                       sat_light=0.45, sep=1.10,
                                       against="background"),
    "memoryBackgroundColor": dict(accent="cyan", lum_dark=0.036, lum_light=0.80,
                                  sat_dark=0.20, sat_light=0.45, sep=1.10,
                                  against="background"),
}
TEXT_FLOOR = 4.5

VARIANTS = ["dracula", "alucard"]


def to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(t):
    return "#%02x%02x%02x" % t


def relative_luminance(h):
    out = []
    for c in (c / 255 for c in to_rgb(h)):
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a, b):
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def hls(hex_colour):
    return colorsys.rgb_to_hls(*(c / 255 for c in to_rgb(hex_colour)))


def retone(hex_colour, lightness, sat_scale=1.0):
    """Keep a colour's hue and saturation, move only its lightness."""
    h, _, s = hls(hex_colour)
    rgb = colorsys.hls_to_rgb(h, max(0.0, min(1.0, lightness)),
                              max(0.0, min(1.0, s * sat_scale)))
    return to_hex(tuple(round(c * 255) for c in rgb))


def brights(meta):
    """The spec's bright ANSI colours, plus orange and comment derived with the
    average lightness step the spec itself uses between normal and bright."""
    colours, spec = meta["colors"], meta["ansi_bright"]
    steps = [hls(spec[n])[1] - hls(colours[n])[1] for n in spec]
    step = sum(steps) / len(steps)
    out = dict(spec)
    for name in ("orange", "comment"):
        out[name] = retone(colours[name], hls(colours[name])[1] + step)
    return out


def solve_background(accent, target_lum, sat_scale, sep_floor, body_text,
                     reference, base_colour, away_from=None):
    """Pick the colour closest to `target_lum` that keeps body text readable and
    stays visible against `reference`.

    The whole lightness range is scanned because the two floors pull in opposite
    directions on a light theme. `away_from` pins a word highlight beyond the
    band it sits in, so it always reads as the stronger of the two. If nothing
    meets both floors, separation relaxes first and the result is reported."""
    steps = [i / 400 for i in range(401)]
    bound = relative_luminance(away_from) if away_from else None
    base_lum = relative_luminance(base_colour)
    relaxations = [(TEXT_FLOOR, sep_floor * f) for f in (1, 0.85, 0.70, 0.55)]
    relaxations.append((3.0, 1.05))
    for tf, sf in relaxations:
        feasible = []
        for lightness in steps:
            candidate = retone(accent, lightness, sat_scale)
            lum = relative_luminance(candidate)
            if bound is not None:
                if base_lum < bound and lum <= bound:
                    continue
                if base_lum > bound and lum >= bound:
                    continue
            if (contrast(candidate, body_text) >= tf
                    and contrast(candidate, reference) >= sf):
                feasible.append((abs(lum - target_lum), candidate))
        if feasible:
            _, best = min(feasible, key=lambda x: x[0])
            return best, (tf, sf)
    return retone(accent, 0.5, sat_scale), None


def build(variant):
    meta = PALETTE[variant]
    colours = meta["colors"]
    is_dark = meta["dark"]
    bright = brights(meta)

    theme = {}
    for token, role in ROLES.items():
        theme[token] = colours[role]
    for token, accent in SHIMMERS.items():
        theme[token] = bright[accent]
    for token, surface in SURFACES[variant].items():
        theme[token] = meta["ui"][surface]

    relaxed = {}
    for token, spec in BACKGROUNDS.items():
        against = spec["against"]
        reference = colours["background"] if against == "background" else theme[against]
        colour, used = solve_background(
            accent=colours[spec["accent"]],
            target_lum=spec["lum_dark"] if is_dark else spec["lum_light"],
            sat_scale=spec["sat_dark"] if is_dark else spec["sat_light"],
            sep_floor=spec["sep"],
            body_text=colours["foreground"],
            reference=reference,
            base_colour=colours["background"],
            away_from=None if against == "background" else theme[against])
        theme[token] = colour
        if used is None or used != (TEXT_FLOOR, spec["sep"]):
            relaxed[token] = used

    missing = [k for k in KEYS if k not in theme]
    extra = [k for k in theme if k not in KEYS]
    if missing or extra:
        raise SystemExit(f"{variant}: missing={missing} unexpected={extra}")

    return {
        "name": meta["name"],
        "base": "dark" if is_dark else "light",
        "overrides": {k: theme[k] for k in KEYS},
    }, relaxed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="fail if the committed themes differ from a fresh build")
    args = ap.parse_args()

    out_dir = ROOT / "themes"
    out_dir.mkdir(exist_ok=True)
    stale = []

    for variant in VARIANTS:
        theme, relaxed = build(variant)
        path = out_dir / f"{variant}.json"
        rendered = json.dumps(theme, indent=2) + "\n"
        if args.check:
            if not path.exists() or path.read_text() != rendered:
                stale.append(path.name)
        else:
            path.write_text(rendered)
        o = theme["overrides"]
        base = PALETTE[variant]["colors"]["background"]
        worst_text = min(contrast(o["text"], o[k]) for k in BACKGROUNDS)
        worst_sep = min(
            contrast(base if spec["against"] == "background" else o[spec["against"]],
                     o[k])
            for k, spec in BACKGROUNDS.items())
        print(f"{theme['name']:8} base={theme['base']:5} tokens={len(o)} "
              f"text>={worst_text:.2f}:1  sep>={worst_sep:.2f}:1"
              + (f"  relaxed={sorted(relaxed)}" if relaxed else ""))

    if stale:
        raise SystemExit(f"out of date, re-run generate.py: {', '.join(stale)}")


if __name__ == "__main__":
    sys.exit(main())
