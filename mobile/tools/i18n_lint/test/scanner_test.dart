import 'package:i18n_lint/i18n_lint.dart';
import 'package:test/test.dart';

List<String> _texts(String source) => [
  for (final f in scanSource('a.dart', source)) f.text,
];

void main() {
  group('scanSource finds text a person reads', () {
    test('Text and named arguments', () {
      expect(
        _texts('''
Text('Order placed'),
const Text("Pay now"),
LpgButton(label: 'Confirm delivery', onPressed: go),
LpgBanner(message: 'No signal. Try again.'),
IconButton(tooltip: 'New order'),
'''),
        [
          'Order placed',
          'Pay now',
          'Confirm delivery',
          'No signal. Try again.',
          'New order',
        ],
      );
    });

    test('a Text inside a named argument is counted once', () {
      expect(_texts("ListTile(title: const Text('Profile'))"), ['Profile']);
    });

    test('toasts and section headings', () {
      expect(_texts("LpgFeedback.showToast(context, 'Saved')"), ['Saved']);
      expect(_texts("SectionHeading('Live trips')"), ['Live trips']);
    });

    test('Hindi text counts too', () {
      expect(_texts("Text('फिर कोशिश करें')"), ['फिर कोशिश करें']);
    });
  });

  group('scanSource ignores what is not text', () {
    test('interpolation only, keys, paths and numbers', () {
      expect(
        _texts('''
Text('\$count'),
Text('\${order.id}'),
LpgButton(label: 'order_new'),
x(title: '/orders/new'),
Text('12'),
Text(''),
'''),
        isEmpty,
      );
    });

    test('comments and imports', () {
      expect(
        _texts('''
// Text('commented out')
/// label: 'doc comment'
import 'package:flutter/material.dart';
'''),
        isEmpty,
      );
    });

    test('catalogue lookups are not literals', () {
      expect(_texts('Text(context.strings.app.title)'), isEmpty);
    });
  });

  test('a sentence with interpolation still counts', () {
    expect(_texts("Text('Updated \$time')"), ['Updated \$time']);
  });

  group('baseline', () {
    final base = Baseline({'a.dart': 2, 'b.dart': 1});

    List<Finding> findings(Map<String, int> counts) => [
      for (final e in counts.entries)
        for (var i = 0; i < e.value; i++) Finding(e.key, i + 1, 'x'),
    ];

    test('the same strings pass', () {
      expect(check(findings({'a.dart': 2, 'b.dart': 1}), base).ok, isTrue);
    });

    test('fewer strings pass and are reported as improved', () {
      final v = check(findings({'a.dart': 1, 'b.dart': 1}), base);

      expect(v.ok, isTrue);
      expect(v.improved, {'a.dart': 1});
    });

    test('one more string in a file fails', () {
      final v = check(findings({'a.dart': 3, 'b.dart': 1}), base);

      expect(v.ok, isFalse);
      expect(v.violations.keys, ['a.dart']);
    });

    test('a string in a file that had none fails', () {
      expect(check(findings({'new.dart': 1}), base).violations.keys, [
        'new.dart',
      ]);
    });

    test('round trips through json', () {
      expect(Baseline.parse(base.toJson()).counts, base.counts);
    });
  });
}
