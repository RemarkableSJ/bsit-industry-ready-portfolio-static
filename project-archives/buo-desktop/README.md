# Buo — Desktop Presentation Build

Buo is a Python/Kivy fitness and strength-progress app. This package includes the complete supplied `buo` source package and a Windows desktop setup path.

## Run on Windows 10/11

Use 64-bit CPython 3.13 or 3.12. Kivy 2.3.2 officially supports CPython 3.8–3.14. The desktop requirements install Kivy with its base SDL2/GLEW dependencies. See the current Kivy installation instructions: https://kivy.org/doc/stable/gettingstarted/installation.html

1. Extract the entire `Buo_Android_Final` folder.
2. Double-click `setup_buo_windows.bat` (requires internet for pip packages).
3. After setup finishes, double-click `run_buo_windows.bat`.

Or run manually from this folder:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-desktop.txt
python main.py
```

Keep the working directory at the project folder because UI assets are referenced relative to it.

## Desktop scope

The main app UI, local SQLite profile/data, strength logging, workout timers, training plans, recovery check-ins, journal, analytics, records, exports, and local backup flows are designed to run without Android packaging. Plyer notifications may be unavailable or behave differently on Windows.

## Known limitations in this source snapshot

- GPS route capture handlers and route/GPX helper functions are placeholders; route tracking is not functional.
- Android foreground/background tracking is not launched by the current app method; the launcher returns `False`.
- Android step-counter APIs require an Android device and are not a desktop feature.
- Gemini and Firebase are optional and require valid private configuration; they are not enabled by the public package.
- The source has not been successfully launched in this build environment because dependencies could not be downloaded here. Run the Windows setup script on your computer and test each screen before calling the app fully working.

## Privacy and GitHub

Do not commit `buo.db`, user fitness exports, `cloud_config.json`, API keys, Firebase tokens, or signing credentials. `cloud_config.example.json` is a placeholder only. The desktop build uses `requirements-desktop.txt`; the Android/Buildozer file uses `requirements.txt`.

## Android build

The Buildozer configuration is retained for future Android work, but this handoff is focused on the desktop presentation build. It is not an APK and has not been built or tested on Android.


## Startup migration fix (20 November 2026)

The SQLite schema upgrade for the `reminders` table now uses valid empty-string defaults for `last_sent_on` and `normalized_time`. This fixes the startup error `sqlite3.OperationalError: incomplete input` raised by SQLite when an existing database needs those columns added. Existing `buo.db` files are retained; the app adds only missing columns when it starts.

After updating the source files, keep your existing `buo.db` in the project root and launch `run_buo_windows.bat` again. Back up the database before replacing project files.

### Gemini connection reliability and API-key handling

- Gemini requests send the API key through Google's `x-goog-api-key` header instead of putting it in the request URL.
- Transient HTTP 429/5xx and network failures receive up to two short exponential-backoff retries.
- The Fitness AI Coach reports the Gemini failure reason when it has to fall back to its offline coach.
- A configured API key does not prove that Gemini is reachable; a successful API response is required.
- Google-side HTTP 503 capacity errors can still occur after retries. In that case, Buo uses its offline fallback.
- Revoke any API key previously exposed in a terminal screenshot or request log, then create a replacement. Keep `cloud_config.json` private and out of Git.


### Long AI answers and scrolling (20 November 2026)

- The Fitness AI Coach, food analyzer, calorie/protein planner, body recomposition calculator, nutrition planner, and workout maker now display their results in content-height labels. The outer Workout AI & Smart Tools page scrolls through the full result instead of clipping it to a short fixed-height read-only text box.
- The Workout AI & Smart Tools page now has a visible vertical scrollbar that can be dragged.
- Long result popups use a dedicated ScrollView, so long Gemini answers can be read from top to bottom.
- This is a UI/layout fix; it does not alter Gemini prompts, training calculations, saved data, or the local SQLite database.
