# Buo — Project Status Review

## Desktop presentation target
- `main.py` imports `buo.app.main`.
- `buo.app` imports and launches `BuoApp` from `buo.legacy_ui`.
- App title, Buildozer title, package directory, and application class are named Buo.
- Desktop dependencies are pinned in `requirements-desktop.txt` (Kivy 2.3.2, Plyer 2.1.0, Requests 2.32.3).
- Windows setup and launch scripts are included.
- The app uses a local SQLite data store and includes strength logging, timers, training plans, recovery, reminders, journal, records, analytics, exports, and local backups.

## Explicitly incomplete / unverified
- Desktop app launch has not been verified in this environment because Kivy could not be installed here (network package index unavailable). Run the Windows setup script on the presentation PC.
- GPS route capture handlers and route/GPX helper functions are placeholders.
- `BuoApp.start_background_tracking()` returns `False`; the app-side Android service is not launched by this snapshot.
- Android step-counter and notifications require Android device testing; they are not desktop functionality.
- Gemini/Firebase optional integrations require private config and have not been tested.
- No Android APK/AAB is included or claimed for the desktop presentation requirement.

## Security / privacy
- `buo.db`, `cloud_config.json`, compiled bytecode, backups, and signing credentials are excluded from release packages.
- Do not upload personal fitness journals or exports to public repositories.


## Desktop startup issue fixed — 20 November 2026

A startup crash was traced to invalid SQLite migration DDL for two reminder columns. The defaults are now valid empty strings (`TEXT DEFAULT ''`). This is a source-level correction; a fresh app launch on the user's Windows machine is still required to confirm the full Kivy desktop runtime.

- Gemini REST requests now use the `x-goog-api-key` header, include short retries for transient errors, and the Fitness AI Coach exposes the Gemini failure reason when it falls back offline. A successful live Gemini response still requires a valid private key and available Google service.


## Workout AI result scrolling fix — 20 November 2026
- AI and smart-tool result displays grow to fit the full response, allowing the parent Workout AI & Smart Tools ScrollView to scroll through long results.
- The page has a visible scrollbar; long result popups also use their own ScrollView.
- Python source syntax passed `py_compile`. Kivy GUI rendering/scroll behavior still requires confirmation on the user's Windows desktop.
