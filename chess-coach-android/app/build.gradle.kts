import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import java.net.URL
import java.security.MessageDigest

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

// Stockfish 17.1 default networks. The file name carries the first 12 hex chars of the SHA-256.
val nnueFiles = listOf("nn-1c0000000000.nnue", "nn-37f18f62d772.nnue")
val nnueDir = layout.buildDirectory.dir("generated/nnue/assets")

fun sha256Prefix(f: File): String {
    val md = MessageDigest.getInstance("SHA-256")
    f.inputStream().use { input ->
        val buf = ByteArray(1 shl 16)
        while (true) {
            val n = input.read(buf)
            if (n < 0) break
            md.update(buf, 0, n)
        }
    }
    return md.digest().joinToString("") { "%02x".format(it) }.substring(0, 12)
}

val downloadNnue by tasks.registering {
    description = "Downloads the Stockfish NNUE networks into the app assets"
    outputs.dir(nnueDir)
    doLast {
        val dir = nnueDir.get().asFile
        dir.mkdirs()
        for (name in nnueFiles) {
            val target = File(dir, name)
            val expected = name.substring(3, 15)
            if (target.exists() && sha256Prefix(target) == expected) continue
            val urls = listOf(
                "https://tests.stockfishchess.org/api/nn/$name",
                "https://github.com/official-stockfish/networks/raw/master/$name",
            )
            var ok = false
            for (u in urls) {
                try {
                    logger.lifecycle("Downloading $u")
                    URL(u).openStream().use { input -> target.outputStream().use { input.copyTo(it) } }
                    if (sha256Prefix(target) == expected) {
                        ok = true
                        break
                    }
                    logger.warn("Checksum mismatch for $name from $u")
                } catch (e: Exception) {
                    logger.warn("Download failed from $u: ${e.message}")
                }
            }
            if (!ok) throw GradleException("Could not download $name. Place it manually in ${dir.absolutePath}")
        }
    }
}

android {
    namespace = "com.chesscoach.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.chesscoach.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1"
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
        externalNativeBuild {
            cmake {
                arguments += listOf("-DANDROID_STL=c++_static")
            }
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    sourceSets["main"].assets.srcDir(nnueDir.get().asFile)

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
    }
    androidResources {
        noCompress += "nnue"
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

tasks.named("preBuild") {
    dependsOn(downloadNnue)
}

dependencies {
    implementation(project(":core"))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.camera.core)
    implementation(libs.androidx.camera.camera2)
    implementation(libs.androidx.camera.lifecycle)
    implementation(libs.androidx.camera.view)
    implementation(libs.kotlinx.coroutines.android)
}
