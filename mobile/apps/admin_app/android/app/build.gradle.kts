plugins {
    id("com.android.application")
    // START: FlutterFire Configuration
    id("com.google.gms.google-services")
    // END: FlutterFire Configuration
    id("dev.flutter.flutter-gradle-plugin")
}

// Shared internal-test key (mobile/signing/README.md): keeps a phone's Android ID
// the same across builds, so reinstalling does not register it as a new device.
val internalTestKeystore = rootProject.file("../../../signing/internal-test.keystore")
val hasInternalTestKeystore = internalTestKeystore.exists()

android {
    namespace = "com.lpgagency.admin_app"
    compileSdk = 37
    ndkVersion = flutter.ndkVersion

    compileOptions {
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.lpgagency.admin_app"
        minSdk = maxOf(flutter.minSdkVersion, 23)
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
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
            signingConfig =
                signingConfigs.getByName(if (hasInternalTestKeystore) "internalTest" else "debug")
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
