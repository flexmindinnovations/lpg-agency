import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

/// The camera/gallery picker, behind a provider so widget tests can swap in
/// a fake that returns fixed bytes.
final imagePickerProvider = Provider<ImagePicker>((ref) => ImagePicker());
