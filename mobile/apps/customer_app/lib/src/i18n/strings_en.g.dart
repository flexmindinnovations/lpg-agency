///
/// Generated file. Do not edit.
///
// coverage:ignore-file
// ignore_for_file: type=lint, unused_import
// dart format off

part of 'strings.g.dart';

// Path: <root>
typedef CustomerStringsEn = CustomerStrings; // ignore: unused_element
class CustomerStrings with BaseTranslations<CustomerLocale, CustomerStrings> {
	/// You can call this constructor and build your own translation instance of this locale.
	/// Constructing via the enum [CustomerLocale.build] is preferred.
	CustomerStrings({Map<String, Node>? overrides, PluralResolver? cardinalResolver, PluralResolver? ordinalResolver, TranslationMetadata<CustomerLocale, CustomerStrings>? meta})
		: assert(overrides == null, 'Set "translation_overrides: true" in order to enable this feature.'),
		  _meta = meta ?? TranslationMetadata(
		    locale: CustomerLocale.en,
		    overrides: overrides ?? {},
		    cardinalResolver: cardinalResolver,
		    ordinalResolver: ordinalResolver,
		  ) {
		_meta.setFlatMapFunction(_flatMapFunction);
	}

	/// Metadata for the translations of <en>.
	final TranslationMetadata<CustomerLocale, CustomerStrings> _meta;
	@override TranslationMetadata<CustomerLocale, CustomerStrings> get $meta => _meta;

	/// Access flat map
	dynamic operator[](String key) => _meta.getTranslation(key);

	late final CustomerStrings _root = this; // ignore: unused_field

	CustomerStrings $copyWith({TranslationMetadata<CustomerLocale, CustomerStrings>? meta}) => CustomerStrings(meta: meta ?? this.$meta);

	// Translations
	late final CustomerStrings$app$en app = CustomerStrings$app$en.internal(_root);
	late final CustomerStrings$dashboard$en dashboard = CustomerStrings$dashboard$en.internal(_root);
}

// Path: app
class CustomerStrings$app$en {
	CustomerStrings$app$en.internal(this._root);

	final CustomerStrings _root; // ignore: unused_field

	// Translations

	/// en: 'LPG Agency'
	String get title => 'LPG Agency';
}

// Path: dashboard
class CustomerStrings$dashboard$en {
	CustomerStrings$dashboard$en.internal(this._root);

	final CustomerStrings _root; // ignore: unused_field

	// Translations
	late final CustomerStrings$dashboard$hero$en hero = CustomerStrings$dashboard$hero$en.internal(_root);
}

// Path: dashboard.hero
class CustomerStrings$dashboard$hero$en {
	CustomerStrings$dashboard$hero$en.internal(this._root);

	final CustomerStrings _root; // ignore: unused_field

	// Translations

	/// en: 'On the way'
	String get onTheWay => 'On the way';

	/// en: 'Orders placed'
	String get ordersPlaced => 'Orders placed';
}

/// The flat map containing all translations for locale <en>.
/// Only for edge cases! For simple maps, use the map function of this library.
///
/// The Dart AOT compiler has issues with very large switch statements,
/// so the map is split into smaller functions (512 entries each).
extension on CustomerStrings {
	dynamic _flatMapFunction(String path) {
		return switch (path) {
			'app.title' => 'LPG Agency',
			'dashboard.hero.onTheWay' => 'On the way',
			'dashboard.hero.ordersPlaced' => 'Orders placed',
			_ => null,
		};
	}
}
