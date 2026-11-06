/// One string literal that looks like text a person reads.
class Finding {
  const Finding(this.path, this.line, this.text);

  final String path;
  final int line;
  final String text;

  @override
  String toString() => "$path:$line  '$text'";
}

/// Widget and parameter names whose string argument is shown to a person.
/// Deliberately a short, conservative list: the lint is a ratchet against new
/// strings, not a complete audit (the migration stories move the rest).
const _namedArguments = [
  'title',
  'label',
  'message',
  'hint',
  'hintText',
  'labelText',
  'helperText',
  'errorText',
  'tooltip',
  'semanticLabel',
  'subtitle',
  'actionLabel',
  'retryLabel',
  'description',
  'buttonLabel',
];

const _positionalWidgets = ['Text', 'SectionHeading', 'LpgSectionHeader'];

final _literal = r'''(?:r?'((?:\\.|[^'\\])*)'|r?"((?:\\.|[^"\\])*)")''';

final List<RegExp> _patterns = [
  // Text('Hello'), const Text("Hello"), SectionHeading('Live trips')
  RegExp(r'\b(?:' + _positionalWidgets.join('|') + r')\(\s*' + _literal),
  // title: 'Hello', label: const Text('Hello')
  RegExp(
    r'\b(?:' +
        _namedArguments.join('|') +
        r')\s*:\s*(?:const\s+)?(?:Text\(\s*)?' +
        _literal,
  ),
  // LpgFeedback.showToast(context, 'Saved')
  RegExp(r'\bshowToast\(\s*[^,()]+,\s*' + _literal),
];

final _hasLetter = RegExp(r'[A-Za-zऀ-ॿ]');
final _identifierLike = RegExp(r'^[a-z][a-z0-9_]*([.\-/][a-z0-9_]+)*$');

/// Whether [text] reads like words, not a key, a path or a bare interpolation.
bool looksLikeUserText(String text) {
  final t = text.trim();
  if (t.isEmpty || !_hasLetter.hasMatch(t)) return false;
  if (RegExp(r'^\$\{?[A-Za-z_][A-Za-z0-9_.]*\}?$').hasMatch(t)) return false;
  if (_identifierLike.hasMatch(t) && !t.contains(' ')) return false;
  if (t.startsWith('/') || t.startsWith('package:') || t.startsWith('http')) {
    return false;
  }
  return true;
}

/// Hardcoded user-visible strings in [source] (a Dart file at [path]).
List<Finding> scanSource(String path, String source) {
  final found = <Finding>[];
  final seen = <int>{};
  final lines = source.split('\n');
  for (var i = 0; i < lines.length; i++) {
    final line = lines[i];
    final trimmed = line.trimLeft();
    if (trimmed.startsWith('//') || trimmed.startsWith('import ')) continue;
    for (final pattern in _patterns) {
      for (final match in pattern.allMatches(line)) {
        final text = match.group(1) ?? match.group(2) ?? '';
        // The same literal can match two patterns (`label: Text('x')`).
        final key = i * 100000 + match.end;
        if (!looksLikeUserText(text) || !seen.add(key)) continue;
        found.add(Finding(path, i + 1, text));
      }
    }
  }
  return found;
}
