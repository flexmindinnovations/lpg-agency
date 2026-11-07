import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

/// The camera and gallery. A provider so tests can swap in a fake.
final profilePhotoPickerProvider = Provider<ImagePicker>(
  (ref) => ImagePicker(),
);

/// What kind of picture [bytes] is, from the file's own first bytes, or `null`
/// when it is not a JPEG, PNG, WebP or HEIC picture. The server checks the
/// bytes against the type it is told, so the type must come from the bytes and
/// not from a file name.
({String contentType, String extension})? pictureKind(List<int> bytes) {
  bool startsWith(List<int> prefix, {int at = 0}) {
    if (bytes.length < at + prefix.length) return false;
    for (var i = 0; i < prefix.length; i++) {
      if (bytes[at + i] != prefix[i]) return false;
    }
    return true;
  }

  if (startsWith(const [0xFF, 0xD8, 0xFF])) {
    return (contentType: 'image/jpeg', extension: 'jpg');
  }
  if (startsWith(const [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])) {
    return (contentType: 'image/png', extension: 'png');
  }
  if (startsWith(const [0x52, 0x49, 0x46, 0x46]) &&
      startsWith(const [0x57, 0x45, 0x42, 0x50], at: 8)) {
    return (contentType: 'image/webp', extension: 'webp');
  }
  // `....ftyp`: the box every HEIC / HEIF file starts with.
  if (startsWith(const [0x66, 0x74, 0x79, 0x70], at: 4)) {
    return (contentType: 'image/heic', extension: 'heic');
  }
  return null;
}
