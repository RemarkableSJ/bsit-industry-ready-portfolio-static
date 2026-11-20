from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

STATE_PATH = Path.home() / '.buo_background_service.json'
STEP_PATH = Path.home() / '.buo_steps.json'

try:
    from plyer import notification
except Exception:
    notification = None


def notify(title: str, message: str) -> None:
    if notification is None:
        return
    try:
        notification.notify(title=title, message=message, app_name='Buo', timeout=5)
    except Exception:
        pass


def load_json(path: Path) -> dict:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_json(path: Path, payload: dict) -> None:
    try:
        path.write_text(json.dumps(payload), encoding='utf-8')
    except Exception:
        pass


def process_reminders(state: dict) -> None:
    now = datetime.now()
    current_hm = now.strftime('%H:%M')
    current_day = now.strftime('%Y-%m-%d')
    changed = False
    for reminder in state.get('reminders', []) or []:
        if not reminder.get('enabled', 1):
            continue
        if reminder.get('time') == current_hm and reminder.get('last_sent_on') != current_day:
            notify('Buo motivation', f"{reminder.get('label', 'Show up for yourself today.')} • {current_hm}")
            reminder['last_sent_on'] = current_day
            changed = True
    if changed:
        save_json(STATE_PATH, state)


def start_step_listener_android() -> bool:
    try:
        from jnius import autoclass, PythonJavaClass, java_method, cast
        PythonService = autoclass('org.kivy.android.PythonService')
        Context = autoclass('android.content.Context')
        Sensor = autoclass('android.hardware.Sensor')
        SensorManager = autoclass('android.hardware.SensorManager')
        service = PythonService.mService
        context = service.getApplicationContext()
        manager = cast('android.hardware.SensorManager', context.getSystemService(Context.SENSOR_SERVICE))
        if manager is None:
            save_json(STEP_PATH, {'supported': False, 'status': 'Sensor manager unavailable.'})
            return False
        sensor = manager.getDefaultSensor(Sensor.TYPE_STEP_COUNTER)
        if sensor is None:
            save_json(STEP_PATH, {'supported': False, 'status': 'Step counter sensor unavailable.'})
            return False

        class StepListener(PythonJavaClass):
            __javainterfaces__ = ['android/hardware/SensorEventListener']
            __javacontext__ = 'app'

            @java_method('(Landroid/hardware/SensorEvent;)V')
            def onSensorChanged(self, event):
                try:
                    raw_total = int(float(event.values[0]))
                    payload = load_json(STEP_PATH)
                    payload.update({
                        'supported': True,
                        'raw_total': raw_total,
                        'status': 'background_listening',
                        'updated_at': datetime.now().isoformat(),
                    })
                    save_json(STEP_PATH, payload)
                except Exception:
                    pass

            @java_method('(Landroid/hardware/Sensor;I)V')
            def onAccuracyChanged(self, sensor, accuracy):
                try:
                    payload = load_json(STEP_PATH)
                    payload.update({'accuracy': int(accuracy), 'updated_at': datetime.now().isoformat()})
                    save_json(STEP_PATH, payload)
                except Exception:
                    pass

        listener = StepListener()
        ok = bool(manager.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_NORMAL))
        if ok:
            globals()['_step_manager'] = manager
            globals()['_step_listener'] = listener
            payload = load_json(STEP_PATH)
            payload.update({'supported': True, 'status': 'background_listening', 'updated_at': datetime.now().isoformat()})
            save_json(STEP_PATH, payload)
            return True
    except Exception as exc:
        save_json(STEP_PATH, {'supported': False, 'status': f'Background step listener failed: {exc}'})
    return False


def build_tracking_message(state: dict, step_state: dict) -> str:
    mode = state.get('detected_activity') or state.get('mode', 'Strength Training')
    elapsed = int(state.get('elapsed_seconds', 0) or 0)
    mins, secs = divmod(max(0, elapsed), 60)
    hr = state.get('avg_hr')
    raw_total = step_state.get('raw_total')
    start_raw = state.get('start_step_raw')
    workout_steps = None
    try:
        if raw_total is not None and start_raw is not None:
            workout_steps = max(0, int(raw_total) - int(start_raw))
    except Exception:
        workout_steps = None
    pieces = [
        f'{mode} • {mins:02d}:{secs:02d}',
        'Strength-only background mode active',
    ]
    if hr:
        pieces.append(f'avg HR {int(hr)}')
    if workout_steps is not None:
        pieces.append(f'steps {int(workout_steps):,}')
    return ' • '.join(pieces)

def main() -> None:
    start_step_listener_android()
    last_tracking_sent = 0.0
    while True:
        state = load_json(STATE_PATH)
        if state.get('command') == 'stop':
            break
        step_state = load_json(STEP_PATH)
        if state.get('active'):
            now = time.time()
            if now - last_tracking_sent >= 30:
                notify('Buo tracking', build_tracking_message(state, step_state))
                last_tracking_sent = now
            state['last_background_tick'] = datetime.now().isoformat()
            if step_state.get('raw_total') is not None:
                state['background_raw_steps'] = int(step_state.get('raw_total'))
            save_json(STATE_PATH, state)
        process_reminders(state)
        time.sleep(5)


if __name__ == '__main__':
    main()
