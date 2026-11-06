///
/// Generated file. Do not edit.
///
// coverage:ignore-file
// ignore_for_file: type=lint, unused_import
// dart format off

part of 'strings.g.dart';

// Path: <root>
typedef AdminStringsEn = AdminStrings; // ignore: unused_element
class AdminStrings with BaseTranslations<AdminLocale, AdminStrings> {
	/// You can call this constructor and build your own translation instance of this locale.
	/// Constructing via the enum [AdminLocale.build] is preferred.
	AdminStrings({Map<String, Node>? overrides, PluralResolver? cardinalResolver, PluralResolver? ordinalResolver, TranslationMetadata<AdminLocale, AdminStrings>? meta})
		: assert(overrides == null, 'Set "translation_overrides: true" in order to enable this feature.'),
		  _meta = meta ?? TranslationMetadata(
		    locale: AdminLocale.en,
		    overrides: overrides ?? {},
		    cardinalResolver: cardinalResolver,
		    ordinalResolver: ordinalResolver,
		  ) {
		_meta.setFlatMapFunction(_flatMapFunction);
	}

	/// Metadata for the translations of <en>.
	final TranslationMetadata<AdminLocale, AdminStrings> _meta;
	@override TranslationMetadata<AdminLocale, AdminStrings> get $meta => _meta;

	/// Access flat map
	dynamic operator[](String key) => _meta.getTranslation(key);

	late final AdminStrings _root = this; // ignore: unused_field

	AdminStrings $copyWith({TranslationMetadata<AdminLocale, AdminStrings>? meta}) => AdminStrings(meta: meta ?? this.$meta);

	// Translations
	late final AdminStrings$app$en app = AdminStrings$app$en.internal(_root);
}

// Path: app
class AdminStrings$app$en {
	AdminStrings$app$en.internal(this._root);

	final AdminStrings _root; // ignore: unused_field

	// Translations

	/// en: 'LPG Agency Admin'
	String get title => 'LPG Agency Admin';
}

/// The flat map containing all translations for locale <en>.
/// Only for edge cases! For simple maps, use the map function of this library.
///
/// The Dart AOT compiler has issues with very large switch statements,
/// so the map is split into smaller functions (512 entries each).
extension on AdminStrings {
	dynamic _flatMapFunction(String path) {
		return switch (path) {
			'app.title' => 'LPG Agency Admin',
			_ => null,
		};
	}
}
