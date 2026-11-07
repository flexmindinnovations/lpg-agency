///
/// Generated file. Do not edit.
///
// coverage:ignore-file
// ignore_for_file: type=lint, unused_import
// dart format off

part of 'strings.g.dart';

// Path: <root>
typedef LpgStringsEn = LpgStrings; // ignore: unused_element
class LpgStrings with BaseTranslations<LpgLocale, LpgStrings> {
	/// You can call this constructor and build your own translation instance of this locale.
	/// Constructing via the enum [LpgLocale.build] is preferred.
	LpgStrings({Map<String, Node>? overrides, PluralResolver? cardinalResolver, PluralResolver? ordinalResolver, TranslationMetadata<LpgLocale, LpgStrings>? meta})
		: assert(overrides == null, 'Set "translation_overrides: true" in order to enable this feature.'),
		  _meta = meta ?? TranslationMetadata(
		    locale: LpgLocale.en,
		    overrides: overrides ?? {},
		    cardinalResolver: cardinalResolver,
		    ordinalResolver: ordinalResolver,
		  ) {
		_meta.setFlatMapFunction(_flatMapFunction);
	}

	/// Metadata for the translations of <en>.
	final TranslationMetadata<LpgLocale, LpgStrings> _meta;
	@override TranslationMetadata<LpgLocale, LpgStrings> get $meta => _meta;

	/// Access flat map
	dynamic operator[](String key) => _meta.getTranslation(key);

	late final LpgStrings _root = this; // ignore: unused_field

	LpgStrings $copyWith({TranslationMetadata<LpgLocale, LpgStrings>? meta}) => LpgStrings(meta: meta ?? this.$meta);

	// Translations
	late final LpgStrings$common$en common = LpgStrings$common$en.internal(_root);
	late final LpgStrings$async$en async = LpgStrings$async$en.internal(_root);
	late final LpgStrings$stock$en stock = LpgStrings$stock$en.internal(_root);
	late final LpgStrings$appearance$en appearance = LpgStrings$appearance$en.internal(_root);
	late final LpgStrings$splash$en splash = LpgStrings$splash$en.internal(_root);
}

// Path: common
class LpgStrings$common$en {
	LpgStrings$common$en.internal(this._root);

	final LpgStrings _root; // ignore: unused_field

	// Translations

	/// en: 'Retry'
	String get retry => 'Retry';

	/// en: 'Cancel'
	String get cancel => 'Cancel';
}

// Path: async
class LpgStrings$async$en {
	LpgStrings$async$en.internal(this._root);

	final LpgStrings _root; // ignore: unused_field

	// Translations

	/// en: 'Something went wrong'
	String get errorTitle => 'Something went wrong';

	/// en: 'Updating…'
	String get updating => 'Updating…';

	/// en: 'Updated {time: String}'
	String lastUpdated({required String time}) => 'Updated ${time}';
}

// Path: stock
class LpgStrings$stock$en {
	LpgStrings$stock$en.internal(this._root);

	final LpgStrings _root; // ignore: unused_field

	// Translations

	/// en: '(one) {{n} cylinder} (other) {{n} cylinders}'
	String cylinders({required num n}) => (_root.$meta.cardinalResolver ?? PluralResolvers.cardinal('en'))(n,
		one: '${n} cylinder',
		other: '${n} cylinders',
	);

	/// en: 'This line exists only in English.'
	String get onlyInEnglish => 'This line exists only in English.';
}

// Path: appearance
class LpgStrings$appearance$en {
	LpgStrings$appearance$en.internal(this._root);

	final LpgStrings _root; // ignore: unused_field

	// Translations

	/// en: 'Appearance'
	String get title => 'Appearance';

	/// en: 'Match your phone, or always use light or dark.'
	String get hint => 'Match your phone, or always use light or dark.';

	/// en: 'Match phone'
	String get system => 'Match phone';

	/// en: 'Light'
	String get light => 'Light';

	/// en: 'Dark'
	String get dark => 'Dark';
}

// Path: splash
class LpgStrings$splash$en {
	LpgStrings$splash$en.internal(this._root);

	final LpgStrings _root; // ignore: unused_field

	// Translations

	/// en: 'Can't reach the server'
	String get offlineTitle => 'Can\'t reach the server';

	/// en: 'Your sign-in is safe. Check your internet connection. We keep trying.'
	String get offlineHint => 'Your sign-in is safe. Check your internet connection. We keep trying.';

	/// en: 'Trying…'
	String get trying => 'Trying…';
}

/// The flat map containing all translations for locale <en>.
/// Only for edge cases! For simple maps, use the map function of this library.
///
/// The Dart AOT compiler has issues with very large switch statements,
/// so the map is split into smaller functions (512 entries each).
extension on LpgStrings {
	dynamic _flatMapFunction(String path) {
		return switch (path) {
			'common.retry' => 'Retry',
			'common.cancel' => 'Cancel',
			'async.errorTitle' => 'Something went wrong',
			'async.updating' => 'Updating…',
			'async.lastUpdated' => ({required String time}) => 'Updated ${time}',
			'stock.cylinders' => ({required num n}) => (_root.$meta.cardinalResolver ?? PluralResolvers.cardinal('en'))(n, one: '${n} cylinder', other: '${n} cylinders', ), 
			'stock.onlyInEnglish' => 'This line exists only in English.',
			'appearance.title' => 'Appearance',
			'appearance.hint' => 'Match your phone, or always use light or dark.',
			'appearance.system' => 'Match phone',
			'appearance.light' => 'Light',
			'appearance.dark' => 'Dark',
			'splash.offlineTitle' => 'Can\'t reach the server',
			'splash.offlineHint' => 'Your sign-in is safe. Check your internet connection. We keep trying.',
			'splash.trying' => 'Trying…',
			_ => null,
		};
	}
}
