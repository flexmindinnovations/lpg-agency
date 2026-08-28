/// Parses a JSON-decoded value into a [double], accepting either a bare
/// JSON number or the string a backend `Decimal` field actually serializes
/// as. Pydantic's default JSON encoding for `Decimal` is a string (e.g.
/// `"14.20"`, to avoid float precision loss) — found live via the
/// customer app's order-placement screen, which crashed on
/// `CylinderTypeResponse.weightKg` with `type 'String' is not a subtype of
/// type 'num' in type cast` because every money/weight field across this
/// package assumed a bare number. Every `Decimal`-backed field
/// (`weight_kg`, `unit_price`, `total_amount`, `subtotal`, `tax_amount`,
/// `amount`, `amount_paid`, ...) must go through this instead of a raw
/// `as num` cast.
double asDouble(dynamic value) =>
    value is String ? double.parse(value) : (value as num).toDouble();

/// Nullable counterpart of [asDouble], for optional `Decimal` fields.
double? asDoubleOrNull(dynamic value) => value == null ? null : asDouble(value);
