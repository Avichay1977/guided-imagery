plugins {
    id("com.android.application")
}

android {
    namespace = "com.kesem.marketplaceanywhere"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.kesem.marketplaceanywhere"
        minSdk = 29
        targetSdk = 36
        versionCode = 4
        versionName = "0.4"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
}
