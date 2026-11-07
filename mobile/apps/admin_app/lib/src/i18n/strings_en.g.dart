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
	late final AdminStrings$dashboard$en dashboard = AdminStrings$dashboard$en.internal(_root);
	late final AdminStrings$cashHandover$en cashHandover = AdminStrings$cashHandover$en.internal(_root);
	late final AdminStrings$profile$en profile = AdminStrings$profile$en.internal(_root);
}

// Path: app
class AdminStrings$app$en {
	AdminStrings$app$en.internal(this._root);

	final AdminStrings _root; // ignore: unused_field

	// Translations

	/// en: 'LPG Agency Admin'
	String get title => 'LPG Agency Admin';
}

// Path: dashboard
class AdminStrings$dashboard$en {
	AdminStrings$dashboard$en.internal(this._root);

	final AdminStrings _root; // ignore: unused_field

	// Translations
	late final AdminStrings$dashboard$hero$en hero = AdminStrings$dashboard$hero$en.internal(_root);
}

// Path: cashHandover
class AdminStrings$cashHandover$en {
	AdminStrings$cashHandover$en.internal(this._root);

	final AdminStrings _root; // ignore: unused_field

	// Translations

	/// en: 'Cash collected ({count: int})'
	String collected({required int count}) => 'Cash collected (${count})';
}

// Path: profile
class AdminStrings$profile$en {
	AdminStrings$profile$en.internal(this._root);

	final AdminStrings _root; // ignore: unused_field

	// Translations

	/// en: 'Edit profile'
	String get editTitle => 'Edit profile';

	/// en: 'Profile updated.'
	String get updated => 'Profile updated.';

	/// en: 'Contact phone'
	String get contactPhone => 'Contact phone';

	/// en: 'Name'
	String get name => 'Name';

	/// en: 'For colleagues to reach you. Optional.'
	String get phoneHelp => 'For colleagues to reach you. Optional.';

	/// en: 'Profile picture'
	String get pictureTitle => 'Profile picture';

	/// en: 'Take photo'
	String get takePhoto => 'Take photo';

	/// en: 'Choose from gallery'
	String get chooseFromGallery => 'Choose from gallery';

	/// en: 'Remove photo'
	String get removePhoto => 'Remove photo';

	/// en: 'Change profile picture'
	String get changePicture => 'Change profile picture';
}

// Path: dashboard.hero
class AdminStrings$dashboard$hero$en {
	AdminStrings$dashboard$hero$en.internal(this._root);

	final AdminStrings _root; // ignore: unused_field

	// Translations

	/// en: 'Delivered'
	String get delivered => 'Delivered';

	/// en: 'Failed'
	String get failed => 'Failed';

	/// en: 'To approve'
	String get toApprove => 'To approve';
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
			'dashboard.hero.delivered' => 'Delivered',
			'dashboard.hero.failed' => 'Failed',
			'dashboard.hero.toApprove' => 'To approve',
			'cashHandover.collected' => ({required int count}) => 'Cash collected (${count})',
			'profile.editTitle' => 'Edit profile',
			'profile.updated' => 'Profile updated.',
			'profile.contactPhone' => 'Contact phone',
			'profile.name' => 'Name',
			'profile.phoneHelp' => 'For colleagues to reach you. Optional.',
			'profile.pictureTitle' => 'Profile picture',
			'profile.takePhoto' => 'Take photo',
			'profile.chooseFromGallery' => 'Choose from gallery',
			'profile.removePhoto' => 'Remove photo',
			'profile.changePicture' => 'Change profile picture',
			_ => null,
		};
	}
}
