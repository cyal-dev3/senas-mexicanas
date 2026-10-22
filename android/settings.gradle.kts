pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "MiraTek"
include(":core")      // lo que comparten las dos apps
include(":app")       // Mira&Tek (traductor)
include(":trainer")   // Mira&Tek Entrenador (grabar y entrenar en el celular)
