# Buo — Consolidated Source Notes

This source package combines the uploaded first and second parts into one Buo Android project.

## Naming and package layout
- User-facing app title and Buildozer title: `Buo`.
- Kivy application class: `BuoApp`.
- Python package: `buo`.
- Entry point: `main.py` → `buo.app.main()` → `BuoApp().run()`.
- Android launcher icon: `assets/icon.png`.
- Local database path: `buo.db` (excluded because it can contain private user records).

## Included source
- Main Kivy application screens and data operations in `buo/legacy_ui.py`.
- Platform helpers in `buo/platform_services.py`.
- Android service script in `service/background_tracker.py`.
- Buildozer configuration and desktop/Android dependency lists.
- Blank example configuration for optional Gemini and Firebase integrations.

## Known implementation limits
- GPS route acquisition and route helper functions are stubs.
- The app-side background tracking launcher returns `False`; the declared service is not connected from the current app method.
- Step-counter and notification code require physical-device tests.
- No Android APK/AAB, live API integration, or Play Store release was tested.

Private database/configuration files, bytecode, and backups are excluded from this distributable source archive.
