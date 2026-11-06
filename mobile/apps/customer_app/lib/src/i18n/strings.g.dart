/// Generated file. Do not edit.
///
/// Source: lib/src/i18n
/// To regenerate, run: `dart run slang`
///
/// Locales: 1
/// Strings: 1

// coverage:ignore-file
// ignore_for_file: type=lint, unused_import
// dart format off

import 'package:flutter/widgets.dart';
import 'package:intl/intl.dart';
import 'package:slang/generated.dart';
import 'package:slang_flutter/slang_flutter.dart';
export 'package:slang_flutter/slang_flutter.dart';

part 'strings_en.g.dart';

/// Supported locales.
///
/// Usage:
/// - LocaleSettings.setLocale(CustomerLocale.en) // set locale
/// - Locale locale = CustomerLocale.en.flutterLocale // get flutter locale from enum
/// - if (LocaleSettings.currentLocale == CustomerLocale.en) // locale check
enum CustomerLocale with BaseAppLocale<CustomerLocale, CustomerStrings> {
	en(languageCode: 'en');

	const CustomerLocale({
		required this.languageCode,
		this.scriptCode, // ignore: unused_element, unused_element_parameter
		this.countryCode, // ignore: unused_element, unused_element_parameter
	});

	@override final String languageCode;
	@override final String? scriptCode;
	@override final String? countryCode;

	@override
	Future<CustomerStrings> build({
		Map<String, Node>? overrides,
		PluralResolver? cardinalResolver,
		PluralResolver? ordinalResolver,
	}) async {
		return buildSync(
			overrides: overrides,
			cardinalResolver: cardinalResolver,
			ordinalResolver: ordinalResolver,
		);
	}

	@override
	CustomerStrings buildSync({
		Map<String, Node>? overrides,
		PluralResolver? cardinalResolver,
		PluralResolver? ordinalResolver,
	}) {
		switch (this) {
			case CustomerLocale.en:
				return CustomerStringsEn(
					overrides: overrides,
					cardinalResolver: cardinalResolver,
					ordinalResolver: ordinalResolver,
				);
		}
	}
}

/// Provides utility functions without any side effects.
class AppLocaleUtils extends BaseAppLocaleUtils<CustomerLocale, CustomerStrings> {
	AppLocaleUtils._() : super(
		baseLocale: CustomerLocale.en,
		locales: CustomerLocale.values,
	);

	static final instance = AppLocaleUtils._();

	// static aliases (checkout base methods for documentation)
	static CustomerLocale parse(String rawLocale) => instance.parse(rawLocale);
	static CustomerLocale parseLocaleParts({required String languageCode, String? scriptCode, String? countryCode}) => instance.parseLocaleParts(languageCode: languageCode, scriptCode: scriptCode, countryCode: countryCode);
	static CustomerLocale findDeviceLocale() => instance.findDeviceLocale();
	static List<Locale> get supportedLocales => instance.supportedLocales;
	static List<String> get supportedLocalesRaw => instance.supportedLocalesRaw;
}
