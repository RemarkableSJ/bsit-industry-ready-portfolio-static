[app]
title = Buo
package.name = buo
package.domain = aremarkables.com
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,md,json
source.exclude_dirs = .git,.venv,venv,__pycache__,.buildozer,bin,tests
source.exclude_patterns = buo.db,cloud_config.json,*.sqlite,*.sqlite3,*.pyc,*.bak,*.keystore,*.jks
version = 1.3.3
requirements = python3,kivy==2.3.0,plyer==2.1.0,requests==2.32.3,pyjnius==1.6.1
orientation = portrait
fullscreen = 0
icon.filename = assets/icon.png
# presplash.filename removed for cleaner launch
android.permissions = INTERNET,ACTIVITY_RECOGNITION,POST_NOTIFICATIONS,VIBRATE,WAKE_LOCK,FOREGROUND_SERVICE,RECEIVE_BOOT_COMPLETED,SCHEDULE_EXACT_ALARM,REQUEST_IGNORE_BATTERY_OPTIMIZATIONS
android.api = 34
android.minapi = 26
android.ndk_api = 26
android.ndk = 25b
p4a.branch = develop
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True
services = background_tracker:service/background_tracker.py:foreground:sticky
android.allow_backup = True
# Fill these for release signing when you are ready
# android.release_artifact = apk
# android.release_keystore = /absolute/path/to/buo-release.keystore
# android.release_keyalias = buo
# android.release_keystore_passwd = YOUR_KEYSTORE_PASSWORD
# android.release_keyalias_passwd = YOUR_KEY_PASSWORD
android.enable_androidx = True
android.logcat_filters = *:S python:D
android.entrypoint = org.kivy.android.PythonActivity
android.manifest.intent_filters = 
[buildozer]
log_level = 2
warn_on_root = 1
