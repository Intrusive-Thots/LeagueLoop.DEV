# Fix warnings and errors in build.gradle files

The `build.gradle` files (both root and app-level) have several deprecation warnings and one error regarding ProGuard configuration. This plan will update these files to use modern Gradle APIs and recommended practices.

## Proposed Changes

### Build Configuration

#### [MODIFY] [build.gradle](file:///C:/Users/Administrator/LeagueLoop.DEV/LeagueLoopMobile/android/build.gradle)
- Update Android Gradle Plugin version to `8.13.2`.
- Update Google Services plugin version to `4.5.0`.
- Replace deprecated `task clean(type: Delete)` with `tasks.register("clean", Delete)`.
- Replace deprecated `rootProject.buildDir` with `rootProject.layout.buildDirectory`.

#### [MODIFY] [app/build.gradle](file:///C:/Users/Administrator/LeagueLoop.DEV/LeagueLoopMobile/android/app/build.gradle)
- Replace deprecated `proguard-android.txt` with `proguard-android-optimize.txt`.
- Fix unused catch parameter `e` by renaming it to `ignored`.

## Verification Plan

### Automated Tests
- Run `./gradlew help` to verify that the build configuration is valid.
- Run `./gradlew clean` to verify the updated clean task works.
- Run `./gradlew assembleDebug` to ensure the project still builds.
