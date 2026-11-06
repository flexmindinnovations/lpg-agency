import 'dart:convert';

import 'scanner.dart';

/// Per-file counts of hardcoded strings that existed when the lint was added.
/// A file may keep or reduce its count; it may not go over, and a file not in
/// the baseline may have none. Counts (not line numbers) so editing or moving
/// code around an old string does not trip the lint.
class Baseline {
  Baseline(this.counts);

  factory Baseline.parse(String json) {
    final raw = jsonDecode(json) as Map<String, dynamic>;
    return Baseline({
      for (final e in (raw['files'] as Map<String, dynamic>).entries)
        e.key: e.value as int,
    });
  }

  factory Baseline.fromFindings(List<Finding> findings) {
    final counts = <String, int>{};
    for (final f in findings) {
      counts[f.path] = (counts[f.path] ?? 0) + 1;
    }
    return Baseline(counts);
  }

  final Map<String, int> counts;

  String toJson() {
    final sorted = {for (final k in counts.keys.toList()..sort()) k: counts[k]};
    return '${const JsonEncoder.withIndent('  ').convert({'note': 'Hardcoded user-visible strings that existed when the lint was '
        'added (story 2.1). Counts may only go down. Regenerate with '
        '`dart run bin/check.dart --update` after moving strings into the '
        'catalogues.', 'files': sorted})}\n';
  }
}

/// The result of checking [findings] against a [Baseline].
class Verdict {
  Verdict(this.violations, this.improved);

  /// Files over their allowance, with their findings.
  final Map<String, List<Finding>> violations;

  /// Files that now have fewer strings than the baseline says.
  final Map<String, int> improved;

  bool get ok => violations.isEmpty;
}

Verdict check(List<Finding> findings, Baseline baseline) {
  final byFile = <String, List<Finding>>{};
  for (final f in findings) {
    byFile.putIfAbsent(f.path, () => []).add(f);
  }
  final violations = <String, List<Finding>>{};
  byFile.forEach((path, list) {
    if (list.length > (baseline.counts[path] ?? 0)) violations[path] = list;
  });
  final improved = <String, int>{};
  baseline.counts.forEach((path, allowed) {
    final now = byFile[path]?.length ?? 0;
    if (now < allowed) improved[path] = now;
  });
  return Verdict(violations, improved);
}
