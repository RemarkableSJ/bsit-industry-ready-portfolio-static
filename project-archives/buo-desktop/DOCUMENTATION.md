# Buo — Strength Training & Fitness Progress App

**Project type:** Local-first desktop fitness application  
**Primary desktop target:** Windows 10/11 64-bit  
**Technology:** Python 3.12/3.13, Kivy 2.3.2, Plyer 2.1.0, Requests 2.32.3, SQLite, JSON  
**Prepared:** 20 November 2026

## 1. Project overview

Buo is a local-first fitness and strength-training application. Its goal is to help an individual record training, organize workouts, review recovery, keep personal notes, and monitor progress in one desktop application.

The current portfolio package is focused on the Windows desktop presentation build. It contains the Python/Kivy application source, a local SQLite data layer, Windows setup and launch scripts, the app icon, documentation, and example configuration. The package is source code, not a prebuilt Windows installer or Android APK.

## 2. Goals

- Keep a personal record of strength-training sessions.
- Record exercises, sets, repetitions, load, and effort information such as RIR where available.
- Organize workouts and training plans.
- Provide rest/workout timers and time-calculation utilities.
- Record recovery and wellness check-ins.
- Keep a private journal and personal records.
- Review training history and analytics.
- Export selected records and create local backups.
- Offer optional AI-assisted fitness guidance when a private Gemini configuration and internet connection are available.

## 3. Application architecture

The Windows entry point is `main.py`, which imports `main()` from `buo.app`. The `buo.app` module launches `BuoApp` from `buo.legacy_ui`.

```text
main.py
  └── buo.app.main()
        └── BuoApp().run()
              └── buo.legacy_ui.BuoApp
                    ├── Kivy user interface
                    ├── SQLite data layer (DB)
                    ├── platform service helpers
                    └── optional Gemini request logic
```

Important paths:

- `buo/config.py` defines the project directory, assets directory, database path, cloud-config path, local sync directory, and application name.
- `buo/legacy_ui.py` contains the main application class, screen-building logic, data access layer, and application interactions in this source snapshot.
- `buo/platform_services.py` contains platform-specific helpers, including notification and Android-related service functions.
- `service/background_tracker.py` contains background tracker service-side code; the current app-side launcher is not wired to run it.
- `assets/icon.png` contains the application icon.
- `requirements-desktop.txt` pins the Windows desktop dependencies.

## 4. Main features represented in the supplied source

- Local user profile and passcode-based access flow.
- SQLite-backed user and fitness records.
- Strength/workout logging with exercise, sets, reps, load, and effort fields.
- Workout and rest timers.
- Training-plan and workout-maker interfaces.
- Time-calculator utility.
- Recovery and wellness check-ins.
- Reminder and notification-related code.
- Private journal/notes.
- Personal records and progress views.
- Analytics and history summaries.
- CSV/JSON export and local backup/restore flows.
- Optional online Fitness AI Coach using Gemini when privately configured.
- Offline/local fallback behavior when online AI is unavailable.
- Windows setup and launch scripts.

The documentation describes features present in the supplied source. Individual screens and calculations should be acceptance-tested on the actual computer before every feature is described as fully verified.

## 5. Local data and database

Buo uses SQLite for local application data. The database path is defined by `DB_PATH` in `buo/config.py` and resolves to `buo.db` in the project directory.

The local database is intended for personal information such as profile details, training logs, wellness/recovery records, reminders, journal entries, and application settings. Treat it as private user data.

The public source package intentionally excludes a real `buo.db`. A database is created/initialized by the application when it starts. Existing user databases should be backed up before replacing application source files or testing migrations.

## 6. Online AI and offline fallback

The Fitness AI Coach can call the Gemini REST API when the user supplies a valid private API key, model identifier, and internet connection. The current implementation reads private configuration from `cloud_config.json`; the repository only includes an example configuration template.

Security and reliability behavior in the supplied source includes:

- sending the Gemini API key through the `x-goog-api-key` request header rather than embedding it in the URL;
- retrying selected temporary network and service failures with short backoff delays;
- exposing a failure reason when an online call fails and the app returns to its offline coach behavior;
- retaining an offline fallback so the app can still provide local responses when the remote service is unavailable.

The owner has demonstrated a successful Gemini HTTP 200 response in the Windows desktop app. That confirms at least one online request succeeded in the owner's environment; it does not prove every AI smart tool, prompt, model, or network condition has been tested.

A configured key alone does not prove online AI is available. HTTP 503, network failures, invalid model identifiers, and quota/rate-limit responses can still prevent a remote answer.

## 7. Windows installation and launch

### Requirements

- Windows 10 or Windows 11, 64-bit.
- Python 3.13 or 3.12, 64-bit.
- Internet access for the first dependency installation.

### Setup

1. Download and extract the Buo desktop source package.
2. Open the extracted `Buo_Desktop` project folder.
3. Double-click `setup_buo_windows.bat`.
4. Wait for the virtual environment and requirements installation to finish.
5. Double-click `run_buo_windows.bat`.

The desktop dependency file contains:

```text
kivy[base]==2.3.2
plyer==2.1.0
requests==2.32.3
```

### Manual launch option

Open PowerShell in the Buo project folder and run:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-desktop.txt
python main.py
```

If Python 3.13 is not installed but Python 3.12 is available, use `py -3.12` when creating the virtual environment. Keep the working directory at the project root because the app uses paths relative to the package.

## 8. Optional private configuration

`cloud_config.example.json` is a placeholder template. If enabling Gemini locally, create a private `cloud_config.json` in the project root and enter the required Gemini API key and model identifier there. Do not commit the real configuration file.

Firebase/cloud sync settings are optional and are not required for local SQLite use. The public source package does not include a private Firebase authentication token or live cloud credentials.

## 9. Testing and verification status

### Owner-observed behavior

- The owner confirmed that the Buo Windows desktop application opens after the SQLite migration correction.
- The owner supplied a terminal screenshot showing a successful Gemini HTTP 200 response from the online Fitness AI Coach.
- The long-answer scrolling layout update was prepared and delivered for the Windows app.

### Source-level checks previously performed

- Python source files passed syntax compilation.
- The SQLite reminder-column migration was corrected to use valid empty-string defaults for `last_sent_on` and `normalized_time`.
- The source package was checked for the expected Windows entry point and dependency setup.

### Still requires structured acceptance testing

- Create a new local profile and verify login/passcode behavior.
- Create, edit, and review strength logs.
- Verify training-plan, timer, recovery, reminder, journal, PR, analytics, and export flows.
- Test backup and restore using a disposable test database.
- Test offline AI behavior with internet disconnected.
- Test online AI behavior with a valid private key, and confirm errors are clearly shown when Gemini is unavailable.
- Test long AI responses and scroll to the end of every result view.

## 10. Known limitations and incomplete platform features

- GPS route capture handlers and the route/GPX helper functions are placeholders; the current helper functions return empty values.
- `BuoApp.start_background_tracking()` returns `False`; the app-side Android background tracking service is not launched by this source snapshot.
- `start_background_tracking_service()` and `stop_background_tracking_service()` in `platform_services.py` return `False`.
- Android step-counter support is platform-specific and requires an Android device and device testing.
- Android notification and background-service behavior is not established by the Windows desktop build.
- No Android APK or AAB is included in this desktop handoff.
- Optional Gemini and Firebase features depend on private configuration and external service availability.
- Plyer notifications may behave differently or be unavailable on Windows.

Do not describe GPS route tracking, GPX export, Android background continuity, or a tested Android release as complete based on this source snapshot.

## 11. Privacy and security

Buo may handle personal workout history, body/fitness measurements, recovery records, and private journal notes. These files must be treated as sensitive personal information.

Never commit or publicly upload:

- `buo.db`;
- personal CSV/JSON exports or backup bundles;
- private journal data or cloud-sync folders;
- `cloud_config.json` or real Gemini/Firebase API keys and tokens;
- Android signing keys and passwords.

Revoke and replace any API key that was ever exposed in a screenshot, terminal output, or public repository. Removing the key from a later commit does not invalidate the old key. For a distributed Android application, do not embed a reusable Gemini API key in the client; use an appropriately authenticated server-side service if remote AI is later distributed to multiple users.

## 12. Future improvements

- Complete and test Android packaging, permission handling, background tracking, and step-counter behavior on physical devices.
- Implement route capture, map display, route browser links, and GPX export end to end.
- Add structured automated and manual acceptance tests for all major tools.
- Improve local data backup/export documentation and data deletion controls.
- Add clear privacy disclosures before any wider distribution.
- Consider a secure backend/proxy if the app is distributed to multiple users and online AI or cloud synchronization is enabled.
