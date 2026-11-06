///
/// Generated file. Do not edit.
///
// coverage:ignore-file
// ignore_for_file: type=lint, unused_import
// dart format off

import 'package:flutter/widgets.dart';
import 'package:intl/intl.dart';
import 'package:slang/generated.dart';
import 'strings.g.dart';

// Path: <root>
class LpgStringsHi extends LpgStrings with BaseTranslations<LpgLocale, LpgStrings> {
	/// You can call this constructor and build your own translation instance of this locale.
	/// Constructing via the enum [LpgLocale.build] is preferred.
	LpgStringsHi({Map<String, Node>? overrides, PluralResolver? cardinalResolver, PluralResolver? ordinalResolver, TranslationMetadata<LpgLocale, LpgStrings>? meta})
		: assert(overrides == null, 'Set "translation_overrides: true" in order to enable this feature.'),
		  _meta = meta ?? TranslationMetadata(
		    locale: LpgLocale.hi,
		    overrides: overrides ?? {},
		    cardinalResolver: cardinalResolver,
		    ordinalResolver: ordinalResolver,
		  ),
		  super(cardinalResolver: cardinalResolver, ordinalResolver: ordinalResolver) {
		_meta.setFlatMapFunction(_flatMapFunction);
	}

	/// Metadata for the translations of <hi>.
	final TranslationMetadata<LpgLocale, LpgStrings> _meta;
	@override TranslationMetadata<LpgLocale, LpgStrings> get $meta => _meta;

	/// Access flat map
	@override dynamic operator[](String key) => _meta.getTranslation(key) ?? super[key];

	late final LpgStringsHi _root = this; // ignore: unused_field

	@override 
	LpgStringsHi $copyWith({TranslationMetadata<LpgLocale, LpgStrings>? meta}) => LpgStringsHi(meta: meta ?? this.$meta);

	// Translations
	@override late final LpgStrings$common$hi common = LpgStrings$common$hi._(_root);
	@override late final LpgStrings$async$hi async = LpgStrings$async$hi._(_root);
	@override late final LpgStrings$stock$hi stock = LpgStrings$stock$hi._(_root);
	@override late final LpgStrings$appearance$hi appearance = LpgStrings$appearance$hi._(_root);
}

// Path: common
class LpgStrings$common$hi extends LpgStrings$common$en {
	LpgStrings$common$hi._(LpgStringsHi root) : this._root = root, super.internal(root);

	final LpgStringsHi _root; // ignore: unused_field

	// Translations
	@override String get retry => 'फिर कोशिश करें';
	@override String get cancel => 'रद्द करें';
}

// Path: async
class LpgStrings$async$hi extends LpgStrings$async$en {
	LpgStrings$async$hi._(LpgStringsHi root) : this._root = root, super.internal(root);

	final LpgStringsHi _root; // ignore: unused_field

	// Translations
	@override String get errorTitle => 'कुछ गड़बड़ हो गई';
	@override String get updating => 'अपडेट हो रहा है…';
	@override String lastUpdated({required String time}) => '${time} को अपडेट किया';
}

// Path: stock
class LpgStrings$stock$hi extends LpgStrings$stock$en {
	LpgStrings$stock$hi._(LpgStringsHi root) : this._root = root, super.internal(root);

	final LpgStringsHi _root; // ignore: unused_field

	// Translations
	@override String cylinders({required num n}) => (_root.$meta.cardinalResolver ?? PluralResolvers.cardinal('hi'))(n,
		one: '${n} सिलेंडर',
		other: '${n} सिलेंडर',
	);
}

// Path: appearance
class LpgStrings$appearance$hi extends LpgStrings$appearance$en {
	LpgStrings$appearance$hi._(LpgStringsHi root) : this._root = root, super.internal(root);

	final LpgStringsHi _root; // ignore: unused_field

	// Translations
	@override String get title => 'दिखावट';
	@override String get hint => 'फ़ोन के अनुसार चलाएँ, या हमेशा लाइट या डार्क रखें।';
	@override String get system => 'फ़ोन के अनुसार';
	@override String get light => 'लाइट';
	@override String get dark => 'डार्क';
}

/// The flat map containing all translations for locale <hi>.
/// Only for edge cases! For simple maps, use the map function of this library.
///
/// The Dart AOT compiler has issues with very large switch statements,
/// so the map is split into smaller functions (512 entries each).
extension on LpgStringsHi {
	dynamic _flatMapFunction(String path) {
		return switch (path) {
			'common.retry' => 'फिर कोशिश करें',
			'common.cancel' => 'रद्द करें',
			'async.errorTitle' => 'कुछ गड़बड़ हो गई',
			'async.updating' => 'अपडेट हो रहा है…',
			'async.lastUpdated' => ({required String time}) => '${time} को अपडेट किया',
			'stock.cylinders' => ({required num n}) => (_root.$meta.cardinalResolver ?? PluralResolvers.cardinal('hi'))(n, one: '${n} सिलेंडर', other: '${n} सिलेंडर', ), 
			'appearance.title' => 'दिखावट',
			'appearance.hint' => 'फ़ोन के अनुसार चलाएँ, या हमेशा लाइट या डार्क रखें।',
			'appearance.system' => 'फ़ोन के अनुसार',
			'appearance.light' => 'लाइट',
			'appearance.dark' => 'डार्क',
			_ => null,
		};
	}
}
