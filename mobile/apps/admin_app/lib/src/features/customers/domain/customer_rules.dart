/// A GSTIN is 15 characters: state code, the holder's PAN, an entity number,
/// "Z", and a check character.
final _gstin = RegExp(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$');

/// The GSTIN as typed, tidied up (spaces dropped, upper case).
String tidyGstin(String value) =>
    value.replaceAll(RegExp(r'\s'), '').toUpperCase();

/// Whether [value] looks like a GSTIN. The check character is not verified.
bool isValidGstin(String value) => _gstin.hasMatch(tidyGstin(value));

/// An Indian PIN code: six digits, not starting with zero.
bool isValidPincode(String value) =>
    RegExp(r'^[1-9][0-9]{5}$').hasMatch(value.trim());

/// A plausible email address.
bool isValidEmail(String value) =>
    RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(value.trim());

/// The states and union territories an address can be in.
const indianStates = <String>[
  'Andaman and Nicobar Islands',
  'Andhra Pradesh',
  'Arunachal Pradesh',
  'Assam',
  'Bihar',
  'Chandigarh',
  'Chhattisgarh',
  'Dadra and Nagar Haveli and Daman and Diu',
  'Delhi',
  'Goa',
  'Gujarat',
  'Haryana',
  'Himachal Pradesh',
  'Jammu and Kashmir',
  'Jharkhand',
  'Karnataka',
  'Kerala',
  'Ladakh',
  'Lakshadweep',
  'Madhya Pradesh',
  'Maharashtra',
  'Manipur',
  'Meghalaya',
  'Mizoram',
  'Nagaland',
  'Odisha',
  'Puducherry',
  'Punjab',
  'Rajasthan',
  'Sikkim',
  'Tamil Nadu',
  'Telangana',
  'Tripura',
  'Uttar Pradesh',
  'Uttarakhand',
  'West Bengal',
];
