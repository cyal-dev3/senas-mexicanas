plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Todo lo que comparten la app de traduccion y el Entrenador: caracteristicas, modelo,
// reconocedor, camara + MediaPipe, tema y componentes de la interfaz.
android {
    namespace = "mx.miratek.senas.core"
    compileSdk = 35
    buildToolsVersion = "35.0.0"

    defaultConfig {
        minSdk = 26
        consumerProguardFiles("consumer-rules.pro")
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    androidResources { noCompress += listOf("task") }
    testOptions { unitTests.isReturnDefaultValues = true }
}

// El detector de manos, las instrucciones de las senas y las animaciones de "Aprender"
// viven en assets/ (raiz del repo) o se generan con tools/: Gradle los copia a la APK.
val sharedAssetsDir = layout.buildDirectory.dir("generated/miratek-assets")
val copySharedAssets by tasks.registering(Copy::class) {
    val required = listOf("hand_landmarker.task", "senas_info.json")
    doFirst {
        for (name in required) {
            val f = rootProject.file("../assets/$name")
            if (!f.exists()) throw GradleException("Falta $f: sin el detector de manos la app no sirve.")
        }
    }
    from(required.map { rootProject.file("../assets/$it") })
    from(rootProject.file("../assets/learn_clips.json"))  // opcional: tools/make_learn_assets.py
    into(sharedAssetsDir)
}
android.sourceSets.getByName("main").assets.srcDir(sharedAssetsDir)
tasks.named("preBuild") { dependsOn(copySharedAssets) }

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    api(composeBom)
    api("androidx.compose.ui:ui")
    api("androidx.compose.ui:ui-graphics")
    api("androidx.compose.foundation:foundation")
    api("androidx.compose.animation:animation")
    api("androidx.compose.material3:material3")
    api("androidx.core:core-ktx:1.15.0")
    api("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    api("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")

    val camerax = "1.4.1"
    api("androidx.camera:camera-core:$camerax")
    api("androidx.camera:camera-camera2:$camerax")
    api("androidx.camera:camera-lifecycle:$camerax")
    api("androidx.camera:camera-view:$camerax")

    api("com.google.mediapipe:tasks-vision:0.10.35")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
