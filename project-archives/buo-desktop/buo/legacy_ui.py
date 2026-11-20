from __future__ import annotations

import csv
import json
import math
import re
import sqlite3
import os
import webbrowser
import time
from datetime import datetime, timedelta
from statistics import median
from pathlib import Path
from urllib.parse import quote
from typing import Dict, Optional, List

from kivy.app import App
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.utils import platform

from buo.platform_services import (
    is_android,
    request_android_permissions as service_request_android_permissions,
    send_local_notification as service_send_local_notification,
    read_step_counter_state as service_read_step_counter_state,
    start_step_counter_listener,
    stop_step_counter_listener,
)

try:
    import requests
except Exception:
    requests = None

from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle

from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager
from kivy.uix.widget import Widget

from buo.config import DB_PATH, CLOUD_CONFIG_PATH, LOCAL_CLOUD_DIR

def _gemini_generate_content(model, api_key, payload):
    """Call Gemini without putting the secret API key in the request URL.

    Retry transient service/network failures with exponential backoff.
    The returned error text is safe to display because the key is never part
    of the URL or the diagnostic message.
    """
    if requests is None:
        raise RuntimeError('The requests package is not available.')

    model_name = str(model or 'gemini-3.8-flash').strip()
    if not model_name:
        model_name = 'gemini-3.8-flash'
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model_name, safe='')}:generateContent"
    headers = {
        'x-goog-api-key': str(api_key).strip(),
        'Content-Type': 'application/json',
    }
    retry_delays = (1.5, 3.0)
    retryable_statuses = {429, 500, 502, 503, 504}

    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45)
        except Exception as exc:
            if attempt < 2:
                time.sleep(retry_delays[attempt])
                continue
            raise RuntimeError(f'Network error contacting Gemini ({type(exc).__name__}). Check your internet connection and try again.') from exc

        if response.status_code in retryable_statuses and attempt < 2:
            time.sleep(retry_delays[attempt])
            continue

        if response.status_code >= 400:
            message = ''
            try:
                error_data = response.json().get('error', {})
                message = str(error_data.get('message') or error_data.get('status') or '').strip()
            except Exception:
                message = ''
            if not message:
                message = 'The server returned an error without a readable message.'
            raise RuntimeError(f'Gemini API HTTP {response.status_code}: {message}')

        try:
            return response.json()
        except Exception as exc:
            raise RuntimeError('Gemini returned an unreadable response.') from exc

    raise RuntimeError('Gemini is temporarily unavailable after retrying. Please try again later.')

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return 0.0

def parse_time_12h_or_24h(time_text: str) -> Optional[str]:
    raw = (time_text or '').strip()
    if not raw:
        return None
    for pattern in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            return datetime.strptime(raw.upper(), pattern).strftime('%H:%M')
        except ValueError:
            pass
    return None


def readiness_color_for(value: int) -> list[float]:
    if value >= 80:
        return [0.20, 0.78, 0.44, 1]
    if value >= 65:
        return [0.95, 0.67, 0.20, 1]
    return [0.90, 0.29, 0.25, 1]

class RoutePreview(Widget):
    points_data = ListProperty([])

    def on_size(self, *_):
        self.redraw()

    def on_pos(self, *_):
        self.redraw()

    def on_points_data(self, *_):
        self.redraw()

    def redraw(self):
        self.canvas.after.clear()
        with self.canvas.after:
            app = App.get_running_app()
            border = getattr(app, 'border_color', [1, 1, 1, 0.08]) if app else [1, 1, 1, 0.08]
            panel = getattr(app, 'panel_color', [0.10, 0.12, 0.18, 1]) if app else [0.10, 0.12, 0.18, 1]
            accent = getattr(app, 'accent_color', [0.99, 0.39, 0.16, 1]) if app else [0.99, 0.39, 0.16, 1]
            Color(*panel)
            Rectangle(pos=self.pos, size=self.size)
            Color(*border)
            Line(rectangle=(self.x + 2, self.y + 2, max(0, self.width - 4), max(0, self.height - 4)), width=1.1)
            pad = 14
            mid_y = self.y + self.height * 0.55
            left_x = self.x + pad
            right_x = self.x + self.width - pad
            Color(*accent)
            Line(points=[left_x, mid_y, right_x, mid_y], width=2.0)
            Ellipse(pos=(left_x - 4, mid_y - 4), size=(8, 8))
            Ellipse(pos=(right_x - 4, mid_y - 4), size=(8, 8))



class MiniBarChart(Widget):
    values = ListProperty([])
    labels = ListProperty([])
    accent_rgba = ListProperty([0.96, 0.40, 0.18, 1])
    max_value = NumericProperty(0)
    show_empty_baseline = BooleanProperty(False)

    def on_size(self, *_): self.redraw()
    def on_pos(self, *_): self.redraw()
    def on_values(self, *_): self.redraw()
    def on_max_value(self, *_): self.redraw()
    def on_accent_rgba(self, *_): self.redraw()

    def redraw(self):
        self.canvas.after.clear()
        vals = []
        for v in (self.values or []):
            try:
                vals.append(max(0.0, float(v or 0)))
            except Exception:
                vals.append(0.0)
        if not vals:
            return
        with self.canvas.after:
            Color(0.08, 0.10, 0.15, 1)
            Rectangle(pos=self.pos, size=self.size)
            count = len(vals)
            gap = 8
            pad = 12
            chart_h = max(1, self.height - pad * 2 - 14)
            usable_w = max(1, self.width - pad * 2 - gap * (count - 1))
            bar_w = max(6, usable_w / max(1, count))
            fixed_max = float(self.max_value or 0)
            data_max = max(vals) if vals else 0.0
            scale_max = fixed_max if fixed_max > 0 else data_max
            scale_max = max(scale_max, 1.0)
            for idx, value in enumerate(vals):
                x = self.x + pad + idx * (bar_w + gap)
                Color(0.18, 0.22, 0.30, 1)
                Rectangle(pos=(x, self.y + pad), size=(bar_w, chart_h))
                if value <= 0:
                    continue
                ratio = max(0.0, min(1.0, value / scale_max))
                h = max(3 if fixed_max > 0 else 6, ratio * chart_h)
                Color(*self.accent_rgba)
                Rectangle(pos=(x, self.y + pad), size=(bar_w, h))



def date_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")



def request_android_permissions() -> None:
    service_request_android_permissions()


def send_local_notification(title: str, message: str) -> None:
    service_send_local_notification(title, message)

def read_step_counter_state() -> dict:
    try:
        data = service_read_step_counter_state()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def read_step_counter_raw_total() -> int | None:
    payload = read_step_counter_state()
    try:
        raw = payload.get('raw_total')
        return int(raw) if raw is not None else None
    except Exception:
        return None


def step_counter_status_text() -> str:
    payload = read_step_counter_state()
    if not payload:
        return 'Step counter idle.'
    if payload.get('supported') is False:
        return str(payload.get('status') or 'Step counter unsupported on this device.')
    raw = payload.get('raw_total')
    if raw is None:
        return 'Step counter ready. Waiting for first sensor sample.'
    return f"Step counter active • raw total {int(raw):,}"


def safe_row_value(row, key: str, default=0):
    try:
        if row is None:
            return default
        if hasattr(row, 'keys') and key in row.keys():
            value = row[key]
            return default if value is None else value
        value = row[key]
        return default if value is None else value
    except Exception:
        return default


def is_real_strength_recovery_reason(reason: str) -> bool:
    text = str(reason or '').lower()
    legacy_markers = [
        'low hydration', 'hydration', 'recovery reset', 'balanced baseline',
        'no check-in', 'incomplete strength recovery check-in',
        'old recovery data', 'recovery readiness'
    ]
    if any(item in text for item in legacy_markers):
        return False
    real_markers = [
        'sleep ', 'quality ', 'soreness ', 'joints ', 'performance ',
        'stress ', 'strong sleep duration', 'good sleep duration',
        'borderline sleep', 'balanced recovery inputs', 'weekly sets',
        'weekly volume', 'rir'
    ]
    return any(item in text for item in real_markers)


def readiness_for_chart(value, reason: str) -> int:
    try:
        score = max(0, min(100, int(value or 0)))
    except Exception:
        score = 0
    return score if is_real_strength_recovery_reason(reason) else 0


def sanitize_recovery_reason(reason: str) -> str:
    text = str(reason or '').strip()
    if not text:
        return ''
    replacements = {
        'low hydration': 'old recovery data; save a new strength recovery check-in',
        'Low hydration': 'Old recovery data; save a new strength recovery check-in',
        'hydration': 'old recovery data',
        'Hydration': 'Old recovery data',
        'water intake': 'old recovery data',
        'Water intake': 'Old recovery data',
        'glasses of water': 'old recovery data',
        'glass of water': 'old recovery data',
        'recovery readiness': 'old recovery data',
        'Recovery readiness': 'Old recovery data',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text



def classify_cardio_speed(speed_kmh: float | None) -> str:
    return 'Support Work'

def show_message(title: str, body: str):
    """Show long AI/tool responses in a scrollable dialog."""
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.scrollview import ScrollView

    wrap = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))
    scroll = ScrollView(
        do_scroll_x=False,
        do_scroll_y=True,
        bar_width=dp(7),
        scroll_type=['bars', 'content'],
    )
    message = Label(
        text=body or '',
        color=(1, 1, 1, 1),
        size_hint=(1, None),
        halign='left',
        valign='top',
        padding=(dp(12), dp(12)),
    )

    def update_text_width(widget, width):
        widget.text_size = (max(dp(1), width - dp(24)), None)

    def update_text_height(widget, texture_size):
        widget.height = max(dp(40), texture_size[1] + dp(24))

    message.bind(width=update_text_width, texture_size=update_text_height)
    scroll.add_widget(message)
    wrap.add_widget(scroll)

    popup = Popup(
        title=title,
        content=wrap,
        size_hint=(0.92, 0.76),
        separator_height=0,
        auto_dismiss=True,
    )
    popup.open()

def sanitize_key(value: str) -> str:
    value = (value or '').strip().lower()
    return re.sub(r'[^a-z0-9._-]+', '_', value) or 'user'






_ANDROID_DIALOGS = []


def open_embedded_web_screen(url: str, title: str = "Connect") -> bool:
    if not is_android():
        try:
            return bool(webbrowser.open(url))
        except Exception:
            return False
    try:
        from jnius import autoclass  # type: ignore[reportMissingImports], PythonJavaClass, java_method, cast

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Dialog = autoclass('android.app.Dialog')
        LinearLayout = autoclass('android.widget.LinearLayout')
        Button = autoclass('android.widget.Button')
        WebView = autoclass('android.webkit.WebView')
        WebViewClient = autoclass('android.webkit.WebViewClient')
        LayoutParams = autoclass('android.view.ViewGroup$LayoutParams')
        LinearLayoutParams = autoclass('android.widget.LinearLayout$LayoutParams')

        activity = cast('android.app.Activity', PythonActivity.mActivity)

        class Runnable(PythonJavaClass):
            __javainterfaces__ = ['java/lang/Runnable']
            __javacontext__ = 'app'
            def __init__(self, fn):
                super().__init__()
                self.fn = fn
            @java_method('()V')
            def run(self):
                self.fn()

        class ClickListener(PythonJavaClass):
            __javainterfaces__ = ['android/view/View$OnClickListener']
            __javacontext__ = 'app'
            def __init__(self, fn):
                super().__init__()
                self.fn = fn
            @java_method('(Landroid/view/View;)V')
            def onClick(self, view):
                self.fn()

        def _ui():
            dialog = Dialog(activity)
            dialog.setTitle(title)
            root = LinearLayout(activity)
            root.setOrientation(1)

            top = LinearLayout(activity)
            top.setOrientation(0)
            close_btn = Button(activity)
            close_btn.setText('Close')
            open_btn = Button(activity)
            open_btn.setText('Open external')
            top.addView(close_btn, LinearLayoutParams(0, LayoutParams.WRAP_CONTENT, 1.0))
            top.addView(open_btn, LinearLayoutParams(0, LayoutParams.WRAP_CONTENT, 1.0))

            web = WebView(activity)
            settings = web.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setLoadWithOverviewMode(True)
            settings.setUseWideViewPort(True)
            try:
                settings.setSupportMultipleWindows(False)
                settings.setJavaScriptCanOpenWindowsAutomatically(True)
                settings.setBuiltInZoomControls(False)
                settings.setDisplayZoomControls(False)
            except Exception:
                pass
            web.setWebViewClient(WebViewClient())
            try:
                web.setWebChromeClient(autoclass('android.webkit.WebChromeClient')())
            except Exception:
                pass
            web.loadUrl(url)

            close_listener = ClickListener(lambda: dialog.dismiss())
            open_listener = ClickListener(lambda: open_external_uri(url))
            close_btn.setOnClickListener(close_listener)
            open_btn.setOnClickListener(open_listener)

            # Keep Python-side references alive while dialog is open
            dialog._py_refs = (close_listener, open_listener)
            _ANDROID_DIALOGS.append(dialog)

            root.addView(top, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
            root.addView(web, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))
            dialog.setContentView(root)
            dialog.show()
            try:
                dialog.getWindow().setLayout(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT)
            except Exception:
                pass

        activity.runOnUiThread(Runnable(_ui))
        return True
    except Exception:
        return open_external_uri(url)


def open_social_in_app(channel: str) -> bool:
    urls = {
        'whatsapp': 'https://web.whatsapp.com/',
        'telegram': 'https://web.telegram.org/a/',
        'messenger': 'https://www.messenger.com/',
        'discord': 'https://discord.com/app',
    }
    return open_embedded_web_screen(urls.get(channel, 'https://discord.com/app'), f'{channel.title()} inside Buo')

def open_external_uri(uri: str) -> bool:
    try:
        if is_android():
            from jnius import autoclass  # type: ignore[reportMissingImports], cast
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            Uri = autoclass('android.net.Uri')
            activity = PythonActivity.mActivity
            intent = Intent(Intent.ACTION_VIEW, Uri.parse(uri))
            current = cast('android.app.Activity', activity)
            current.startActivity(intent)
            return True
    except Exception:
        pass
    try:
        return bool(webbrowser.open(uri))
    except Exception:
        return False


def android_share_text(subject: str, body: str) -> bool:
    if is_android():
        try:
            from jnius import autoclass  # type: ignore[reportMissingImports], cast
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            String = autoclass('java.lang.String')
            activity = PythonActivity.mActivity
            intent = Intent()
            intent.setAction(Intent.ACTION_SEND)
            intent.setType(String('text/plain'))
            intent.putExtra(Intent.EXTRA_SUBJECT, String(subject))
            intent.putExtra(Intent.EXTRA_TEXT, String(body))
            chooser = Intent.createChooser(intent, String('Share your progress'))
            current = cast('android.app.Activity', activity)
            current.startActivity(chooser)
            return True
        except Exception:
            pass
    return open_external_uri('mailto:?subject=' + quote(subject) + '&body=' + quote(body))


def build_personal_share_text(app) -> str:
    user = app.current_user()
    name = user['display_name'] if user else 'Athlete'
    totals = app.db.weekly_totals(app.current_user_id)
    records = app.db.get_records(app.current_user_id)
    journal = app.db.journal_entries(app.current_user_id, limit=1)
    lines = [
        f"{name}'s private Buo check-in",
        f"This week: {totals['lifts']} strength session(s), {totals.get('sets', 0)} hard set(s), and {totals.get('volume', 0):.0f} kg volume logged.",
    ]
    if records.get('longest_lift'):
        lines.append(f"Best current record: {records['longest_lift']}.")
    if journal:
        j = journal[0]
        lines.append(f"Latest journal note: {j['title']} — {j['body'][:140].strip()}")
    lines.append('Shared from my private Buo journal.')
    return "\n".join(lines)

def build_static_map_url(points, width: int = 900, height: int = 420) -> str:
    return ''

def build_route_browser_url(points):
    return ''

def build_gpx(points, name: str = 'Buo Route') -> str:
    return ''

def safe_write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def summarize_achievements(records: Dict[str, str]) -> str:
    lines = []
    if records.get('longest_lift'):
        lines.append(f"🏅 Best progression marker: {records['longest_lift']}")
    if records.get('fastest_pace'):
        lines.append(f"⚡ Best intensity marker: {records['fastest_pace']}")
    if records.get('biggest_strength'):
        lines.append(f"🏋️ Biggest strength day: {records['biggest_strength']}")
    if records.get('highest_elevation'):
        lines.append(f"⛰️ Best elevation gain: {records['highest_elevation']}")
    if records.get('gps_sessions'):
        lines.append(f"🗺️ Session routes saved: {records['gps_sessions']}")
    return '\n'.join(lines) if lines else 'No personal bests yet. Save a few sessions and your records will appear here.'



STRENGTH_TIPS = [
    (
        "How hard should I train?",
        "Leave around 1 to 3 reps in reserve on most work sets. This usually lets you train hard enough for strength and muscle while keeping form cleaner and recovery more manageable.",
    ),
    (
        "How many sets should I do?",
        "Start with a small number you can recover from, then build. Many lifters do well with a few hard sets per exercise and 2 or more strength sessions each week.",
    ),
    (
        "Do I need to lift to failure?",
        "Not every set. Failure can be useful sometimes, but doing every set to failure usually creates more fatigue than needed. Use it sparingly, especially on big compound lifts.",
    ),
    (
        "How long should I rest?",
        "For heavy compound lifts, 2 to 4 minutes often helps performance stay high. For smaller isolation work, 60 to 90 seconds can be enough.",
    ),
    (
        "How do I progressively overload?",
        "Add a little weight, an extra rep, an extra set, or improve technique at the same load. Progress is not only about heavier weights.",
    ),
    (
        "How much protein matters?",
        "A useful target for many active adults is roughly 1.4 to 2.0 grams of protein per kilogram of body weight per day, spread across meals.",
    ),
    (
        "Why is sleep affecting my lifts?",
        "Sleep strongly affects recovery, focus, mood, and effort tolerance. Poor sleep often shows up as lower readiness, worse bar speed, and more perceived fatigue.",
    ),
    (
        "Why track RIR and readiness?",
        "They help you avoid guessing. If RIR keeps dropping and readiness stays low, your app can warn you to reduce volume or intensity before performance falls off.",
    ),
]

RUNNING_TIPS = [
    (
        "How should I use support work in a strength-focused app?",
        "Use support work only as a helper for gym progress. Keep it light enough that it does not reduce strength performance or recovery quality.",
    ),
    (
        "What matters most for gym progress?",
        "The big drivers are progressive overload, enough weekly hard sets, enough time between overlapping sessions, and enough food, sleep, and consistency.",
    ),
    (
        "How often should I train each muscle?",
        "A good default is around twice per week for most muscles while still keeping weekly hard-set volume recoverable.",
    ),
    (
        "What should I track every week?",
        "Track exercises, sets, reps, load, RIR, recovery signals, and body-weight trend. Those are more useful for gym progress than random exhaustion.",
    ),
]



MOTIVATION_PROMPTS = [
    'Show up for yourself today. Small sessions still count.',
    'Consistency beats perfection. Start with the first 10 minutes.',
    'Train the version of you that you want to become.',
    'One clean set, one recovery choice, or one honest note is still progress.',
    'Do the basics well today: lift with control, recover, reflect, repeat.',
    'You do not need a perfect day. You need another honest rep.',
]

def pick_motivation(index: int = 0) -> str:
    if not MOTIVATION_PROMPTS:
        return 'Keep going.'
    return MOTIVATION_PROMPTS[index % len(MOTIVATION_PROMPTS)]
KV = r'''
#:import dp kivy.metrics.dp

<SFScreen@Screen>:
    canvas.before:
        Color:
            rgba: app.bg_color
        Rectangle:
            pos: self.pos
            size: self.size

<SFCard@BoxLayout>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(14)
    spacing: dp(10)
    canvas.before:
        Color:
            rgba: app.card_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [18, 18, 18, 18]
        Color:
            rgba: app.border_color3
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 18)
            width: 1.0

<SFPanel@BoxLayout>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(12)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: app.panel_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [14, 14, 14, 14]
        Color:
            rgba: app.border_color2
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 14)
            width: 1.0

<SFTitle@Label>:
    color: app.text_color
    font_size: '22sp'
    bold: True
    halign: 'left'
    valign: 'middle'
    text_size: self.width, None
    size_hint_y: None
    height: max(dp(30), self.texture_size[1])

<SFSubtitle@Label>:
    color: app.secondary_text_color
    font_size: '15sp'
    halign: 'left'
    valign: 'middle'
    text_size: self.width, None
    size_hint_y: None
    height: max(dp(24), self.texture_size[1])

<SFCaption@Label>:
    color: app.muted_text_color
    font_size: '13sp'
    halign: 'left'
    valign: 'middle'
    text_size: self.width, None
    size_hint_y: None
    height: max(dp(20), self.texture_size[1])

<SFValue@Label>:
    color: app.text_color
    font_size: '18sp'
    bold: True
    halign: 'left'
    valign: 'middle'
    text_size: self.width, None
    size_hint_y: None
    height: max(dp(26), self.texture_size[1])

<SFButton@Button>:
    size_hint_y: None
    height: dp(46)
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    color: app.button_text_color
    bold: True
    font_size: '15sp'
    canvas.before:
        Color:
            rgba: app.accent_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [14, 14, 14, 14]

<SFGhostButton@Button>:
    size_hint_y: None
    height: dp(44)
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    color: app.button_text_color
    font_size: '15sp'
    canvas.before:
        Color:
            rgba: app.panel_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [14, 14, 14, 14]
        Color:
            rgba: app.border_color4
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 14)
            width: 1.0

<SFInput@TextInput>:
    multiline: False
    size_hint_y: None
    height: dp(48)
    padding: [dp(12), dp(12), dp(12), dp(12)]
    foreground_color: app.input_text_color
    hint_text_color: app.hint_text_color
    background_normal: ''
    background_active: ''
    background_color: 0, 0, 0, 0
    cursor_color: app.text_color
    canvas.before:
        Color:
            rgba: app.panel_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [12, 12, 12, 12]
        Color:
            rgba: app.border_color3
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 12)
            width: 1.0

<SFScroll@ScrollView>:
    do_scroll_x: False
    bar_width: dp(4)

<SFHeaderBar@BoxLayout>:
    size_hint_y: None
    height: dp(64)
    spacing: dp(10)
    padding: dp(4), dp(4)


<SectionCard@BoxLayout>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(14)
    spacing: dp(10)
    canvas.before:
        Color:
            rgba: app.card_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [18, 18, 18, 18]
        Color:
            rgba: app.border_color3
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 18)
            width: 1.05

<PrimaryButton@Button>:
    size_hint_y: None
    height: dp(48)
    background_normal: ''
    background_down: ''
    bold: True
    font_size: '15sp'
    color: app.button_text_color
    background_color: app.accent_color
    canvas.before:
        Color:
            rgba: self.background_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [14, 14, 14, 14]

<GhostButton@Button>:
    size_hint_y: None
    height: dp(44)
    background_normal: ''
    background_down: ''
    color: app.button_text_color
    background_color: app.button_alt_color
    canvas.before:
        Color:
            rgba: self.background_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [14, 14, 14, 14]
        Color:
            rgba: app.border_color4
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 16)
            width: 1

<AppInput@TextInput>:
    multiline: False
    size_hint_y: None
    height: dp(46)
    padding: [dp(14), dp(13), dp(14), dp(13)]
    foreground_color: app.input_text_color
    hint_text_color: app.hint_text_color
    background_color: 0, 0, 0, 0
    background_normal: ''
    background_active: ''
    cursor_color: app.accent_color
    canvas.before:
        Color:
            rgba: app.input_bg_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [16, 16, 16, 16]
        Color:
            rgba: app.border_color5
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 16)
            width: 1

<StatPill@BoxLayout>:
    orientation: 'vertical'
    padding: dp(12)
    spacing: dp(4)
    canvas.before:
        Color:
            rgba: app.pill_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [18, 18, 18, 18]

<RoutePreview>:
    size_hint_y: None
    height: dp(186)
    canvas.before:
        Color:
            rgba: app.input_bg_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [20, 20, 20, 20]
        Color:
            rgba: app.border_color
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 20)
            width: 1

<MiniBarChart>:
    size_hint_y: None
    height: dp(160)
    canvas.before:
        Color:
            rgba: app.input_bg_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [20, 20, 20, 20]



<SplashScreen>:
    name: 'splash'
    canvas.before:
        Color:
            rgba: app.bg_color
        Rectangle:
            pos: self.pos
            size: self.size

    FloatLayout:
        Image:
            id: splash_logo
            source: 'assets/icon.png'
            size_hint: None, None
            size: dp(118), dp(118)
            x: -self.width - dp(60)
            center_y: root.height * 0.54

        Label:
            id: splash_title
            text: 'Buo'
            color: app.text_color
            bold: True
            font_size: '28sp'
            halign: 'left'
            valign: 'middle'
            text_size: None, None
            size_hint: None, None
            size: self.texture_size
            x: root.width + dp(60)
            center_y: root.height * 0.57

        Label:
            id: splash_verse
            text: '1 Corinthians 6:19–20 "Your body is a temple of the Holy Spirit."'
            color: app.secondary_text_color
            font_size: '15sp'
            halign: 'left'
            valign: 'middle'
            text_size: dp(250), None
            size_hint: None, None
            size: dp(250), self.texture_size[1]
            x: root.width + dp(60)
            center_y: root.height * 0.47

<LoginScreen>:
    name: 'login'
    SFScreen:
        BoxLayout:
            orientation: 'vertical'
            padding: dp(20)
            spacing: dp(14)

            Widget:
                size_hint_y: 0.15

            SFCard:
                SFTitle:
                    text: 'Buo'
                    font_size: '30sp'
                    halign: 'center'
                    valign: 'middle'
                    text_size: self.width, None
                    height: max(dp(40), self.texture_size[1])

                SFSubtitle:
                    text: 'Strength training progress, gym planning, recovery, and private progress tracking built for daily use.'
                    halign: 'center'
                    text_size: self.width, None
                    height: self.texture_size[1]

                SFPanel:
                    SFSubtitle:
                        text: 'Unlock your profile or create a local one'
                        valign: 'middle'
                        text_size: self.width, None
                        height: max(dp(28), self.texture_size[1])
                    SFInput:
                        id: login_name
                        hint_text: 'Display name'
                    SFInput:
                        id: login_password
                        hint_text: 'Passcode'
                        password: True
                    SFButton:
                        text: 'Unlock'
                        on_release: root.login(login_name.text, login_password.text)
                    SFGhostButton:
                        text: 'Save profile'
                        on_release: root.register(login_name.text, login_password.text)
                    SFCaption:
                        text: root.login_status
                        halign: 'left'
                        text_size: self.width, None
                        height: self.texture_size[1]

            Widget:
<DashboardScreen>:
    name: 'dashboard'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size

        BoxLayout:
            size_hint_y: None
            height: dp(76)
            padding: dp(18), dp(16)
            spacing: dp(10)
            Label:
                text: 'Buo'
                bold: True
                font_size: '28sp'
                color: app.text_color
                halign: 'left'
                text_size: self.size
            GhostButton:
                text: 'Lock'
                size_hint_x: None
                width: dp(108)
                on_release: app.logout_user()

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(16)
                padding: dp(18), dp(10), dp(18), dp(24)

                SectionCard:
                    Label:
                        text: 'Workout timer'
                        bold: True
                        color: app.text_color
                        font_size: '22sp'
                        size_hint_y: None
                        height: self.texture_size[1]
                        halign: 'left'
                        text_size: self.width, None

                    Label:
                        text: root.rest_timer_name_text
                        bold: True
                        color: app.secondary_text_color
                        halign: 'center'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

                    Label:
                        text: root.rest_timer_text
                        bold: True
                        font_size: '56sp'
                        color: app.accent_text_color
                        size_hint_y: None
                        height: dp(86)
                        halign: 'center'
                        text_size: self.width, None

                    Label:
                        text: root.rest_timer_status
                        color: app.subtle_text_color
                        halign: 'center'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        AppInput:
                            id: timer_name
                            hint_text: 'Timer name, e.g. Warm-up set'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: timer_time
                            hint_text: 'Time: 30s, 2m, 3m, 2:30'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)

                    GridLayout:
                        cols: 3
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        GhostButton:
                            text: 'Warm-up 30s'
                            on_release: root.set_named_timer('Warm-up set', '30s')
                        GhostButton:
                            text: 'Work set 2m'
                            on_release: root.set_named_timer('Working set', '2m')
                        GhostButton:
                            text: 'Heavy set 3m'
                            on_release: root.set_named_timer('Heavy set', '3m')

                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        PrimaryButton:
                            text: 'Start timer'
                            on_release: root.start_named_timer(timer_name.text, timer_time.text)
                        GhostButton:
                            text: 'Pause / Resume'
                            on_release: root.toggle_rest_timer()
                        GhostButton:
                            text: 'Reset timer'
                            on_release: root.reset_rest_timer()
                        GhostButton:
                            text: 'Log set now'
                            on_release: root.log_set_now()

                    Label:
                        text: root.set_counter_text
                        bold: True
                        color: app.text_color
                        halign: 'center'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

                    GhostButton:
                        text: 'Reset set counter'
                        on_release: root.reset_set_counter()

                SectionCard:
                    Label:
                        text: 'Time calculator'
                        bold: True
                        color: app.text_color
                        font_size: '20sp'
                        size_hint_y: None
                        height: self.texture_size[1]
                        halign: 'left'
                        text_size: self.width, None
                    Label:
                        text: 'Enter start and end time. Example: fast or sleep from 12:00 AM to 10:00 AM.'
                        color: app.muted_color
                        size_hint_y: None
                        height: self.texture_size[1]
                        halign: 'left'
                        text_size: self.width, None
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        AppInput:
                            id: time_start
                            hint_text: 'Start, e.g. 12:00 AM'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: time_end
                            hint_text: 'End, e.g. 10:00 AM'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                    Spinner:
                        id: time_purpose
                        text: 'Fasting'
                        values: ['Fasting', 'Sleep', 'Workout window', 'Study / work block', 'Custom']
                        size_hint_y: None
                        height: dp(44)
                    PrimaryButton:
                        text: 'Calculate duration'
                        on_release: root.calculate_time_between(time_start.text, time_end.text, time_purpose.text)
                    Label:
                        text: root.time_calc_result
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

                SectionCard:
                    Label:
                        text: 'Profile & Settings'
                        bold: True
                        color: app.text_color
                        font_size: '18sp'
                        size_hint_y: None
                        height: self.texture_size[1]
                        halign: 'left'
                        text_size: self.width, None
                    AppInput:
                        id: profile_name
                        hint_text: 'New display name'
                    AppInput:
                        id: profile_password
                        hint_text: 'New passcode'
                        password: True
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        PrimaryButton:
                            text: 'Update Profile'
                            on_release: root.update_profile(profile_name.text, profile_password.text)
                        GhostButton:
                            text: root.theme_mode_text
                            on_release: root.toggle_theme()
                    Label:
                        text: root.profile_status
                        color: app.subtle_text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                        halign: 'left'
                        text_size: self.width, None

                SectionCard:
                    Label:
                        text: 'Gym shortcuts'
                        bold: True
                        color: app.text_color
                        font_size: '20sp'
                        size_hint_y: None
                        height: self.texture_size[1]
                        halign: 'left'
                        text_size: self.width, None
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        GhostButton:
                            text: 'Strength log'
                            on_release: app.open_screen('strength')
                        GhostButton:
                            text: 'Workout maker'
                            on_release: app.open_screen('tips')
                        GhostButton:
                            text: 'Recovery'
                            on_release: app.open_screen('wellness')
                        GhostButton:
                            text: 'Analytics'
                            on_release: app.open_screen('analytics')
                        GhostButton:
                            text: 'Training plan'
                            on_release: app.open_screen('plans')
                        GhostButton:
                            text: 'Records'
                            on_release: app.open_screen('records')
                        GhostButton:
                            text: 'Journal'
                            on_release: app.open_screen('journal')
                        GhostButton:
                            text: 'Backup'
                            on_release: app.open_screen('sync')

<RecordsScreen>:
    name: 'records'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Records & milestones'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)
                SectionCard:
                    Label:
                        text: 'Personal records'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.records_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Milestones'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.milestones_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Lifetime totals'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.lifetime_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

<LiveMonitorScreen>:
    name: 'live'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Live strength session'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)
                SectionCard:
                    Label:
                        text: 'Session setup'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Spinner:
                        id: live_mode
                        text: 'Strength Training'
                        values: ['Strength Training']
                        size_hint_y: None
                        height: dp(44)
                    Label:
                        text: root.live_status
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        PrimaryButton:
                            text: 'Start session'
                            on_release: root.start_live(live_mode.text)
                        GhostButton:
                            text: 'Pause / Resume'
                            on_release: root.toggle_pause()
                        GhostButton:
                            text: 'Finish & save'
                            on_release: root.finish_session()
                        GhostButton:
                            text: 'Reset session'
                            on_release: root.reset_session()
                SectionCard:
                    Label:
                        text: 'Live inputs'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    AppInput:
                        id: live_distance
                        hint_text: 'Session note or top set marker'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: live_hr
                        hint_text: 'Heart rate (optional)'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: live_weight
                        hint_text: 'Weight (kg) • strength only'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: live_reps
                        hint_text: 'Reps • strength only'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: live_rir
                        hint_text: 'RIR • strength only'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    PrimaryButton:
                        text: 'Update session note'
                        on_release: root.update_live(live_distance.text, live_hr.text)
                    GhostButton:
                        text: 'Log set'
                        on_release: root.log_live_strength_set(live_weight.text, live_reps.text, live_rir.text)
                SectionCard:
                    Label:
                        text: root.live_metrics
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.live_tip
                        color: 0.94, 0.78, 0.58, 1
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]


                SectionCard:
                    Label:
                        text: 'Strength session panel'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.gps_signal_text
                        color: root.gps_signal_color
                        bold: True
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.gps_status
                        color: 0.75, 0.83, 0.92, 1
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    RoutePreview:
                        id: route_preview
                    Label:
                        text: 'Track set quality, load, reps, RIR, and pacing between sets. Outdoor route and location tracking have been removed.'
                        color: 0.6, 0.66, 0.75, 1
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

<ActivityScreen>:
    name: 'activity'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Strength support log'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)
                SectionCard:
                    Label:
                        text: 'Log support work that helps your strength progress'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Spinner:
                        id: activity_type
                        text: 'Mobility'
                        values: ['Mobility', 'Conditioning', 'Recovery Circuit']
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: distance_input
                        hint_text: 'Session minutes or volume note'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: duration_input
                        hint_text: 'Duration in minutes'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: avg_hr_input
                        hint_text: 'Average heart rate (optional)'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: notes_input
                        hint_text: 'Notes'
                        multiline: True
                        size_hint_y: None
                        height: dp(100)
                    PrimaryButton:
                        text: 'Save support session'
                        on_release: root.save_activity(activity_type.text, distance_input.text, duration_input.text, avg_hr_input.text, notes_input.text)
                SectionCard:
                    Label:
                        text: root.summary_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

<StrengthScreen>:
    name: 'strength'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Strength log'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)
                SectionCard:
                    Label:
                        text: 'Log a strength session'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    AppInput:
                        id: exercise_input
                        hint_text: 'Exercise name'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: sets_input
                        hint_text: 'Sets'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: reps_input
                        hint_text: 'Reps per set'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: weight_input
                        hint_text: 'Weight in kg'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: rir_input
                        hint_text: 'RIR (0-5)'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    PrimaryButton:
                        text: 'Save strength entry'
                        on_release: root.save_strength(exercise_input.text, sets_input.text, reps_input.text, weight_input.text, rir_input.text)
                SectionCard:
                    Label:
                        text: root.monitor_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

<WellnessScreen>:
    name: 'wellness'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Strength recovery'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)

                SectionCard:
                    Label:
                        text: 'Strength recovery check-in'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.recovery_status
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        AppInput:
                            id: sleep_hours_input
                            hint_text: 'Sleep hours, e.g. 7.5'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: sleep_quality_input
                            hint_text: 'Sleep quality 1-5'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: soreness_input
                            hint_text: 'Muscle soreness 1-5'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: joint_input
                            hint_text: 'Joint discomfort 1-5'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: performance_input
                            hint_text: 'Warm-up/performance readiness 1-5'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: stress_input
                            hint_text: 'Stress / mental fatigue 1-5'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)

                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        StatPill:
                            size_hint_y: None
                            height: dp(84)
                            Label:
                                text: 'Readiness'
                                color: app.muted_color
                            Label:
                                text: root.readiness_score_text
                                bold: True
                                font_size: '24sp'
                                color: root.readiness_color
                        StatPill:
                            size_hint_y: None
                            height: dp(84)
                            Label:
                                text: 'Training decision'
                                color: app.muted_color
                            Label:
                                text: root.readiness_band_text
                                bold: True
                                font_size: '18sp'
                                color: root.readiness_color

                    Label:
                        text: root.readiness_reason_text
                        color: root.readiness_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

                    Label:
                        text: 'Readiness trend • last 14 days'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    MiniBarChart:
                        values: root.readiness_values
                        accent_rgba: root.readiness_color
                        max_value: 100
                    Label:
                        text: root.readiness_labels
                        color: app.subtle_text_color
                        halign: 'center'
                        text_size: self.width, None
                        font_size: '13sp'
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.readiness_trend_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

                    GridLayout:
                        cols: 1
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        PrimaryButton:
                            text: 'Save strength recovery'
                            on_release: root.save_strength_recovery(sleep_hours_input.text, sleep_quality_input.text, soreness_input.text, joint_input.text, performance_input.text, stress_input.text)
                        GhostButton:
                            text: 'Reset recovery check-in'
                            on_release: root.reset_recovery()

                SectionCard:
                    Label:
                        text: 'Recovery action plan'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.recovery_action_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    GhostButton:
                        text: 'Refresh recovery coach'
                        on_release: root.refresh_recovery_ai()

                SectionCard:
                    Label:
                        text: 'Training reminder'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.reminder_status
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    AppInput:
                        id: med_name
                        hint_text: 'Goal or habit, e.g. Pull day, mobility, deload, sleep'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: med_time
                        hint_text: 'Time, e.g. 08:00 AM'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    GridLayout:
                        cols: 1
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        PrimaryButton:
                            text: 'Save reminder'
                            on_release: root.save_reminder(med_name.text, med_time.text)
                        GhostButton:
                            text: 'Enable reliable reminders'
                            on_release: app.prepare_reliable_reminders()
                        GhostButton:
                            text: 'Sync reminder engine'
                            on_release: app.sync_reminders_to_service()
                        GhostButton:
                            text: 'Reset reminders'
                            on_release: root.reset_reminders()
                    Label:
                        text: root.reminder_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

                SectionCard:
                    Label:
                        text: 'Smart injury risk warning'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.injury_risk_text
                        color: root.injury_risk_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

                SectionCard:
                    Label:
                        text: 'Recovery score AI coach'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.recovery_ai_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

<ReportsScreen>:
    name: 'reports'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Reports'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)
                SectionCard:
                    Label:
                        text: root.report_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    PrimaryButton:
                        text: 'Refresh'
                        on_release: root.refresh_report()
                    GhostButton:
                        text: 'Export summary as CSV'
                        on_release: root.export_report_csv()


<AnalyticsScreen>:
    name: 'analytics'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Analytics'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)
                SectionCard:
                    Label:
                        text: root.summary_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Quick view'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.kpi_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Strength sessions • last 7 days'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    MiniBarChart:
                        values: root.strength_session_values
                        max_value: 0
                    Label:
                        text: root.strength_labels
                        color: app.secondary_text_color if hasattr(app, 'secondary_text_color') else (0.70, 0.75, 0.84, 1)
                        halign: 'center'
                        text_size: self.width, None
                        font_size: '13sp'
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Strength volume • last 7 days'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    MiniBarChart:
                        values: root.strength_values
                        accent_rgba: [0.40, 0.73, 0.98, 1]
                        max_value: 0
                    Label:
                        text: root.strength_labels
                        color: app.secondary_text_color if hasattr(app, 'secondary_text_color') else (0.70, 0.75, 0.84, 1)
                        halign: 'center'
                        text_size: self.width, None
                        font_size: '13sp'
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Readiness trend • last 14 days'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    MiniBarChart:
                        values: root.readiness_values
                        accent_rgba: [0.58, 0.87, 0.55, 1]
                        max_value: 100
                    Label:
                        text: root.readiness_labels
                        color: app.secondary_text_color if hasattr(app, 'secondary_text_color') else (0.70, 0.75, 0.84, 1)
                        halign: 'center'
                        text_size: self.width, None
                        font_size: '13sp'
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.readiness_explain_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.trend_summary_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    GridLayout:
                        cols: 1
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        GhostButton:
                            text: 'Export analytics as JSON'
                            on_release: root.export_analytics_json()
                        GhostButton:
                            text: 'Export analytics as CSV'
                            on_release: root.export_analytics_csv()

<HistoryScreen>:
    name: 'history'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Lift history & progress'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)
                SectionCard:
                    Label:
                        text: 'Personal bests & milestones'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.pb_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Latest strength-session summary'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.route_summary
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Recent strength sessions'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.history_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

<SyncScreen>:
    name: 'sync'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Backup & sync'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)
                SectionCard:
                    Label:
                        text: 'Sync status'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.status_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    PrimaryButton:
                        text: 'Back up now'
                        on_release: root.backup_now()
                    GhostButton:
                        text: 'Restore latest backup'
                        on_release: root.restore_now()
                    GhostButton:
                        text: 'Export full data bundle'
                        on_release: root.export_bundle()
                    GhostButton:
                        text: 'Open export folder'
                        on_release: root.open_export_folder()
                SectionCard:
                    Label:
                        text: 'Release & store prep'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.release_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'How this works'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.info_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

<AutoHeightAnswerLabel@Label>:
    size_hint_y: None
    halign: 'left'
    valign: 'top'
    text_size: max(dp(1), self.width - dp(28)), None
    padding: [dp(14), dp(14)]
    height: max(dp(240), self.texture_size[1] + dp(28))
    color: 1, 1, 1, 1
    canvas.before:
        Color:
            rgba: [0.05, 0.09, 0.16, 1]
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [16, 16, 16, 16]
        Color:
            rgba: app.border_color5
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 16)
            width: 1

<TipsScreen>:
    name: 'tips'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Workout AI & smart tools'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            do_scroll_y: True
            bar_width: dp(8)
            scroll_type: ['bars', 'content']
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)

                SectionCard:
                    Label:
                        text: 'AI Mode'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.ai_status
                        color: app.secondary_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    BoxLayout:
                        orientation: 'horizontal'
                        size_hint_y: None
                        height: dp(42)
                        Widget:
                        Switch:
                            id: ai_switch_toggle
                            active: root.ai_switch
                            size_hint: None, None
                            size: dp(60), dp(32)
                            on_active: root.toggle_ai_switch(self.active)
                            canvas.before:
                                Color:
                                    rgba: (0.18, 0.78, 0.32, 1) if self.active else (0.88, 0.22, 0.22, 1)
                                RoundedRectangle:
                                    pos: self.pos
                                    size: self.size
                                    radius: [16, 16, 16, 16]
                        Widget:
                    Label:
                        text: root.ai_mode_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

                SectionCard:
                    Label:
                        text: 'Body recomposition calculator'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.recomp_status
                        color: app.secondary_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        AppInput:
                            id: recomp_age
                            hint_text: 'Age'
                        Spinner:
                            id: recomp_sex
                            text: 'Male'
                            values: ['Male', 'Female']
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: recomp_height
                            hint_text: 'Height in cm'
                        AppInput:
                            id: recomp_weight
                            hint_text: 'Weight in kg'
                        AppInput:
                            id: recomp_bodyfat
                            hint_text: 'Body fat %, optional'
                        AppInput:
                            id: recomp_days
                            hint_text: 'Training days / week'
                        Spinner:
                            id: recomp_focus
                            text: 'Recomposition'
                            values: ['Recomposition', 'Fat loss focus', 'Lean gain focus']
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: recomp_steps
                            hint_text: 'Average daily steps, optional'
                    PrimaryButton:
                        text: 'Calculate body recomposition'
                        on_release: root.calculate_body_recomp(recomp_age.text, recomp_sex.text, recomp_height.text, recomp_weight.text, recomp_bodyfat.text, recomp_days.text, recomp_focus.text, recomp_steps.text)
                    AutoHeightAnswerLabel:
                        text: root.recomp_result
                SectionCard:
                    Label:
                        text: 'AI calorie & protein planner'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.plan_status
                        color: app.secondary_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        AppInput:
                            id: plan_age
                            hint_text: 'Age'
                        Spinner:
                            id: plan_sex
                            text: 'Male'
                            values: ['Male', 'Female']
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: plan_height
                            hint_text: 'Height in cm'
                        AppInput:
                            id: plan_weight
                            hint_text: 'Weight in kg'
                        Spinner:
                            id: plan_activity
                            text: 'Moderately active'
                            values: ['Sedentary', 'Lightly active', 'Moderately active', 'Very active', 'Athlete']
                            size_hint_y: None
                            height: dp(44)
                        Spinner:
                            id: plan_goal
                            text: 'Calorie maintenance'
                            values: ['Calorie deficit', 'Calorie maintenance', 'Lean bulking', 'Bulking']
                            size_hint_y: None
                            height: dp(44)
                    PrimaryButton:
                        text: 'Calculate AI plan'
                        on_release: root.calculate_ai_plan(plan_age.text, plan_sex.text, plan_height.text, plan_weight.text, plan_activity.text, plan_goal.text)
                    AutoHeightAnswerLabel:
                        text: root.plan_result
                SectionCard:
                    Label:
                        text: 'AI nutrition plan'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.nutrition_status
                        color: app.secondary_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        Spinner:
                            id: nutrition_goal
                            text: 'Maintenance'
                            values: ['Deficit', 'Maintenance', 'Lean bulk', 'Bulk', 'Recomposition']
                            size_hint_y: None
                            height: dp(44)
                        Spinner:
                            id: nutrition_style
                            text: 'Balanced'
                            values: ['Balanced', 'High protein', 'Lower carb', 'Higher carb', 'Budget friendly']
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: nutrition_calories
                            hint_text: 'Target calories, optional'
                        AppInput:
                            id: nutrition_protein
                            hint_text: 'Protein grams, optional'
                        AppInput:
                            id: nutrition_meals
                            hint_text: 'Meals per day'
                        AppInput:
                            id: nutrition_restrictions
                            hint_text: 'Restrictions: halal, lactose free, etc.'
                            multiline: True
                            size_hint_y: None
                            height: dp(84)
                    PrimaryButton:
                        text: 'Generate AI nutrition plan'
                        on_release: root.generate_nutrition_plan(nutrition_goal.text, nutrition_style.text, nutrition_calories.text, nutrition_protein.text, nutrition_meals.text, nutrition_restrictions.text)
                    AutoHeightAnswerLabel:
                        text: root.nutrition_result
                SectionCard:
                    Label:
                        text: 'AI food nutrition analyzer'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.food_status
                        color: app.secondary_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    AppInput:
                        id: food_description
                        hint_text: 'Describe food and amount, e.g. 8 boiled egg whites for 439.2g'
                        multiline: True
                        size_hint_y: None
                        height: dp(100)
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: dp(48)
                        PrimaryButton:
                            text: 'Analyze food'
                            on_release: root.analyze_food(food_description.text)
                        GhostButton:
                            text: 'Clear food'
                            on_release: root.clear_food()
                    AutoHeightAnswerLabel:
                        text: root.food_result
                SectionCard:
                    Label:
                        text: 'AI fitness & health coach'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    AppInput:
                        id: ai_question
                        hint_text: 'Ask any fitness or health question'
                        multiline: True
                        size_hint_y: None
                        height: dp(110)
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: dp(48)
                        PrimaryButton:
                            text: 'Ask AI coach'
                            on_release: root.ask_ai(ai_question.text)
                        GhostButton:
                            text: 'Clear'
                            on_release: root.clear_ai()
                    AutoHeightAnswerLabel:
                        text: root.ai_answer
                SectionCard:
                    Label:
                        text: 'Smart AI workout maker'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.workout_status
                        color: app.secondary_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        Spinner:
                            id: wk_goal
                            text: 'Build muscle'
                            values: ['Build muscle', 'Strength + muscle', 'Body recomposition', 'Beginner gym progress']
                            size_hint_y: None
                            height: dp(44)
                        Spinner:
                            id: wk_level
                            text: 'Intermediate'
                            values: ['Beginner', 'Intermediate', 'Advanced']
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: wk_days
                            hint_text: 'Training days per week'
                        AppInput:
                            id: wk_minutes
                            hint_text: 'Minutes per session'
                        AppInput:
                            id: wk_rest
                            hint_text: 'Preferred rest days, e.g. Wed Sun'
                            multiline: True
                            size_hint_y: None
                            height: dp(84)
                        AppInput:
                            id: wk_notes
                            hint_text: 'Equipment, weak points, sore areas, schedule notes'
                            multiline: True
                            size_hint_y: None
                            height: dp(84)
                    PrimaryButton:
                        text: 'Generate smart workout'
                        on_release: root.generate_workout_maker(wk_goal.text, wk_level.text, wk_days.text, wk_minutes.text, wk_rest.text, wk_notes.text)
                    AutoHeightAnswerLabel:
                        text: root.workout_result
                SectionCard:
                    Label:
                        text: 'How this works'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.reference_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

<JournalScreen>:
    name: 'journal'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Training journal'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)

                SectionCard:
                    Label:
                        text: 'Strength reflection'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    AppInput:
                        id: journal_title
                        hint_text: 'Title, e.g. Push Day Check-in'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    Spinner:
                        id: journal_type
                        text: 'Workout Reflection'
                        values: ['Workout Reflection', 'Recovery Note', 'Technique Note', 'PR Attempt', 'Deload Note', 'Mindset Note']
                        size_hint_y: None
                        height: dp(44)
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        AppInput:
                            id: journal_energy
                            hint_text: 'Energy 1-5'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: journal_soreness
                            hint_text: 'Soreness 1-5'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                    AppInput:
                        id: journal_lesson
                        hint_text: 'What improved? What needs adjustment?'
                        multiline: True
                        size_hint_y: None
                        height: dp(96)
                    AppInput:
                        id: journal_next
                        hint_text: 'Next session focus, e.g. keep 2 RIR on bench'
                        multiline: True
                        size_hint_y: None
                        height: dp(96)
                    AppInput:
                        id: journal_body
                        hint_text: 'Full note'
                        multiline: True
                        size_hint_y: None
                        height: dp(130)
                    PrimaryButton:
                        text: 'Save training journal'
                        on_release: root.save_training_journal(journal_title.text, journal_type.text, journal_energy.text, journal_soreness.text, journal_lesson.text, journal_next.text, journal_body.text)
                    GhostButton:
                        text: 'Generate reflection prompt'
                        on_release: root.generate_reflection_prompt()
                    Label:
                        text: root.journal_status
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

                SectionCard:
                    Label:
                        text: 'Journal coach'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.journal_prompt_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

                SectionCard:
                    Label:
                        text: 'Recent reflections'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.entries_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]


<TabataScreen>:
    name: 'tabata'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Strength interval timer'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)
                SectionCard:
                    Label:
                        text: root.phase_text
                        bold: True
                        color: app.text_color
                        font_size: '22sp'
                        halign: 'center'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.timer_text
                        bold: True
                        font_size: '52sp'
                        color: app.accent_text_color
                        halign: 'center'
                        text_size: self.width, None
                        size_hint_y: None
                        height: dp(80)
                    Label:
                        text: root.round_text
                        color: app.secondary_text_color
                        halign: 'center'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.status_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Set intervals'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    GridLayout:
                        cols: 3
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        AppInput:
                            id: work_time
                            hint_text: 'Work, e.g. 30s'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: rest_time
                            hint_text: 'Rest, e.g. 90s'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                        AppInput:
                            id: rounds
                            hint_text: 'Rounds'
                            multiline: False
                            size_hint_y: None
                            height: dp(44)
                    GridLayout:
                        cols: 2
                        spacing: dp(10)
                        size_hint_y: None
                        height: self.minimum_height
                        PrimaryButton:
                            text: 'Start'
                            on_release: root.start_timer(work_time.text, rest_time.text, rounds.text)
                        GhostButton:
                            text: 'Pause'
                            on_release: root.pause_timer()
                        GhostButton:
                            text: 'Reset'
                            on_release: root.reset_timer()
                        GhostButton:
                            text: 'Default 30/90 x4'
                            on_release: root.configure_timer('30s', '90s', '4')

<ShareHubScreen>:
    name: 'sharehub'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Private sharing'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)
                SectionCard:
                    Label:
                        text: 'Keep everything private by default'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.privacy_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Share preview'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.share_preview
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    PrimaryButton:
                        text: 'Share to any installed app'
                        on_release: root.share_any()

                SectionCard:
                    Label:
                        text: 'Why this page exists'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.mode_notes
                        color: 0.75, 0.8, 0.9, 1
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]

<PlansScreen>:

    name: 'plans'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: app.bg_color
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(12)
            spacing: dp(10)
            GhostButton:
                text: '< Back'
                size_hint_x: None
                width: dp(108)
                on_release: app.open_screen('dashboard')
            Label:
                text: 'Goals & plans'
                bold: True
                color: app.text_color
                font_size: '22sp'
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: dp(16)
                spacing: dp(12)
                SectionCard:
                    Label:
                        text: 'Build a focused plan'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: 'Choose a goal, then tailor the plan by experience level, weekly time, and your own adjustment note.'
                        color: app.secondary_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                    Spinner:
                        id: plan_goal
                        text: 'Hypertrophy Block'
                        values: ['Hypertrophy Block', 'Strength Base', 'Strength PR Focus', 'Body Recomposition', 'Fat Loss', 'Muscle Gain', 'Return to Training']
                        size_hint_y: None
                        height: dp(44)
                    Spinner:
                        id: plan_level
                        text: 'Beginner'
                        values: ['Beginner', 'Intermediate', 'Advanced', 'Professional']
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: plan_weeks
                        hint_text: 'Plan length in weeks, e.g. 6 or 8'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: plan_days
                        hint_text: 'Training days per week'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: plan_time
                        hint_text: 'Minutes available per session, e.g. 45 or 60'
                        multiline: False
                        size_hint_y: None
                        height: dp(44)
                    AppInput:
                        id: plan_adjustments
                        hint_text: 'Adjustments: weak knees, prefers home workouts, busy schedule, wants more recovery, etc.'
                        multiline: True
                        size_hint_y: None
                        height: dp(84)
                    PrimaryButton:
                        text: 'Generate tailored plan'
                        on_release: root.generate_plan(plan_goal.text, plan_level.text, plan_weeks.text, plan_days.text, plan_time.text, plan_adjustments.text)
                SectionCard:
                    Label:
                        text: root.plan_summary
                        color: 0.93, 0.77, 0.58, 1
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Plan timeline'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.plan_phase_text
                        color: app.secondary_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Weekly calendar view'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.plan_calendar_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
                SectionCard:
                    Label:
                        text: 'Week-by-week details'
                        bold: True
                        color: app.text_color
                        size_hint_y: None
                        height: self.texture_size[1]
                    Label:
                        text: root.plan_text
                        color: app.subtle_text_color
                        halign: 'left'
                        text_size: self.width, None
                        size_hint_y: None
                        height: self.texture_size[1]
'''


class DB:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        cur = self.conn.cursor()
        cur.executescript(
            '''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                email TEXT UNIQUE,
                password TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_health (
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                steps INTEGER DEFAULT 0,
                water INTEGER DEFAULT 0,
                resting_hr INTEGER DEFAULT 70,
                readiness INTEGER DEFAULT 78,
                PRIMARY KEY (user_id, date)
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                distance_km REAL NOT NULL,
                duration_min REAL NOT NULL,
                avg_hr INTEGER,
                notes TEXT,
                estimated_steps INTEGER DEFAULT 0,
                effort_score REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS strength_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                exercise TEXT NOT NULL,
                sets INTEGER NOT NULL,
                reps INTEGER NOT NULL,
                weight REAL NOT NULL,
                rir INTEGER NOT NULL,
                volume REAL NOT NULL,
                load_score REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                reminder_time TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS activity_routes (
                activity_id INTEGER PRIMARY KEY,
                path_json TEXT NOT NULL,
                start_lat REAL,
                start_lon REAL,
                end_lat REAL,
                end_lon REAL,
                elevation_gain_m REAL DEFAULT 0,
                max_speed_kmh REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS social_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                body TEXT NOT NULL,
                linked_activity_id INTEGER,
                likes INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS social_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                body TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                metrics TEXT,
                linked_activity_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS training_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                goal TEXT NOT NULL,
                weeks INTEGER NOT NULL,
                days_per_week INTEGER NOT NULL,
                summary TEXT NOT NULL,
                plan_text TEXT NOT NULL
            );

CREATE TABLE IF NOT EXISTS personal_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    record_key TEXT NOT NULL,
    label TEXT NOT NULL,
    value_text TEXT NOT NULL,
    sort_value REAL NOT NULL,
    unit TEXT DEFAULT '',
    achieved_at TEXT NOT NULL,
    UNIQUE(user_id, category, record_key)
);

CREATE TABLE IF NOT EXISTS milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    milestone_key TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT DEFAULT '',
    achieved_at TEXT NOT NULL,
    UNIQUE(user_id, milestone_key)
);
            '''
        )
        self.conn.commit()
        self._ensure_columns()
        self.seed_default_user_if_empty()

    def _ensure_columns(self):
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(daily_health)").fetchall()}
        additions = {
            "sleep_hours": "REAL DEFAULT 7.0",
            "mood_score": "INTEGER DEFAULT 3",
            "energy_score": "INTEGER DEFAULT 3",
            "readiness_reason": "TEXT DEFAULT 'Balanced baseline. Log wellness and training to personalize this score.'",
            "updated_at": "TEXT DEFAULT ''",
        }
        for name, ddl in additions.items():
            if name not in existing:
                self.conn.execute(f"ALTER TABLE daily_health ADD COLUMN {name} {ddl}")
        act_existing = {row[1] for row in self.conn.execute("PRAGMA table_info(activities)").fetchall()}
        act_additions = {
            "workout_steps": "INTEGER DEFAULT 0",
            "calories": "REAL DEFAULT 0",
            "avg_speed_kmh": "REAL DEFAULT 0",
            "max_speed_kmh": "REAL DEFAULT 0",
            "elevation_gain_m": "REAL DEFAULT 0",
            "splits_json": "TEXT DEFAULT '[]'",
            "hr_samples_json": "TEXT DEFAULT '[]'",
            "injury_risk": "REAL DEFAULT 0",
            "training_load": "REAL DEFAULT 0",
        }
        for name, ddl in act_additions.items():
            if name not in act_existing:
                self.conn.execute(f"ALTER TABLE activities ADD COLUMN {name} {ddl}")
        dh2_additions = {
            "sensor_baseline": "INTEGER DEFAULT 0",
            "sensor_last_total": "INTEGER DEFAULT 0",
            "sensor_steps": "INTEGER DEFAULT 0",
        }
        for name, ddl in dh2_additions.items():
            if name not in existing:
                self.conn.execute(f"ALTER TABLE daily_health ADD COLUMN {name} {ddl}")
        rem_existing = {row[1] for row in self.conn.execute("PRAGMA table_info(reminders)").fetchall()}
        rem_additions = {
            "enabled": "INTEGER DEFAULT 1",
            "last_sent_on": "TEXT DEFAULT ''",
            "normalized_time": "TEXT DEFAULT ''",
        }
        for name, ddl in rem_additions.items():
            if name not in rem_existing:
                self.conn.execute(f"ALTER TABLE reminders ADD COLUMN {name} {ddl}")
        self.conn.commit()

    def seed_default_user_if_empty(self):
        """Production default: start clean. No seeded users, workouts, or plans."""
        return

    def insert_demo_pack(self, user_id: int):
        latest_activity_id = None
        for i in range(5, 0, -1):
            dt = (datetime.now() - timedelta(days=i)).replace(hour=6 + i, minute=15)
            distance = round(3.2 + i * 0.9, 1)
            duration = round(distance * (6.3 + i * 0.2), 1)
            effort = distance * 12 + i * 5
            steps = int(distance * 1312)
            cur = self.conn.execute(
                '''INSERT INTO activities(user_id, created_at, activity_type, distance_km, duration_min, avg_hr, notes, estimated_steps, effort_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (user_id, dt.isoformat(), 'Lift', distance, duration, 138 + i, 'DEMO: training session', steps, effort),
            )
            latest_activity_id = cur.lastrowid
            dkey = dt.strftime('%Y-%m-%d')
            self.conn.execute(
                '''INSERT OR REPLACE INTO daily_health(user_id, date, steps, water, resting_hr, readiness)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (user_id, dkey, steps, 5 + i % 3, 67 + i, 72 + i),
            )
        self.conn.execute(
            '''INSERT INTO journal_entries(user_id, created_at, category, title, body, metrics, linked_activity_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user_id, datetime.now().isoformat(), 'training', 'DEMO: sample journal', 'This is sample data for testing the layout. Turn off demo mode any time to clear it.', '', latest_activity_id),
        )
        self.conn.execute(
            'INSERT INTO training_plans(user_id, created_at, goal, weeks, days_per_week, summary, plan_text) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (user_id, datetime.now().isoformat(), 'Hypertrophy Block', 6, 4, 'DEMO: sample 5K progression block.', 'Week 1-2: Build easy volume and strides.\nWeek 3-4: Add one threshold workout.\nWeek 5: Peak quality, lower total volume slightly.\nWeek 6: Sharpen and taper.'),
        )
        self.conn.commit()

    def purge_demo_content(self, user_id: int | None = None):
        activity_sql = "DELETE FROM activities WHERE notes LIKE 'DEMO:%'"
        journal_sql = "DELETE FROM journal_entries WHERE title LIKE 'DEMO:%' OR body LIKE 'DEMO:%'"
        plan_sql = "DELETE FROM training_plans WHERE summary LIKE 'DEMO:%'"
        params = ()
        if user_id is not None:
            activity_sql += ' AND user_id = ?'
            journal_sql += ' AND user_id = ?'
            plan_sql += ' AND user_id = ?'
            params = (user_id,)
        self.conn.execute(activity_sql, params)
        self.conn.execute(journal_sql, params)
        self.conn.execute(plan_sql, params)
        self.conn.commit()

    def get_setting(self, key: str, default: str = '') -> str:
        row = self.conn.execute('SELECT setting_value FROM app_settings WHERE setting_key = ?', (key,)).fetchone()
        return row['setting_value'] if row else default

    def set_setting(self, key: str, value: str):
        self.conn.execute(
            'INSERT INTO app_settings(setting_key, setting_value) VALUES (?, ?) ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value',
            (key, value),
        )
        self.conn.commit()

    def get_demo_mode(self) -> bool:
        return self.get_setting('demo_mode', '0') == '1'

    def set_demo_mode(self, enabled: bool, user_id: int | None = None):
        self.set_setting('demo_mode', '1' if enabled else '0')
        if user_id is None:
            return
        if enabled:
            self.purge_demo_content(user_id)
            self.insert_demo_pack(user_id)
        else:
            self.purge_demo_content(user_id)

    def _make_local_key(self, display_name: str) -> str:
        cleaned = re.sub(r'[^a-z0-9]+', '-', (display_name or 'owner').lower()).strip('-')
        return f"{cleaned or 'owner'}@local.buo"

    def create_user(self, display_name: str, password: str) -> int:
        now = datetime.now().isoformat()
        display_name = display_name.strip()
        cur = self.conn.execute(
            'INSERT INTO users(display_name, email, password, created_at) VALUES (?, ?, ?, ?)',
            (display_name, self._make_local_key(display_name), password, now),
        )
        self.conn.commit()
        user_id = cur.lastrowid
        self.ensure_today(user_id)
        return user_id

    def authenticate(self, display_name: str, password: str):
        return self.conn.execute(
            'SELECT * FROM users WHERE lower(display_name) = ? AND password = ?',
            (display_name.lower().strip(), password),
        ).fetchone()

    def get_first_user(self):
        return self.conn.execute('SELECT * FROM users ORDER BY id LIMIT 1').fetchone()

    def update_user_credentials(self, user_id: int, display_name: str, password: str):
        display_name = display_name.strip()
        self.conn.execute(
            'UPDATE users SET display_name = ?, email = ?, password = ? WHERE id = ?',
            (display_name, self._make_local_key(display_name), password, user_id),
        )
        self.conn.commit()

    def upsert_single_local_profile(self, display_name: str, password: str) -> int:
        existing = self.get_first_user()
        if existing:
            self.update_user_credentials(int(existing['id']), display_name, password)
            return int(existing['id'])
        return self.create_user(display_name, password)

    def get_user(self, user_id: int):
        return self.conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    def ensure_today(self, user_id: int):
        self.conn.execute(
            '''INSERT OR IGNORE INTO daily_health(user_id, date, steps, water, resting_hr, readiness, sleep_hours, mood_score, energy_score, readiness_reason, updated_at, sensor_baseline, sensor_last_total, sensor_steps)
               VALUES (?, ?, 0, 0, 70, 78, 7.0, 3, 3, 'Balanced baseline. Log wellness and training to personalize this score.', ?, 0, 0, 0)''',
            (user_id, date_key(), datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_today(self, user_id: int):
        self.ensure_today(user_id)
        return self.conn.execute(
            'SELECT * FROM daily_health WHERE user_id = ? AND date = ?',
            (user_id, date_key()),
        ).fetchone()

    def update_today_steps(self, user_id: int, delta: int):
        self.ensure_today(user_id)
        self.conn.execute(
            'UPDATE daily_health SET steps = COALESCE(steps, 0) + ? WHERE user_id = ? AND date = ?',
            (delta, user_id, date_key()),
        )
        self.conn.commit()

    def add_water(self, user_id: int, delta: int = 1):
        self.ensure_today(user_id)
        self.conn.execute(
            'UPDATE daily_health SET water = COALESCE(water, 0) + ? WHERE user_id = ? AND date = ?',
            (delta, user_id, date_key()),
        )
        self.conn.commit()
        self.recalculate_readiness(user_id)

    def update_wellness(self, user_id: int, sleep_hours: float, mood_score: int, energy_score: int):
        self.ensure_today(user_id)
        self.conn.execute(
            "UPDATE daily_health SET sleep_hours = ?, mood_score = ?, energy_score = ?, updated_at = ? WHERE user_id = ? AND date = ?",
            (sleep_hours, mood_score, energy_score, datetime.now().isoformat(), user_id, date_key()),
        )
        self.conn.commit()
        return self.recalculate_readiness(user_id)

    def recalculate_readiness(self, user_id: int):
        self.ensure_today(user_id)
        today = self.get_today(user_id)
        since = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
        activity_row = self.conn.execute("SELECT COALESCE(SUM(effort_score),0) AS effort, COUNT(*) AS sessions FROM activities WHERE user_id = ? AND date(created_at) >= ?", (user_id, since)).fetchone()
        strength_row = self.conn.execute("SELECT COALESCE(SUM(load_score),0) AS load, COUNT(*) AS lifts FROM strength_logs WHERE user_id = ? AND date(created_at) >= ?", (user_id, since)).fetchone()
        sleep_hours = float(today["sleep_hours"] or 7.0)
        mood = int(today["mood_score"] or 3)
        energy = int(today["energy_score"] or 3)
        water = int(today["water"] or 0)
        resting_hr = int(today["resting_hr"] or 70)
        activity_effort = float(activity_row["effort"] or 0.0)
        weekly_sessions = int(activity_row["sessions"] or 0)
        strength_load = float(strength_row["load"] or 0.0)
        weekly_lifts = int(strength_row["lifts"] or 0)
        score = 72.0
        score += max(-12, min(12, (sleep_hours - 7.0) * 4.0))
        score += (mood - 3) * 4.0
        score += (energy - 3) * 5.0
        score += min(8, water * 1.3)
        score -= min(18, activity_effort / 18.0)
        score -= min(16, strength_load / 180.0)
        score -= max(0, weekly_sessions - 3) * 2.5
        score -= max(0, weekly_lifts - 2) * 2.0
        if resting_hr > 72:
            score -= min(8, (resting_hr - 72) * 0.6)
        readiness = max(25, min(100, int(round(score))))
        reasons = []
        if sleep_hours < 6.5:
            reasons.append(f"low sleep ({sleep_hours:.1f}h)")
        elif sleep_hours >= 8.0:
            reasons.append(f"strong sleep ({sleep_hours:.1f}h)")
        if water >= 6:
            reasons.append("good recovery readiness")
        elif water <= 2:
            reasons.append("recovery readiness")
        if mood <= 2:
            reasons.append("low mood")
        elif mood >= 4:
            reasons.append("positive mood")
        if energy <= 2:
            reasons.append("low energy")
        elif energy >= 4:
            reasons.append("good energy")
        if activity_effort >= 120:
            reasons.append("cardio fatigue")
        if strength_load >= 1200:
            reasons.append("strength fatigue")
        if not reasons:
            reasons.append("balanced baseline")
        reason_text = "Readiness drivers: " + ", ".join(reasons[:4]) + "."
        self.conn.execute("UPDATE daily_health SET readiness = ?, readiness_reason = ?, updated_at = ? WHERE user_id = ? AND date = ?", (readiness, reason_text, datetime.now().isoformat(), user_id, date_key()))
        self.conn.commit()
        return readiness, reason_text

    def reset_today_recovery(self, user_id: int):
        self.ensure_today(user_id)
        self.conn.execute(
            'UPDATE daily_health SET water = 0, resting_hr = 70, sleep_hours = 7.0, mood_score = 3, energy_score = 3, readiness = 78, readiness_reason = ?, updated_at = ? WHERE user_id = ? AND date = ?',
            ('Recovery reset to a balanced baseline.', datetime.now().isoformat(), user_id, date_key()),
        )
        self.conn.commit()


    def upsert_personal_record(self, user_id: int, category: str, record_key: str, label: str, value_text: str, sort_value: float, unit: str = '') -> bool:
        row = self.conn.execute(
            'SELECT sort_value FROM personal_records WHERE user_id = ? AND category = ? AND record_key = ?',
            (user_id, category, record_key),
        ).fetchone()
        improved = row is None or sort_value > float(row['sort_value'])
        if improved:
            self.conn.execute(
                "INSERT INTO personal_records(user_id, category, record_key, label, value_text, sort_value, unit, achieved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(user_id, category, record_key) DO UPDATE SET label = excluded.label, value_text = excluded.value_text, sort_value = excluded.sort_value, unit = excluded.unit, achieved_at = excluded.achieved_at",
                (user_id, category, record_key, label, value_text, float(sort_value), unit, datetime.now().isoformat()),
            )
            self.conn.commit()
        return improved

    def unlock_milestone(self, user_id: int, milestone_key: str, title: str, detail: str = '') -> bool:
        row = self.conn.execute(
            'SELECT id FROM milestones WHERE user_id = ? AND milestone_key = ?',
            (user_id, milestone_key),
        ).fetchone()
        if row:
            return False
        self.conn.execute(
            'INSERT INTO milestones(user_id, milestone_key, title, detail, achieved_at) VALUES (?, ?, ?, ?, ?)',
            (user_id, milestone_key, title, detail, datetime.now().isoformat()),
        )
        self.conn.commit()
        return True

    def evaluate_activity_records(self, user_id: int, activity_type: str, distance_km: float, duration_min: float):
        if distance_km <= 0 or duration_min <= 0:
            return []
        pace_min_per_km = duration_min / max(distance_km, 0.001)
        speed_score = 1.0 / pace_min_per_km
        self.upsert_personal_record(user_id, 'strength', 'longest_distance', 'Longest distance', f'{distance_km:.1f} km', distance_km, 'km')
        self.upsert_personal_record(user_id, 'strength', 'fastest_pace', 'Fastest pace', f'{pace_min_per_km:.2f} effort score', speed_score, 'effort score')
        race_marks = [(1, '1k_time', 'Fastest 1K'), (3, '3k_time', 'Fastest 3K'), (5, '5k_time', 'Fastest 5K'), (10, '10k_time', 'Fastest 10K')]
        for threshold, key, label in race_marks:
            if distance_km >= threshold:
                time_for_mark = pace_min_per_km * threshold
                self.upsert_personal_record(user_id, 'strength', key, label, f'{time_for_mark:.1f} min', 1.0 / time_for_mark, 'min')
        total_distance = float(self.conn.execute('SELECT COALESCE(SUM(distance_km), 0) AS total FROM activities WHERE user_id = ?', (user_id,)).fetchone()['total'] or 0)
        activity_count = int(self.conn.execute('SELECT COUNT(*) AS n FROM activities WHERE user_id = ?', (user_id,)).fetchone()['n'] or 0)
        if activity_count >= 1:
            self.unlock_milestone(user_id, 'first_activity', 'First activity logged', f'{activity_type} session recorded.')
        if distance_km >= 5:
            self.unlock_milestone(user_id, 'first_5k', 'First 5K completed', f'Session distance reached {distance_km:.1f} km.')
        if total_distance >= 50:
            self.unlock_milestone(user_id, 'distance_50', '50 km total distance', f'Lifetime cardio distance: {total_distance:.1f} km.')
        if total_distance >= 100:
            self.unlock_milestone(user_id, 'distance_100', '100 km total distance', f'Lifetime cardio distance: {total_distance:.1f} km.')
        if activity_count >= 10:
            self.unlock_milestone(user_id, 'activity_10', '10 cardio sessions', f'{activity_count} cardio sessions logged.')

    def evaluate_strength_records(self, user_id: int, exercise: str, sets: int, reps: int, weight: float, volume: float):
        if weight <= 0:
            return
        ex_key = sanitize_key(exercise)
        self.upsert_personal_record(user_id, 'strength', f'{ex_key}_max_weight', f'{exercise} max weight', f'{weight:.1f} kg', weight, 'kg')
        self.upsert_personal_record(user_id, 'strength', f'{ex_key}_max_volume', f'{exercise} max volume', f'{volume:.0f} kg volume', volume, 'kg volume')
        lift_count = int(self.conn.execute('SELECT COUNT(*) AS n FROM strength_logs WHERE user_id = ?', (user_id,)).fetchone()['n'] or 0)
        if lift_count >= 1:
            self.unlock_milestone(user_id, 'first_strength', 'First strength session', f'{exercise} logged.')
        thresholds = {
            'bench': (60, 'bench_60', 'Bench press 60 kg'),
            'squat': (100, 'squat_100', 'Squat 100 kg'),
            'deadlift': (140, 'deadlift_140', 'Deadlift 140 kg'),
        }
        lower = exercise.lower()
        for token, (target, key, title) in thresholds.items():
            if token in lower and weight >= target:
                self.unlock_milestone(user_id, key, title, f'{exercise} reached {weight:.1f} kg.')
        if lift_count >= 10:
            self.unlock_milestone(user_id, 'strength_10', '10 strength sessions', f'{lift_count} strength logs recorded.')

    def get_personal_records(self, user_id: int):
        return self.conn.execute('SELECT * FROM personal_records WHERE user_id = ? ORDER BY category, label', (user_id,)).fetchall()

    def get_milestones(self, user_id: int, limit: int = 20):
        return self.conn.execute('SELECT * FROM milestones WHERE user_id = ? ORDER BY datetime(achieved_at) DESC LIMIT ?', (user_id, limit)).fetchall()

    def sync_step_counter(self, user_id: int):
        self.ensure_today(user_id)
        raw = read_step_counter_raw_total()
        if raw is None:
            return None
        today = self.get_today(user_id)
        baseline = int(today['sensor_baseline'] or 0)
        if baseline <= 0 or raw < baseline:
            baseline = raw
        sensor_steps = max(0, raw - baseline)
        self.conn.execute(
            'UPDATE daily_health SET sensor_baseline = ?, sensor_last_total = ?, sensor_steps = ?, steps = CASE WHEN steps < ? THEN ? ELSE steps END WHERE user_id = ? AND date = ?',
            (baseline, raw, sensor_steps, sensor_steps, sensor_steps, user_id, date_key()),
        )
        self.conn.commit()
        return sensor_steps

    def get_sensor_lifetime_steps(self, user_id: int) -> int:
        row = self.conn.execute('SELECT COALESCE(SUM(sensor_steps),0) AS total FROM daily_health WHERE user_id = ?', (user_id,)).fetchone()
        return int(row['total'] or 0) if row else 0

    def get_lifetime_stats(self, user_id: int) -> dict:
        acts = self.conn.execute(
            'SELECT COUNT(*) AS sessions, COALESCE(SUM(duration_min),0) AS minutes, COALESCE(SUM(estimated_steps),0) AS steps FROM activities WHERE user_id = ?',
            (user_id,),
        ).fetchone()
        st = self.conn.execute(
            'SELECT COUNT(*) AS lifts, COALESCE(SUM(volume),0) AS volume, COALESCE(SUM(sets),0) AS sets, COALESCE(SUM(sets * reps),0) AS reps FROM strength_logs WHERE user_id = ?',
            (user_id,),
        ).fetchone()
        jr = self.conn.execute('SELECT COUNT(*) AS n FROM journal_entries WHERE user_id = ?', (user_id,)).fetchone()
        sensor_steps = self.get_sensor_lifetime_steps(user_id)
        return {
            'cardio_sessions': int(safe_row_value(acts, 'sessions', 0)),
            'distance': 0.0,
            'minutes': float(safe_row_value(acts, 'minutes', 0.0)),
            'steps': int(safe_row_value(acts, 'steps', 0)),
            'sensor_steps': int(sensor_steps or 0),
            'strength_sessions': int(safe_row_value(st, 'lifts', 0)),
            'volume': float(safe_row_value(st, 'volume', 0.0)),
            'sets': int(safe_row_value(st, 'sets', 0)),
            'reps': int(safe_row_value(st, 'reps', 0)),
            'journal_entries': int(safe_row_value(jr, 'n', 0)),
        }


    def clear_reminders(self, user_id: int):
        self.conn.execute('DELETE FROM reminders WHERE user_id = ?', (user_id,))
        self.conn.commit()

    def save_activity(self, user_id: int, activity_type: str, distance_km: float, duration_min: float, avg_hr: Optional[int], notes: str):
        step_factors = {'Walk': 1420, 'Jog': 1280, 'Lift': 1220}
        steps = int(distance_km * step_factors.get(activity_type, 1200))
        effort = round((distance_km * 10) + (duration_min * 0.7) + ((avg_hr or 130) - 90) * 0.4, 1)
        avg_speed = (distance_km / max(duration_min, 0.001)) * 60.0
        calories = round(distance_km * 70.0 * 1.036, 1)
        cur = self.conn.execute(
            "INSERT INTO activities(user_id, created_at, activity_type, distance_km, duration_min, avg_hr, notes, estimated_steps, effort_score, workout_steps, calories, avg_speed_kmh, max_speed_kmh, elevation_gain_m, splits_json, hr_samples_json, injury_risk, training_load) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, datetime.now().isoformat(), activity_type, distance_km, duration_min, avg_hr, notes, steps, effort, steps, calories, avg_speed, avg_speed, 0.0, '[]', json.dumps([avg_hr] if avg_hr else []), 0.0, effort),
        )
        activity_id = cur.lastrowid
        self.update_today_steps(user_id, steps)
        self.sync_step_counter(user_id)
        self.conn.commit()
        self.evaluate_activity_records(user_id, activity_type, distance_km, duration_min)
        self.recalculate_readiness(user_id)
        return steps, effort, activity_id

    def update_activity_metrics(self, activity_id: int, *, workout_steps: int | None = None, calories: float | None = None, avg_speed_kmh: float | None = None, max_speed_kmh: float | None = None, elevation_gain_m: float | None = None, splits_json: str | None = None, hr_samples_json: str | None = None, injury_risk: float | None = None, training_load: float | None = None):
        row = self.conn.execute('SELECT * FROM activities WHERE id = ?', (activity_id,)).fetchone()
        if not row:
            return
        def row_val(key, default):
            return row[key] if key in row.keys() and row[key] is not None else default
        payload = {
            'workout_steps': int(workout_steps if workout_steps is not None else row_val('workout_steps', 0)),
            'calories': float(calories if calories is not None else row_val('calories', 0.0)),
            'avg_speed_kmh': float(avg_speed_kmh if avg_speed_kmh is not None else row_val('avg_speed_kmh', 0.0)),
            'max_speed_kmh': float(max_speed_kmh if max_speed_kmh is not None else row_val('max_speed_kmh', 0.0)),
            'elevation_gain_m': float(elevation_gain_m if elevation_gain_m is not None else row_val('elevation_gain_m', 0.0)),
            'splits_json': splits_json if splits_json is not None else row_val('splits_json', '[]'),
            'hr_samples_json': hr_samples_json if hr_samples_json is not None else row_val('hr_samples_json', '[]'),
            'injury_risk': float(injury_risk if injury_risk is not None else row_val('injury_risk', 0.0)),
            'training_load': float(training_load if training_load is not None else row_val('training_load', 0.0)),
        }
        self.conn.execute(
            'UPDATE activities SET workout_steps=?, calories=?, avg_speed_kmh=?, max_speed_kmh=?, elevation_gain_m=?, splits_json=?, hr_samples_json=?, injury_risk=?, training_load=? WHERE id=?',
            (payload['workout_steps'], payload['calories'], payload['avg_speed_kmh'], payload['max_speed_kmh'], payload['elevation_gain_m'], payload['splits_json'], payload['hr_samples_json'], payload['injury_risk'], payload['training_load'], activity_id),
        )
        self.conn.commit()


    def save_route_data(self, activity_id: int, path_points, elevation_gain_m: float = 0.0, max_speed_kmh: float = 0.0):
        if not activity_id or not path_points or len(path_points) < 2:
            return
        start = path_points[0]
        end = path_points[-1]
        self.conn.execute(
            '''INSERT OR REPLACE INTO activity_routes(activity_id, path_json, start_lat, start_lon, end_lat, end_lon, elevation_gain_m, max_speed_kmh)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (activity_id, json.dumps(path_points), start[0], start[1], end[0], end[1], elevation_gain_m, max_speed_kmh),
        )
        self.conn.commit()

    def gps_session_count(self, user_id: int) -> int:
        row = self.conn.execute(
            '''SELECT COUNT(*) AS n FROM activities a
               JOIN activity_routes r ON r.activity_id = a.id
               WHERE a.user_id = ?''',
            (user_id,),
        ).fetchone()
        return int(row['n']) if row else 0

    def save_strength(self, user_id: int, exercise: str, sets: int, reps: int, weight: float, rir: int):
        volume = sets * reps * weight
        load = round(volume * (1.25 + max(0, 5 - rir) * 0.08), 1)
        self.conn.execute(
            '''INSERT INTO strength_logs(user_id, created_at, exercise, sets, reps, weight, rir, volume, load_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, datetime.now().isoformat(), exercise, sets, reps, weight, rir, volume, load),
        )
        self.conn.commit()
        self.evaluate_strength_records(user_id, exercise, sets, reps, weight, volume)
        self.recalculate_readiness(user_id)
        return volume, load

    def save_reminder(self, user_id: int, label: str, reminder_time: str):
        self.conn.execute(
            'INSERT INTO reminders(user_id, label, reminder_time, created_at, enabled, last_sent_on, normalized_time) VALUES (?, ?, ?, ?, 1, '', ?)',
            (user_id, label, reminder_time, datetime.now().isoformat(), parse_time_12h_or_24h(reminder_time) or ""),
        )
        self.conn.commit()

    def recent_activities(self, user_id: int, limit: int = 5):
        return self.conn.execute(
            'SELECT * FROM activities WHERE user_id = ? ORDER BY datetime(created_at) DESC LIMIT ?',
            (user_id, limit),
        ).fetchall()

    def recent_strength(self, user_id: int, limit: int = 5):
        return self.conn.execute(
            'SELECT * FROM strength_logs WHERE user_id = ? ORDER BY datetime(created_at) DESC LIMIT ?',
            (user_id, limit),
        ).fetchall()

    def reminder_list(self, user_id: int, limit: int = 5):
        return self.conn.execute(
            'SELECT * FROM reminders WHERE user_id = ? ORDER BY datetime(created_at) DESC LIMIT ?',
            (user_id, limit),
        ).fetchall()

    def weekly_totals(self, user_id: int) -> Dict[str, float]:
        since = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')
        strength = self.conn.execute(
            """SELECT COUNT(*) AS lifts, COALESCE(SUM(volume),0) AS volume, COALESCE(SUM(sets),0) AS sets,
                      COALESCE(SUM(sets * reps),0) AS reps, COALESCE(AVG(rir),0) AS avg_rir
               FROM strength_logs WHERE user_id = ? AND date(created_at) >= ?""",
            (user_id, since),
        ).fetchone()
        support = self.conn.execute(
            """SELECT COUNT(*) AS support_sessions, COALESCE(SUM(duration_min),0) AS support_minutes
               FROM activities WHERE user_id = ? AND date(created_at) >= ?""",
            (user_id, since),
        ).fetchone()
        water = self.conn.execute(
            'SELECT COALESCE(SUM(water),0) AS water FROM daily_health WHERE user_id = ? AND date >= ?',
            (user_id, since),
        ).fetchone()
        lifts = int(safe_row_value(strength, 'lifts', 0))
        volume = float(safe_row_value(strength, 'volume', 0.0))
        sets = int(safe_row_value(strength, 'sets', 0))
        reps = int(safe_row_value(strength, 'reps', 0))
        return {
            'sessions': lifts,
            'distance': 0.0,
            'duration': float(safe_row_value(support, 'support_minutes', 0.0)),
            'support_sessions': int(safe_row_value(support, 'support_sessions', 0)),
            'lifts': lifts,
            'volume': round(volume, 1),
            'sets': sets,
            'reps': reps,
            'avg_rir': round(float(safe_row_value(strength, 'avg_rir', 0.0)), 1),
            'water': int(safe_row_value(water, 'water', 0)),
        }


    def analytics_last_n_days(self, user_id: int, days: int = 7):
        rows = []
        for offset in range(days - 1, -1, -1):
            day = datetime.now() - timedelta(days=offset)
            dkey = day.strftime('%Y-%m-%d')
            st = self.conn.execute(
                """SELECT COUNT(*) AS lifts, COALESCE(SUM(volume),0) AS volume, COALESCE(SUM(sets),0) AS sets,
                          COALESCE(SUM(sets * reps),0) AS reps, COALESCE(AVG(rir),0) AS avg_rir
                   FROM strength_logs WHERE user_id = ? AND date(created_at) = ?""",
                (user_id, dkey),
            ).fetchone()
            dh = self.conn.execute(
                'SELECT readiness, readiness_reason FROM daily_health WHERE user_id = ? AND date = ?',
                (user_id, dkey),
            ).fetchone()
            rows.append({
                'date': dkey,
                'label': day.strftime('%a') if days <= 7 else day.strftime('%m/%d'),
                'distance': 0.0,
                'strength_sessions': int(safe_row_value(st, 'lifts', 0)),
                'strength_sets': int(safe_row_value(st, 'sets', 0)),
                'strength_reps': int(safe_row_value(st, 'reps', 0)),
                'strength_volume': round(float(safe_row_value(st, 'volume', 0.0)), 1),
                'avg_rir': round(float(safe_row_value(st, 'avg_rir', 0.0)), 1),
                'readiness': readiness_for_chart(safe_row_value(dh, 'readiness', 0), safe_row_value(dh, 'readiness_reason', '')),
                'reason': safe_row_value(dh, 'readiness_reason', ''),
            })
        return rows


    def analytics_last_7_days(self, user_id: int):
        return self.analytics_last_n_days(user_id, 7)

    def route_history(self, user_id: int, limit: int = 10):
        return self.conn.execute(
            """SELECT a.*, r.path_json, r.elevation_gain_m, r.max_speed_kmh
               FROM activities a
               JOIN activity_routes r ON r.activity_id = a.id
               WHERE a.user_id = ?
               ORDER BY datetime(a.created_at) DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()

    def get_records(self, user_id: int) -> Dict[str, str]:
        records: Dict[str, str] = {}

        strongest = self.conn.execute(
            'SELECT exercise, volume FROM strength_logs WHERE user_id = ? ORDER BY volume DESC LIMIT 1',
            (user_id,),
        ).fetchone()
        if strongest and safe_row_value(strongest, 'volume', 0):
            records['biggest_strength'] = f"{safe_row_value(strongest, 'exercise', 'Lift')} • {float(safe_row_value(strongest, 'volume', 0.0)):.0f} kg volume"

        heaviest = self.conn.execute(
            'SELECT exercise, weight, reps FROM strength_logs WHERE user_id = ? ORDER BY weight DESC LIMIT 1',
            (user_id,),
        ).fetchone()
        if heaviest and safe_row_value(heaviest, 'weight', 0):
            records['heaviest_lift'] = f"{safe_row_value(heaviest, 'exercise', 'Lift')} • {float(safe_row_value(heaviest, 'weight', 0.0)):.1f} kg x {int(safe_row_value(heaviest, 'reps', 0))}"

        most_sets = self.conn.execute(
            'SELECT exercise, sets FROM strength_logs WHERE user_id = ? ORDER BY sets DESC LIMIT 1',
            (user_id,),
        ).fetchone()
        if most_sets and safe_row_value(most_sets, 'sets', 0):
            records['most_sets'] = f"{safe_row_value(most_sets, 'exercise', 'Lift')} • {int(safe_row_value(most_sets, 'sets', 0))} sets"

        weekly = self.weekly_totals(user_id)
        if weekly.get('lifts', 0):
            records['weekly_volume'] = f"{weekly['volume']:.0f} kg this week across {weekly['sets']} sets"

        records['strength_sessions'] = str(self.conn.execute(
            'SELECT COUNT(*) AS n FROM strength_logs WHERE user_id = ?', (user_id,)
        ).fetchone()['n'] or 0)
        return records


    def export_user_bundle(self, user_id: int) -> Dict[str, object]:
        user = dict(self.get_user(user_id))
        tables = {}
        for table in ['daily_health', 'activities', 'strength_logs', 'reminders', 'journal_entries', 'training_plans']:
            rows = self.conn.execute(f'SELECT * FROM {table} WHERE user_id = ? ORDER BY rowid ASC', (user_id,)).fetchall()
            tables[table] = [dict(r) for r in rows]
        route_rows = self.conn.execute(
            """SELECT r.* FROM activity_routes r JOIN activities a ON a.id = r.activity_id
               WHERE a.user_id = ? ORDER BY a.created_at ASC""",
            (user_id,),
        ).fetchall()
        tables['activity_routes'] = [dict(r) for r in route_rows]
        return {'exported_at': datetime.now().isoformat(), 'user': user, 'tables': tables}

    def restore_user_bundle(self, current_user_id: int, bundle: Dict[str, object]) -> None:
        tables = bundle.get('tables', {}) if isinstance(bundle, dict) else {}
        self.conn.execute('DELETE FROM daily_health WHERE user_id = ?', (current_user_id,))
        self.conn.execute('DELETE FROM reminders WHERE user_id = ?', (current_user_id,))
        self.conn.execute('DELETE FROM strength_logs WHERE user_id = ?', (current_user_id,))
        self.conn.execute('DELETE FROM journal_entries WHERE user_id = ?', (current_user_id,))
        self.conn.execute('DELETE FROM training_plans WHERE user_id = ?', (current_user_id,))
        activity_ids = [r['id'] for r in self.conn.execute('SELECT id FROM activities WHERE user_id = ?', (current_user_id,)).fetchall()]
        for aid in activity_ids:
            self.conn.execute('DELETE FROM activity_routes WHERE activity_id = ?', (aid,))
        self.conn.execute('DELETE FROM activities WHERE user_id = ?', (current_user_id,))
        activity_id_map = {}
        for row in tables.get('activities', []):
            cur = self.conn.execute(
                """INSERT INTO activities(user_id, created_at, activity_type, distance_km, duration_min, avg_hr, notes, estimated_steps, effort_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (current_user_id, row['created_at'], row['activity_type'], row['distance_km'], row['duration_min'], row.get('avg_hr'), row.get('notes', ''), row.get('estimated_steps', 0), row.get('effort_score', 0)),
            )
            activity_id_map[row['id']] = cur.lastrowid
        for row in tables.get('activity_routes', []):
            new_id = activity_id_map.get(row['activity_id'])
            if new_id:
                self.conn.execute(
                    """INSERT INTO activity_routes(activity_id, path_json, start_lat, start_lon, end_lat, end_lon, elevation_gain_m, max_speed_kmh)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (new_id, row['path_json'], row.get('start_lat'), row.get('start_lon'), row.get('end_lat'), row.get('end_lon'), row.get('elevation_gain_m', 0), row.get('max_speed_kmh', 0)),
                )
        for row in tables.get('strength_logs', []):
            self.conn.execute(
                """INSERT INTO strength_logs(user_id, created_at, exercise, sets, reps, weight, rir, volume, load_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (current_user_id, row['created_at'], row['exercise'], row['sets'], row['reps'], row['weight'], row['rir'], row['volume'], row['load_score']),
            )
        for row in tables.get('reminders', []):
            self.conn.execute(
                'INSERT INTO reminders(user_id, label, reminder_time, created_at, enabled, last_sent_on, normalized_time) VALUES (?, ?, ?, ?, 1, '', ?)',
                (current_user_id, row['label'], row['reminder_time'], row['created_at']),
            )
        for row in tables.get('daily_health', []):
            self.conn.execute(
                """INSERT OR REPLACE INTO daily_health(user_id, date, steps, water, resting_hr, readiness)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (current_user_id, row['date'], row.get('steps', 0), row.get('water', 0), row.get('resting_hr', 70), row.get('readiness', 78)),
            )
        for row in tables.get('journal_entries', []):
            self.conn.execute(
                '''INSERT INTO journal_entries(user_id, created_at, category, title, body, metrics, linked_activity_id)
                   VALUES (?, ?, ?, ?, ?, ?, NULL)''',
                (current_user_id, row['created_at'], row.get('category', 'Lifestyle'), row.get('title', 'Journal entry'), row.get('body', ''), row.get('metrics', '')),
            )
        for row in tables.get('training_plans', []):
            self.conn.execute(
                '''INSERT INTO training_plans(user_id, created_at, goal, weeks, days_per_week, summary, plan_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (current_user_id, row['created_at'], row.get('goal', 'General Fitness'), row.get('weeks', 6), row.get('days_per_week', 4), row.get('summary', ''), row.get('plan_text', '')),
            )
        self.conn.commit()


    def create_post(self, user_id: int, body: str, linked_activity_id: Optional[int] = None):
        cur = self.conn.execute(
            'INSERT INTO social_posts(user_id, created_at, body, linked_activity_id, likes) VALUES (?, ?, ?, ?, 0)',
            (user_id, datetime.now().isoformat(), body.strip(), linked_activity_id),
        )
        self.conn.commit()
        return cur.lastrowid

    def social_feed(self, limit: int = 12):
        return self.conn.execute(
            '''SELECT p.*, u.display_name,
                      a.activity_type, a.distance_km, a.duration_min,
                      (SELECT COUNT(*) FROM social_comments c WHERE c.post_id = p.id) AS comment_count
               FROM social_posts p
               JOIN users u ON u.id = p.user_id
               LEFT JOIN activities a ON a.id = p.linked_activity_id
               ORDER BY datetime(p.created_at) DESC
               LIMIT ?''',
            (limit,),
        ).fetchall()

    def comment_list(self, post_id: int, limit: int = 3):
        return self.conn.execute(
            '''SELECT c.*, u.display_name FROM social_comments c
               JOIN users u ON u.id = c.user_id
               WHERE c.post_id = ?
               ORDER BY datetime(c.created_at) DESC
               LIMIT ?''',
            (post_id, limit),
        ).fetchall()

    def like_post(self, post_id: int):
        self.conn.execute('UPDATE social_posts SET likes = COALESCE(likes, 0) + 1 WHERE id = ?', (post_id,))
        self.conn.commit()

    def add_comment(self, post_id: int, user_id: int, body: str):
        self.conn.execute(
            'INSERT INTO social_comments(post_id, user_id, created_at, body) VALUES (?, ?, ?, ?)',
            (post_id, user_id, datetime.now().isoformat(), body.strip()),
        )
        self.conn.commit()

    def latest_post_id(self) -> Optional[int]:
        row = self.conn.execute('SELECT id FROM social_posts ORDER BY datetime(created_at) DESC LIMIT 1').fetchone()
        return int(row['id']) if row else None


    def save_journal_entry(self, user_id: int, category: str, title: str, body: str, metrics: str = '', linked_activity_id: Optional[int] = None):
        cur = self.conn.execute(
            '''INSERT INTO journal_entries(user_id, created_at, category, title, body, metrics, linked_activity_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user_id, datetime.now().isoformat(), category, title, body, metrics, linked_activity_id),
        )
        self.conn.commit()
        return cur.lastrowid

    def journal_entries(self, user_id: int, limit: int = 20):
        return self.conn.execute(
            '''SELECT j.*, a.activity_type, a.distance_km, a.duration_min
               FROM journal_entries j
               LEFT JOIN activities a ON a.id = j.linked_activity_id
               WHERE j.user_id = ?
               ORDER BY datetime(j.created_at) DESC
               LIMIT ?''',
            (user_id, limit),
        ).fetchall()

    def save_training_plan(self, user_id: int, goal: str, weeks: int, days_per_week: int, summary: str, plan_text: str):
        self.conn.execute(
            '''INSERT INTO training_plans(user_id, created_at, goal, weeks, days_per_week, summary, plan_text)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user_id, datetime.now().isoformat(), goal, weeks, days_per_week, summary, plan_text),
        )
        self.conn.commit()

    def latest_training_plan(self, user_id: int):
        return self.conn.execute(
            'SELECT * FROM training_plans WHERE user_id = ? ORDER BY datetime(created_at) DESC LIMIT 1',
            (user_id,),
        ).fetchone()

    def close(self):
        self.conn.close()

def build_coach_message(db: 'DB', user_id: int, readiness: int, sessions: int, lifts: int) -> dict:
    recents = db.recent_activities(user_id, 6)
    strength = db.recent_strength(user_id, 6)
    last_days = []
    for row in recents:
        try:
            last_days.append((datetime.now() - datetime.fromisoformat(row['created_at'])).days)
        except Exception:
            pass
    avg_effort = sum(float(r['effort_score'] or 0) for r in recents) / len(recents) if recents else 0.0
    total_volume = sum(float(r['volume'] or 0) for r in strength)
    if readiness >= 85 and avg_effort < 95:
        headline = 'Coach Pulse: green light for quality work.'
    elif readiness >= 70:
        headline = 'Coach Pulse: solid day for purposeful training.'
    elif readiness >= 55:
        headline = 'Coach Pulse: keep today controlled.'
    else:
        headline = 'Coach Pulse: recovery comes first today.'

    freshness = 'No recent sessions yet, so guidance is based on readiness and consistency.'
    if last_days:
        if min(last_days) == 0:
            freshness = 'You already trained today. Prioritize quality over extra volume.'
        elif min(last_days) == 1:
            freshness = 'Your last logged session was yesterday. Today can be either quality work or recovery, depending on how you feel.'
        else:
            freshness = f'Your last logged session was {min(last_days)} day(s) ago. Ease back in instead of jumping straight to max effort.'

    if sessions + lifts == 0:
        next_step = 'Start with one real session. Once you log consistent training, Coach Pulse can guide load, pacing, and recovery more accurately.'
    elif lifts > sessions:
        next_step = f'Recent strength volume is about {total_volume:.0f} kg. Keep 1 to 3 reps in reserve on most compound lifts unless today is meant to be hard.'
    else:
        next_step = f'Average recent cardio effort is {avg_effort:.0f}. Most lifts should stay easy enough that breathing is controlled and tomorrow still feels trainable.'

    detail = f"This week: {sessions} cardio session(s), {lifts} strength session(s). {freshness} {next_step}"
    return {'headline': headline, 'detail': detail}


def pick_live_tip(mode: str, elapsed_s: int, hr: Optional[int], pace_min_km: Optional[float], readiness: int) -> str:
    if mode in {'Strength Training'}:
        if elapsed_s < 300:
            return 'Live tip: Use the first few minutes for ramp-up sets, not max effort.'
        if readiness < 60:
            return 'Live tip: Readiness is low today. Keep 2 to 3 reps in reserve on most working sets.'
        return 'Live tip: Rest long enough to keep rep quality high, especially on big lifts.'
    if pace_min_km is not None and pace_min_km < 4.5 and hr and hr > 175:
        return 'Live tip: Pace and heart rate are both high. Check your form and avoid turning every lift into a race.'
    if elapsed_s < 600:
        return 'Live tip: Keep the first 10 minutes easy so your breathing and mechanics can settle in.'
    if readiness < 60:
        return 'Live tip: Lower readiness today. A steady easy lift or jog may be the smart call.'
    return 'Live tip: Most of your strength should feel controlled enough that you can still talk.'




class SplashScreen(Screen):
    _started = False

    def on_pre_enter(self, *args):
        self._started = False
        Clock.schedule_once(self.start_animation, 0.05)

    def start_animation(self, *_):
        if self._started:
            return
        self._started = True

        logo = self.ids.get('splash_logo')
        title = self.ids.get('splash_title')
        verse = self.ids.get('splash_verse')
        if not logo or not title or not verse:
            Clock.schedule_once(self.goto_login, 1.2)
            return

        logo.x = -logo.width - 60
        title.x = self.width + 60
        verse.x = self.width + 60
        verse.opacity = 1

        group_gap = 18
        text_gap = 8
        text_block_w = max(title.width, verse.width)
        total_w = logo.width + group_gap + text_block_w
        group_left = max(20, (self.width - total_w) / 2.0)

        target_logo_x = group_left
        target_text_x = target_logo_x + logo.width + group_gap
        title_target_y = self.height * 0.57 - title.height / 2.0
        verse_target_y = title_target_y - verse.height - text_gap

        logo.y = self.height * 0.54 - logo.height / 2.0
        title.y = title_target_y
        verse.y = verse_target_y

        Animation.cancel_all(logo)
        Animation.cancel_all(title)
        Animation.cancel_all(verse)

        Animation(x=target_logo_x, duration=0.78, t='out_cubic').start(logo)
        Animation(x=target_text_x, duration=0.78, t='out_cubic').start(title)
        Animation(x=target_text_x, duration=0.78, t='out_cubic').start(verse)
        Clock.schedule_once(self.goto_login, 1.70)

    def goto_login(self, *_):
        if self.manager and self.manager.has_screen('login'):
            self.manager.current = 'login'


class LoginScreen(Screen):
    login_status = StringProperty('Private mode: create your own display name and passcode on this device. First launch starts completely clean.')

    def login(self, display_name: str, password: str):
        if not display_name.strip() or not password.strip():
            self.login_status = 'Enter your display name and passcode.'
            return
        app = App.get_running_app()
        user = app.db.authenticate(display_name, password)
        if not user:
            self.login_status = 'Unlock failed. Check your display name and passcode.'
            return
        app.current_user_id = int(user['id'])
        self.login_status = f"Welcome back, {user['display_name']}."
        app.open_screen('dashboard')

    def register(self, display_name: str, password: str):
        if not display_name.strip() or not password.strip():
            self.login_status = 'Choose a display name and passcode first.'
            return
        app = App.get_running_app()
        user_id = app.db.upsert_single_local_profile(display_name.strip(), password)
        app.current_user_id = user_id
        self.login_status = 'Private profile saved on this device.'
        app.open_screen('dashboard')


class DashboardScreen(Screen):
    rest_timer_total_seconds = NumericProperty(120)
    rest_timer_name_text = StringProperty('Timer: Working set')
    rest_timer_text = StringProperty('02:00')
    rest_timer_status = StringProperty('Ready for your next set.')
    rest_timer_seconds = NumericProperty(120)
    rest_timer_running = BooleanProperty(False)
    set_counter = NumericProperty(0)
    set_counter_text = StringProperty('Sets completed: 0')
    time_calc_result = StringProperty('Use the calculator for fasting windows, sleep targets, or workout planning.')
    header_text = StringProperty('Buo')
    today_header = StringProperty('Today')
    today_subtitle = StringProperty('Build momentum with cardio, strength, and recovery.')
    steps_text = StringProperty('0')
    distance_text = StringProperty('0.0 km')
    water_text = StringProperty('0 glasses')
    readiness_text = StringProperty('0%')
    readiness_reason_text = StringProperty('Balanced baseline.')
    readiness_color = ListProperty([0.95, 0.67, 0.20, 1])
    coach_message = StringProperty('')
    coach_detail = StringProperty('Coach Pulse becomes smarter as you log real training, recovery readiness, and consistency.')
    profile_status = StringProperty('')
    theme_mode_text = StringProperty('Theme: Dark')
    recent_text = StringProperty('No activities yet.')
    profile_status = StringProperty('')
    theme_mode_text = StringProperty('Theme: Dark')

    def update_profile(self, display_name: str, password: str):
        app = App.get_running_app()

        if not display_name.strip() or not password.strip():
           self.profile_status = 'Enter both name and passcode.'
           return

        try:
            app.db.update_user_credentials(
                app.current_user_id,
                display_name.strip(),
                password
        )
            self.profile_status = 'Profile updated successfully.'
        except Exception as e:
            self.profile_status = f'Error: {e}'


    def toggle_theme(self):
        app = App.get_running_app()

        new_mode = 'light' if app.theme_mode == 'dark' else 'dark'
        app.set_theme_mode(new_mode)

        self.theme_mode_text = f"Theme: {new_mode.title()}"
        self.profile_status = f"Switched to {new_mode} mode."

    def update_profile(self, display_name: str, password: str):
        app = App.get_running_app()
        if not app.require_login():
            return
        if not display_name.strip() or not password.strip():
            self.profile_status = 'Enter both a display name and a passcode to update the local lock.'
            return
        app.db.update_user_credentials(app.current_user_id, display_name.strip(), password)
        self.profile_status = 'Private profile updated. Use the new display name and passcode next time you unlock the app.'
        self.on_pre_enter()

    def toggle_theme(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        app.set_theme_mode('light' if app.theme_mode == 'dark' else 'dark')
        self.profile_status = f"Theme switched to {app.theme_mode.title()}."
        self.on_pre_enter()

    def on_pre_enter(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        self.theme_mode_text = f"Theme: {app.theme_mode.title()}"
        app.db.recalculate_readiness(app.current_user_id)
        try:
            app.db.sync_step_counter(app.current_user_id)
        except Exception:
            pass
        app.db.recalculate_readiness(app.current_user_id)
        today = app.db.get_today(app.current_user_id)
        weekly = app.db.weekly_totals(app.current_user_id)
        recents = app.db.recent_activities(app.current_user_id, 4)
        user = app.db.get_user(app.current_user_id)
        display_name = safe_row_value(user, 'display_name', 'Athlete')
        self.header_text = f"Buo • {display_name}"
        if not self.profile_status:
            self.profile_status = f"Current local owner: {display_name}"
        self.today_header = f"Today • {datetime.now().strftime('%b %d, %Y')}"
        sensor_steps = int(safe_row_value(today, 'sensor_steps', 0))
        total_steps = max(int(safe_row_value(today, 'steps', 0)), sensor_steps)
        self.steps_text = f"{total_steps:,}"
        self.distance_text = f"{float(safe_row_value(weekly, 'distance', 0.0)):.1f} km"
        self.water_text = f"{int(safe_row_value(today, 'water', 0))} glasses"
        readiness = int(safe_row_value(today, 'readiness', 78))
        self.readiness_text = f"{readiness}%"
        self.readiness_reason_text = safe_row_value(today, 'readiness_reason', 'Balanced baseline.')
        self.readiness_color = readiness_color_for(readiness)
        coach = build_coach_message(app.db, app.current_user_id, readiness, int(safe_row_value(weekly, 'sessions', 0)), int(safe_row_value(weekly, 'lifts', 0)))
        self.coach_message = coach['headline']
        self.coach_detail = coach['detail']
        self.theme_mode_text = f"Theme: {app.theme_mode.title()}"
        self.today_subtitle = 'Local-first training dashboard with step sensor sync, smarter readiness, injury warning, and real-session-only history.'
        if recents:
            self.recent_text = '\n'.join(
                f"• {safe_row_value(row, 'activity_type', 'Activity')} • {float(safe_row_value(row, 'distance_km', 0.0)):.1f} km in {float(safe_row_value(row, 'duration_min', 0.0)):.0f} min • effort {float(safe_row_value(row, 'effort_score', 0.0)):.0f}"
                for row in recents
            )
        else:
            self.recent_text = 'No activities logged yet.'

    def _format_timer(self, seconds):
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def set_named_timer(self, name, duration):
        try:
            duration = duration.strip().lower()

            if duration.endswith('s'):
                seconds = int(duration[:-1])
            elif duration.endswith('m'):
                seconds = int(duration[:-1]) * 60
            elif ':' in duration:
                m, s = map(int, duration.split(':'))
                seconds = m * 60 + s
            else:
                seconds = int(duration) * 60

        except:
            show_message("Error", "Invalid time format (use 30s, 2m, 2:30)")
            return

        self.rest_timer_name_text = f"Timer: {name or 'Workout'}"
        self.rest_timer_total_seconds = seconds
        self.rest_timer_seconds = seconds
        self.rest_timer_text = self._format_timer(seconds)
        self.rest_timer_status = "Ready. Press Start timer."

    def start_named_timer(self, name, duration):
        if duration:
            self.set_named_timer(name, duration)

        if self.rest_timer_seconds <= 0:
            self.rest_timer_seconds = self.rest_timer_total_seconds

        self.rest_timer_running = True
        self.rest_timer_status = "Timer running..."

        try:
            if hasattr(self, "_timer_event"):
                self._timer_event.cancel()
        except:
            pass

        self._timer_event = Clock.schedule_interval(self._tick_timer, 1)

    def _tick_timer(self, dt):
        if not self.rest_timer_running:
            return

        self.rest_timer_seconds -= 1
        self.rest_timer_text = self._format_timer(self.rest_timer_seconds)

        if self.rest_timer_seconds <= 0:
            self.rest_timer_running = False
            self.set_counter += 1
            self.set_counter_text = f"Sets completed: {self.set_counter}"
            self.rest_timer_status = "Done! Set logged."

            try:
                self._timer_event.cancel()
            except:
                pass

    def toggle_rest_timer(self):
        self.rest_timer_running = not self.rest_timer_running
        self.rest_timer_status = "Paused" if not self.rest_timer_running else "Resumed"

    def reset_rest_timer(self):
        self.rest_timer_running = False
        self.rest_timer_seconds = self.rest_timer_total_seconds
        self.rest_timer_text = self._format_timer(self.rest_timer_seconds)
        self.rest_timer_status = "Reset."

    def log_set_now(self):
        self.set_counter += 1
        self.set_counter_text = f"Sets completed: {self.set_counter}"

    def reset_set_counter(self):
        self.set_counter = 0
        self.set_counter_text = "Sets completed: 0"

    def calculate_time_between(self, start, end, purpose):
        try:
            start_dt = datetime.strptime(start.strip().upper(), "%I:%M %p")
            end_dt = datetime.strptime(end.strip().upper(), "%I:%M %p")

            if end_dt <= start_dt:
                end_dt += timedelta(days=1)

            diff = end_dt - start_dt
            hours = diff.seconds // 3600
            minutes = (diff.seconds % 3600) // 60

            self.time_calc_result = f"{purpose}: {hours}h {minutes}m"

        except:
            self.time_calc_result = "Invalid format. Use 12:00 AM"


class LiveMonitorScreen(Screen):
    live_status = StringProperty('Not tracking yet.')
    live_metrics = StringProperty('Start a live strength session to see elapsed time, set count, training volume, and effort guidance update while you train.')
    live_tip = StringProperty('Coach tip will appear here.')
    gps_status = StringProperty('Strength-only mode active. Track sets, load, RIR, and recovery here.')
    gps_signal_text = StringProperty('Session: Inactive')
    gps_signal_color = ListProperty([0.60, 0.66, 0.75, 1])

    def on_pre_enter(self):
        self.refresh_display()

    def start_live(self, mode: str):
        app = App.get_running_app()
        if not app.require_login():
            return
        app.live_state = {
            'active': True,
            'paused': False,
            'mode': mode,
            'start_ts': datetime.now().timestamp(),
            'paused_total': 0.0,
            'pause_started': None,
            'distance_km': 0.0,
            'avg_hr': None,
            'strength_sets': 0,
            'strength_volume': 0.0,
            'avg_rir': None,
            'route_points': [],
            'elevation_gain_m': 0.0,
            'hr_samples': [],
            'workout_steps': 0,
            'step_start_raw': read_step_counter_raw_total(),
            'last_altitude': None,
            'gps_locked': False,
            'max_speed_kmh': 0.0,
            'gps_started': False,
            'speed_kmh': None,
            'smoothed_speed_kmh': None,
            'gps_accuracy_m': None,
            'gps_samples': 0,
            'gps_last_ts': None,
            'auto_activity_type': None,
            'distance_source': 'manual',
            'start_step_raw': read_step_counter_raw_total(),
        }

        if mode in {'Strength', 'Strength', 'Strength'}:
            self._begin_outdoor_session(mode)
            return

        self.live_status = f'{mode} session started.'
        pass
        self.refresh_display()

    def _begin_outdoor_session(self, mode: str):
        app = App.get_running_app()

        if not is_android():
            self.live_status = f'{mode} session started. Session is starting...'
            app.start_gps_tracking()
            pass
            self.refresh_display()


    def toggle_pause(self):
        app = App.get_running_app()
        state = app.live_state
        if not state or not state.get('active'):
            show_message('No live session', 'Start a live session first.')
            return
        if state.get('paused'):
            pause_started = state.get('pause_started')
            if pause_started:
                state['paused_total'] += max(0.0, datetime.now().timestamp() - pause_started)
            state['pause_started'] = None
            state['paused'] = False
            self.live_status = 'Live session resumed.'
        else:
            state['paused'] = True
            state['pause_started'] = datetime.now().timestamp()
            self.live_status = 'Live session paused.'
        self.refresh_display()

    def update_live(self, distance: str, hr: str):
        app = App.get_running_app()
        state = app.live_state
        if not state or not state.get('active'):
            show_message('No live session', 'Start a live session first.')
            return
        try:
            if distance.strip():
                d = float(distance)
                if d < 0:
                    raise ValueError
                state['distance_km'] = d
            if hr.strip():
                h = int(hr)
                if h <= 0:
                    raise ValueError
                state['avg_hr'] = h
                state.setdefault('hr_samples', []).append(h)
                if len(state['hr_samples']) > 240:
                    del state['hr_samples'][:-240]
        except ValueError:
            show_message('Invalid live input', 'Enter valid positive numbers for distance and heart rate.')
            return
        self.live_status = 'Live metrics updated.'
        self.refresh_display()

    def log_live_strength_set(self, weight: str, reps: str, rir: str):
        app = App.get_running_app()
        state = app.live_state
        if not state or not state.get('active') or state.get('mode') != 'Strength Training':
            show_message('Wrong mode', 'Start a live Strength Training session first.')
            return
        try:
            w = float(weight)
            r = int(reps)
            rr = int(rir)
            if w <= 0 or r <= 0 or rr < 0 or rr > 5:
                raise ValueError
        except ValueError:
            show_message('Invalid set', 'Enter a positive weight and reps, and RIR from 0 to 5.')
            return
        state['strength_sets'] += 1
        state['strength_volume'] += w * r
        prev_rir = state.get('avg_rir')
        if prev_rir is None:
            state['avg_rir'] = rr
        else:
            sets = state['strength_sets']
            state['avg_rir'] = round(((prev_rir * (sets - 1)) + rr) / sets, 1)
        self.live_status = f"Logged live set #{state['strength_sets']}"
        self.refresh_display()

    def finish_session(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        state = app.live_state
        if not state or not state.get('active'):
            show_message('No live session', 'There is no active session to save.')
            return
        elapsed_min = max(1.0, self._elapsed_seconds(state) / 60.0)
        mode = state.get('mode')
        hr = state.get('avg_hr')
        if mode == 'Strength Training':
            volume = state.get('strength_volume', 0.0)
            if volume <= 0:
                show_message('Nothing to save', 'Log at least one live strength set before finishing.')
                return
            reps_est = max(1, int(volume / max(1.0, state['strength_sets'] * max(1.0, volume / max(1, state['strength_sets'])))))
            avg_weight = max(1.0, volume / max(1, state['strength_sets'] * max(1, reps_est)))
            app.db.save_strength(
                app.current_user_id,
                'Live strength session',
                state['strength_sets'],
                max(1, reps_est),
                round(avg_weight, 1),
                int(round(state.get('avg_rir') or 2)),
            )
            show_message('Live session saved', f"Strength session saved with {state['strength_sets']} live set(s) and {volume:.0f} kg volume.")
        else:
            distance = float(state.get('distance_km', 0.0))
            if distance <= 0:
                show_message('Nothing to save', 'Update live distance before finishing your lift, jog, or walk.')
                return
            detected = state.get('auto_activity_type')
            mapped = detected if detected in {'Lift', 'Jog', 'Walk'} else {'Strength': 'Lift', 'Strength': 'Jog', 'Strength': 'Walk'}.get(mode, 'Lift')
            steps, effort, activity_id = app.db.save_activity(app.current_user_id, mapped, distance, elapsed_min, hr, 'Saved from live monitor')
            app.db.save_route_data(activity_id, state.get('route_points') or [], float(state.get('elevation_gain_m') or 0.0), float(state.get('max_speed_kmh') or 0.0))
            show_message('Live session saved', f"{mapped} saved: {distance:.2f} km in {elapsed_min:.1f} min.\nSession points: {len(state.get('route_points') or [])}")
        app.stop_gps_tracking()
        pass
        app.live_state = None
        self.live_status = 'Live session saved and cleared.'
        self.refresh_display()

    def reset_session(self):
        app = App.get_running_app()
        app.stop_gps_tracking()
        pass
        app.live_state = None
        self.live_status = 'Live session reset.'
        self.refresh_display()

    def refresh_gps_signal(self):
        app = App.get_running_app()
        state = app.live_state or {}

        if not state or state.get('mode') not in {'Strength', 'Strength', 'Strength'}:
            self.gps_signal_text = 'Session: Inactive'
            self.gps_signal_color = [0.60, 0.66, 0.75, 1]
            return

        samples = int(state.get('gps_samples') or 0)
        accuracy = state.get('gps_accuracy_m')
        locked = bool(state.get('gps_locked'))

        if samples <= 0:
            self.gps_signal_text = 'Session: No signal'
            self.gps_signal_color = [0.90, 0.29, 0.25, 1]
            return

        if accuracy is None:
            self.gps_signal_text = 'Session: Searching...'
            self.gps_signal_color = [0.95, 0.67, 0.20, 1]
            return

        try:
            accuracy = float(accuracy)
        except Exception:
            self.gps_signal_text = 'Session: Searching...'
            self.gps_signal_color = [0.95, 0.67, 0.20, 1]
            return

        if locked and accuracy <= 8:
            self.gps_signal_text = f'Session: Excellent ({accuracy:.0f} m)'
            self.gps_signal_color = [0.20, 0.78, 0.44, 1]
        elif locked and accuracy <= 20:
            self.gps_signal_text = f'Session: Good ({accuracy:.0f} m)'
            self.gps_signal_color = [0.45, 0.82, 0.48, 1]
        elif accuracy <= 50:
            self.gps_signal_text = f'GPS: Weak ({accuracy:.0f} m)'
            self.gps_signal_color = [0.95, 0.67, 0.20, 1]
        else:
            self.gps_signal_text = f'GPS: Poor ({accuracy:.0f} m)'
            self.gps_signal_color = [0.90, 0.29, 0.25, 1]

    def refresh_display(self):
        app = App.get_running_app()
        if not app.live_state or not app.live_state.get('active'):
            self.live_metrics = 'No active session. Start one to monitor elapsed time, pace, heart rate, and strength load live.'
            self.live_tip = 'Tip: use Strength or Strength for pace-based coaching, or Strength Training for live set tracking.'
            self.gps_status = 'GPS inactive. Start a strength, strength, or strength session to attempt a live route lock.'
            self.refresh_gps_signal()
            if 'route_preview' in self.ids:
                self.ids.route_preview.points_data = []
            return
        s = app.live_state
        elapsed_s = self._elapsed_seconds(s)
        elapsed_min = max(elapsed_s / 60.0, 0.01)
        dist = float(s.get('distance_km') or 0.0)
        hr = s.get('avg_hr')
        pace = (elapsed_min / dist) if dist > 0 else None
        calories = (elapsed_min * 7.0) if s.get('mode') in {'Strength', 'Strength'} else (elapsed_min * 5.0)
        paused = 'Yes' if s.get('paused') else 'No'
        extra = ''
        if s.get('mode') == 'Strength Training':
            extra = (
                f"Live sets: {s.get('strength_sets', 0)}\n"
                f"Session volume: {s.get('strength_volume', 0.0):.0f} kg\n"
                f"Average RIR: {s.get('avg_rir') if s.get('avg_rir') is not None else '-'}\n"
            )
        else:
            extra = (
                f"Distance: {dist:.2f} km\n"
                f"Current pace: {(f'{pace:.2f} effort score' if pace is not None else '-')}\n"
                f"Heart rate: {hr if hr is not None else '-'} bpm\n"
            )
        today = app.db.get_today(app.current_user_id) if app.current_user_id else {'readiness': 78}
        self.live_metrics = (
            f"Mode: {s.get('mode')}\n"
            f"Elapsed: {int(elapsed_s // 60):02d}:{int(elapsed_s % 60):02d}\n"
            f"Paused: {paused}\n"
            f"{extra}"
            f"Estimated calories: {calories:.0f}\n"
            f"Workout steps: {int(s.get('workout_steps') or 0):,}\n"
            f"Today's readiness: {today['readiness']}%"
        )
        route_points = s.get('route_points') or []
        if s.get('mode') in {'Strength', 'Strength', 'Strength'}:
            lock_text = 'locked' if s.get('gps_locked') else ('starting' if s.get('gps_started') else 'unavailable')
            accuracy = s.get('gps_accuracy_m')
            detected = s.get('auto_activity_type') or {'Strength': 'Lift', 'Strength': 'Jog', 'Strength': 'Walk'}.get(s.get('mode'), 'Cardio')
            source = s.get('distance_source', 'manual')
            self.gps_status = f"GPS {lock_text} • {detected} • source {source} • points {len(route_points)} • accuracy {(f'{float(accuracy):.0f} m' if accuracy is not None else '-')} • max speed {float(s.get('max_speed_kmh') or 0.0):.1f} km/h • elevation gain {float(s.get('elevation_gain_m') or 0.0):.0f} m"
        else:
            self.gps_status = 'Strength-only mode active. Use this session area for live gym tracking.'
        self.refresh_gps_signal()
        if 'route_preview' in self.ids:
            self.ids.route_preview.points_data = [(float(p[1]), float(p[0])) for p in route_points if len(p) >= 2]
        self.live_tip = pick_live_tip(s.get('mode'), int(elapsed_s), hr, pace, int(today['readiness']))
        app.update_background_tracking_snapshot()

    def _elapsed_seconds(self, state) -> float:
        if not state:
            return 0.0
        now_ts = datetime.now().timestamp()
        paused_total = state.get('paused_total', 0.0)
        if state.get('paused') and state.get('pause_started'):
            paused_total += max(0.0, now_ts - state['pause_started'])
        return max(0.0, now_ts - state['start_ts'] - paused_total)


class ActivityScreen(Screen):
    summary_text = StringProperty('Track support work manually. This keeps the app focused on gym progress without relying on outdoor tracking.')

    def on_pre_enter(self):
        self.update_summary()

    def update_summary(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        recent = app.db.recent_activities(app.current_user_id, 3)
        if not recent:
            self.summary_text = 'No support-work sessions saved yet.'
            return
        self.summary_text = 'Latest support-work entries:\n' + '\n'.join(
            f"• {r['activity_type']} • {r['distance_km']:.1f} km • {r['duration_min']:.0f} min • avg HR {r['avg_hr'] or '-'}"
            for r in recent
        )

    def save_activity(self, activity_type: str, distance: str, duration: str, avg_hr: str, notes: str):
        app = App.get_running_app()
        if not app.require_login():
            return
        try:
            d = float(distance)
            t = float(duration)
            hr = int(avg_hr) if avg_hr.strip() else None
            if d <= 0 or t <= 0:
                raise ValueError
        except ValueError:
            show_message('Invalid input', 'Enter valid positive numbers for distance and duration.')
            return
        steps, effort, _ = app.db.save_activity(app.current_user_id, activity_type, d, t, hr, notes.strip())
        self.update_summary()
        show_message('Support work saved', f'{activity_type} saved. Estimated steps: {steps:,}\nEffort score: {effort}')


class StrengthScreen(Screen):
    monitor_text = StringProperty('Log gym work and monitor total volume, load, and fatigue.')

    def on_pre_enter(self):
        self.update_monitor()

    def update_monitor(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        recent = app.db.recent_strength(app.current_user_id, 4)
        if not recent:
            self.monitor_text = 'No strength sessions logged yet.'
            return
        lines = []
        for r in recent:
            lines.append(
                f"• {r['exercise']} • {r['sets']}x{r['reps']} @ {r['weight']} kg • volume {r['volume']:.0f} • load {r['load_score']:.0f}"
            )
        self.monitor_text = 'Recent strength entries:\n' + '\n'.join(lines)

    def save_strength(self, exercise: str, sets: str, reps: str, weight: str, rir: str):
        app = App.get_running_app()
        if not app.require_login():
            return
        try:
            s = int(sets)
            r = int(reps)
            w = float(weight)
            rr = int(rir)
            if not exercise.strip() or s <= 0 or r <= 0 or w <= 0 or rr < 0 or rr > 5:
                raise ValueError
        except ValueError:
            show_message('Invalid input', 'Fill all fields. RIR should be from 0 to 5.')
            return
        volume, load = app.db.save_strength(app.current_user_id, exercise.strip(), s, r, w, rr)
        self.update_monitor()
        show_message('Strength saved', f'{exercise} saved.\nVolume: {volume:.0f} kg\nLoad score: {load:.0f}')


class WellnessScreen(Screen):
    water_status = StringProperty('Strength recovery check-in ready.')
    recovery_status = StringProperty('Log strength recovery using sleep, soreness, joints, performance readiness, and stress.')
    recovery_action_text = StringProperty('Recovery action plan will appear after your check-in.')
    reminder_status = StringProperty('No reminder saved yet.')
    reminder_text = StringProperty('')
    readiness_score_text = StringProperty('0%')
    readiness_band_text = StringProperty('No data')
    readiness_reason_text = StringProperty('Save a strength recovery check-in to calculate today’s readiness.')
    readiness_color = ListProperty([0.95, 0.67, 0.20, 1])
    readiness_values = ListProperty([])
    readiness_labels = StringProperty('')
    readiness_trend_text = StringProperty('')
    injury_risk_text = StringProperty('Log recovery and strength sessions to estimate injury risk.')
    injury_risk_color = ListProperty([0.95, 0.67, 0.20, 1])
    recovery_ai_text = StringProperty('Recovery coach uses strength volume, RIR, sleep, soreness, joints, stress, and performance readiness.')

    def on_pre_enter(self):
        self.refresh_recovery()

    def _num(self, value, default, low, high):
        try:
            number = float((value or '').strip())
        except Exception:
            number = default
        return max(low, min(high, number))

    def _band_for_score(self, score):
        if score >= 80:
            return 'Green', [0.20, 0.78, 0.44, 1]
        if score >= 65:
            return 'Yellow', [0.95, 0.67, 0.20, 1]
        if score >= 45:
            return 'Orange', [0.95, 0.45, 0.18, 1]
        return 'Red', [0.90, 0.29, 0.25, 1]

    def _score_strength_recovery(self, sleep_h, sleep_quality, soreness, joint, performance, stress, weekly):
        sets = int(weekly.get('sets', 0) or 0)
        volume = float(weekly.get('volume', 0.0) or 0.0)
        avg_rir = float(weekly.get('avg_rir', 3.0) or 3.0)

        score = 55.0
        drivers = []

        if sleep_h >= 8:
            score += 12
            drivers.append('strong sleep duration')
        elif sleep_h >= 7:
            score += 8
            drivers.append('good sleep duration')
        elif sleep_h >= 6:
            score += 1
            drivers.append('borderline sleep')
        else:
            score -= 14
            drivers.append('low sleep')

        score += (sleep_quality - 3) * 6
        score += (performance - 3) * 8
        score -= max(0, soreness - 2) * 7
        score -= max(0, joint - 1) * 10
        score -= max(0, stress - 3) * 5

        if sets >= 40:
            score -= 14
            drivers.append('very high weekly sets')
        elif sets >= 28:
            score -= 7
            drivers.append('high weekly sets')
        elif sets < 6:
            score -= 2
            drivers.append('low weekly lifting exposure')

        if volume >= 30000:
            score -= 10
            drivers.append('very high weekly volume')
        elif volume >= 18000:
            score -= 5
            drivers.append('high weekly volume')

        if avg_rir <= 1 and sets >= 16:
            score -= 10
            drivers.append('many sets close to failure')
        elif avg_rir >= 3 and sets > 0:
            score += 3
            drivers.append('RIR is managing fatigue')

        score = int(round(max(5, min(100, score))))
        band, color = self._band_for_score(score)
        detail = ', '.join(drivers[:4]) if drivers else 'balanced recovery inputs'
        return score, band, color, detail

    def save_strength_recovery(self, sleep_hours, sleep_quality, soreness, joint, performance, stress):
        app = App.get_running_app()
        if not app.require_login():
            return

        sleep_h = self._num(sleep_hours, 7.0, 0, 14)
        sleep_q = self._num(sleep_quality, 3, 1, 5)
        sore = self._num(soreness, 3, 1, 5)
        joint_v = self._num(joint, 1, 1, 5)
        perf = self._num(performance, 3, 1, 5)
        stress_v = self._num(stress, 3, 1, 5)

        weekly = app.db.weekly_totals(app.current_user_id)
        score, band, color, detail = self._score_strength_recovery(
            sleep_h, sleep_q, sore, joint_v, perf, stress_v, weekly
        )

        reason = (
            f'{band} • {detail}. '
            f'Sleep {sleep_h:g}h, quality {sleep_q:.0f}/5, soreness {sore:.0f}/5, '
            f'joints {joint_v:.0f}/5, performance {perf:.0f}/5, stress {stress_v:.0f}/5.'
        )

        today_key = date_key()
        try:
            app.db.conn.execute(
                """INSERT INTO daily_health(user_id, date, sleep_hours, mood_score, energy_score, water, readiness, readiness_reason)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(user_id, date) DO UPDATE SET
                       sleep_hours=excluded.sleep_hours,
                       mood_score=excluded.mood_score,
                       energy_score=excluded.energy_score,
                       water=0,
                       readiness=excluded.readiness,
                       readiness_reason=excluded.readiness_reason""",
                (
                    app.current_user_id,
                    today_key,
                    sleep_h,
                    int(round(6 - stress_v)),
                    int(round(perf)),
                    0,
                    score,
                    reason,
                ),
            )
            app.db.conn.commit()
        except Exception:
            app.db.save_wellness(app.current_user_id, sleep_h, int(round(6 - stress_v)), int(round(perf)))
            try:
                app.db.conn.execute(
                    'UPDATE daily_health SET readiness=?, readiness_reason=?, water=0 WHERE user_id=? AND date=?',
                    (score, reason, app.current_user_id, today_key),
                )
                app.db.conn.commit()
            except Exception:
                pass

        self.readiness_score_text = f'{score}%'
        self.readiness_band_text = band
        self.readiness_color = color
        self.readiness_reason_text = reason
        self.recovery_status = 'Strength recovery check-in saved.'
        self.recovery_action_text = self._build_recovery_action_plan(score, band, weekly, sore, joint_v, perf)
        self._refresh_injury_risk()
        self.refresh_recovery_ai()
        self.refresh_trend()

    def _build_recovery_action_plan(self, score, band, weekly, soreness, joint, performance):
        sets = int(weekly.get('sets', 0) or 0)
        avg_rir = float(weekly.get('avg_rir', 3.0) or 3.0)
        lines = [f'Training decision: {band} ({score}%).']
        if score >= 80:
            lines.append('• Normal lifting is okay. Progress only if warm-up sets feel strong.')
        elif score >= 65:
            lines.append('• Train as planned, but cap most work around 1–3 RIR.')
        elif score >= 45:
            lines.append('• Reduce volume by 20–40% or skip the most fatiguing accessories.')
        else:
            lines.append('• Rest, mobility, technique work, or a very light pump session is smarter today.')
        if soreness >= 4:
            lines.append('• High soreness: avoid training the same muscle hard today.')
        if joint >= 3:
            lines.append('• Joint discomfort: use stable movements, slower tempo, and avoid max loading.')
        if avg_rir <= 1 and sets >= 15:
            lines.append('• You are pushing close to failure often. Leave more reps in reserve today.')
        return '\n'.join(lines)

    def refresh_recovery(self):
        app = App.get_running_app()
        if not app.require_login():
            return

        today = app.db.get_today(app.current_user_id)
        weekly = app.db.weekly_totals(app.current_user_id)
        readiness = max(0, min(100, int(safe_row_value(today, 'readiness', 0) or 0)))
        reason = sanitize_recovery_reason(safe_row_value(today, 'readiness_reason', ''))
        if not is_real_strength_recovery_reason(reason):
            readiness = 0
            reason = ''
        try:
            old_reason = str(safe_row_value(today, 'readiness_reason', '') or '')
            if reason and old_reason != reason:
                app.db.conn.execute(
                    'UPDATE daily_health SET readiness_reason=? WHERE user_id=? AND date=?',
                    (reason, app.current_user_id, date_key()),
                )
                app.db.conn.commit()
        except Exception:
            pass

        if readiness <= 0:
            self.readiness_score_text = 'No data'
            self.readiness_band_text = 'No check-in'
            self.readiness_color = [0.70, 0.75, 0.84, 1]
            self.readiness_reason_text = 'No real strength recovery check-in yet. Save today’s check-in to calculate readiness.'
            self.recovery_action_text = 'No decision yet because no real strength recovery check-in is saved. Add sleep, soreness, joints, stress, and performance readiness.'
        else:
            band, color = self._band_for_score(readiness)
            self.readiness_score_text = f'{readiness}%'
            self.readiness_band_text = band
            self.readiness_color = color
            self.readiness_reason_text = sanitize_recovery_reason(str(reason or f'{band} readiness.'))
            self.recovery_action_text = self._build_recovery_action_plan(readiness, band, weekly, soreness=3, joint=1, performance=3)

        self.recovery_status = (
            f"Strength workload this week: {int(weekly.get('sets', 0))} sets, "
            f"{float(weekly.get('volume', 0.0)):.0f} kg volume, avg RIR {float(weekly.get('avg_rir', 0.0)):.1f}."
        )
        self.refresh_reminders()
        self._refresh_injury_risk()
        self.refresh_recovery_ai()
        self.refresh_trend()

    def refresh_trend(self):
        app = App.get_running_app()
        rows = app.db.analytics_last_n_days(app.current_user_id, 14)
        self.readiness_values = [
            max(0, min(100, int(safe_row_value(r, 'readiness', 0) or 0)))
            for r in rows
        ]
        self.readiness_labels = '   '.join(str(safe_row_value(r, 'label', '')) for r in rows)

        logged = [v for v in self.readiness_values if v > 0]
        if len(logged) >= 2:
            first = logged[0]
            latest = logged[-1]
            trend = 'improving' if latest > first else ('dropping' if latest < first else 'stable')
            self.readiness_trend_text = (
                f'Readiness trend is {trend}: {first}% → {latest}%. '
                f'Only real strength recovery check-ins are shown; old/default recovery rows are hidden.'
            )
        elif len(logged) == 1:
            self.readiness_trend_text = f'Only one logged readiness value so far: {logged[0]}%.'
        else:
            self.readiness_trend_text = 'No logged readiness values yet. Save recovery check-ins to build the chart.'

    def _refresh_injury_risk(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        weekly = app.db.weekly_totals(app.current_user_id)
        recent_strength = app.db.recent_strength(app.current_user_id, 8)
        today = app.db.get_today(app.current_user_id)
        readiness = max(0, min(100, int(safe_row_value(today, 'readiness', 0) or 0)))
        sleep_h = float(safe_row_value(today, 'sleep_hours', 7.0))
        sets = int(weekly.get('sets', 0) or 0)
        volume = float(weekly.get('volume', 0.0) or 0.0)
        avg_rir = float(weekly.get('avg_rir', 3.0) or 3.0)

        risk = 12.0
        reasons = []
        if sets >= 40:
            risk += 22
            reasons.append('very high weekly set count')
        elif sets >= 28:
            risk += 12
            reasons.append('high weekly set count')
        if volume >= 30000:
            risk += 16
            reasons.append('very high lifting volume')
        elif volume >= 18000:
            risk += 8
            reasons.append('high lifting volume')
        if avg_rir <= 1.0 and sets >= 16:
            risk += 16
            reasons.append('many sets close to failure')
        if sleep_h < 6.5 and sleep_h > 0:
            risk += 12
            reasons.append('low sleep')
        if readiness and readiness < 65:
            risk += 18
            reasons.append('low readiness')

        if len(recent_strength) >= 2:
            latest = float(safe_row_value(recent_strength[0], 'load_score', 0.0))
            previous = [float(safe_row_value(r, 'load_score', 0.0)) for r in recent_strength[1:5]]
            avg_prev = sum(previous) / max(1, len(previous))
            if avg_prev > 0 and latest > avg_prev * 1.5:
                risk += 14
                reasons.append('recent workload spike')

        risk = int(max(5, min(95, round(risk))))
        if risk >= 70:
            band = 'High'
            self.injury_risk_color = [0.90, 0.29, 0.25, 1]
            advice = 'Cut volume, avoid failure, and protect joints today.'
        elif risk >= 45:
            band = 'Moderate'
            self.injury_risk_color = [0.95, 0.67, 0.20, 1]
            advice = 'Train conservatively and avoid sudden load jumps.'
        else:
            band = 'Low'
            self.injury_risk_color = [0.20, 0.78, 0.44, 1]
            advice = 'Risk looks manageable if progression stays controlled.'
        detail = ', '.join(reasons[:4]) if reasons else 'balanced workload and recovery'
        self.injury_risk_text = f'Injury risk: {band} ({risk}%). Drivers: {detail}. {advice}'

    def refresh_recovery_ai(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        today = app.db.get_today(app.current_user_id)
        weekly = app.db.weekly_totals(app.current_user_id)
        readiness = max(0, min(100, int(safe_row_value(today, 'readiness', 0) or 0)))
        sleep_h = float(safe_row_value(today, 'sleep_hours', 0.0))
        sets = int(weekly.get('sets', 0) or 0)
        volume = float(weekly.get('volume', 0.0) or 0.0)
        avg_rir = float(weekly.get('avg_rir', 3.0) or 3.0)

        lines = []
        if readiness <= 0:
            lines.append('No readiness check-in yet. Save today’s strength recovery first.')
        elif readiness >= 80:
            lines.append('Green light: normal training is acceptable if warm-up sets feel strong.')
        elif readiness >= 65:
            lines.append('Yellow light: train normally but avoid extra volume and failure.')
        elif readiness >= 45:
            lines.append('Orange light: reduce sets or load and use technique-focused work.')
        else:
            lines.append('Red light: recovery session or rest is the smarter choice.')

        if sets >= 35:
            lines.append('Weekly sets are high; reduce accessories or keep compounds submaximal.')
        elif sets < 6:
            lines.append('Weekly sets are low; build consistency with a recoverable plan.')
        if avg_rir <= 1 and sets >= 15:
            lines.append('Average RIR is low; stop more sets with 2–3 reps in reserve.')
        if sleep_h and sleep_h < 6.5:
            lines.append('Sleep is limiting recovery; prioritize sleep before adding intensity.')
        if volume > 0:
            lines.append(f'This week: {sets} sets, about {volume:.0f} kg volume, avg RIR {avg_rir:.1f}.')

        self.recovery_ai_text = 'Recovery score AI coach\n' + '\n'.join(f'• {line}' for line in lines[:6])

    def save_wellness(self, sleep_hours, mood, energy):
        self.save_strength_recovery(sleep_hours, '3', '3', '1', energy or '3', str(max(1, 6 - int(float(mood or 3)))))

    def add_water(self):
        self.recovery_status = 'recovery readiness tracking is not used in this strength recovery score. Use the recovery check-in instead.'

    def reset_recovery(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        try:
            app.db.conn.execute(
                'UPDATE daily_health SET sleep_hours=0, mood_score=3, energy_score=3, water=0, readiness=0, readiness_reason=? WHERE user_id=? AND date=?',
                ('Recovery reset. No real strength recovery check-in is saved yet.', app.current_user_id, date_key()),
            )
            app.db.conn.commit()
        except Exception:
            pass
        self.refresh_recovery()

    def save_reminder(self, name, time_text):
        app = App.get_running_app()
        if not app.require_login():
            return
        parsed = parse_time_12h_or_24h(time_text)
        if not name.strip() or not parsed:
            self.reminder_status = 'Enter a reminder name and a valid time like 08:00 AM.'
            return
        app.db.add_reminder(app.current_user_id, name.strip(), parsed)
        send_local_notification('Buo reminder saved', f'{name.strip()} at {parsed}')
        self.refresh_reminders()
        self.reminder_status = f'Reminder saved: {name.strip()} at {parsed}.'

    def refresh_reminders(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        try:
            reminders = app.db.reminder_list(app.current_user_id)
        except Exception:
            reminders = []
        if reminders:
            self.reminder_text = '\n'.join(
                f"• {safe_row_value(row, 'name', 'Reminder')} at {safe_row_value(row, 'time_text', '--:--')}"
                for row in reminders
            )
        else:
            self.reminder_text = 'No reminders yet. Add a training, sleep, deload, or mobility reminder.'

    def reset_reminders(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        app.db.clear_reminders(app.current_user_id)
        self.refresh_reminders()
        self.reminder_status = 'Reminders reset.'

class ReportsScreen(Screen):
    report_text = StringProperty('')

    def on_pre_enter(self):
        self.refresh_report()

    def export_report_csv(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        path = app.export_report_csv()
        show_message('Export ready', f'Report CSV saved to\n{path}')

    def refresh_report(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        today = app.db.get_today(app.current_user_id)
        weekly = app.db.weekly_totals(app.current_user_id)
        recents = app.db.recent_activities(app.current_user_id, 7)
        gps_sessions = app.db.gps_session_count(app.current_user_id)
        best_pace = None
        for r in recents:
            if r['distance_km'] > 0:
                pace = r['duration_min'] / r['distance_km']
                if best_pace is None or pace < best_pace:
                    best_pace = pace
        self.report_text = (
            f"Weekly cardio sessions: {weekly['sessions']}\n"
            f"Weekly distance: {weekly['distance']:.1f} km\n"
            f"Weekly duration: {weekly['duration']:.0f} min\n"
            f"Strength entries: {weekly['lifts']}\n"
            f"Strength volume: {weekly['volume']:.0f} kg\n"
            f"Water this week: {weekly['water']} glasses\n"
            f"Today's steps: {today['steps']:,}\n"
            f"Today's readiness: {today['readiness']}%\n"
            f"Best pace in recent sessions: {(f'{best_pace:.2f} effort score' if best_pace is not None else 'N/A')}\n\n"
            f"GPS route sessions saved: {gps_sessions}\n\n"
            "What is new:\n"
            "• Local private display-name + passcode lock screen\n"
            "• Personalized dashboard and reports per user\n"
            "• Live workout for strength, strength, strength, and strength\n"
            "• Real phone GPS route capture with simple in-app route preview\n"
            "• FAQ screen with science-based training tips\n"
            "• Strength load monitor sharing one readiness score with cardio\n\n"
            f"Achievements:\n{summarize_achievements(app.db.get_records(app.current_user_id))}"
        )


class AnalyticsScreen(Screen):
    summary_text = StringProperty('No analytics yet.')
    kpi_text = StringProperty('No analytics yet.')
    trend_summary_text = StringProperty('Readiness trend will appear after a few days of data.')
    distance_values = ListProperty([0, 0, 0, 0, 0, 0, 0])
    strength_session_values = ListProperty([0, 0, 0, 0, 0, 0, 0])
    strength_values = ListProperty([0, 0, 0, 0, 0, 0, 0])
    readiness_values = ListProperty([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    distance_labels = StringProperty('')
    strength_labels = StringProperty('')
    readiness_labels = StringProperty('')
    readiness_explain_text = StringProperty('')

    def on_pre_enter(self):
        self.refresh_analytics()


    def refresh_analytics(self):
        app = App.get_running_app()
        if not app.require_login():
            return

        weekly = app.db.weekly_totals(app.current_user_id)
        rows7 = app.db.analytics_last_n_days(app.current_user_id, 7)
        rows14 = app.db.analytics_last_n_days(app.current_user_id, 14)

        self.strength_session_values = [
            max(0.0, float(safe_row_value(r, 'strength_sessions', 0) or 0))
            for r in rows7
        ]
        self.strength_values = [
            max(0.0, float(safe_row_value(r, 'strength_volume', 0.0) or 0.0))
            for r in rows7
        ]
        self.distance_values = list(self.strength_session_values)

        self.strength_labels = '   '.join(str(safe_row_value(r, 'label', '')) for r in rows7)
        self.distance_labels = self.strength_labels

        self.readiness_values = [
            max(0, min(100, int(safe_row_value(r, 'readiness', 0) or 0)))
            for r in rows14
        ]
        self.readiness_labels = '   '.join(str(safe_row_value(r, 'label', '')) for r in rows14)

        logged_readiness = [v for v in self.readiness_values if v > 0]
        avg_readiness = sum(logged_readiness) / len(logged_readiness) if logged_readiness else 0

        weekly_sets = int(weekly.get('sets', 0) or 0)
        weekly_volume = float(weekly.get('volume', 0.0) or 0.0)
        weekly_lifts = int(weekly.get('lifts', 0) or 0)
        weekly_reps = int(weekly.get('reps', 0) or 0)
        avg_rir = float(weekly.get('avg_rir', 0.0) or 0.0)

        self.summary_text = (
            f"This week: {weekly_lifts} strength session(s), "
            f"{weekly_sets} hard set(s), {weekly_reps} total rep(s), "
            f"{weekly_volume:.0f} kg total volume."
        )
        self.kpi_text = (
            f"Strength sessions: {weekly_lifts}\n"
            f"Weekly sets: {weekly_sets}\n"
            f"Weekly volume: {weekly_volume:.0f} kg\n"
            f"Average RIR: {avg_rir:.1f}\n"
            f"Support/recovery minutes: {float(weekly.get('duration', 0.0) or 0.0):.0f}"
        )
        self.readiness_explain_text = (
            f"Readiness is charted on a fixed 0–100 scale. "
            f"A 50% day will show around half height, not full height. "
            f"Logged 14-day average: {avg_readiness:.0f}%."
        )

        if len(logged_readiness) >= 2:
            first = logged_readiness[0]
            latest = logged_readiness[-1]
            delta = latest - first
            direction = 'improving' if delta > 0 else ('dropping' if delta < 0 else 'stable')
            self.trend_summary_text = f"Readiness trend is {direction}: {first}% → {latest}%."
        else:
            self.trend_summary_text = 'Add more recovery check-ins to see a reliable readiness trend.'


    def export_analytics_json(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        path = app.export_analytics_json()
        show_message('Export ready', f'Analytics JSON saved to\n{path}')

    def export_analytics_csv(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        path = app.export_report_csv()
        show_message('Export ready', f'Analytics CSV saved to\n{path}')



class HistoryScreen(Screen):
    history_text = StringProperty('')
    pb_text = StringProperty('')
    map_url = StringProperty('')
    map_caption = StringProperty('Strength-only mode does not use outdoor maps.')
    route_browser_url = StringProperty('')
    route_summary = StringProperty('No strength sessions saved yet. Log strength work to unlock progress history.')
    latest_route_points = ListProperty([])

    def on_pre_enter(self):
        self.refresh_history()

    def refresh_history(self):
        app = App.get_running_app()
        if not app.require_login():
            return

        records = app.db.get_records(app.current_user_id)
        self.pb_text = summarize_achievements(records)

        rows = app.db.recent_strength(app.current_user_id, 10)
        if rows:
            self.history_text = '\n'.join(
                f"• {safe_row_value(row, 'exercise', 'Lift')} — "
                f"{int(safe_row_value(row, 'sets', 0))}x{int(safe_row_value(row, 'reps', 0))} "
                f"@ {float(safe_row_value(row, 'weight', 0.0)):.1f} kg "
                f"• volume {float(safe_row_value(row, 'volume', 0.0)):.0f} kg "
                f"• RIR {int(safe_row_value(row, 'rir', 0))}"
                for row in rows
            )
            latest = rows[0]
            self.route_summary = (
                f"Latest: {safe_row_value(latest, 'exercise', 'Lift')} — "
                f"{int(safe_row_value(latest, 'sets', 0))} sets, "
                f"{int(safe_row_value(latest, 'reps', 0))} reps, "
                f"{float(safe_row_value(latest, 'weight', 0.0)):.1f} kg, "
                f"{float(safe_row_value(latest, 'volume', 0.0)):.0f} kg volume."
            )
        else:
            self.history_text = 'No strength sessions yet. Log sets, reps, load, and RIR to build your history.'
            self.route_summary = 'No strength sessions saved yet.'
        self.map_url = ''
        self.route_browser_url = ''
        self.latest_route_points = []

    def open_latest_route(self):
        show_message('Strength session', self.route_summary or 'No strength session saved yet.')

    def export_latest_gpx(self):
        show_message('Strength-only mode', 'Buo no longer exports summary. Use Reports or Analytics export for strength progress.')

class SyncScreen(Screen):
    status_text = StringProperty('')
    info_text = StringProperty('')
    release_text = StringProperty('')

    def on_pre_enter(self):
        self.refresh_sync_status()

    def refresh_sync_status(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        self.status_text = app.get_sync_status_text()
        self.info_text = (
            'This version adds account backup and restore. It always saves a local mirror backup per account, and it can also sync to Firebase Realtime Database if you add cloud_config.json with a database URL and optional auth token.\n\n'
            'That means the feature works right now for safe local backup, and becomes real cross-device cloud sync when you plug in your Firebase project.'
        )
        self.release_text = (
            'App icon and splash are already wired in. For release builds, generate a keystore, add the signing values to buildozer.spec, build with buildozer android release, then test an .aab or release APK.\n\n'
            'Before Play Store submission, finish your privacy policy, confirm location/background behavior, and replace any demo text or debug logging.'
        )

    def backup_now(self):
        app = App.get_running_app()
        ok, msg = app.backup_current_user()
        self.refresh_sync_status()
        show_message('Backup result', msg)

    def restore_now(self):
        app = App.get_running_app()
        ok, msg = app.restore_current_user()
        self.refresh_sync_status()
        show_message('Restore result', msg)

    def export_bundle(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        path = app.export_full_bundle()
        show_message('Export ready', f'Full data bundle saved to\n{path}')

    def open_export_folder(self):
        app = App.get_running_app()
        ok = open_external_uri(app.export_dir_uri())
        if not ok:
            show_message('Open folder failed', 'The export folder could not be opened on this device.')



class TipsScreen(Screen):
    strength_text = StringProperty('')
    strength_text = StringProperty('')
    reference_text = StringProperty('')
    ai_status = StringProperty('Offline AI coach ready.')
    ai_answer = StringProperty('Ask a fitness or health question.')
    ai_mode = StringProperty('offline')
    ai_mode_text = StringProperty('Current mode: Offline AI')
    offline_button_text = StringProperty('Use Offline AI ✓')
    online_button_text = StringProperty('Use Online AI')
    ai_switch = BooleanProperty(False)
    plan_status = StringProperty('Enter your details to get a calorie and protein target.')
    plan_result = StringProperty('No AI plan calculated yet.')
    food_status = StringProperty('Describe a food and amount to estimate calories, protein, carbs, fat, sugar, fiber, and sodium.')
    food_result = StringProperty('No food analysis yet.')
    recomp_status = StringProperty('Use this to estimate a recomposition-friendly target and lean-mass outlook.')
    recomp_result = StringProperty('No body recomposition calculation yet.')
    nutrition_status = StringProperty('Generate an AI nutrition plan based on your goal, meal structure, and restrictions.')
    nutrition_result = StringProperty('No nutrition plan generated yet.')
    workout_status = StringProperty('Generate a gym-focused workout split that respects weekly sets, recovery spacing, and 2x+ per-muscle frequency.')
    workout_result = StringProperty('No smart workout generated yet.')

    def on_pre_enter(self):
        self.strength_text = ''
        self.strength_text = ''
        self.reference_text = (
            'This app now leans heavily toward strength and gym progress. '
            'The workout maker follows three main science-based checks: enough weekly volume at about 6 to 20 hard sets per muscle, '
            'enough time between overlapping sessions so a sore or weak muscle is not trained too soon, and a default target of 2x+ per-muscle frequency when possible. '
            'Offline mode uses built-in strength-planning rules and estimates. Online mode uses Gemini for more flexible coaching, workout design, calorie planning, body recomposition guidance, food analysis, and nutrition planning.'
        )
        self.refresh_ai()

    def refresh_ai(self):
        cfg = self.load_gemini_config()
        online_ready = bool(cfg.get('enabled'))
        if self.ai_mode == 'online' and not online_ready:
            self.ai_mode = 'offline'
        if self.ai_mode == 'online':
            self.ai_switch = True
            self.ai_mode_text = 'Current mode: Online AI (Gemini)'
            self.ai_status = 'Gemini key detected; connection will be verified when you send a request.'
            self.plan_status = 'Online AI calorie and protein planner is active. Offline formulas stay available as backup.'
            self.food_status = 'Online AI food analyzer is active. Offline estimates stay available as backup.'
            self.recomp_status = 'Online AI body recomposition guidance is active. Offline formulas stay available as backup.'
            self.nutrition_status = 'Online AI nutrition planner is active. Offline meal planning stays available as backup.'
            self.workout_status = 'Online AI workout maker is active. Offline science-based split rules stay available as backup.'
        else:
            self.ai_switch = False
            self.ai_mode_text = 'Current mode: Offline AI'
            if online_ready:
                self.ai_status = 'Offline AI strength coach ready. Gemini is available if you switch it on.'
            else:
                self.ai_status = 'Offline AI strength coach ready. Gemini not configured.'
            self.plan_status = 'Offline AI planner is active. It uses science-based formulas for calories and protein.'
            self.food_status = 'Offline AI food analyzer is active. It uses built-in food estimates for common foods.'
            self.recomp_status = 'Offline body recomposition calculator is active.'
            self.nutrition_status = 'Offline nutrition planner is active.'
            self.workout_status = 'Offline workout maker is active. It uses weekly set targets, recovery spacing, and 2x+ frequency rules.'

    def set_ai_mode(self, mode):
        if mode == 'online':
            cfg = self.load_gemini_config()
            if not cfg.get('enabled'):
                self.ai_status = 'Gemini not configured.'
                self.ai_mode = 'offline'
                self.ai_switch = False
                self.refresh_ai()
                return
            self.ai_mode = 'online'
            self.ai_switch = True
        else:
            self.ai_mode = 'offline'
            self.ai_switch = False
        self.refresh_ai()

    def toggle_ai_switch(self, value):
        self.set_ai_mode('online' if value else 'offline')

    def clear_ai(self):
        self.ai_answer = 'Ask a fitness or health question.'
        self.refresh_ai()

    def clear_food(self):
        self.food_result = 'No food analysis yet.'
        self.refresh_ai()

    def ask_ai(self, question):
        question = (question or '').strip()
        if not question:
            self.ai_answer = 'Type a question.'
            return
        gemini_error = None
        try:
            if self.ai_mode == 'online':
                answer = self.ask_gemini(question, purpose='coach')
                if answer:
                    self.ai_answer = answer
                    self.ai_status = 'Answer from Gemini'
                    show_message('AI Coach Answer', answer)
                    return
        except Exception as exc:
            gemini_error = str(exc)
        self.ai_answer = self.offline_ai(question)
        if self.ai_mode == 'online' and gemini_error:
            self.ai_status = f'Gemini unavailable: {gemini_error}. Offline answer shown.'
        else:
            self.ai_status = 'Offline AI answer'
        show_message('AI Coach Answer', self.ai_answer)

    def generate_workout_maker(self, goal, level, days_text, minutes_text, rest_days, notes):
        try:
            days = max(2, min(6, int(float(days_text or '4'))))
            minutes = max(30, min(150, int(float(minutes_text or '60'))))
        except Exception:
            self.workout_result = 'Enter valid numbers for training days and session length.'
            self.workout_status = 'Fix the workout-maker inputs and try again.'
            return

        offline = self._offline_strength_workout_maker(goal, level, days, minutes, rest_days, notes)

        if self.ai_mode == 'online':
            try:
                prompt = (
                    f'Build a gym-focused workout split. Goal: {goal}. Level: {level}. '
                    f'Training days per week: {days}. Minutes per session: {minutes}. '
                    f'Preferred rest days: {rest_days or "none"}. Notes: {notes or "none"}. '
                    f'Use these science-based rules: 6 to 20 sets per muscle per week, enough time between overlapping sore muscles, '
                    f'and a target of 2x+ per-muscle frequency when possible. '
                    f'Base structured plan: {offline}. Include effective and science-based exercise choices for each day, with compounds first, then stable accessories, and give useful set and rep guidance.'
                )
                answer = self.ask_gemini(prompt, purpose='training_plan')
                if answer:
                    self.workout_result = answer + '\n\nOffline structured split\n' + offline
                    self.workout_status = 'AI workout maker answer from Gemini'
                    show_message('Smart AI Workout Maker', self.workout_result)
                    return
            except Exception:
                self.workout_status = 'Gemini failed, showing offline strength split.'
        self.workout_result = offline
        self.workout_status = 'Offline workout maker answer'
        show_message('Smart AI Workout Maker', self.workout_result)

    def _offline_strength_workout_maker(self, goal, level, days, minutes, rest_days, notes):
        split_name, schedule_lines, weekly_sets = self._build_strength_split_template(goal, level, days, minutes, rest_days, notes)
        checklist = (
            'Split checklist\n'
            '• Enough weekly volume: each major muscle should usually land around 6 to 20 challenging sets per week.\n'
            '• Enough time between sessions: avoid repeating the same sore or weak muscle on back-to-back days unless session volume is very low.\n'
            '• 2x+ per-muscle frequency when possible: twice per week is the default sweet spot for most people.\n'
        )
        notes_block = (
            'How to use it\n'
            '• Start at the lower end of weekly volume if recovery is weak, sleep is poor, or gym technique is still improving.\n'
            '• If a muscle is still clearly sore or performance is down, cut sets slightly or give it more time before hitting it again.\n'
            '• If you use a bro split or fewer weekly days, push more sets into the working day so the weekly total still lands in range.\n'
            '• Track hard sets, reps, load, and RIR so progression stays objective.'
        )
        extra = f'Custom notes considered: {notes or "none"}\nPreferred rest days: {rest_days or "none"}'
        return (
            f'Strength focus: {goal}\n'
            f'Level: {level}\n'
            f'Days per week: {days}\n'
            f'Session length: about {minutes} minutes\n'
            f'Recommended split: {split_name}\n\n'
            + '\n'.join(schedule_lines)
            + '\n\nWeekly set targets\n'
            + '\n'.join(f'• {k}: {v}' for k, v in weekly_sets.items())
            + '\n\n' + checklist + '\n' + notes_block + '\n\n' + extra
        )

    def _build_strength_split_template(self, goal, level, days, minutes, rest_days, notes):
        goal_low = (goal or '').lower()

        if days <= 2:
            split_name = 'Alternating full body'
            schedule = [
                'Day 1 • Full Body A — Back Squat 3–4 sets, Barbell Bench Press 3–4 sets, Chest-Supported Row 3–4 sets, Romanian Deadlift 2–3 sets, Lateral Raise 2 sets, Cable Curl 2 sets, Rope Pushdown 2 sets.',
                'Day 2 • Full Body B — Deadlift or Trap-Bar Deadlift 2–3 sets, Incline Dumbbell Press 3 sets, Lat Pulldown or Pull-Up 3–4 sets, Leg Press or Split Squat 3 sets, Seated Hamstring Curl 2–3 sets, Cable Lateral Raise 2 sets, Overhead Triceps Extension 2 sets.',
            ]
            weekly_sets = {
                'Chest': '6 to 8 hard sets',
                'Back': '6 to 10 hard sets',
                'Quads': '6 to 10 hard sets',
                'Hamstrings/Glutes': '4 to 8 hard sets',
                'Delts': '4 to 6 hard sets',
                'Arms': '4 to 6 hard sets',
            }
        elif days == 3:
            split_name = 'Upper / Lower / Full body'
            schedule = [
                'Day 1 • Upper — Barbell Bench Press 3–4 sets, Chest-Supported Row 3–4 sets, Incline Dumbbell Press 2–3 sets, Lat Pulldown 2–3 sets, Lateral Raise 2–3 sets, Cable Curl 2 sets, Rope Pushdown 2 sets.',
                'Day 2 • Lower — Back Squat 3–4 sets, Romanian Deadlift 3 sets, Leg Press 2–3 sets, Seated Leg Curl 2–3 sets, Standing Calf Raise 3 sets, Hanging Leg Raise 2–3 sets.',
                'Day 3 • Full Body — Machine Chest Press 2–3 sets, Pull-Up or Pulldown 3 sets, Hack Squat or Split Squat 2–3 sets, Hip Hinge Variation 2 sets, Rear-Delt Fly 2 sets, Curl 2 sets, Triceps Pressdown 2 sets.',
            ]
            weekly_sets = {
                'Chest': '6 to 9 hard sets',
                'Back': '8 to 11 hard sets',
                'Quads': '6 to 9 hard sets',
                'Hamstrings/Glutes': '5 to 8 hard sets',
                'Delts': '4 to 7 hard sets',
                'Arms': '4 to 6 hard sets',
            }
        elif days == 4:
            split_name = 'Upper / Lower / Upper / Lower'
            schedule = [
                'Day 1 • Upper A — Bench Press 3–4 sets, Barbell Row 3–4 sets, Incline Dumbbell Press 2–3 sets, Lat Pulldown 2–3 sets, Lateral Raise 2–3 sets, Cable Curl 2 sets, Rope Pushdown 2 sets.',
                'Day 2 • Lower A — Back Squat 3–4 sets, Romanian Deadlift 3 sets, Leg Press 2–3 sets, Seated Leg Curl 2–3 sets, Standing Calf Raise 3 sets, Cable Cliftch 2–3 sets.',
                'Day 3 • Upper B — Overhead Press 3 sets, Pull-Up or Chest-Supported Row 3–4 sets, Machine Chest Press 2–3 sets, Single-Arm Cable Row 2–3 sets, Rear-Delt Fly 2 sets, Incline Curl 2 sets, Overhead Triceps Extension 2 sets.',
                'Day 4 • Lower B — Deadlift or Trap-Bar Deadlift 2–3 sets, Hack Squat 3 sets, Bulgarian Split Squat 2–3 sets, Lying Leg Curl 2–3 sets, Seated Calf Raise 3 sets, Ab Wheel 2–3 sets.',
            ]
            weekly_sets = {
                'Chest': '8 to 12 hard sets',
                'Back': '10 to 14 hard sets',
                'Quads': '8 to 12 hard sets',
                'Hamstrings/Glutes': '8 to 12 hard sets',
                'Delts': '6 to 10 hard sets',
                'Arms': '4 to 8 hard sets',
            }
        elif days == 5:
            split_name = 'Push / Pull / Legs / Upper / Lower'
            schedule = [
                'Day 1 • Push — Bench Press 3–4 sets, Incline Dumbbell Press 3 sets, Machine Chest Press 2 sets, Overhead Press 2–3 sets, Lateral Raise 3 sets, Rope Pushdown 2–3 sets.',
                'Day 2 • Pull — Weighted Pull-Up or Lat Pulldown 3–4 sets, Barbell or Chest-Supported Row 3–4 sets, Single-Arm Row 2 sets, Rear-Delt Fly 2–3 sets, Dumbbell Curl 2–3 sets, Hammer Curl 2 sets.',
                'Day 3 • Legs — Back Squat 3–4 sets, Romanian Deadlift 3 sets, Leg Press 2–3 sets, Leg Curl 2–3 sets, Calf Raise 3–4 sets.',
                'Day 4 • Upper — Incline Bench 3 sets, Machine Row 3 sets, Dumbbell Shoulder Press 2–3 sets, Pulldown 2–3 sets, Pec Deck 2 sets, Curl 2 sets, Triceps Extension 2 sets.',
                'Day 5 • Lower — Deadlift or Hack Squat 2–3 sets, Front Squat or Split Squat 2–3 sets, Hip Thrust 2–3 sets, Leg Curl 2 sets, Calf Raise 3 sets, Abs 2–3 sets.',
            ]
            weekly_sets = {
                'Chest': '10 to 14 hard sets',
                'Back': '10 to 16 hard sets',
                'Quads': '8 to 14 hard sets',
                'Hamstrings/Glutes': '8 to 14 hard sets',
                'Delts': '8 to 12 hard sets',
                'Arms': '6 to 10 hard sets',
            }
        else:
            split_name = 'Push / Pull / Legs / Upper / Lower / Weak-point'
            schedule = [
                'Day 1 • Push — Bench Press 3–4 sets, Incline Dumbbell Press 3 sets, Chest Press 2 sets, Overhead Press 2–3 sets, Lateral Raise 3 sets, Triceps Pressdown 2–3 sets.',
                'Day 2 • Pull — Pull-Up or Pulldown 3–4 sets, Chest-Supported Row 3–4 sets, Cable Row 2 sets, Rear-Delt Fly 2–3 sets, Dumbbell Curl 2–3 sets, Hammer Curl 2 sets.',
                'Day 3 • Legs — Back Squat 3–4 sets, Romanian Deadlift 3 sets, Leg Press 2–3 sets, Leg Curl 2–3 sets, Calves 3 sets.',
                'Day 4 • Upper — Incline Bench 3 sets, Machine Row 3 sets, Shoulder Press 2–3 sets, Pulldown 2–3 sets, Pec Deck 2 sets, Curl 2 sets, Triceps Extension 2 sets.',
                'Day 5 • Lower — Deadlift or Hack Squat 2–3 sets, Split Squat 2–3 sets, Hip Thrust 2–3 sets, Leg Curl 2 sets, Calves 3 sets, Abs 2–3 sets.',
                'Day 6 • Weak-point / pump — choose 2 lagging muscles only, 4 to 6 total sets each with stable low-fatigue exercises like machine press, cable fly, machine row, lateral raise, curls, triceps extensions, leg extension, or leg curl.',
            ]
            weekly_sets = {
                'Chest': '10 to 16 hard sets',
                'Back': '12 to 18 hard sets',
                'Quads': '10 to 14 hard sets',
                'Hamstrings/Glutes': '10 to 14 hard sets',
                'Delts': '8 to 14 hard sets',
                'Arms': '8 to 12 hard sets',
            }

        if 'strength' in goal_low:
            schedule.append('Strength emphasis note — keep the first main compound of the day in a lower rep range such as 4 to 6 reps and trim some isolation work if recovery drops.')
        if 'recomposition' in goal_low:
            schedule.append('Recomposition note — keep weekly sets in the middle of the range, keep compounds hard, and avoid junk volume.')
        if (notes or '').strip():
            schedule.append(f'Custom adjustment note — {notes.strip()}')
        return split_name, schedule, weekly_sets

    def calculate_body_recomp(self, age, sex, height_cm, weight_kg, bodyfat_pct, training_days, focus, steps_text):
        try:
            age_v = self._parse_positive_float(age, 'Age')
            height_v = self._parse_positive_float(height_cm, 'Height')
            weight_v = self._parse_positive_float(weight_kg, 'Weight')
            bf = float(bodyfat_pct) if (bodyfat_pct or '').strip() else None
            days = int(float(training_days or '3'))
            steps = int(float(steps_text or '7000'))
            if days < 0:
                days = 0
        except Exception as exc:
            self.recomp_result = f'Could not calculate recomposition target: {exc}'
            self.recomp_status = 'Fix the inputs and try again.'
            return
        sex_text = (sex or 'Male').strip().lower()
        if sex_text.startswith('f'):
            bmr = 10 * weight_v + 6.25 * height_v - 5 * age_v - 161
        else:
            bmr = 10 * weight_v + 6.25 * height_v - 5 * age_v + 5
        activity_factor = 1.25 + min(0.35, days * 0.06) + min(0.15, max(0, steps - 4000) / 30000.0)
        maintenance = bmr * activity_factor
        focus_low = (focus or 'Recomposition').strip().lower()
        if focus_low == 'fat loss focus':
            target = maintenance - 300
            protein_per_kg = 2.1
        elif focus_low == 'lean gain focus':
            target = maintenance + 150
            protein_per_kg = 1.8
        else:
            target = maintenance - 100
            protein_per_kg = 2.0
        protein = weight_v * protein_per_kg
        lean_mass_text = 'Lean-mass estimate unavailable without body-fat input.'
        if bf is not None and 3 <= bf <= 70:
            lean_mass = weight_v * (1 - bf / 100.0)
            fat_mass = weight_v - lean_mass
            lean_mass_text = f'Estimated lean mass: {lean_mass:.1f} kg\nEstimated fat mass: {fat_mass:.1f} kg'
        offline = (
            f'Estimated maintenance calories: {round(maintenance):,} kcal/day\n'
            f'Recomposition-focused calories: {round(target):,} kcal/day\n'
            f'Protein target: about {round(protein):,} g/day\n'
            f'{lean_mass_text}\n\n'
            f'Recomposition advice\n'
            f'• Lift progressively {max(2, days)} times per week.\n'
            f'• Keep daily steps consistent.\n'
            f'• Track body weight, waist, gym performance, and photos for 2 to 4 weeks before adjusting.\n'
            f'• A small calorie deficit with high protein usually works best when body-fat is higher.'
        )
        if self.ai_mode == 'online':
            try:
                prompt = (
                    f'Explain this body recomposition calculation in a practical coaching style. '
                    f'Age {age}, sex {sex}, height {height_cm} cm, weight {weight_kg} kg, body fat {bodyfat_pct or "unknown"}%, '
                    f'training days {training_days}, daily steps {steps_text or "unknown"}, focus {focus}. '
                    f'Base result: {offline}'
                )
                answer = self.ask_gemini(prompt, purpose='recomp')
                if answer:
                    self.recomp_result = answer + "\n\nBase calculation\n" + offline
                    self.recomp_status = 'AI body recomposition answer from Gemini'
                    show_message('Body Recomposition Calculator', self.recomp_result)
                    return
            except Exception:
                self.recomp_status = 'Gemini failed, showing offline body recomposition guidance.'
        self.recomp_result = offline
        self.recomp_status = 'Offline body recomposition answer'
        show_message('Body Recomposition Calculator', self.recomp_result)

    def calculate_ai_plan(self, age, sex, height_cm, weight_kg, activity, goal):
        try:
            base = self._offline_plan(age, sex, height_cm, weight_kg, activity, goal)
        except Exception as exc:
            self.plan_result = f'Could not calculate plan: {exc}'
            self.plan_status = 'Fix the inputs and try again.'
            return
        if self.ai_mode == 'online':
            try:
                prompt = (
                    f"Use these already-computed targets and explain them like a smart fitness nutrition coach. "
                    f"Age: {age}, sex: {sex}, height_cm: {height_cm}, weight_kg: {weight_kg}, activity: {activity}, goal: {goal}. "
                    f"Base plan: {base}. Keep it practical, science-based, and concise."
                )
                answer = self.ask_gemini(prompt, purpose='nutrition_plan')
                if answer:
                    self.plan_result = answer + f"\n\nBase targets\n{base}"
                    self.plan_status = 'AI planner answer from Gemini'
                    show_message('AI Calorie & Protein Plan', self.plan_result)
                    return
            except Exception:
                self.plan_status = 'Gemini failed, showing offline science-based plan.'
        self.plan_result = base
        self.plan_status = 'Offline AI planner answer'
        show_message('AI Calorie & Protein Plan', self.plan_result)

    def generate_nutrition_plan(self, goal, style, calories_text, protein_text, meals_text, restrictions):
        calories = (calories_text or '').strip()
        protein = (protein_text or '').strip()
        meals = (meals_text or '').strip() or '3'
        restrictions = (restrictions or '').strip()
        base = self._offline_nutrition_plan(goal, style, calories, protein, meals, restrictions)
        if self.ai_mode == 'online':
            try:
                prompt = (
                    f'Create a practical nutrition plan. Goal: {goal}. Style: {style}. Target calories: {calories or "not provided"}. '
                    f'Protein target: {protein or "not provided"}. Meals per day: {meals}. Restrictions: {restrictions or "none"}. '
                    f'Base plan: {base}'
                )
                answer = self.ask_gemini(prompt, purpose='nutrition_plan')
                if answer:
                    self.nutrition_result = answer + '\n\nOffline structure\n' + base
                    self.nutrition_status = 'AI nutrition plan from Gemini'
                    show_message('AI Nutrition Plan', self.nutrition_result)
                    return
            except Exception:
                self.nutrition_status = 'Gemini failed, showing offline nutrition plan.'
        self.nutrition_result = base
        self.nutrition_status = 'Offline nutrition plan'
        show_message('AI Nutrition Plan', self.nutrition_result)

    def analyze_food(self, food_text):
        food_text = (food_text or '').strip()
        if not food_text:
            self.food_result = 'Describe the food and amount first.'
            return
        offline_estimate = self._offline_food_analysis(food_text)
        if self.ai_mode == 'online':
            try:
                prompt = (
                    "Estimate the nutrition for this food description as a fitness nutrition coach. "
                    "Return a clear plain-text nutrition breakdown using these exact labels on separate lines: "
                    "Calories:, Protein:, Carbs:, Fat:, Sugar:, Fiber:, Sodium:. "
                    "After that, add a short note called Estimate Note:. "
                    f"Food: {food_text}"
                )
                answer = self.ask_gemini(prompt, purpose='food_analysis')
                if answer and self._looks_like_complete_nutrition_answer(answer):
                    self.food_result = answer
                    self.food_status = 'AI food analysis from Gemini'
                    show_message('AI Food Analysis', answer)
                    return
                if answer:
                    self.food_result = answer + "\n\nOffline structured estimate\n" + offline_estimate
                    self.food_status = 'Gemini answer was incomplete, so offline nutrition details were added.'
                    show_message('AI Food Analysis', self.food_result)
                    return
            except Exception:
                self.food_status = 'Gemini failed, showing offline food estimate.'
        self.food_result = offline_estimate
        self.food_status = 'Offline AI food estimate'
        show_message('AI Food Analysis', self.food_result)

    def load_gemini_config(self):
        try:
            if CLOUD_CONFIG_PATH.exists():
                data = json.loads(CLOUD_CONFIG_PATH.read_text(encoding='utf-8'))
                if isinstance(data, dict) and data.get('gemini_api_key'):
                    return {'enabled': True, **data}
        except Exception:
            pass
        return {'enabled': False}

    def ask_gemini(self, question, purpose='coach'):
        if requests is None:
            raise RuntimeError('The requests package is not available.')
        cfg = self.load_gemini_config()
        if not cfg.get('enabled'):
            return None
        api_key = cfg.get('gemini_api_key')
        model = cfg.get('gemini_model', 'gemini-3.8-flash')
        system_prompt = (
            'You are a science-based strength training and fitness coach. '
            'Give evidence-based advice about hypertrophy, gym progress, recovery, exercise technique, calorie intake, protein targets, body recomposition, nutrition planning, and food nutrition estimates. '
            'When making workouts, respect these rules: enough weekly volume around 6 to 20 hard sets per muscle, enough time between overlapping sessions, and a target of 2x+ per-muscle frequency when possible. '
            'For food estimates, clearly state that values are estimates. '
            'Do not diagnose diseases. If the user describes dangerous symptoms, advise urgent medical care. '
            'Keep answers practical, simple, and concise.'
        )
        if purpose == 'nutrition_plan':
            system_prompt += ' Explain calorie and macro targets clearly and make the plan useful for real-world eating.'
        elif purpose == 'food_analysis':
            system_prompt += ' Estimate calories, protein, carbs, fat, sugar, fiber, and sodium. Use a readable format with those labels.'
        elif purpose == 'recomp':
            system_prompt += ' Explain body recomposition clearly, with realistic expectations and useful next steps.'
        elif purpose == 'training_plan':
            system_prompt += ' Build structured weekly gym plans with progression, recovery spacing, weekly set targets, and smart per-muscle frequency.'
        else:
            system_prompt += ' Answer like a helpful strength coach.'
        payload = {
            'systemInstruction': {'parts': [{'text': system_prompt}]},
            'contents': [{'role': 'user', 'parts': [{'text': question}]}],
            'generationConfig': {'temperature': 0.2, 'maxOutputTokens': 800},
        }
        data = _gemini_generate_content(model, api_key, payload)
        candidates = data.get('candidates') or []
        if not candidates:
            raise RuntimeError('Gemini returned no candidates.')
        content = (candidates[0].get('content') or {})
        parts = content.get('parts') or []
        answer = ''.join(part.get('text', '') for part in parts if isinstance(part, dict)).strip()
        if not answer:
            raise RuntimeError('Gemini returned an empty answer.')
        return answer

    def _looks_like_complete_nutrition_answer(self, answer: str) -> bool:
        low = (answer or '').lower()
        required = ['calories', 'protein', 'carbs', 'fat']
        return all(word in low for word in required) and len((answer or '').strip()) >= 80

    def _parse_positive_float(self, value, label):
        text_v = (value or '').strip()
        if not text_v:
            raise ValueError(f'{label} is required.')
        number = float(text_v)
        if number <= 0:
            raise ValueError(f'{label} must be greater than 0.')
        return number

    def _offline_plan(self, age, sex, height_cm, weight_kg, activity, goal):
        age_v = self._parse_positive_float(age, 'Age')
        height_v = self._parse_positive_float(height_cm, 'Height')
        weight_v = self._parse_positive_float(weight_kg, 'Weight')
        sex_text = (sex or 'Male').strip().lower()
        if sex_text.startswith('f'):
            bmr = 10 * weight_v + 6.25 * height_v - 5 * age_v - 161
        else:
            bmr = 10 * weight_v + 6.25 * height_v - 5 * age_v + 5
        activity_map = {
            'sedentary': 1.2,
            'lightly active': 1.375,
            'moderately active': 1.55,
            'very active': 1.725,
            'athlete': 1.9,
        }
        activity_key = (activity or 'Moderately active').strip().lower()
        factor = activity_map.get(activity_key, 1.55)
        maintenance = bmr * factor
        goal_text = (goal or 'Calorie maintenance').strip().lower()
        if goal_text == 'calorie deficit':
            target_cal = maintenance - 450
            protein_low, protein_high = 1.8, 2.4
        elif goal_text == 'lean bulking':
            target_cal = maintenance + 200
            protein_low, protein_high = 1.6, 2.2
        elif goal_text == 'bulking':
            target_cal = maintenance + 350
            protein_low, protein_high = 1.6, 2.0
        else:
            target_cal = maintenance
            protein_low, protein_high = 1.6, 2.2
        protein_target = weight_v * ((protein_low + protein_high) / 2.0)
        fat_target = weight_v * (0.8 if goal_text != 'calorie deficit' else 0.7)
        carb_target = max(0.0, (target_cal - protein_target * 4 - fat_target * 9) / 4)
        return (
            f"Estimated maintenance calories: {round(maintenance):,} kcal/day\n"
            f"Suggested calories for {goal}: {round(target_cal):,} kcal/day\n"
            f"Protein target: about {round(protein_target):,} g/day "
            f"(roughly {protein_low:.1f} to {protein_high:.1f} g/kg range)\n"
            f"Fat target: about {round(fat_target):,} g/day\n"
            f"Carb target: about {round(carb_target):,} g/day\n\n"
            f"Notes\n"
            f'• Pair this with progressive lifting and consistent weekly gym volume.\n'
            f"• Re-check body weight, gym performance, hunger, and recovery after 2 to 3 weeks.\n"
            f"• For deficit, prioritize high protein and strength training.\n"
            f"• For lean bulking and bulking, keep rate of gain controlled so fat gain stays reasonable."
        )

    def _offline_nutrition_plan(self, goal, style, calories, protein, meals, restrictions):
        calories_v = calories if calories else 'Use your calorie target from the planner'
        protein_v = protein if protein else 'Aim for 1.6 to 2.2 g/kg body weight'
        try:
            meals_n = max(2, min(6, int(float(meals or '3'))))
        except Exception:
            meals_n = 3
        style_low = (style or 'Balanced').lower()
        carb_note = 'center most carbs around training and earlier meals'
        fat_note = 'keep fats moderate and steady'
        if 'lower carb' in style_low:
            carb_note = 'keep carbs lower and place most of them around training'
            fat_note = 'use more fats for satiety'
        elif 'higher carb' in style_low:
            carb_note = 'push more carbs around training and recovery'
            fat_note = 'keep fats a bit lower'
        elif 'budget' in style_low:
            carb_note = 'use affordable staples like rice, oats, bread, potatoes, and bananas'
            fat_note = 'use eggs, sardines, peanut butter, and cooking oil carefully'
        return (
            f"Goal: {goal}\nStyle: {style}\nTarget calories: {calories_v}\nProtein target: {protein_v}\nMeals per day: {meals_n}\nRestrictions: {restrictions or 'None'}\n\n"
            f"Daily structure\n"
            f"• Meal 1: protein + carbs + fruit\n"
            f"• Meal 2: protein + carbs + vegetables\n"
            f"• Meal 3: protein + carbs + vegetables\n"
            f"• Extra meal/snack if needed: whey, eggs, yogurt, milk, tuna, sandwich, or oats\n\n"
            f"Planning notes\n"
            f"• {carb_note}.\n"
            f"• {fat_note}.\n"
            f"• Keep protein spread across the day in 3 to 5 feedings.\n"
            f"• Adjust portions after 2 to 3 weeks based on body weight, hunger, and gym performance."
        )

    def _offline_food_analysis(self, food_text):
        low = (food_text or '').lower()
        food_db = {
            'egg white': {'cal': 17, 'protein': 3.6, 'carbs': 0.2, 'fat': 0.1, 'sugar': 0.2, 'fiber': 0.0, 'sodium': 55},
            'egg whites': {'cal': 17, 'protein': 3.6, 'carbs': 0.2, 'fat': 0.1, 'sugar': 0.2, 'fiber': 0.0, 'sodium': 55},
            'egg': {'cal': 78, 'protein': 6.3, 'carbs': 0.6, 'fat': 5.3, 'sugar': 0.6, 'fiber': 0.0, 'sodium': 62},
            'rice': {'cal': 205, 'protein': 4.3, 'carbs': 44.5, 'fat': 0.4, 'sugar': 0.1, 'fiber': 0.6, 'sodium': 2},
            'chicken breast': {'cal': 165, 'protein': 31.0, 'carbs': 0.0, 'fat': 3.6, 'sugar': 0.0, 'fiber': 0.0, 'sodium': 74},
            'banana': {'cal': 105, 'protein': 1.3, 'carbs': 27.0, 'fat': 0.4, 'sugar': 14.0, 'fiber': 3.1, 'sodium': 1},
            'oats': {'cal': 389, 'protein': 16.9, 'carbs': 66.3, 'fat': 6.9, 'sugar': 0.9, 'fiber': 10.6, 'sodium': 2},
            'bread': {'cal': 80, 'protein': 4.0, 'carbs': 14.0, 'fat': 1.0, 'sugar': 2.0, 'fiber': 2.0, 'sodium': 150},
            'whey': {'cal': 120, 'protein': 24.0, 'carbs': 3.0, 'fat': 1.5, 'sugar': 2.0, 'fiber': 0.0, 'sodium': 80},
            'milk': {'cal': 122, 'protein': 8.0, 'carbs': 12.0, 'fat': 4.8, 'sugar': 12.0, 'fiber': 0.0, 'sodium': 115},
            'fried chicken': {'cal': 320, 'protein': 25.0, 'carbs': 12.0, 'fat': 20.0, 'sugar': 0.5, 'fiber': 1.0, 'sodium': 700},
            'apple': {'cal': 95, 'protein': 0.5, 'carbs': 25.0, 'fat': 0.3, 'sugar': 19.0, 'fiber': 4.4, 'sodium': 2},
            'peanut butter': {'cal': 188, 'protein': 8.0, 'carbs': 7.0, 'fat': 16.0, 'sugar': 3.0, 'fiber': 2.0, 'sodium': 147},
        }
        quantity = 1.0
        qty_match = re.search(r'(\d+(?:\.\d+)?)', low)
        if qty_match:
            try:
                quantity = float(qty_match.group(1))
            except Exception:
                quantity = 1.0
        matched_key = None
        for key in sorted(food_db.keys(), key=len, reverse=True):
            if key in low:
                matched_key = key
                break
        if not matched_key:
            return (
                'Offline estimator could not confidently match that food. '
                'Switch to Online AI for a smarter estimate of calories, protein, carbs, sugar, sodium, and more.'
            )
        item = food_db[matched_key]
        cal = item['cal'] * quantity
        protein = item['protein'] * quantity
        carbs = item['carbs'] * quantity
        fat = item['fat'] * quantity
        sugar = item['sugar'] * quantity
        fiber = item['fiber'] * quantity
        sodium = item['sodium'] * quantity
        return (
            f"Estimated nutrition for about {quantity:g} serving(s) of {matched_key}\n"
            f"Calories: {round(cal):,} kcal\n"
            f"Protein: {protein:.1f} g\n"
            f"Carbs: {carbs:.1f} g\n"
            f"Fat: {fat:.1f} g\n"
            f"Sugar: {sugar:.1f} g\n"
            f"Fiber: {fiber:.1f} g\n"
            f"Sodium: {round(sodium):,} mg\n\n"
            f"Offline estimates are approximate and work best for common foods and simple portions."
        )

    def offline_ai(self, question):
        q = (question or '').lower()
        if any(flag in q for flag in ['chest pain', 'stroke', 'fainted', 'fainting', 'passed out', 'severe shortness of breath']):
            return 'This could be urgent. Please seek immediate medical care or emergency help now.'
        if 'protein' in q:
            return 'Protein intake around 1.4–2.0 g per kg of body weight can support muscle growth, recovery, and fat loss while preserving lean mass.'
        if 'fat loss' in q or 'weight loss' in q or 'lose fat' in q:
            return 'Fat loss usually works best with a sustainable calorie deficit, high protein intake, resistance training, daily movement, and enough sleep.'
        if 'muscle' in q or 'hypertrophy' in q:
            return 'Muscle gain needs progressive overload, enough training volume, enough protein, and recovery. A small calorie surplus can help if gaining size is your goal.'
        if 'sleep' in q or 'recovery' in q:
            return 'Sleep strongly affects recovery, hormones, mood, and performance. A practical target for most adults is about 7–9 hours per night.'
        if 'strength' in q or 'jog' in q or 'cardio' in q:
            return 'For this strength-focused app, treat cardio as support work. Keep it moderate so it does not hurt gym performance or recovery.'
        if 'creatine' in q:
            return 'Creatine monohydrate is one of the best-supported supplements for strength and power. A common daily dose is 3–5 g with good recovery readiness.'
        if 'recovery readiness' in q or 'water' in q:
            return 'recovery readiness should match thirst, sweat rate, heat, and workout length. Longer or hotter sessions may also need electrolytes.'
        if 'injury' in q or 'pain' in q:
            return 'For injury risk, avoid sudden spikes in hard sets, keep technique controlled, recover well, and get medical evaluation if pain is severe, worsening, or persistent.'
        if 'calorie' in q or 'maintenance' in q or 'bulking' in q or 'deficit' in q:
            return 'Use your body weight, height, age, activity level, and goal to estimate calories. Then adjust based on scale trend, gym performance, hunger, and recovery after 2 to 3 weeks.'
        if 'carb' in q or 'sugar' in q or 'sodium' in q:
            return 'Nutrition estimates depend on the food, cooking method, brand, and portion size. For best results, describe the food and amount in the AI food analyzer.'
        if 'split' in q or 'training plan' in q or 'workout' in q:
            return 'A good gym split usually answers three things: enough weekly hard sets per muscle, enough recovery time before repeating a sore muscle, and a frequency close to twice per week when possible.'
        return 'Train consistently, progress gradually, eat enough protein, sleep well, and match your training to your goal. That is the strongest base for most gym progress.'

class JournalScreen(Screen):
    entries_text = StringProperty('No journal entries yet.')
    journal_status = StringProperty('Use this like a private training log for decisions, lessons, and next-session focus.')
    journal_prompt_text = StringProperty('Prompt: What lift felt better today, what caused fatigue, and what will you adjust next session?')

    def on_pre_enter(self):
        self.refresh_entries()

    def generate_reflection_prompt(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        weekly = app.db.weekly_totals(app.current_user_id)
        today = app.db.get_today(app.current_user_id)
        readiness = int(safe_row_value(today, 'readiness', 70))
        prompts = [
            f"This week you logged {int(weekly.get('sets', 0))} sets and {float(weekly.get('volume', 0.0)):.0f} kg volume. What exercise needs better progression?",
            f"Readiness is {readiness}%. Did your warm-up sets match that feeling?",
            'What muscle or joint needs more recovery before the next hard session?',
            'What technique cue should you focus on next time?',
            'Did you stop sets at the planned RIR, or did you push too close to failure?',
        ]
        idx = datetime.now().day % len(prompts)
        self.journal_prompt_text = 'Prompt: ' + prompts[idx]

    def save_training_journal(self, title, entry_type, energy, soreness, lesson, next_focus, body):
        app = App.get_running_app()
        if not app.require_login():
            return
        title = (title or '').strip() or f'{entry_type} • {datetime.now().strftime("%b %d")}'
        entry_type = (entry_type or 'Workout Reflection').strip()
        lesson = (lesson or '').strip()
        next_focus = (next_focus or '').strip()
        body = (body or '').strip()
        energy = (energy or '').strip() or '?'
        soreness = (soreness or '').strip() or '?'
        full_body = (
            f'Type: {entry_type}\n'
            f'Energy: {energy}/5\n'
            f'Soreness: {soreness}/5\n\n'
            f'What improved / lesson:\n{lesson or "Not written."}\n\n'
            f'Next session focus:\n{next_focus or "Not written."}\n\n'
            f'Full note:\n{body or "Not written."}'
        )
        app.db.add_journal(app.current_user_id, title, full_body)
        self.journal_status = 'Training journal saved.'
        self.refresh_entries()
        self.generate_reflection_prompt()

    def save_entry(self, title, body):
        app = App.get_running_app()
        if not app.require_login():
            return
        if not title.strip() and not body.strip():
            self.journal_status = 'Write a title or note first.'
            return
        app.db.add_journal(app.current_user_id, title.strip() or 'Training note', body.strip())
        self.journal_status = 'Journal entry saved.'
        self.refresh_entries()

    def refresh_entries(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        rows = app.db.journal_entries(app.current_user_id, limit=8)
        if rows:
            chunks = []
            for row in rows:
                created = safe_row_value(row, 'created_at', '')
                try:
                    stamp = datetime.fromisoformat(str(created)).strftime('%b %d, %I:%M %p')
                except Exception:
                    stamp = str(created)[:16]
                chunks.append(f"• {safe_row_value(row, 'title', 'Training note')} — {stamp}\n{str(safe_row_value(row, 'body', '')).strip()[:360]}")
            self.entries_text = '\n\n'.join(chunks)
        else:
            self.entries_text = 'No reflections yet. Save a workout, recovery, technique, PR, or deload note.'



class TabataScreen(Screen):
    status_text = StringProperty('Strength interval timer ready.')
    timer_text = StringProperty('00:30')
    round_text = StringProperty('Round 0 / 0')
    phase_text = StringProperty('Ready')
    running = BooleanProperty(False)
    work_seconds = NumericProperty(30)
    rest_seconds = NumericProperty(90)
    total_rounds = NumericProperty(4)
    current_round = NumericProperty(0)
    remaining_seconds = NumericProperty(30)
    phase = StringProperty('work')

    def on_pre_enter(self):
        self.refresh_display()

    def _parse_seconds(self, value, default):
        raw = (value or '').strip().lower()
        if not raw:
            return int(default)
        try:
            if ':' in raw:
                mins, secs = raw.split(':', 1)
                total = int(float(mins or 0)) * 60 + int(float(secs or 0))
            elif raw.endswith(('seconds', 'second', 'secs', 'sec', 's')):
                total = int(float(re.sub(r'[^0-9.]', '', raw)))
            elif raw.endswith(('minutes', 'minute', 'mins', 'min', 'm')):
                total = int(float(re.sub(r'[^0-9.]', '', raw)) * 60)
            else:
                total = int(float(raw))
        except Exception:
            total = int(default)
        return max(1, min(3600, total))

    def _format_seconds(self, seconds):
        seconds = max(0, int(seconds or 0))
        mins, secs = divmod(seconds, 60)
        return f'{mins:02d}:{secs:02d}'

    def refresh_display(self):
        self.timer_text = self._format_seconds(self.remaining_seconds)
        self.round_text = f'Round {int(self.current_round)} / {int(self.total_rounds)}'
        self.phase_text = self.phase.title() if self.running else 'Ready'

    def configure_timer(self, work_text, rest_text, rounds_text):
        self.work_seconds = self._parse_seconds(work_text, 30)
        self.rest_seconds = self._parse_seconds(rest_text, 90)
        try:
            rounds = int(float((rounds_text or '').strip() or 4))
        except Exception:
            rounds = 4
        self.total_rounds = max(1, min(30, rounds))
        self.current_round = 0
        self.phase = 'work'
        self.remaining_seconds = self.work_seconds
        self.running = False
        self.status_text = (
            f'Set: {self._format_seconds(self.work_seconds)} work / '
            f'{self._format_seconds(self.rest_seconds)} rest x {int(self.total_rounds)} rounds.'
        )
        self.refresh_display()

    def start_timer(self, work_text='', rest_text='', rounds_text=''):
        if work_text or rest_text or rounds_text:
            self.configure_timer(work_text, rest_text, rounds_text)
        if self.current_round <= 0:
            self.current_round = 1
            self.phase = 'work'
            self.remaining_seconds = self.work_seconds
        self.running = True
        self.status_text = 'Timer running. Use this for warm-up sets, pump work, mobility, or conditioning circuits.'
        try:
            if getattr(self, '_interval_event', None):
                self._interval_event.cancel()
        except Exception:
            pass
        self._interval_event = Clock.schedule_interval(self._tick, 1)
        self.refresh_display()

    def pause_timer(self):
        self.running = False
        self.status_text = 'Timer paused.'
        try:
            if getattr(self, '_interval_event', None):
                self._interval_event.cancel()
                self._interval_event = None
        except Exception:
            pass
        self.refresh_display()

    def reset_timer(self):
        self.running = False
        self.current_round = 0
        self.phase = 'work'
        self.remaining_seconds = self.work_seconds
        self.status_text = 'Timer reset.'
        try:
            if getattr(self, '_interval_event', None):
                self._interval_event.cancel()
                self._interval_event = None
        except Exception:
            pass
        self.refresh_display()

    def _tick(self, dt):
        if not self.running:
            return False
        self.remaining_seconds = max(0, int(self.remaining_seconds) - 1)
        if self.remaining_seconds <= 0:
            if self.phase == 'work':
                self.phase = 'rest'
                self.remaining_seconds = self.rest_seconds
                self.status_text = 'Rest phase. Recover for the next round.'
            else:
                if self.current_round >= self.total_rounds:
                    self.running = False
                    self.status_text = 'Interval timer complete.'
                    try:
                        send_local_notification('Buo timer', 'Strength interval timer complete.')
                    except Exception:
                        pass
                    self.refresh_display()
                    return False
                self.current_round += 1
                self.phase = 'work'
                self.remaining_seconds = self.work_seconds
                self.status_text = 'Work phase. Keep technique clean.'
        self.refresh_display()
        return True

class ShareHubScreen(Screen):
    privacy_text = StringProperty('Buo is now framed as a private, personal-use training app. Your journal, goals, reminders, and plans stay local unless you choose to share a summary out to another app.')
    share_preview = StringProperty('')
    mode_notes = StringProperty('Use this page when you want to share a private summary from Buo. Your workouts, notes, and progress stay local unless you choose to send a summary out. The new in-app option tries to keep the experience inside Buo first.')

    def on_pre_enter(self, *args):
        self.share_preview = build_personal_share_text(App.get_running_app())

    def share_any(self):
        ok = android_share_text('Buo progress update', self.share_preview)
        if not ok:
            show_message('Share not available', 'Could not open a share target on this device.')

    def open_in_app(self, channel: str):
        ok = open_social_in_app(channel)
        if not ok:
            show_message('In-app browser failed', 'Could not open that service inside the app on this device.')

    def open_channel(self, channel: str):
        targets = {
            'whatsapp': 'https://wa.me/',
            'telegram': 'https://t.me/',
            'messenger': 'fb-messenger://',
            'discord': 'https://discord.com/app',
        }
        ok = open_external_uri(targets.get(channel, 'https://discord.com/app'))
        if not ok:
            show_message('Open app failed', 'That app could not be opened on this device.')

    def on_leave(self):
        try:
            ev = getattr(self, '_rest_timer_event', None)
            if ev:
                ev.cancel()
            self._rest_timer_event = None
        except Exception:
            pass

    def _format_timer_seconds(self, seconds):
        seconds = max(0, int(seconds or 0))
        mins, secs = divmod(seconds, 60)
        return f'{mins:02d}:{secs:02d}'

    def _parse_timer_duration(self, value):
        raw = (value or '').strip().lower()
        if not raw:
            return int(self.rest_timer_total_seconds or 120)

        if ':' in raw:
            left, right = raw.split(':', 1)
            mins = int(float(left.strip() or 0))
            secs = int(float(right.strip() or 0))
            total = mins * 60 + secs
        elif raw.endswith(('seconds', 'second', 'secs', 'sec', 's')):
            total = int(float(re.sub(r'[^0-9.]', '', raw)))
        elif raw.endswith(('minutes', 'minute', 'mins', 'min', 'm')):
            total = int(float(re.sub(r'[^0-9.]', '', raw)) * 60)
        else:
            total = int(float(raw) * 60)

        if total <= 0 or total > 3600:
            raise ValueError('Timer must be between 1 second and 60 minutes.')
        return total

    def set_named_timer(self, name, duration_text):
        try:
            seconds = self._parse_timer_duration(duration_text)
        except Exception:
            show_message('Invalid timer', 'Use 30s, 2m, 3m, 2:30, or plain 2 for 2 minutes.')
            return

        clean_name = (name or '').strip() or 'Workout timer'
        self.rest_timer_running = False
        try:
            ev = getattr(self, '_rest_timer_event', None)
            if ev:
                ev.cancel()
            self._rest_timer_event = None
        except Exception:
            pass

        self.rest_timer_total_seconds = seconds
        self.rest_timer_seconds = seconds
        self.rest_timer_text = self._format_timer_seconds(seconds)
        self.rest_timer_name_text = f'Timer: {clean_name}'
        self.rest_timer_status = f'{clean_name} set to {self.rest_timer_text}. Press Start timer.'

    def start_named_timer(self, name, duration_text):
        if (duration_text or '').strip():
            self.set_named_timer(name, duration_text)
        elif (name or '').strip():
            self.rest_timer_name_text = f'Timer: {(name or "").strip()}'

        if int(self.rest_timer_seconds or 0) <= 0:
            self.rest_timer_seconds = int(self.rest_timer_total_seconds or 120)
            self.rest_timer_text = self._format_timer_seconds(self.rest_timer_seconds)

        self.rest_timer_running = True
        self.rest_timer_status = 'Timer running.'
        try:
            ev = getattr(self, '_rest_timer_event', None)
            if ev:
                ev.cancel()
        except Exception:
            pass
        self._rest_timer_event = Clock.schedule_interval(self._tick_rest_timer, 1)

    def start_rest_timer(self, minutes_text=''):
        self.start_named_timer('Working set', minutes_text)

    def toggle_rest_timer(self):
        if self.rest_timer_running:
            self.rest_timer_running = False
            self.rest_timer_status = 'Timer paused.'
            try:
                ev = getattr(self, '_rest_timer_event', None)
                if ev:
                    ev.cancel()
                self._rest_timer_event = None
            except Exception:
                pass
            return

        if int(self.rest_timer_seconds or 0) <= 0:
            self.rest_timer_seconds = int(self.rest_timer_total_seconds or 120)
            self.rest_timer_text = self._format_timer_seconds(self.rest_timer_seconds)

        self.rest_timer_running = True
        self.rest_timer_status = 'Timer resumed.'
        try:
            ev = getattr(self, '_rest_timer_event', None)
            if ev:
                ev.cancel()
        except Exception:
            pass
        self._rest_timer_event = Clock.schedule_interval(self._tick_rest_timer, 1)

    def pause_rest_timer(self):
        if self.rest_timer_running:
            self.rest_timer_running = False
            self.rest_timer_status = 'Timer paused.'
            try:
                ev = getattr(self, '_rest_timer_event', None)
                if ev:
                    ev.cancel()
                self._rest_timer_event = None
            except Exception:
                pass

    def reset_rest_timer(self):
        self.rest_timer_running = False
        try:
            ev = getattr(self, '_rest_timer_event', None)
            if ev:
                ev.cancel()
            self._rest_timer_event = None
        except Exception:
            pass
        self.rest_timer_seconds = int(self.rest_timer_total_seconds or 120)
        self.rest_timer_text = self._format_timer_seconds(self.rest_timer_seconds)
        self.rest_timer_status = 'Timer reset. Press Start timer.'

    def _tick_rest_timer(self, dt):
        if not self.rest_timer_running:
            return False

        remaining = max(0, int(self.rest_timer_seconds or 0) - 1)
        self.rest_timer_seconds = remaining
        self.rest_timer_text = self._format_timer_seconds(remaining)

        if remaining <= 0:
            self.rest_timer_running = False
            self.set_counter += 1
            self.set_counter_text = f'Sets completed: {int(self.set_counter)}'
            self.rest_timer_status = 'Timer done. Set logged automatically.'
            try:
                ev = getattr(self, '_rest_timer_event', None)
                if ev:
                    ev.cancel()
                self._rest_timer_event = None
            except Exception:
                pass
            try:
                send_local_notification('Buo timer', f'{self.rest_timer_name_text.replace("Timer: ", "")} done. Next set ready.')
            except Exception:
                pass
            return False
        return True

    def log_set_now(self):
        self.set_counter += 1
        self.set_counter_text = f'Sets completed: {int(self.set_counter)}'
        self.rest_timer_status = 'Set logged manually.'

    def reset_set_counter(self):
        self.set_counter = 0
        self.set_counter_text = 'Sets completed: 0'
        self.rest_timer_status = 'Set counter reset.'

    def _parse_clock_time(self, raw):
        text = (raw or '').strip()
        if not text:
            return None
        for pattern in ('%I:%M %p', '%I:%M%p', '%H:%M'):
            try:
                return datetime.strptime(text.upper(), pattern)
            except Exception:
                pass
        return None

    def calculate_time_between(self, start_text, end_text, purpose):
        start_dt = self._parse_clock_time(start_text)
        end_dt = self._parse_clock_time(end_text)

        if start_dt is None or end_dt is None:
            self.time_calc_result = 'Enter times like 12:00 AM, 10:00 AM, 8:30 PM, or 20:30.'
            return

        crossed_midnight = False
        if end_dt <= start_dt:
            end_dt = end_dt + timedelta(days=1)
            crossed_midnight = True

        delta = end_dt - start_dt
        total_minutes = int(delta.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        purpose_label = purpose or 'Time window'

        extra = ''
        lower = str(purpose_label).lower()
        if lower.startswith('fast'):
            extra = '\nFasting note: this is your fasting window until your break-fast time.'
        elif lower.startswith('sleep'):
            extra = '\nSleep note: this is your sleep opportunity window.'

        midnight_note = '\nNote: end time was treated as the next day.' if crossed_midnight else ''

        self.time_calc_result = (
            f'{purpose_label}\n'
            f'From: {start_dt.strftime("%I:%M %p")}\n'
            f'To: {end_dt.strftime("%I:%M %p")}\n'
            f'Duration: {hours} hour(s) and {minutes} minute(s)'
            f'{midnight_note}'
            f'{extra}'
        )

    def calculate_time_window(self, start_text, hours_text, purpose):
        parsed = self._parse_clock_time(start_text)
        if parsed is None:
            self.time_calc_result = 'Enter start time like 8:00 PM or 20:00.'
            return
        try:
            hours = float((hours_text or '').strip())
            if hours <= 0 or hours > 72:
                raise ValueError
        except Exception:
            self.time_calc_result = 'Enter hours from 0.5 to 72.'
            return
        end_dt = parsed + timedelta(hours=hours)
        self.time_calc_result = (
            f'{purpose or "Time window"}\n'
            f'Start: {parsed.strftime("%I:%M %p")}\n'
            f'Duration: {hours:g} hour(s)\n'
            f'End: {end_dt.strftime("%I:%M %p")}'
        )


class RecordsScreen(Screen):
    records_text = StringProperty('No records yet. Log your first lift or strength session to start building personal bests.')
    milestones_text = StringProperty('No milestones yet. Consistency will unlock them automatically.')
    lifetime_text = StringProperty('No lifetime totals yet.')

    def on_pre_enter(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        try:
            app.db.sync_step_counter(app.current_user_id)
        except Exception:
            pass

        records = app.db.get_records(app.current_user_id)
        lines = []
        if records.get('heaviest_lift'):
            lines.append(f"• Heaviest lift: {records['heaviest_lift']}")
        if records.get('biggest_strength'):
            lines.append(f"• Biggest volume entry: {records['biggest_strength']}")
        if records.get('most_sets'):
            lines.append(f"• Most sets in one entry: {records['most_sets']}")
        if records.get('weekly_volume'):
            lines.append(f"• Weekly volume: {records['weekly_volume']}")
        if records.get('strength_sessions'):
            lines.append(f"• Strength sessions logged: {records['strength_sessions']}")
        self.records_text = '\n'.join(lines) if lines else 'No strength records yet. Log lifts to start building personal bests.'

        milestones = app.db.get_milestones(app.current_user_id, 16)
        if milestones:
            self.milestones_text = '\n'.join(
                f"• {safe_row_value(row, 'title', 'Milestone')} — {safe_row_value(row, 'detail', '') or datetime.fromisoformat(safe_row_value(row, 'achieved_at', datetime.now().isoformat())).strftime('%b %d, %Y')}"
                for row in milestones
            )
        else:
            self.milestones_text = 'No milestones yet. Finish a few strength sessions and they will start unlocking automatically.'

        stats = app.db.get_lifetime_stats(app.current_user_id)
        self.lifetime_text = (
            f"Strength sessions: {stats['strength_sessions']}\n"
            f"Total lifting volume: {stats['volume']:.0f} kg\n"
            f"Total sets: {stats['sets']}\n"
            f"Total reps: {stats['reps']}\n"
            f"Support/recovery time: {stats['minutes']:.0f} min\n"
            f"Estimated steps: {stats['steps']:,}\n"
            f"Sensor lifetime steps: {int(stats.get('sensor_steps', 0)):,}\n"
            f"Journal entries: {stats['journal_entries']}"
        )


class PlansScreen(Screen):

    plan_summary = StringProperty('Generate a structured gym block that balances progressive overload, weekly hard sets, and recovery spacing.')
    plan_text = StringProperty('No plan generated yet.')
    plan_phase_text = StringProperty('Generate a plan to see its build, sharpen, and taper phases.')
    plan_calendar_text = StringProperty('Weekly calendar will appear here after you generate a plan.')
    plan_meta_text = StringProperty('You can tailor gym plans by level, weekly training days, session length, weak points, and schedule limits.')

    def on_pre_enter(self):
        app = App.get_running_app()
        if not app.require_login():
            return
        row = app.db.latest_training_plan(app.current_user_id)
        if row:
            self.plan_summary = row['summary']
            self.plan_text = row['plan_text']
            self.plan_phase_text = app.build_plan_phase_text(row['weeks'])
            self.plan_calendar_text = app.build_plan_calendar_text(row['goal'], row['weeks'], row['days_per_week'])
            self.plan_meta_text = 'Latest saved plan loaded.'

    def _load_gemini_config(self):
        try:
            if CLOUD_CONFIG_PATH.exists():
                data = json.loads(CLOUD_CONFIG_PATH.read_text(encoding='utf-8'))
                if isinstance(data, dict) and data.get('gemini_api_key'):
                    return {'enabled': True, **data}
        except Exception:
            pass
        return {'enabled': False}

    def _ask_gemini_plan(self, prompt: str):
        if requests is None:
            return None
        cfg = self._load_gemini_config()
        if not cfg.get('enabled'):
            return None
        model = cfg.get('gemini_model', 'gemini-3.8-flash')
        api_key = cfg.get('gemini_api_key')
        system_prompt = (
            'You are a science-based fitness coach building safe training plans. '
            'Create structured, practical plans with progression, recovery, deload awareness, and injury-risk reduction. '
            'Keep it concise but useful.'
        )
        payload = {
            'systemInstruction': {'parts': [{'text': system_prompt}]},
            'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0.2, 'maxOutputTokens': 700},
        }
        data = _gemini_generate_content(model, api_key, payload)
        cands = data.get('candidates') or []
        if not cands:
            return None
        parts = ((cands[0].get('content') or {}).get('parts') or [])
        answer = ''.join(part.get('text', '') for part in parts if isinstance(part, dict)).strip()
        return answer or None

    def generate_plan(self, goal: str, level: str, weeks_text: str, days_text: str, minutes_text: str, adjustments: str):
        app = App.get_running_app()
        if not app.require_login():
            return
        try:
            weeks = max(3, min(20, int(weeks_text or '6')))
            days = max(2, min(7, int(days_text or '4')))
            minutes = max(20, min(180, int(minutes_text or '45')))
        except ValueError:
            show_message('Invalid inputs', 'Enter whole numbers for weeks, training days, and session minutes.')
            return
        safe_goal = f"{goal} • {level}"
        summary, plan_text = app.build_periodized_plan(goal, weeks, days, level=level, minutes=minutes, adjustments=adjustments)
        ai_overlay = None
        try:
            prompt = (
                f'Build a training plan for goal {goal}, level {level}, {weeks} weeks, {days} days per week, {minutes} minutes per session. '
                f'Adjustments: {adjustments or "none"}. Base plan summary: {summary}. Base plan details: {plan_text}'
            )
            ai_overlay = self._ask_gemini_plan(prompt)
        except Exception:
            ai_overlay = None
        final_summary = summary if not ai_overlay else ('AI training plan ready. Base structure kept and AI coaching notes added.')
        final_text = plan_text if not ai_overlay else (ai_overlay + '\n\nBase structured plan\n' + plan_text)
        app.db.save_training_plan(app.current_user_id, safe_goal, weeks, days, final_summary, final_text)
        self.plan_summary = final_summary
        self.plan_text = final_text
        self.plan_phase_text = app.build_plan_phase_text(weeks)
        self.plan_calendar_text = app.build_plan_calendar_text(safe_goal, weeks, days)
        self.plan_meta_text = 'AI-enhanced training plan generated.' if ai_overlay else 'Offline structured training plan generated.'
        show_message('Training plan ready', final_summary)

class BuoApp(App):
    title = 'Buo'
    theme_mode = StringProperty('dark')
    bg_color = ListProperty([0.07, 0.07, 0.09, 1])
    card_color = ListProperty([0.12, 0.12, 0.15, 1])
    panel_color = ListProperty([0.10, 0.10, 0.13, 1])
    input_bg_color = ListProperty([0.08, 0.10, 0.15, 1])
    pill_color = ListProperty([0.13, 0.16, 0.23, 1])
    button_alt_color = ListProperty([0.16, 0.19, 0.27, 1])
    text_color = ListProperty([1, 1, 1, 1])
    secondary_text_color = ListProperty([0.78, 0.80, 0.85, 1])
    muted_text_color = ListProperty([0.58, 0.60, 0.66, 1])
    muted_color = ListProperty([0.72, 0.77, 0.86, 1])
    subtle_text_color = ListProperty([0.84, 0.88, 0.94, 1])
    input_text_color = ListProperty([1, 1, 1, 1])
    hint_text_color = ListProperty([0.55, 0.58, 0.64, 1])
    button_text_color = ListProperty([1, 1, 1, 1])
    border_color = ListProperty([0.20, 0.20, 0.25, 1])
    border_color2 = ListProperty([0.25, 0.25, 0.28, 1])
    border_color3 = ListProperty([0.30, 0.30, 0.35, 1])
    border_color4 = ListProperty([0.35, 0.35, 0.40, 1])
    border_color5 = ListProperty([0.40, 0.40, 0.45, 1])
    accent_color = ListProperty([0.96, 0.40, 0.18, 1])
    accent_text_color = ListProperty([1, 0.84, 0.62, 1])

    def build(self):
        self.db = DB(DB_PATH)
        self.db.set_setting('theme_mode', self.db.get_setting('theme_mode', 'dark'))
        self.theme_mode = self.db.get_setting('theme_mode', 'dark')
        self.tracking_service_active = False
        self.current_user_id = None
        self.live_state = None

        self.bg_color = [0.07, 0.07, 0.09, 1]
        self.card_color = [0.12, 0.12, 0.15, 1]
        self.panel_color = [0.10, 0.10, 0.13, 1]
        self.input_bg_color = [0.08, 0.10, 0.15, 1]
        self.pill_color = [0.13, 0.16, 0.23, 1]
        self.button_alt_color = [0.16, 0.19, 0.27, 1]
        self.text_color = [1, 1, 1, 1]
        self.secondary_text_color = [0.78, 0.80, 0.85, 1]
        self.muted_text_color = [0.58, 0.60, 0.66, 1]
        self.muted_color = [0.72, 0.77, 0.86, 1]
        self.subtle_text_color = [0.84, 0.88, 0.94, 1]
        self.input_text_color = [1, 1, 1, 1]
        self.hint_text_color = [0.55, 0.58, 0.64, 1]
        self.button_text_color = [1, 1, 1, 1]
        self.border_color = [0.20, 0.20, 0.25, 1]
        self.border_color2 = [0.25, 0.25, 0.28, 1]
        self.border_color3 = [0.30, 0.30, 0.35, 1]
        self.border_color4 = [0.35, 0.35, 0.40, 1]
        self.border_color5 = [0.40, 0.40, 0.45, 1]
        self.accent_color = [0.96, 0.40, 0.18, 1]
        self.accent_text_color = [1, 0.84, 0.62, 1]

        Builder.load_string(KV)
        self.apply_theme()
        self.sm = ScreenManager(transition=FadeTransition())
        self.sm.add_widget(SplashScreen())
        self.sm.add_widget(LoginScreen())
        self.sm.add_widget(DashboardScreen())
        self.sm.add_widget(LiveMonitorScreen())
        self.sm.add_widget(ActivityScreen())
        self.sm.add_widget(StrengthScreen())
        self.sm.add_widget(WellnessScreen())
        self.sm.add_widget(ReportsScreen())
        self.sm.add_widget(AnalyticsScreen())
        self.sm.add_widget(HistoryScreen())
        self.sm.add_widget(SyncScreen())
        self.sm.add_widget(JournalScreen())
        self.sm.add_widget(ShareHubScreen())
        self.sm.add_widget(RecordsScreen())
        self.sm.add_widget(PlansScreen())
        self.sm.add_widget(TabataScreen())
        self.sm.add_widget(TipsScreen())
        Clock.schedule_interval(self._tick_live_screen, 1.0)
        return self.sm


    def apply_theme(self):
        mode = self.theme_mode
        if mode == 'light':
            self.bg_color = [0.95, 0.95, 0.97, 1]
            self.card_color = [1, 1, 1, 1]
            self.panel_color = [0.93, 0.94, 0.96, 1]
            self.input_bg_color = [0.95, 0.96, 0.98, 1]
            self.pill_color = [0.91, 0.94, 0.98, 1]
            self.button_alt_color = [0.92, 0.94, 0.97, 1]
            self.text_color = [0.08, 0.09, 0.12, 1]
            self.secondary_text_color = [0.22, 0.25, 0.30, 1]
            self.muted_text_color = [0.42, 0.45, 0.50, 1]
            self.muted_color = [0.38, 0.45, 0.58, 1]
            self.subtle_text_color = [0.26, 0.33, 0.46, 1]
            self.input_text_color = [0.08, 0.09, 0.12, 1]
            self.hint_text_color = [0.50, 0.53, 0.58, 1]
            self.button_text_color = [0.08, 0.09, 0.12, 1]
            self.border_color = [0.82, 0.82, 0.86, 1]
            self.border_color2 = [0.76, 0.76, 0.81, 1]
            self.border_color3 = [0.70, 0.70, 0.75, 1]
            self.border_color4 = [0.64, 0.64, 0.70, 1]
            self.border_color5 = [0.58, 0.58, 0.64, 1]
            self.accent_color = [0.92, 0.36, 0.14, 1]
            self.accent_text_color = [0.73, 0.28, 0.10, 1]
        else:
            self.bg_color = [0.07, 0.07, 0.09, 1]
            self.card_color = [0.12, 0.12, 0.15, 1]
            self.panel_color = [0.10, 0.10, 0.13, 1]
            self.input_bg_color = [0.08, 0.10, 0.15, 1]
            self.pill_color = [0.13, 0.16, 0.23, 1]
            self.button_alt_color = [0.16, 0.19, 0.27, 1]
            self.text_color = [1, 1, 1, 1]
            self.secondary_text_color = [0.78, 0.80, 0.85, 1]
            self.muted_text_color = [0.58, 0.60, 0.66, 1]
            self.muted_color = [0.72, 0.77, 0.86, 1]
            self.subtle_text_color = [0.84, 0.88, 0.94, 1]
            self.input_text_color = [1, 1, 1, 1]
            self.hint_text_color = [0.55, 0.58, 0.64, 1]
            self.button_text_color = [1, 1, 1, 1]
            self.border_color = [0.20, 0.20, 0.25, 1]
            self.border_color2 = [0.25, 0.25, 0.28, 1]
            self.border_color3 = [0.30, 0.30, 0.35, 1]
            self.border_color4 = [0.35, 0.35, 0.40, 1]
            self.border_color5 = [0.40, 0.40, 0.45, 1]
            self.accent_color = [0.96, 0.40, 0.18, 1]
            self.accent_text_color = [1, 0.84, 0.62, 1]
        Window.clearcolor = tuple(self.bg_color)

    def set_theme_mode(self, mode: str):
        self.theme_mode = 'light' if mode == 'light' else 'dark'
        self.db.set_setting('theme_mode', self.theme_mode)
        self.apply_theme()
        if hasattr(self, 'sm') and self.sm:
            current = self.sm.current
            Clock.schedule_once(lambda dt: setattr(self.sm, 'current', current), 0)

    def export_dir(self) -> Path:
        path = Path.home() / 'buo_exports'
        path.mkdir(exist_ok=True)
        return path

    def export_dir_uri(self) -> str:
        return self.export_dir().as_uri()

    def export_full_bundle(self) -> Path:
        user = self.current_user()
        bundle = self.db.export_user_bundle(self.current_user_id)
        filename = f"{sanitize_key(user['display_name'])}_bundle.json" if user else 'buo_bundle.json'
        return safe_write_text(self.export_dir() / filename, json.dumps(bundle, indent=2))

    def export_report_csv(self) -> Path:
        today = self.db.get_today(self.current_user_id)
        weekly = self.db.weekly_totals(self.current_user_id)
        user = self.current_user()
        path = self.export_dir() / f"{sanitize_key(user['display_name']) if user else 'buo'}_report.csv"
        with path.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            writer.writerow(['metric', 'value'])
            writer.writerow(['weekly_sessions', weekly['sessions']])
            writer.writerow(['weekly_distance_km', weekly['distance']])
            writer.writerow(['weekly_duration_min', weekly['duration']])
            writer.writerow(['weekly_strength_sessions', weekly['lifts']])
            writer.writerow(['weekly_strength_volume', weekly['volume']])
            writer.writerow(['weekly_water_glasses', weekly['water']])
            writer.writerow(['today_steps', today['steps']])
            writer.writerow(['today_readiness', today['readiness']])
        return path

    def export_analytics_json(self) -> Path:
        rows = self.db.analytics_last_7_days(self.current_user_id)
        user = self.current_user()
        return safe_write_text(self.export_dir() / f"{sanitize_key(user['display_name']) if user else 'buo'}_analytics.json", json.dumps({'generated_at': datetime.now().isoformat(), 'days': rows}, indent=2))

    def build_plan_phase_text(self, weeks: int):
        build_weeks = max(1, int(round(weeks * 0.5)))
        sharpen_weeks = max(1, int(round(weeks * 0.33)))
        taper_weeks = max(1, weeks - build_weeks - sharpen_weeks)
        return (
            f'Build phase: weeks 1-{build_weeks}. Focus on routine, consistency, and progressive load.\n'
            f'Sharpen phase: next {sharpen_weeks} week(s). Shift toward goal-specific intensity while keeping recovery stable.\n'
            f'Taper or deload phase: final {taper_weeks} week(s). Reduce fatigue, keep quality, and arrive fresh.'
        )

    def build_plan_calendar_text(self, goal: str, weeks: int, days: int):
        active = min(7, max(2, int(days or 4)))
        if active <= 2:
            slots = ['Full Body A', 'Rest', 'Rest', 'Full Body B', 'Rest', 'Mobility', 'Rest']
        elif active == 3:
            slots = ['Upper', 'Rest', 'Lower', 'Rest', 'Full Body', 'Mobility', 'Rest']
        elif active == 4:
            slots = ['Upper A', 'Lower A', 'Rest', 'Upper B', 'Lower B', 'Mobility', 'Rest']
        elif active == 5:
            slots = ['Push', 'Pull', 'Legs', 'Upper', 'Lower', 'Rest', 'Rest']
        else:
            slots = ['Push', 'Pull', 'Legs', 'Upper', 'Lower', 'Weak Point', 'Rest']

        lines = []
        for week in range(1, weeks + 1):
            lines.append(
                f"Week {week}: Mon {slots[0]} • Tue {slots[1]} • Wed {slots[2]} • Thu {slots[3]} • Fri {slots[4]} • Sat {slots[5]} • Sun {slots[6]}"
            )
        return '\\n'.join(lines)


    def build_periodized_plan(self, goal: str, weeks: int, days: int, level: str = 'Beginner', minutes: int = 45, adjustments: str = ''):
        level = (level or 'Beginner').strip()
        adjustments = (adjustments or '').strip()
        level_factor = {'Beginner': 0, 'Intermediate': 1, 'Advanced': 2, 'Professional': 3}.get(level, 0)
        build_weeks = max(1, int(round(weeks * 0.5)))
        sharpen_weeks = max(1, int(round(weeks * 0.33)))
        taper_weeks = max(1, weeks - build_weeks - sharpen_weeks)
        recovery_note = 'Keep at least one full recovery day each week.' if level_factor < 2 else 'Keep one lower-load day and one mobility slot each week.'
        if goal in {'Hypertrophy Block', 'Strength PR Focus'}:
            quality = '1 heavy top-set practice'
            long_lift = '1 heavy compound day'
            support = '1-2 technique-focused sessions plus 1 short strength session'
            if goal == 'Strength PR Focus':
                long_lift = '1 longer aerobic lift with steady finish every other week'
            if level == 'Beginner':
                support = '2 technique-focused sessions, 1 full-body technique progression, and basic mobility'
            elif level in {'Advanced', 'Professional'}:
                quality = '1 threshold session plus 1 faster economy or hill session'
                support = '2 technique-focused sessions, 1 short strength session, and mobility'
            summary = f'{goal} • {level} • {weeks} weeks • {days} training days per week • about {minutes} minutes per session. Built around mostly easy strength, one quality day, and a lower-fatigue taper phase. {recovery_note}'
            weeks_out = []
            for w in range(1, weeks + 1):
                if w <= build_weeks:
                    focus = 'Build aerobic base and durable routine'
                elif w <= build_weeks + sharpen_weeks:
                    focus = 'Add race-specific pace work and keep easy days easy'
                else:
                    focus = 'Reduce volume, keep some speed, arrive fresh'
                note = f'Week {w}: {focus}. Include {quality}, {long_lift}, and {support}. Target session length: about {minutes} minutes.'
                if adjustments:
                    note += f' Adjustment note: {adjustments}.'
                weeks_out.append(note)
        elif goal in {'Strength Base', 'Hypertrophy Block', 'Muscle Gain'}:
            main = '3-5 hard sets on compound lifts with 1-3 reps in reserve'
            accessory = '2-4 accessory movements with controlled tempo'
            if level == 'Beginner':
                main = '2-4 technically clean sets on basic compound lifts with longer rests'
                accessory = '1-3 accessory movements with simple progression'
            elif level in {'Advanced', 'Professional'}:
                main = 'top sets plus back-off work on compounds with planned progression'
                accessory = 'targeted accessory blocks and fatigue-managed assistance'
            summary = f'{goal} • {level} • {weeks} weeks • {days} lifting days per week • about {minutes} minutes per session. Uses progressive overload for two to three weeks, then a lighter deload week when needed. {recovery_note}'
            weeks_out = []
            for w in range(1, weeks + 1):
                if w % 4 == 0:
                    focus = 'Deload week: cut volume by about one third and keep technique sharp'
                elif goal == 'Strength Base':
                    focus = 'Prioritize heavier compound work and longer rests'
                else:
                    focus = 'Prioritize total weekly volume and stable technique'
                note = f'Week {w}: {focus}. Main lifts: {main}. Assistance: {accessory}. Session target: about {minutes} minutes.'
                if adjustments:
                    note += f' Adjustment note: {adjustments}.'
                weeks_out.append(note)
        elif goal in {'Fat Loss', 'Return to Training', 'General Fitness'}:
            intensity = 'low to moderate' if level == 'Beginner' else 'mixed easy and moderate'
            summary = f'{goal} • {level} • {weeks} weeks • {days} training days per week • about {minutes} minutes per session. Blends cardio, strength, mobility, and recovery so training stays sustainable. {recovery_note}'
            weeks_out = []
            for w in range(1, weeks + 1):
                if goal == 'Return to Training' and w <= 2:
                    focus = 'Rebuild consistency with lower-impact work and short, repeatable sessions'
                elif w % 4 == 0:
                    focus = 'Use a lighter consolidation week so fatigue stays under control'
                else:
                    focus = 'Build consistency across cardio, strength, and recovery habits'
                note = f'Week {w}: {focus}. Use {days} sessions at {intensity} intensity, around {minutes} minutes each, with one mobility or recovery focus day.'
                if adjustments:
                    note += f' Adjustment note: {adjustments}.'
                weeks_out.append(note)
        else:
            summary = f'{goal} • {level} • {weeks} weeks • {days} training days per week • about {minutes} minutes per session. Tailored block that balances cardio, strength, mobility, and recovery. {recovery_note}'
            weeks_out = [f"Week {w}: {days} flexible sessions around {minutes} minutes each. Keep one session skill-focused, one session easier, and one session recovery-biased.{' Adjustment note: ' + adjustments + '.' if adjustments else ''}" for w in range(1, weeks + 1)]
        return summary, '\n'.join(weeks_out)

    def on_start(self):
        request_android_permissions()
        try:
            from buo.platform_services import request_android_scheduler_exemptions
            request_android_scheduler_exemptions()
        except Exception:
            pass
        self.sync_reminders_to_service()
        try:
            start_step_counter_listener()
        except Exception:
            pass

    def prepare_reliable_reminders(self):
        request_android_permissions()
        try:
            from buo.platform_services import request_android_scheduler_exemptions
            request_android_scheduler_exemptions()
        except Exception:
            pass
        self.sync_reminders_to_service()
        show_message('Reliable reminders', 'Buo requested notification, battery, and exact-alarm support where the device allows it. Keep the reminder engine enabled on Android for the most reliable daily reminders.')

    def reminder_engine_status(self, empty_ok: bool = False) -> str:
        if platform != 'android':
            return 'Desktop mode: reminder storage works, but reliable scheduled reminders are intended for Android builds.'
        if not self.current_user_id:
            return 'Android reminder engine is ready after you unlock the app.'
        count = len(self.db.reminder_list(self.current_user_id, 100))
        if count == 0 and empty_ok:
            return 'No reminders scheduled yet.'
        return f'Android reminder engine: {count} daily reminder(s) synced. Open "Enable reliable reminders" once after install so the foreground reminder engine can stay active.'

    def on_resume(self):
        try:
            start_step_counter_listener()
        except Exception:
            pass
        if self.current_user_id:
            try:
                self.db.sync_step_counter(self.current_user_id)
            except Exception:
                pass
        if self.live_state and self.live_state.get('active'):
            self.start_background_tracking()

    def on_pause(self):
        if self.live_state and self.live_state.get('active'):
            try:
                self.db.set_setting('live_snapshot', json.dumps(self.live_state))
            except Exception:
                pass
            self.update_background_tracking_snapshot()
            self.start_background_tracking()
        return True

    def sync_reminders_to_service(self):
        reminders = []
        if self.current_user_id:
            for row in self.db.reminder_list(self.current_user_id, 100):
                normalized = row["normalized_time"] if "normalized_time" in row.keys() else parse_time_12h_or_24h(row["reminder_time"])
                if normalized:
                    reminders.append({"id": int(row["id"]), "label": row["label"], "time": normalized, "last_sent_on": row["last_sent_on"] if "last_sent_on" in row.keys() else "", "enabled": int(row["enabled"]) if "enabled" in row.keys() else 1})
        if reminders:
            pass
            # removed write_background_service_state({"active": False, "reminders": reminders, "reminder_only": True, "command": ""})
            # removed start_background_tracking_service("Buo reminders", "Daily motivation reminders are active.")
        elif not (self.live_state and self.live_state.get("active")):
            pass
            # removed write_background_service_state({"command": "stop"})
            # removed stop_background_tracking_service()
            # removed clear_background_service_state()

    def update_background_tracking_snapshot(self):
        # Strength-only mode: no GPS/location background payload is needed.
        return
    def start_background_tracking(self):
        self.tracking_service_active = False
        return False
    def stop_background_tracking(self):
        self.tracking_service_active = False
        return
    def start_gps_tracking(self):
        return
    def on_stop(self):
        self.stop_background_tracking()
        self.stop_gps_tracking()
        try:
            stop_step_counter_listener()
        except Exception:
            pass

    def stop_gps_tracking(self):
        return
    def on_gps_status(self, stype=None, status=None):
        return
    def on_gps_location(self, **kwargs):
        return
    def _tick_live_screen(self, *_):
        if self.sm.has_screen('live') and self.sm.current == 'live':
            self.sm.get_screen('live').refresh_display()

    def _cloud_file_for_current_user(self) -> Path:
        user = self.db.get_user(self.current_user_id) if self.current_user_id else None
        LOCAL_CLOUD_DIR.mkdir(exist_ok=True)
        label = user['display_name'] if user else 'user'
        return LOCAL_CLOUD_DIR / f"{sanitize_key(label)}.json"

    def _firebase_config(self):
        if not CLOUD_CONFIG_PATH.exists():
            return None
        try:
            data = json.loads(CLOUD_CONFIG_PATH.read_text())
            url = (data.get('firebase_database_url') or '').rstrip('/')
            token = data.get('auth_token') or ''
            if not url:
                return None
            return {'url': url, 'token': token}
        except Exception:
            return None

    def get_sync_status_text(self) -> str:
        user = self.db.get_user(self.current_user_id) if self.current_user_id else None
        if not user:
            return 'No active user.'
        local_file = self._cloud_file_for_current_user()
        local_line = f"Local mirror: {'ready' if local_file.exists() else 'not backed up yet'} at {local_file.name}"
        firebase = self._firebase_config()
        firebase_line = 'Remote cloud: Firebase configured' if firebase else 'Remote cloud: not configured yet'
        return f"Signed in as {user['display_name']}\n{local_line}\n{firebase_line}"

    def backup_current_user(self):
        if not self.require_login():
            return False, 'Login required.'
        bundle = self.db.export_user_bundle(self.current_user_id)
        local_file = self._cloud_file_for_current_user()
        local_file.write_text(json.dumps(bundle, indent=2))
        firebase = self._firebase_config()
        if firebase and requests is not None:
            try:
                user = self.db.get_user(self.current_user_id)
                key = sanitize_key(user['display_name'])
                url = f"{firebase['url']}/buo/{key}.json"
                if firebase.get('token'):
                    url += f"?auth={firebase['token']}"
                resp = requests.put(url, json=bundle, timeout=10)
                resp.raise_for_status()
                return True, 'Backup saved locally and pushed to Firebase cloud.'
            except Exception as e:
                return False, f'Local backup saved, but remote sync failed: {e}'
        return True, 'Backup saved locally. Add cloud_config.json to enable true Firebase cloud sync.'

    def restore_current_user(self):
        if not self.require_login():
            return False, 'Login required.'
        bundle = None
        firebase = self._firebase_config()
        if firebase and requests is not None:
            try:
                user = self.db.get_user(self.current_user_id)
                key = sanitize_key(user['display_name'])
                url = f"{firebase['url']}/buo/{key}.json"
                if firebase.get('token'):
                    url += f"?auth={firebase['token']}"
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data:
                    bundle = data
            except Exception:
                bundle = None
        if bundle is None:
            local_file = self._cloud_file_for_current_user()
            if not local_file.exists():
                return False, 'No backup found yet for this account.'
            bundle = json.loads(local_file.read_text())
        self.db.restore_user_bundle(self.current_user_id, bundle)
        return True, 'Backup restored into this account.'

    def current_user(self):
        return self.db.get_user(self.current_user_id) if self.current_user_id else None

    def require_login(self) -> bool:
        if self.current_user_id is None:
            self.sm.current = 'login'
            return False
        return True

    def open_screen(self, name: str):
        if name != 'login' and not self.require_login():
            return
        self.sm.current = name
        screen = self.sm.get_screen(name)
        if hasattr(screen, 'on_pre_enter'):
            try:
                screen.on_pre_enter()
            except TypeError:
                pass

    def logout_user(self):
        self.current_user_id = None
        self.live_state = None
        self.sm.current = 'login'
        show_message('Logged out', 'The app is now locked. Your data stays saved locally on this phone.')

    def on_stop(self):
        self.stop_gps_tracking()
        self.db.close()


