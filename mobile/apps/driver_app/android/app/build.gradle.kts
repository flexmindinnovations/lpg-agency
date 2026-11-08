import java.util.Properties

plugins {
    id("com.android.application")
    // START: FlutterFire Configuration
    id("com.google.gms.google-services")
    // END: FlutterFire Configuration
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing. Reads android/key.properties (git-ignored) when present;
// see mobile/RELEASE.md. Without it, release builds fall back to the shared
// internal-test key (mobile/signing/README.md), then the debug key - such a
// build cannot be uploaded to the Play Store.
val keystoreProperties = Properties().apply {
    val file = rootProject.file("key.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}
val hasReleaseKeystore = keystoreProperties.getProperty("storeFile") != null
// Shared internal-test key, used when there is no real release key.
val internalTestKeystore = rootProject.file("../../../signing/internal-test.keystore")
val hasInternalTestKeystore = internalTestKeystore.exists()

android {
    namespace = "com.lpgagency.driver_app"
    // flutter_secure_storage (via local_storage) requires compiling against
    // API 37+ — matches the customer app.
    compileSdk = 37
    ndkVersion = flutter.ndkVersion

    compileOptions {
        // Required by flutter_local_notifications (uses java.time on older APIs).
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.lpgagency.driver_app"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        // firebase_core 3.x requires API 23+.
        minSdk = maxOf(flutter.minSdkVersion, 23)
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasReleaseKeystore) {
            create("release") {
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
        }
        // Shared key for internal test APKs (mobile/signing/README.md): keeps a
        // phone's Android ID the same across builds, so reinstalling does not
        // register it as a new device.
        if (hasInternalTestKeystore) {
            create("internalTest") {
                storeFile = internalTestKeystore
                storePassword = "lpg-internal-test"
                keyAlias = "lpg-internal-test"
                keyPassword = "lpg-internal-test"
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName(
                if (hasReleaseKeystore) {
                    "release"
                } else if (hasInternalTestKeystore) {
                    "internalTest"
                } else {
                    "debug"
                },
            )
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}
