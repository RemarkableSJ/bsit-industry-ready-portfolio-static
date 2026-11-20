from __future__ import annotations

from kivy.utils import platform
from pathlib import Path
import json

try:
    from plyer import notification
except Exception:
    notification = None

gps = None


def is_android() -> bool:
    return platform == "android"


def request_android_permissions() -> None:
    if not is_android():
        return
    try:
        from android.permissions import Permission, request_permissions  # type: ignore[reportMissingImports]

        request_permissions([
            Permission.ACTIVITY_RECOGNITION,
            Permission.POST_NOTIFICATIONS,
            Permission.VIBRATE,
            Permission.WAKE_LOCK,
            Permission.FOREGROUND_SERVICE,
            Permission.RECEIVE_BOOT_COMPLETED,
        ])
    except Exception:
        pass


def has_android_location_permission() -> bool:
    return False
def is_android_location_enabled() -> bool:
    return False
def open_android_location_settings() -> bool:
    return False
def send_local_notification(title: str, message: str) -> None:
    if notification is None:
        return
    try:
        notification.notify(title=title, message=message, app_name="Buo", timeout=6)
    except Exception:
        pass


def _service_state_path() -> Path:
    return Path.home() / '.buo_background_service.json'


def write_background_service_state(payload: dict) -> None:
    try:
        _service_state_path().write_text(json.dumps(payload), encoding='utf-8')
    except Exception:
        pass


def clear_background_service_state() -> None:
    try:
        _service_state_path().unlink(missing_ok=True)
    except Exception:
        pass


def start_background_tracking_service(title: str = 'Buo tracking', message: str = 'Background tracking is active.') -> bool:
    return False

def stop_background_tracking_service() -> bool:
    return False

def request_android_scheduler_exemptions() -> bool:
    if not is_android():
        return False
    opened_any = False
    try:
        from jnius import autoclass, cast  # type: ignore[reportMissingImports]
        Intent = autoclass('android.content.Intent')
        Settings = autoclass('android.provider.Settings')
        Uri = autoclass('android.net.Uri')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        BuildVersion = autoclass('android.os.Build$VERSION')
        BuildVersionCodes = autoclass('android.os.Build$VERSION_CODES')

        current = cast('android.app.Activity', PythonActivity.mActivity)
        package_name = current.getPackageName()

        try:
            power_manager = cast('android.os.PowerManager', current.getSystemService(current.POWER_SERVICE))
            ignoring = bool(power_manager.isIgnoringBatteryOptimizations(package_name)) if power_manager else False
            if not ignoring:
                intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                intent.setData(Uri.parse(f'package:{package_name}'))
                current.startActivity(intent)
                opened_any = True
        except Exception:
            pass

        try:
            if int(BuildVersion.SDK_INT) >= int(BuildVersionCodes.S):
                alarm_manager = cast('android.app.AlarmManager', current.getSystemService(current.ALARM_SERVICE))
                can_schedule = bool(alarm_manager.canScheduleExactAlarms()) if alarm_manager else True
                if not can_schedule:
                    intent2 = Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM)
                    intent2.setData(Uri.parse(f'package:{package_name}'))
                    current.startActivity(intent2)
                    opened_any = True
        except Exception:
            pass
    except Exception:
        return False
    return opened_any


_STEP_COUNTER_REFS = {}

def _step_counter_state_path() -> Path:
    return Path.home() / '.buo_steps.json'


def read_step_counter_state() -> dict:
    try:
        path = _step_counter_state_path()
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _write_step_counter_state(payload: dict) -> None:
    try:
        _step_counter_state_path().write_text(json.dumps(payload), encoding='utf-8')
    except Exception:
        pass


def start_step_counter_listener() -> bool:
    if not is_android():
        return False
    try:
        from jnius import autoclass, PythonJavaClass, java_method, cast  # type: ignore[reportMissingImports]
        if _STEP_COUNTER_REFS.get('started'):
            return True
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        Sensor = autoclass('android.hardware.Sensor')
        SensorManager = autoclass('android.hardware.SensorManager')
        activity = cast('android.app.Activity', PythonActivity.mActivity)
        manager = cast('android.hardware.SensorManager', activity.getSystemService(Context.SENSOR_SERVICE))
        if manager is None:
            _write_step_counter_state({'supported': False, 'status': 'Sensor manager unavailable.'})
            return False
        sensor = manager.getDefaultSensor(Sensor.TYPE_STEP_COUNTER)
        if sensor is None:
            _write_step_counter_state({'supported': False, 'status': 'Step counter sensor not available on this device.'})
            return False

        class StepListener(PythonJavaClass):
            __javainterfaces__ = ['android/hardware/SensorEventListener']
            __javacontext__ = 'app'

            @java_method('(Landroid/hardware/SensorEvent;)V')
            def onSensorChanged(self, event):
                try:
                    values = event.values
                    raw_total = int(float(values[0]))
                    payload = read_step_counter_state()
                    payload.update({'supported': True, 'raw_total': raw_total, 'status': 'active', 'updated_at': __import__('datetime').datetime.now().isoformat()})
                    _write_step_counter_state(payload)
                except Exception:
                    pass

            @java_method('(Landroid/hardware/Sensor;I)V')
            def onAccuracyChanged(self, sensor, accuracy):
                try:
                    payload = read_step_counter_state()
                    payload.update({'supported': True, 'accuracy': int(accuracy), 'updated_at': __import__('datetime').datetime.now().isoformat()})
                    _write_step_counter_state(payload)
                except Exception:
                    pass

        listener = StepListener()
        ok = bool(manager.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_NORMAL))
        if ok:
            _STEP_COUNTER_REFS.update({'started': True, 'manager': manager, 'listener': listener})
            payload = read_step_counter_state()
            payload.update({'supported': True, 'status': 'listening', 'updated_at': __import__('datetime').datetime.now().isoformat()})
            _write_step_counter_state(payload)
            return True
    except Exception as exc:
        _write_step_counter_state({'supported': False, 'status': f'Step counter failed: {exc}'})
    return False


def stop_step_counter_listener() -> bool:
    if not is_android():
        return False
    try:
        manager = _STEP_COUNTER_REFS.get('manager')
        listener = _STEP_COUNTER_REFS.get('listener')
        if manager is not None and listener is not None:
            manager.unregisterListener(listener)
        _STEP_COUNTER_REFS.clear()
        payload = read_step_counter_state()
        payload.update({'status': 'stopped'})
        _write_step_counter_state(payload)
        return True
    except Exception:
        return False
