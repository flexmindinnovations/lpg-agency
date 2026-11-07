///
/// Generated file. Do not edit.
///
// coverage:ignore-file
// ignore_for_file: type=lint, unused_import
// dart format off

part of 'strings.g.dart';

// Path: <root>
typedef DriverStringsEn = DriverStrings; // ignore: unused_element
class DriverStrings with BaseTranslations<DriverLocale, DriverStrings> {
	/// You can call this constructor and build your own translation instance of this locale.
	/// Constructing via the enum [DriverLocale.build] is preferred.
	DriverStrings({Map<String, Node>? overrides, PluralResolver? cardinalResolver, PluralResolver? ordinalResolver, TranslationMetadata<DriverLocale, DriverStrings>? meta})
		: assert(overrides == null, 'Set "translation_overrides: true" in order to enable this feature.'),
		  _meta = meta ?? TranslationMetadata(
		    locale: DriverLocale.en,
		    overrides: overrides ?? {},
		    cardinalResolver: cardinalResolver,
		    ordinalResolver: ordinalResolver,
		  ) {
		_meta.setFlatMapFunction(_flatMapFunction);
	}

	/// Metadata for the translations of <en>.
	final TranslationMetadata<DriverLocale, DriverStrings> _meta;
	@override TranslationMetadata<DriverLocale, DriverStrings> get $meta => _meta;

	/// Access flat map
	dynamic operator[](String key) => _meta.getTranslation(key);

	late final DriverStrings _root = this; // ignore: unused_field

	DriverStrings $copyWith({TranslationMetadata<DriverLocale, DriverStrings>? meta}) => DriverStrings(meta: meta ?? this.$meta);

	// Translations
	late final DriverStrings$app$en app = DriverStrings$app$en.internal(_root);
	late final DriverStrings$today$en today = DriverStrings$today$en.internal(_root);
	late final DriverStrings$stop$en stop = DriverStrings$stop$en.internal(_root);
}

// Path: app
class DriverStrings$app$en {
	DriverStrings$app$en.internal(this._root);

	final DriverStrings _root; // ignore: unused_field

	// Translations

	/// en: 'LPG Agency'
	String get title => 'LPG Agency';
}

// Path: today
class DriverStrings$today$en {
	DriverStrings$today$en.internal(this._root);

	final DriverStrings _root; // ignore: unused_field

	// Translations
	late final DriverStrings$today$stats$en stats = DriverStrings$today$stats$en.internal(_root);
}

// Path: stop
class DriverStrings$stop$en {
	DriverStrings$stop$en.internal(this._root);

	final DriverStrings _root; // ignore: unused_field

	// Translations
	late final DriverStrings$stop$failedSheet$en failedSheet = DriverStrings$stop$failedSheet$en.internal(_root);
}

// Path: today.stats
class DriverStrings$today$stats$en {
	DriverStrings$today$stats$en.internal(this._root);

	final DriverStrings _root; // ignore: unused_field

	// Translations

	/// en: 'Delivered'
	String get delivered => 'Delivered';

	/// en: 'Remaining'
	String get remaining => 'Remaining';

	/// en: 'Failed'
	String get failed => 'Failed';
}

// Path: stop.failedSheet
class DriverStrings$stop$failedSheet$en {
	DriverStrings$stop$failedSheet$en.internal(this._root);

	final DriverStrings _root; // ignore: unused_field

	// Translations

	/// en: 'Why did the delivery fail?'
	String get title => 'Why did the delivery fail?';
}

/// The flat map containing all translations for locale <en>.
/// Only for edge cases! For simple maps, use the map function of this library.
///
/// The Dart AOT compiler has issues with very large switch statements,
/// so the map is split into smaller functions (512 entries each).
extension on DriverStrings {
	dynamic _flatMapFunction(String path) {
		return switch (path) {
			'app.title' => 'LPG Agency',
			'today.stats.delivered' => 'Delivered',
			'today.stats.remaining' => 'Remaining',
			'today.stats.failed' => 'Failed',
			'stop.failedSheet.title' => 'Why did the delivery fail?',
			_ => null,
		};
	}
}
