---
name: Compile Android App
description: Compile a Capacitor-based Vite mobile application into an Android APK and AAB for Google Play Store release.
---

# Compile Android App

This skill automates the compilation of a web application to an Android binary using Gradle and Capacitor.

## Prerequisites
1. You must be in the `LeagueLoopMobile` directory (or equivalent Capacitor root).
2. The `android/` subdirectory must exist (run `npx cap add android` if not).

## Execution Steps

1. **Build Web Frontend**
   Run the web bundler (Vite) to compile the React/Vanilla HTML assets.
   ```powershell
   npm run build
   ```

2. **Sync Native Projects**
   Transfer the `dist/` web output into the native Android folder.
   ```powershell
   npx cap sync android
   ```

3. **Compile Binaries via Gradle**
   Execute Gradle inside the `android` directory to generate the bundles. Set `JAVA_HOME` to JDK 21 (e.g. `C:\Program Files\Android\openjdk\jdk-21.0.8`) first if the default system JDK is 17 or lower.
   ```powershell
   cd android
   $env:JAVA_HOME = "C:\Program Files\Android\openjdk\jdk-21.0.8"
   ./gradlew assembleRelease   # For APK (direct install)
   ./gradlew bundleRelease     # For AAB (Play Store)
   cd ..
   ```

4. **Locate Outputs**
   The compiled but unsigned binaries will be placed in:
   - APK: `android/app/build/outputs/apk/release/app-release-unsigned.apk`
   - AAB: `android/app/build/outputs/bundle/release/app-release.aab`
