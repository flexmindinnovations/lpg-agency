// Fails when a mobile source file has more hardcoded user-visible strings than
// the committed baseline allows (story 2.1).
//
//   dart run bin/check.dart --root ../..           # check (CI)
//   dart run bin/check.dart --root ../.. --update  # lower the baseline
import 'dart:io';

import 'package:i18n_lint/i18n_lint.dart';

const _scanned = [
  'apps/admin_app/lib',
  'apps/customer_app/lib',
  'apps/driver_app/lib',
  'packages/design_system/lib',
];

/// The component gallery is a developer-only specimen page (sample copy that
/// no user sees), so its text is not held to the catalogue rule.
bool _skip(String path) =>
    path.endsWith('.g.dart') ||
    path.contains('/i18n/') ||
    path.contains('/gallery/');

Future<void> main(List<String> args) async {
  final update = args.contains('--update');
  final rootIndex = args.indexOf('--root');
  final root = Directory(rootIndex >= 0 ? args[rootIndex + 1] : '.').absolute;
  final baselineFile = File(
    '${Directory.current.path}/hardcoded_strings_baseline.json',
  );

  final findings = <Finding>[];
  for (final dir in _scanned) {
    final d = Directory('${root.path}/$dir');
    if (!d.existsSync()) continue;
    final files = d
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'));
    for (final file in files) {
      final rel = file.path.substring(root.path.length + 1);
      if (_skip(rel)) continue;
      findings.addAll(scanSource(rel, file.readAsStringSync()));
    }
  }
  findings.sort(
    (a, b) =>
        a.path != b.path ? a.path.compareTo(b.path) : a.line.compareTo(b.line),
  );

  if (update) {
    final next = Baseline.fromFindings(findings);
    if (baselineFile.existsSync()) {
      final old = Baseline.parse(baselineFile.readAsStringSync());
      final raised = [
        for (final e in next.counts.entries)
          if (e.value > (old.counts[e.key] ?? 0)) e.key,
      ];
      if (raised.isNotEmpty && !args.contains('--allow-increase')) {
        stderr.writeln(
          'Refusing to raise the baseline for:\n  ${raised.join('\n  ')}\n'
          'Move those strings into the catalogue instead.',
        );
        exit(1);
      }
    }
    baselineFile.writeAsStringSync(next.toJson());
    stdout.writeln(
      'Baseline written: ${findings.length} strings in '
      '${next.counts.length} files.',
    );
    return;
  }

  final baseline = Baseline.parse(baselineFile.readAsStringSync());
  final verdict = check(findings, baseline);
  if (verdict.ok) {
    final total = findings.length;
    stdout.writeln('OK: $total hardcoded strings, none new.');
    if (verdict.improved.isNotEmpty) {
      stdout.writeln(
        '${verdict.improved.length} file(s) are below the baseline;'
        ' run with --update to lower it.',
      );
    }
    return;
  }
  stderr.writeln(
    'New hardcoded user-visible strings (use the string catalogue, '
    'see planning/features/61-mobile-ui-revamp/i18n-howto.md):',
  );
  verdict.violations.forEach((path, list) {
    stderr.writeln(
      '\n$path  (allowed ${baseline.counts[path] ?? 0}, found ${list.length})',
    );
    for (final f in list) {
      stderr.writeln('  line ${f.line}: \'${f.text}\'');
    }
  });
  exit(1);
}
