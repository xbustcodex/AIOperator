import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

// Release signing is deliberately SEPARATE from every other Prime Tech product.
//
// Buster is its own Android security principal. TerminalP authenticates a caller
// by (UID -> package -> pinned signing-certificate digest), so sharing a key
// with Prime Tech Terminal would make the package name the only discriminator
// between two principals that must never be confusable. Buster therefore owns a
// dedicated keystore, loaded here from a git-ignored properties file or the
// environment, and is NEVER defaulted to the debug key.
val releaseSigning: Properties? = run {
    val fromFile = rootProject.file("signing.properties")
    val props = Properties()
    var loaded = false
    if (fromFile.exists()) {
        fromFile.inputStream().use { props.load(it) }
        loaded = true
    }
    val fromEnv = System.getenv("BUSTER_RELEASE_STORE_FILE")
    if (loaded || !fromEnv.isNullOrBlank()) props else null
}

android {
    namespace = "com.primetech.buster"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.primetech.buster"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
    }

    signingConfigs {
        // Buster's OWN debug identity, not the machine-wide Android debug key.
        //
        // The shared ~/.android/debug.keystore is the same key the installed
        // Prime Tech Terminal is signed with. Reusing it would make two
        // distinct security principals share a signing identity, which is
        // exactly what this application exists to avoid. TerminalP keys on
        // (package, certificate) today, but a certificate-keyed policy must
        // never be able to confuse the two products.
        getByName("debug") {
            storeFile = rootProject.file("buster-debug.jks")
            storePassword = "busterdebug"
            keyAlias = "busterdebugkey"
            keyPassword = "busterdebug"
            enableV1Signing = true
        }
        if (releaseSigning != null) {
            create("busterRelease") {
                storeFile = file(releaseSigning.getProperty("storeFile"))
                storePassword = releaseSigning.getProperty("storePassword")
                keyAlias = releaseSigning.getProperty("keyAlias")
                keyPassword = releaseSigning.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
            buildConfigField("String", "SIGNING_FLAVOR", "\"DEBUG\"")
        }
        release {
            isMinifyEnabled = false
            buildConfigField("String", "SIGNING_FLAVOR", "\"RELEASE\"")
            // A release build with no configured keystore stays UNSIGNED rather
            // than silently inheriting the debug identity.
            signingConfig = signingConfigs.findByName("busterRelease")
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
        // The Buster APK keeps its own copy of the bridge AIDL contract so it
        // is a distinct Binder client rather than a PTT one.
        aidl = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.material3)

    testImplementation(libs.junit)
    testImplementation(libs.robolectric)
}
