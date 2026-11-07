/// Design system for the LPG mobile apps: generated tokens, the Flutter
/// theme built from them, icons, motion and shared widgets.
///
/// Tokens are generated from `design-tokens/tokens.json` by
/// `scripts/generate-tokens.mjs` — the same source that produces the web CSS
/// variables. Never hand-edit `src/tokens.dart`. See this package's README
/// for how screens are expected to use it and how to rebrand.
library;

export 'src/async/lpg_async_view.dart';
export 'src/async/lpg_error_copy.dart';
export 'src/async/quiet_when.dart';
export 'src/tokens.dart';
export 'src/layout.dart';
export 'src/surface.dart';
export 'src/theme.dart';
export 'src/theme_engine.dart';
export 'src/tone.dart';
export 'src/icons.dart';
export 'src/motion.dart';
export 'src/haptics.dart';
export 'src/format.dart';
export 'src/i18n/lpg_locale.dart';
export 'src/i18n/lpg_strings_delegate.dart';
export 'src/i18n/strings.g.dart' show LpgLocale, LpgStrings;
export 'src/components/components.dart';
