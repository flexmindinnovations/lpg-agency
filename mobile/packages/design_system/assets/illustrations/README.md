# Illustrations

Flat pictures drawn behind stat cards. One SVG per picture, shared by every
app through `LpgIllustration` (see `lib/src/components/lpg_illustration.dart`).
Never put SVG markup or path data in Dart.

## Rules for a new file

- `viewBox="0 0 100 100"`. Keep what matters inside 0 to 90: the picture bleeds
  off the tile's bottom-right corner, so the last ten units can be clipped.
- Use only these four colours. `LpgIllustrationArt` replaces them with opaque
  tints of the tile's tone, so the picture follows the theme and every tone.
  `illustration_assets_test.dart` rejects any other colour.

  | Colour    | Role                                                 |
  | --------- | ---------------------------------------------------- |
  | `#D9D9D9` | soft: the largest, faintest shapes                   |
  | `#B3B3B3` | mid: the main body                                   |
  | `#808080` | strong: small accents (badges, valves, wheels)       |
  | `#FFFFFF` | ground: marks cut out of a shape, in the card colour |

- No `opacity`, `fill-opacity`, `stroke-opacity`, gradients, filters or text.
  Surfaces are solid in this design system, and text over a picture is only
  guaranteed 4.5:1 against the strong tint.
- Keep it simple: plain shapes and short strokes. Add the file to the
  `LpgIllustration` enum, then pass it to a tile.
