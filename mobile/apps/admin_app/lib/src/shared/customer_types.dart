/// The kinds of customer, in the order the office thinks of them. The keys
/// are the backend codes.
const customerTypeLabels = <String, String>{
  'domestic': 'Domestic',
  'commercial': 'Commercial',
  'industrial': 'Industrial',
  'government': 'Government',
};

String customerTypeLabel(String type) =>
    customerTypeLabels[type] ??
    '${type.substring(0, 1).toUpperCase()}${type.substring(1)}';

/// Whether the customer is a business, which has a contact person and may
/// have a GSTIN (everything except a household).
bool isBusinessCustomer(String type) => type != 'domestic';
