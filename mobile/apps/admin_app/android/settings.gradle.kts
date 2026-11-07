// Fix AGP 9.0.1 conflict when both ANDROID_PREFS_ROOT and ANDROID_USER_HOME exist in OS env
run {
    fun removeFromEnv(key: String) {
        try {
            val env = System.getenv()
            val field = env.javaClass.getDeclaredField("m")
            field.isAccessible = true
            (field.get(env) as? MutableMap<*, *>)?.remove(key)
        } catch (_: Throwable) {}
        try {
            val pe = Class.forName("java.lang.ProcessEnvironment")
            val field = pe.getDeclaredField("theCaseInsensitiveEnvironment")
            field.isAccessible = true
            (field.get(null) as? MutableMap<*, *>)?.remove(key)
        } catch (_: Throwable) {}
    }
    removeFromEnv("ANDROID_PREFS_ROOT")
}

pluginManagement {
    val flutterSdkPath =
        run {
            val properties = java.util.Properties()
            file("local.properties").inputStream().use { properties.load(it) }
            val flutterSdkPath = properties.getProperty("flutter.sdk")
            require(flutterSdkPath != null) { "flutter.sdk not set in local.properties" }
            flutterSdkPath
        }

    includeBuild("$flutterSdkPath/packages/flutter_tools/gradle")

    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    id("dev.flutter.flutter-plugin-loader") version "1.0.0"
    id("com.android.application") version "9.0.1" apply false
    // START: FlutterFire Configuration
    id("com.google.gms.google-services") version("4.4.2") apply false
    // END: FlutterFire Configuration
    id("org.jetbrains.kotlin.android") version "2.3.20" apply false
}

include(":app")
