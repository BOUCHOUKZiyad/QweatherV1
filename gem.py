from __future__ import annotations

import json
import os
import sys
import traceback
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import (
    QTimer, Qt, QThread, Signal, QSize, QPoint, QRect, QEvent, QUrl
)
from PySide6.QtGui import (
    QAction, QColor, QCloseEvent, QFont, QIcon, QMouseEvent,
    QPainter, QPixmap, QCursor, QLinearGradient, QPen
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFrame, QGraphicsBlurEffect, QGraphicsDropShadowEffect, QGridLayout,
    QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox, QPushButton,
    QScrollArea, QSlider, QSizePolicy, QSpinBox, QSystemTrayIcon,
    QToolButton, QVBoxLayout, QWidget, QFormLayout, QStyle, QStackedWidget
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_OK = True
except Exception:
    WEBENGINE_OK = False

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    MULTIMEDIA_OK = True
except Exception:
    MULTIMEDIA_OK = False

# ==================== CONSTANTS ====================
APP_NAME = "Qingdao Weather"
APP_ORG = "OpenAI"
APP_NAME_ID = "qingdao_weather_upc"

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
BG_DIR = ASSETS_DIR / "backgrounds"
ICON_DIR = ASSETS_DIR / "icons"
SOUND_DIR = ASSETS_DIR / "sounds"
DATA_DIR = Path(os.getenv("APPDATA", str(BASE_DIR))) / "QingdaoWeather"
SETTINGS_FILE = DATA_DIR / "settings.json"

QINGDAO_LAT = 36.0671
QINGDAO_LON = 120.3826
QINGDAO_TZ = "Asia/Shanghai"

DEFAULT_SETTINGS = {
    "volume": 40,
    "always_on_top": False,
    "refresh_interval": 15,
    "opacity": 0.95,
    "theme_override": "auto",
    "auto_start": False,
}

WEATHER_BG_MAP = {
    "sunny": "sunny",
    "cloudy": "cloudy",
    "rainy": "rain",
    "storm": "storm",
    "snow": "snow",
    "fog": "fog",
    "night": "night",
}

WEATHER_GRADIENT_FALLBACK = {
    "sunny": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a2639, stop:1 #111823);",
    "cloudy": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151922, stop:1 #0d1017);",
    "rainy": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0f131c, stop:1 #080a0f);",
    "storm": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0a0d14, stop:1 #030406);",
    "snow": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1c2331, stop:1 #10141d);",
    "fog": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #131722, stop:1 #0b0d13);",
    "night": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #090c12, stop:1 #020305);",
}

WEATHER_SOUND_MAP = {
    "sunny": ["sunny.mp3", "sunny.wav", "sunny.ogg"],
    "cloudy": ["cloudy.mp3", "cloudy.wav", "cloudy.ogg"],
    "rainy": ["rainy.mp3", "rainy.wav", "rainy.ogg", "rain.mp3"],
    "storm": ["storm.mp3", "storm.wav", "storm.ogg"],
    "snow": ["snow.mp3", "snow.wav", "snow.ogg"],
    "fog": ["fog.mp3", "fog.wav", "fog.ogg"],
    "night": ["night.mp3", "night.wav", "night.ogg"],
}

# ==================== UTILITIES ====================
def app_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(100, 190, 255))
    painter.drawEllipse(10, 10, 44, 44)
    painter.setBrush(QColor(255, 255, 255))
    painter.drawEllipse(20, 18, 18, 18)
    painter.setBrush(QColor(40, 120, 255, 230))
    painter.drawRoundedRect(18, 30, 34, 16, 8, 8)
    painter.end()
    return QIcon(pix)

def load_settings() -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SETTINGS_FILE.exists():
        try:
            with SETTINGS_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(DEFAULT_SETTINGS)
            if isinstance(data, dict):
                merged.update(data)
            return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)

def save_settings(settings: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = dict(DEFAULT_SETTINGS)
    payload.update(settings)
    try:
        with SETTINGS_FILE.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def set_windows_autostart(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    try:
        import winreg
    except Exception:
        return
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                if getattr(sys, "frozen", False):
                    command = f'"{sys.executable}"'
                else:
                    script = Path(__file__).resolve()
                    python = Path(sys.executable)
                    if python.name.lower() == "python.exe":
                        pythonw = python.with_name("pythonw.exe")
                        if pythonw.exists():
                            python = pythonw
                    command = f'"{python}" "{script}"'
                winreg.SetValueEx(key, APP_NAME_ID, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME_ID)
                except FileNotFoundError:
                    pass
    except Exception:
        pass

def fetch_json(url: str, timeout: float = 15.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 QingdaoWeather/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8", errors="replace")
    return json.loads(payload)

def build_url(base: str, params: dict[str, Any]) -> str:
    clean = {}
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            clean[k] = ",".join(str(x) for x in v)
        else:
            clean[k] = str(v)
    return f"{base}?{urllib.parse.urlencode(clean, safe=',')}"

def parse_iso_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))

def fmt_time(text: str) -> str:
    if not text:
        return "--:--"
    try:
        return parse_iso_time(text).strftime("%H:%M")
    except Exception:
        return text

def fmt_day(dt: Any) -> str:
    if isinstance(dt, str):
        try:
            dt = parse_iso_time(dt)
        except Exception:
            return dt
    return dt.strftime("%A")

def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))

def weather_theme_from_code(code: int, is_day: Optional[int]) -> str:
    is_night = is_day == 0
    if code in (95,96,99):
        return "storm"
    if code in (71,73,75,77,85,86):
        return "snow"
    if code in (45,48):
        return "fog"
    if code in (51,53,55,56,57,61,63,65,66,67,80,81,82):
        return "rainy"
    # Clear or cloudy skies: night takes priority over "cloudy" once the sun is down
    if is_night:
        return "night"
    if code in (1,2,3):
        return "cloudy"
    if code == 0:
        return "sunny"
    return "cloudy"

def weather_icon(code: int, is_day: Optional[int] = 1) -> str:
    if code in (95,96,99):
        return "⛈"
    if code in (71,73,75,77,85,86):
        return "❄"
    if code in (45,48):
        return "🌫"
    if code in (51,53,55,56,57,61,63,65,66,67,80,81,82):
        return "🌧"
    if code in (1,2):
        return "⛅"
    if code == 3:
        return "☁"
    if code == 0:
        return "☀" if is_day in (None,1) else "🌙"
    return "☁"

def weather_label(code: int) -> str:
    labels = {
        0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing Rime Fog",
        51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
        56: "Freezing Drizzle", 57: "Freezing Drizzle",
        61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
        66: "Freezing Rain", 67: "Freezing Rain",
        71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow", 77: "Snow Grains",
        80: "Rain Showers", 81: "Heavy Showers", 82: "Violent Showers",
        85: "Snow Showers", 86: "Heavy Snow Showers",
        95: "Thunderstorm", 96: "Thunderstorm with Hail", 99: "Thunderstorm with Hail",
    }
    return labels.get(code, "Weather")

def aqi_label(value: Optional[float]) -> str:
    if value is None:
        return "Unknown"
    if value <= 50:
        return "Good"
    if value <= 100:
        return "Moderate"
    if value <= 150:
        return "Unhealthy for Sensitive"
    if value <= 200:
        return "Unhealthy"
    if value <= 300:
        return "Very Unhealthy"
    return "Hazardous"

def first_existing_file(folder: Path, names: list[str]) -> Optional[Path]:
    for name in names:
        p = folder / name
        if p.exists():
            return p
    return None

# ==================== WEATHER WORKER ====================
class WeatherWorker(QThread):
    fetched = Signal(dict)
    failed = Signal(str)
    def run(self):
        try:
            forecast = self._fetch_forecast()
            air = self._fetch_air_quality()
            merged = self._merge(forecast, air)
            self.fetched.emit(merged)
        except Exception as e:
            self.failed.emit(f"{e}\n{traceback.format_exc()}")

    def _fetch_forecast(self) -> dict:
        params = {
            "latitude": QINGDAO_LAT, "longitude": QINGDAO_LON, "timezone": QINGDAO_TZ,
            "current": ["temperature_2m","apparent_temperature","relative_humidity_2m",
                        "pressure_msl","wind_speed_10m","weather_code","is_day","uv_index"],
            "hourly": ["temperature_2m","apparent_temperature","relative_humidity_2m",
                       "pressure_msl","wind_speed_10m","weather_code","is_day","uv_index"],
            "daily": ["weather_code","temperature_2m_max","temperature_2m_min",
                      "apparent_temperature_max","apparent_temperature_min",
                      "sunrise","sunset","uv_index_max"],
            "forecast_days": 7, "temperature_unit": "celsius", "windspeed_unit": "kmh",
            "precipitation_unit": "mm", "timeformat": "iso8601",
        }
        url = build_url("https://api.open-meteo.com/v1/forecast", params)
        return fetch_json(url)

    def _fetch_air_quality(self) -> dict:
        params = {
            "latitude": QINGDAO_LAT, "longitude": QINGDAO_LON, "timezone": QINGDAO_TZ,
            "current": ["us_aqi","european_aqi","pm10","pm2_5","carbon_monoxide",
                        "nitrogen_dioxide","ozone","sulphur_dioxide"],
            "hourly": ["us_aqi","european_aqi","pm10","pm2_5"],
            "domains": "auto", "timeformat": "iso8601",
        }
        url = build_url("https://air-quality-api.open-meteo.com/v1/air-quality", params)
        return fetch_json(url)

    def _merge(self, forecast: dict, air: dict) -> dict:
        current = forecast.get("current", {})
        current_time = current.get("time")
        current_dt = parse_iso_time(current_time) if current_time else datetime.now()

        hourly = forecast.get("hourly", {})
        times = [parse_iso_time(t) for t in hourly.get("time", [])]
        hourly_rows = []
        for i, t in enumerate(times):
            hourly_rows.append({
                "time": t,
                "temperature": self._get(hourly, "temperature_2m", i),
                "apparent": self._get(hourly, "apparent_temperature", i),
                "humidity": self._get(hourly, "relative_humidity_2m", i),
                "pressure": self._get(hourly, "pressure_msl", i),
                "wind_speed": self._get(hourly, "wind_speed_10m", i),
                "weather_code": int(self._get(hourly, "weather_code", i, 0) or 0),
                "is_day": self._get(hourly, "is_day", i),
                "uv_index": self._get(hourly, "uv_index", i),
            })

        daily = forecast.get("daily", {})
        daily_times = [parse_iso_time(t) for t in daily.get("time", [])]
        daily_rows = []
        for i, d in enumerate(daily_times):
            daily_rows.append({
                "date": d,
                "weather_code": int(self._get(daily, "weather_code", i, 0) or 0),
                "high": self._get(daily, "temperature_2m_max", i),
                "low": self._get(daily, "temperature_2m_min", i),
                "apparent_high": self._get(daily, "apparent_temperature_max", i),
                "apparent_low": self._get(daily, "apparent_temperature_min", i),
                "sunrise": self._get(daily, "sunrise", i),
                "sunset": self._get(daily, "sunset", i),
                "uv_max": self._get(daily, "uv_index_max", i),
            })

        aq_current = air.get("current", {})
        aq_hourly = air.get("hourly", {})
        aq_val = aq_current.get("us_aqi") or aq_current.get("european_aqi")
        aq_sys = "US" if aq_current.get("us_aqi") is not None else "EU"
        if aq_val is None and aq_hourly.get("time"):
            aq_val = self._get(aq_hourly, "us_aqi", 0) or self._get(aq_hourly, "european_aqi", 0)
        cur_code = int(current.get("weather_code",0) or 0)
        cur_day = current.get("is_day",1)
        theme = weather_theme_from_code(cur_code, cur_day)
        return {
            "location": "Qingdao", "current_time": current_dt,
            "current": {
                "temperature": current.get("temperature_2m"),
                "apparent_temperature": current.get("apparent_temperature"),
                "humidity": current.get("relative_humidity_2m"),
                "pressure": current.get("pressure_msl"),
                "wind_speed": current.get("wind_speed_10m"),
                "weather_code": cur_code,
                "is_day": cur_day,
                "uv_index": current.get("uv_index"),
                "label": weather_label(cur_code),
                "icon": weather_icon(cur_code, cur_day),
                "theme": theme,
            },
            "hourly": hourly_rows,
            "daily": daily_rows,
            "aqi": {
                "value": aq_val, "system": aq_sys, "label": aqi_label(aq_val),
                "pm2_5": aq_current.get("pm2_5"), "pm10": aq_current.get("pm10"),
            },
            "sunrise": daily.get("sunrise", [None])[0],
            "sunset": daily.get("sunset", [None])[0],
        }

    def _get(self, data: dict, key: str, idx: int, default=None):
        try:
            val = data.get(key, [])
            if isinstance(val, list) and idx < len(val):
                return val[idx]
            return default
        except Exception:
            return default

# ==================== SOUND MANAGER ====================
class AmbientSoundManager(QWidget):
    def __init__(self):
        super().__init__()
        self._player = None
        self._audio = None
        self._current = None
        self._enabled = MULTIMEDIA_OK
        self._volume = 0.4
        if MULTIMEDIA_OK:
            self._audio = QAudioOutput()
            self._audio.setVolume(self._volume)
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._audio)
            self._player.mediaStatusChanged.connect(self._loop_audio)

    def _loop_audio(self, status):
        try:
            if self._player is None:
                return
            if status == QMediaPlayer.EndOfMedia:
                self._player.setPosition(0)
                self._player.play()
        except Exception:
            pass

    def set_volume(self, val: int):
        self._volume = clamp(val/100.0, 0, 1)
        if self._audio:
            self._audio.setVolume(self._volume)

    def play_theme(self, theme: str):
        if not self._enabled or self._player is None:
            return
        if theme == self._current:
            return
        self._current = theme
        src = first_existing_file(SOUND_DIR, WEATHER_SOUND_MAP.get(theme, []))
        if src is None:
            self._player.stop()
            return
        self._player.stop()
        self._player.setSource(QUrl.fromLocalFile(str(src)))
        self._player.play()

    def stop(self):
        if self._player:
            self._player.stop()

# ==================== LOADING SPINNER ====================
class LoadingSpinner(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.start(30)
        self.setVisible(False)

    def _rotate(self):
        if self.isVisible():
            self._angle = (self._angle + 10) % 360
            self.update()

    def paintEvent(self, event):
        if not self.isVisible():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width()/2, self.height()/2)
        painter.rotate(self._angle)
        for i in range(8):
            painter.save()
            painter.rotate(i * 45)
            alpha = int(200 - (i * 20))
            if alpha < 30:
                alpha = 30
            painter.setBrush(QColor(100, 180, 255, alpha))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(8, -4, 20, 8, 4, 4)
            painter.restore()
        painter.end()

# ==================== GLASS COMPONENTS ====================
class GlassFrame(QFrame):
    clicked = Signal()

    def __init__(self, parent=None, radius=16):
        super().__init__(parent)
        self.radius = radius
        self.setObjectName("GlassFrame")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.apply_shadow()

    def apply_shadow(self, blur=20, alpha=25):
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(blur)
        sh.setOffset(0, 4)
        sh.setColor(QColor(0,0,0,alpha))
        self.setGraphicsEffect(sh)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
            e.accept()
        super().mousePressEvent(e)

class StatCard(GlassFrame):
    def __init__(self, key_type: str, title: str, parent=None):
        super().__init__(parent, radius=16)
        self.key_type = key_type
        self.setCursor(Qt.PointingHandCursor)
        
        self.title_lbl = QLabel(title)
        self.value_lbl = QLabel("--")
        self.sub_lbl = QLabel("")
        self.title_lbl.setObjectName("StatTitle")
        self.value_lbl.setObjectName("StatValue")
        self.sub_lbl.setObjectName("StatSub")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20,18,20,18)
        layout.setSpacing(6)
        layout.addWidget(self.title_lbl)
        layout.addStretch()
        layout.addWidget(self.value_lbl)
        layout.addWidget(self.sub_lbl)
        self.setMinimumSize(180,125)

    def set_value(self, val: str, sub: str = ""):
        self.value_lbl.setText(val)
        self.sub_lbl.setText(sub)

# ==================== ANALYTICS GRAPH COMPONENT ====================
class WeatherAnalyticsChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(240)
        self._points = []
        self._labels = []

    def set_data(self, points: list[float], labels: list[str]):
        self._points = points
        self._labels = labels
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        padding_left, padding_right = 60, 40
        padding_top, padding_bottom = 40, 40
        
        # Background Grid Line Matrix setup
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1, Qt.DashLine))
        for i in range(4):
            y_pos = int(padding_top + (h - padding_top - padding_bottom) * i / 3)
            painter.drawLine(padding_left, y_pos, w - padding_right, y_pos)

        if not self._points:
            painter.setPen(QColor(255, 255, 255, 120))
            painter.drawText(self.rect(), Qt.AlignCenter, "Loading Atmospheric Metrics Data...")
            painter.end()
            return

        min_val, max_val = min(self._points), max(self._points)
        val_range = max_val - min_val if max_val != min_val else 1.0
        
        graph_w = w - padding_left - padding_right
        graph_h = h - padding_top - padding_bottom
        
        coords = []
        for idx, val in enumerate(self._points):
            cx = int(padding_left + graph_w * idx / (len(self._points) - 1))
            cy = int(padding_top + graph_h * (1.0 - (val - min_val) / val_range))
            coords.append(QPoint(cx, cy))

        # Fill spline area gradient bounds
        path_gradient = QLinearGradient(0, padding_top, 0, h - padding_bottom)
        path_gradient.setColorAt(0, QColor(100, 180, 255, 100))
        path_gradient.setColorAt(1, QColor(100, 180, 255, 0))
        painter.setBrush(path_gradient)
        painter.setPen(Qt.NoPen)
        
        poly_points = [QPoint(padding_left, h - padding_bottom)] + coords + [QPoint(coords[-1].x(), h - padding_bottom)]
        painter.drawPolygon(poly_points)

        # Main Trending Spline Line Segment Setup
        painter.setPen(QPen(QColor(100, 180, 255), 3, Qt.SolidLine))
        for idx in range(len(coords) - 1):
            painter.drawLine(coords[idx], coords[idx+1])

        # Plot Metrics Vector Anchor Nodes explicitly
        for idx, pt in enumerate(coords):
            painter.setBrush(QColor(255, 255, 255))
            painter.setPen(QPen(QColor(40, 120, 255), 2))
            painter.drawEllipse(pt, 5, 5)
            
            # Draw Data values above knots
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(pt.x() - 15, pt.y() - 10, 30, 20, Qt.AlignCenter, f"{round(self._points[idx])}°")
            
            # Bottom X-Axis category indexing markers 
            if idx % 3 == 0 and idx < len(self._labels):
                painter.setPen(QColor(143, 149, 165))
                painter.drawText(pt.x() - 25, h - padding_bottom + 10, 50, 20, Qt.AlignCenter, self._labels[idx])
        painter.end()


# ==================== TITLE BAR ====================
class TitleBar(QFrame):
    compactReq = Signal()
    maxReq = Signal()
    settingsReq = Signal()
    onTopReq = Signal(bool)
    closeReq = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setObjectName("TitleBarPanel")
        self._drag_pos = None
        
        icon_label = QLabel("○")
        icon_label.setStyleSheet("font-size: 18px; color: #64B4FF; font-weight: 900;")
        icon_label.setFixedSize(28, 28)
        icon_label.setAlignment(Qt.AlignCenter)
        
        title_text = QLabel(APP_NAME)
        title_text.setObjectName("TitleBarTitle")

        left_layout = QHBoxLayout()
        left_layout.setSpacing(12)
        left_layout.setContentsMargins(0,0,0,0)
        left_layout.addWidget(icon_label)
        left_layout.addWidget(title_text)
        left_layout.addStretch()
        left_wrap = QWidget()
        left_wrap.setLayout(left_layout)

        self.compact_btn = self._btn("Mini Mode", self._load_icon("icon_compact.png"))
        self.max_btn = self._btn("Maximize", self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
        self.settings_btn = self._btn("Settings", self._load_icon("icon_settings.png"))
        self.pin_btn = self._btn("Always on Top", self._load_icon("icon_pin.png"), checkable=True)
        self.close_btn = self._btn("Close to Tray", self._load_icon("icon_close.png"))

        self.compact_btn.clicked.connect(self.compactReq.emit)
        self.max_btn.clicked.connect(self.maxReq.emit)
        self.settings_btn.clicked.connect(self.settingsReq.emit)
        self.pin_btn.toggled.connect(self.onTopReq.emit)
        self.close_btn.clicked.connect(self.closeReq.emit)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        for b in (self.compact_btn, self.max_btn, self.settings_btn, self.pin_btn, self.close_btn):
            btns.addWidget(b)

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 0, 20, 0)
        root.setSpacing(12)
        root.addWidget(left_wrap)
        root.addStretch()
        root.addLayout(btns)

    def _load_icon(self, filename):
        path = ICON_DIR / filename
        if path.exists():
            return QIcon(str(path))
        return self.style().standardIcon(QStyle.SP_FileIcon)

    def _btn(self, tip: str, icon: QIcon, checkable=False):
        b = QToolButton(self)
        b.setToolTip(tip)
        b.setIcon(icon)
        b.setCheckable(checkable)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedSize(32,32)
        b.setIconSize(QSize(18,18))
        b.setAutoRaise(True)
        return b

    def set_maximized(self, maxed: bool):
        self.max_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarNormalButton if maxed else QStyle.SP_TitleBarMaxButton))
        self.max_btn.setToolTip("Restore" if maxed else "Maximize")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()
            self._win_pos = self.window().pos()
            e.accept()
        super().mousePressEvent(e)
    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.LeftButton:
            delta = e.globalPosition().toPoint() - self._drag_pos
            self.window().move(self._win_pos + delta)
            e.accept()
        super().mouseMoveEvent(e)
    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        super().mouseReleaseEvent(e)
    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.maxReq.emit()
        super().mouseDoubleClickEvent(e)

# ==================== COMPACT MODE WITH ROBUST DRAG AND MINIMIZE/RESTORE ====================
class CompactWidget(GlassFrame):
    clicked = Signal()
    minimizeReq = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, radius=16)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(310, 130)
        self._drag_pos = None
        self._win_pos = None

        self.icon = QLabel("☀")
        self.temp = QLabel("--°")
        self.feels = QLabel("Feels --°")
        self.hum = QLabel("💧 --%")
        self.wind = QLabel("💨 -- km/h")
        
        # Interactive Controls inside Compact Widget Layer
        self.min_btn = QToolButton()
        self.min_btn.setText("—")
        self.min_btn.setToolTip("Minimize Window")
        self.min_btn.setStyleSheet("color: white; font-weight: bold; background: transparent; border: none;")
        self.min_btn.setCursor(Qt.PointingHandCursor)
        self.min_btn.clicked.connect(lambda: self.showMinimized())

        self.restore_btn = QToolButton()
        self.restore_btn.setText("⬜")
        self.restore_btn.setToolTip("Restore Application Window")
        self.restore_btn.setStyleSheet("color: white; background: transparent; border: none;")
        self.restore_btn.setCursor(Qt.PointingHandCursor)
        self.restore_btn.clicked.connect(self.clicked.emit)

        for w in (self.icon, self.temp, self.feels, self.hum, self.wind):
            w.setStyleSheet("color: white; background: transparent;")
        self.icon.setStyleSheet("font-size: 32px; min-width: 40px; background: transparent;")
        self.temp.setStyleSheet("font-size: 24px; font-weight: 700; background: transparent;")
        self.feels.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.7); background: transparent;")
        self.hum.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.8); background: transparent;")
        self.wind.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.8); background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(6)
        
        ctrls = QHBoxLayout()
        ctrls.addStretch()
        ctrls.addWidget(self.min_btn)
        ctrls.addWidget(self.restore_btn)
        layout.addLayout(ctrls)

        top = QHBoxLayout()
        top.addWidget(self.icon)
        top.addWidget(self.temp)
        top.addWidget(self.feels)
        top.addStretch()
        layout.addLayout(top)
        
        bottom = QHBoxLayout()
        bottom.addWidget(self.hum)
        bottom.addWidget(self.wind)
        bottom.addStretch()
        layout.addLayout(bottom)

    def update_data(self, data):
        cur = data.get("current", {})
        self.icon.setText(cur.get("icon","☀"))
        t = cur.get("temperature")
        f = cur.get("apparent_temperature")
        h = cur.get("humidity")
        w = cur.get("wind_speed")
        self.temp.setText(f"{self._fmt(t)}°")
        self.feels.setText(f"Feels {self._fmt(f)}°")
        self.hum.setText(f"💧 {self._fmt(h)}%")
        self.wind.setText(f"💨 {self._fmt(w)} km/h")

    def _fmt(self, v):
        return "--" if v is None else str(round(float(v)))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()
            self._win_pos = self.pos()
            e.accept()
        # Note: intentionally NOT calling GlassFrame's mousePressEvent here.
        # GlassFrame.mousePressEvent emits `clicked` on every press, and this
        # widget's `clicked` is wired to restore the main window — which was
        # firing on press and yanking the widget away before a drag could start.
        QFrame.mousePressEvent(self, e)

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.LeftButton:
            delta = e.globalPosition().toPoint() - self._drag_pos
            self.move(self._win_pos + delta)
            e.accept()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.clicked.emit()
        super().mouseDoubleClickEvent(e)

# ==================== BACKGROUND ROOT ====================
class BackgroundRoot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bg_label = QLabel(self)
        self.bg_label.setScaledContents(False)
        self.bg_label.setStyleSheet("background: transparent;")
        self.bg_label.lower()
        self.bg_pixmap = None
        
        self.overlay = QFrame(self)
        self.overlay.setObjectName("MainWindowOverlay")
        self.content = QWidget(self.overlay)
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setSpacing(0)
        ov = QVBoxLayout(self.overlay)
        ov.setContentsMargins(0,0,0,0)
        ov.addWidget(self.content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0,0,0,0)
        main.addWidget(self.overlay)

    def set_background(self, theme: str):
        name = WEATHER_BG_MAP.get(theme, "cloudy")
        candidates = [f"{name}.jpg", f"{name}.png", f"{name}.jpeg"]
        
        for candidate in candidates:
            p = BG_DIR / candidate
            if p.exists():
                self.bg_pixmap = QPixmap(str(p))
                self._update()
                return
        
        self.bg_pixmap = None
        self._update(fallback_theme=theme)

    def resizeEvent(self, e):
        self.bg_label.setGeometry(self.rect())
        self.overlay.setGeometry(self.rect())
        self._update()
        super().resizeEvent(e)

    def _update(self, fallback_theme="cloudy"):
        if self.bg_pixmap and not self.bg_pixmap.isNull():
            scaled = self.bg_pixmap.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            self.bg_label.setPixmap(scaled)
            self.bg_label.show()
            self.bg_label.lower()
        else:
            self.bg_label.setPixmap(QPixmap())
            gradient = WEATHER_GRADIENT_FALLBACK.get(fallback_theme, WEATHER_GRADIENT_FALLBACK["cloudy"])
            self.bg_label.setStyleSheet(f"background: {gradient}")

# ==================== NAVIGATION BUTTON ====================
class NavButton(QPushButton):
    def __init__(self, text, icon, parent=None):
        super().__init__(text, parent)
        self.setIcon(icon)
        self.setIconSize(QSize(20,20))
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(46)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 20px;
                background-color: transparent;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-weight: 500;
                color: #A0A7B5;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.06);
                color: #FFF;
            }
            QPushButton:checked {
                background-color: rgba(100,180,255,0.12);
                color: #64B4FF;
                font-weight: 600;
            }
        """)

# ==================== DIALOG SYSTEMS ====================
class StatInsightDialog(QDialog):
    def __init__(self, card_key: str, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Atmospheric Insights Engine")
        self.setModal(True)
        self.setMinimumSize(420, 280)
        self.setStyleSheet("background-color: #111522; color: white; border-radius: 16px;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)
        
        title_lbl = QLabel()
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 600; color: #64B4FF;")
        body_lbl = QLabel()
        body_lbl.setWordWrap(True)
        body_lbl.setStyleSheet("font-size: 14px; color: #D0D5E0; line-height: 20px;")
        
        cur = data.get("current", {})
        aqi = data.get("aqi", {})
        
        if card_key == "humidity":
            title_lbl.setText("Humidity & Saturation Metrics")
            val = cur.get("humidity", "--")
            body_lbl.setText(f"The current relative humidity reading along the coast is {val}%.\n\nThis percentage represents the amount of moisture present in the atmosphere compared to the maximum capacity the air can hold at the current temperature framework.")
        elif card_key == "wind":
            title_lbl.setText("Surface Wind & Velocity Dynamics")
            val = cur.get("wind_speed", "--")
            body_lbl.setText(f"Current localized velocity is estimated at {val} km/h.\n\nWind vectors are critical indicators for marine operations across the Yellow Sea.")
        elif card_key == "pressure":
            title_lbl.setText("Atmospheric Surface Pressure")
            val = cur.get("pressure", "--")
            body_lbl.setText(f"Barometric tracking indicates a localized mean sea-level pressure of {val} hPa.")
        elif card_key == "uv":
            title_lbl.setText("Solar UV Exposure Indices")
            val = cur.get("uv_index", "0.0")
            body_lbl.setText(f"The structural ultraviolet radiance index is registered at {val}.")
        elif card_key == "aqi":
            title_lbl.setText("Air Quality Monitoring Array")
            val = aqi.get("value", "--")
            lbl = aqi.get("label", "Unknown")
            body_lbl.setText(f"The dynamic Air Quality Index registers at {val} ({lbl}).\n\nParticulate breakdown metrics:\n• PM2.5 Concentration: {aqi.get('pm2_5','--')} µg/m³\n• PM10 Concentration: {aqi.get('pm10','--')} µg/m³")
        elif card_key == "sun":
            title_lbl.setText("Astronomical Solar Horizon Windows")
            body_lbl.setText(f"Daily daylight cycle properties:\n• Sunrise Threshold: {fmt_time(data.get('sunrise'))} AM\n• Sunset Threshold: {fmt_time(data.get('sunset'))} PM")
        elif card_key == "umbrella":
            title_lbl.setText("Precipitation & Umbrella Outlook")
            code = cur.get("weather_code", 0)
            rain_codes = (51,53,55,56,57,61,63,65,66,67,80,81,82,95,96,99)
            if code in rain_codes:
                body_lbl.setText(f"Current conditions ({weather_label(code)}) indicate active precipitation.\n\nAn umbrella or waterproof shell is recommended before heading out.")
            else:
                body_lbl.setText(f"Current conditions ({weather_label(code)}) show no active precipitation.\n\nAn umbrella isn't necessary right now, but it's worth keeping a compact one nearby if skies look uncertain later.")
        elif card_key == "mask":
            title_lbl.setText("Air Quality & Mask Guidance")
            val = aqi.get("value", "--")
            lbl = aqi.get("label", "Unknown")
            if isinstance(val, (int, float)) and val > 100:
                rec = "A mask is recommended, especially for sensitive groups spending extended time outdoors."
            elif isinstance(val, (int, float)) and val > 50:
                rec = "Air quality is acceptable for most, though sensitive individuals may want a mask."
            else:
                rec = "Air quality is good — a mask isn't necessary for typical outdoor activity."
            body_lbl.setText(f"The dynamic Air Quality Index registers at {val} ({lbl}).\n\n{rec}\n\n• PM2.5 Concentration: {aqi.get('pm2_5','--')} µg/m³\n• PM10 Concentration: {aqi.get('pm10','--')} µg/m³")
        elif card_key == "coast":
            title_lbl.setText("Coastal Activity Conditions")
            wind = cur.get("wind_speed", 0) or 0
            try:
                wind_f = float(wind)
            except Exception:
                wind_f = 0
            if wind_f < 15:
                rec = "Calm conditions along the waterfront — favorable for walking, cycling, or light coastal activity."
            elif wind_f < 30:
                rec = "Moderate coastal winds — pleasant for a walk, but small craft and umbrellas may be affected."
            else:
                rec = "Strong coastal winds — outdoor waterfront activity may be uncomfortable or hazardous."
            body_lbl.setText(f"Surface wind along the Qingdao coastline is estimated at {wind} km/h.\n\n{rec}")
        else:
            title_lbl.setText("System Information Node")
            body_lbl.setText("The clicked system component is fully operational.")

        layout.addWidget(title_lbl)
        layout.addWidget(body_lbl, 1)
        
        close_btn = QPushButton("Dismiss Panel")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("background-color: #1A2130; border: none; padding: 10px; border-radius: 8px; color: white; font-weight: 600;")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

class DayDetailDialog(QDialog):
    def __init__(self, day_data: dict, hourly_data: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Extended Synoptic Forecast")
        self.setModal(True)
        self.setMinimumSize(520, 360)
        self.setStyleSheet("background-color: #0E121E; color: white; border: 1px solid #1A2238;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        header = QLabel(fmt_day(day_data['date']))
        header.setStyleSheet("font-size: 20px; font-weight: 700; color: white; border: none;")
        subheader = QLabel(day_data['date'].strftime('%B %d, %Y'))
        subheader.setStyleSheet("font-size: 14px; color: #8F95A5; border: none;")
        
        v_head = QVBoxLayout()
        v_head.setSpacing(4)
        v_head.addWidget(header)
        v_head.addWidget(subheader)
        layout.addLayout(v_head)
        
        info = QGridLayout()
        info.setSpacing(14)
        high_low = QLabel(f"High / Low: <span style='color:#FFF; font-weight:600;'>{round(day_data['high'])}°</span> / <span style='color:#8F95A5;'>{round(day_data['low'])}°</span>")
        uv = QLabel(f"UV Exposure Index: <span style='color:#FFF; font-weight:600;'>{day_data['uv_max']:.1f}</span>")
        feels = QLabel(f"Thermal Feels: {round(day_data['apparent_high'])}° to {round(day_data['apparent_low'])}°")
        
        for lbl in (high_low, uv, feels):
            lbl.setStyleSheet("font-size: 14px; color: #B0B5C0; border: none;")
        info.addWidget(high_low, 0, 0)
        info.addWidget(uv, 0, 1)
        info.addWidget(feels, 1, 0, 1, 2)
        layout.addLayout(info)
        
        hourly_title = QLabel("Hourly Breakdown")
        hourly_title.setStyleSheet("font-size: 16px; font-weight: 600; color: white; margin-top: 10px; border: none;")
        layout.addWidget(hourly_title)
        
        hour_scroll = QScrollArea()
        hour_scroll.setWidgetResizable(True)
        hour_scroll.setFrameShape(QFrame.NoFrame)
        hour_scroll.setStyleSheet("background: transparent; border: none;")
        
        hour_container = QWidget()
        hour_layout = QHBoxLayout(hour_container)
        hour_layout.setSpacing(12)
        hour_layout.setContentsMargins(0,0,0,0)
        hour_layout.addStretch()
        
        target_date = day_data["date"].date()
        for h in hourly_data:
            if h["time"].date() == target_date:
                card = GlassFrame(radius=12)
                card.setFixedSize(95, 120)
                card_layout = QVBoxLayout(card)
                card_layout.setAlignment(Qt.AlignCenter)
                card_layout.setSpacing(6)
                
                time_lbl = QLabel(h["time"].strftime("%H:%M"))
                time_lbl.setStyleSheet("font-size: 13px; color: #8F95A5; background:transparent; border:none;")
                ico_lbl = QLabel(weather_icon(h["weather_code"], h.get("is_day",1)))
                ico_lbl.setStyleSheet("font-size: 22px; background:transparent; border:none;")
                temp_lbl = QLabel(f"{round(h['temperature'])}°")
                temp_lbl.setStyleSheet("font-size: 15px; font-weight: 600; color: white; background:transparent; border:none;")
                
                card_layout.addWidget(time_lbl, alignment=Qt.AlignCenter)
                card_layout.addWidget(ico_lbl, alignment=Qt.AlignCenter)
                card_layout.addWidget(temp_lbl, alignment=Qt.AlignCenter)
                hour_layout.addWidget(card)
        
        hour_layout.addStretch()
        hour_scroll.setWidget(hour_container)
        layout.addWidget(hour_scroll)
        
        close_btn = QPushButton("Dismiss")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("background: rgba(255,255,255,0.08); border: none; padding: 10px 24px; border-radius: 8px; color: white; font-weight:500;")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

# ==================== MAIN WINDOW ====================
class WeatherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.worker = None
        self.data = None
        self.compact = CompactWidget()
        self.compact.clicked.connect(self._restore_from_compact)
        self.sound = AmbientSoundManager()
        self.tray = self._make_tray()

        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(1024, 680)
        self.resize(1100, 720)

        self.root = BackgroundRoot(self)
        self.setCentralWidget(self.root)

        main_container = QWidget()
        main_container.setObjectName("MainWindowContainer")
        h_layout = QHBoxLayout(main_container)
        h_layout.setContentsMargins(0,0,0,0)
        h_layout.setSpacing(0)

        # Left Column: Navigation Dock
        self.nav_dock = QFrame()
        self.nav_dock.setObjectName("NavigationDockPanel")
        self.nav_dock.setFixedWidth(240)
        nav_layout = QVBoxLayout(self.nav_dock)
        nav_layout.setContentsMargins(16, 24, 16, 24)
        nav_layout.setSpacing(8)

        brand_wrap = QHBoxLayout()
        brand_wrap.setContentsMargins(12, 0, 12, 16)
        brand_lbl = QLabel("ZIYAD METEO")
        brand_lbl.setObjectName("NavBrandLabel")
        brand_wrap.addWidget(brand_lbl)
        nav_layout.addLayout(brand_wrap)

        self.nav_dashboard = NavButton("Dashboard Runway", self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.nav_hourly = NavButton("Hourly Analytics", self.style().standardIcon(QStyle.SP_FileDialogListView))
        self.nav_daily = NavButton("Synoptic 7-Day", self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.nav_map = NavButton("Radar Earth Map", self.style().standardIcon(QStyle.SP_DriveHDIcon))
        self.nav_wear = NavButton("What To Wear", self.style().standardIcon(QStyle.SP_DialogResetButton))

        self.nav_dashboard.setChecked(True)
        for btn in (self.nav_dashboard, self.nav_hourly, self.nav_daily, self.nav_map, self.nav_wear):
            nav_layout.addWidget(btn)
        nav_layout.addStretch()

        h_layout.addWidget(self.nav_dock)

        # Right Column: View Management Stacks
        self.stacked = QStackedWidget()
        h_layout.addWidget(self.stacked, 1)

        # ---------------- PAGE 0: DASHBOARD ----------------
        self.page_dash = QWidget()
        dash_scroll = QScrollArea(self.page_dash)
        dash_scroll.setWidgetResizable(True)
        dash_scroll.setFrameShape(QFrame.NoFrame)
        dash_scroll.setStyleSheet("background: transparent; border: none;")
        
        dash_content = QWidget()
        dash_content.setStyleSheet("background: transparent;")
        dash_layout = QVBoxLayout(dash_content)
        dash_layout.setContentsMargins(32, 24, 32, 32)
        dash_layout.setSpacing(24)

        # Hero Module Panel Header
        self.hero = GlassFrame(radius=16)
        self.hero.setCursor(Qt.PointingHandCursor)
        self.hero.apply_shadow(32, 40)
        self.hero.setMinimumHeight(160)
        self.hero.setMaximumHeight(190)
        self.hero.clicked.connect(self.refresh)
        
        hero_layout = QHBoxLayout(self.hero)
        hero_layout.setContentsMargins(32, 20, 32, 20)
        left_hero = QVBoxLayout()
        left_hero.setSpacing(4)
        self.hero_loc = QLabel("Qingdao")
        self.hero_loc.setObjectName("HeroLocation")
        self.hero_cond = QLabel("Updating local atmospheric fields...")
        self.hero_cond.setObjectName("HeroCondition")
        left_hero.addWidget(self.hero_loc)
        left_hero.addWidget(self.hero_cond)
        
        center_hero = QHBoxLayout()
        center_hero.setSpacing(16)
        self.hero_icon = QLabel("☀")
        self.hero_icon.setObjectName("HeroIcon")
        self.hero_temp = QLabel("--°")
        self.hero_temp.setObjectName("HeroTemp")
        self.hero_feels = QLabel("Feels like --°")
        self.hero_feels.setObjectName("HeroFeels")
        center_hero.addWidget(self.hero_icon)
        center_hero.addWidget(self.hero_temp)
        center_hero.addWidget(self.hero_feels)
        
        hero_layout.addLayout(left_hero, 2)
        hero_layout.addLayout(center_hero, 3)
        dash_layout.addWidget(self.hero)

        # Dynamic Statistics Grid System Modules
        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(18)
        stats_grid.setVerticalSpacing(18)
        self.stat_cards = {}
        titles = ["Humidity","Wind Pace","Pressure Value","UV Metrics","Air Conditions","Solar Windows"]
        keys = ["humidity","wind","pressure","uv","aqi","sun"]
        for idx, (key, title) in enumerate(zip(keys, titles)):
            card = StatCard(key, title)
            card.clicked.connect(lambda k=key: self._on_stat_card_clicked(k))
            stats_grid.addWidget(card, idx//3, idx%3)
            self.stat_cards[key] = card
        dash_layout.addLayout(stats_grid)

        quick_hourly_title = QLabel("Short-Term Outlook")
        quick_hourly_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #7F8695; text-transform: uppercase; letter-spacing: 1.5px;")
        dash_layout.addWidget(quick_hourly_title)
        
        self.quick_hourly_layout = QHBoxLayout()
        self.quick_hourly_layout.setSpacing(16)
        dash_layout.addLayout(self.quick_hourly_layout)

        dash_scroll.setWidget(dash_content)
        v_dash_main = QVBoxLayout(self.page_dash)
        v_dash_main.setContentsMargins(0,0,0,0)
        v_dash_main.addWidget(dash_scroll)
        self.stacked.addWidget(self.page_dash)

        # ---------------- PAGE 1: HOURLY ANALYTICS ----------------
        self.page_hourly = QWidget()
        hr_scroll = QScrollArea(self.page_hourly)
        hr_scroll.setWidgetResizable(True)
        hr_scroll.setFrameShape(QFrame.NoFrame)
        hr_scroll.setStyleSheet("background: transparent; border: none;")
        
        hr_content = QWidget()
        hr_layout = QVBoxLayout(hr_content)
        hr_layout.setContentsMargins(32, 24, 32, 32)
        hr_layout.setSpacing(20)
        
        hr_title = QLabel("24-Hour Synoptic Progression")
        hr_title.setStyleSheet("font-size: 22px; font-weight: 700; color: white;")
        hr_layout.addWidget(hr_title)
        
        self.hourly_scroll_area = QScrollArea()
        self.hourly_scroll_area.setWidgetResizable(True)
        self.hourly_scroll_area.setFixedHeight(170)
        self.hourly_scroll_area.setStyleSheet("background:transparent; border:none;")
        self.hourly_scroll_widget = QWidget()
        self.hourly_grid_layout = QHBoxLayout(self.hourly_scroll_widget)
        self.hourly_grid_layout.setSpacing(12)
        self.hourly_scroll_area.setWidget(self.hourly_scroll_widget)
        hr_layout.addWidget(self.hourly_scroll_area)
        
        hr_scroll.setWidget(hr_content)
        v_hr_main = QVBoxLayout(self.page_hourly)
        v_hr_main.setContentsMargins(0,0,0,0)
        v_hr_main.addWidget(hr_scroll)
        self.stacked.addWidget(self.page_hourly)

        # ---------------- PAGE 2: SYNOPTIC DAILY ----------------
        self.page_daily = QWidget()
        dy_scroll = QScrollArea(self.page_daily)
        dy_scroll.setWidgetResizable(True)
        dy_scroll.setFrameShape(QFrame.NoFrame)
        dy_scroll.setStyleSheet("background: transparent; border: none;")
        
        dy_content = QWidget()
        dy_layout = QVBoxLayout(dy_content)
        dy_layout.setContentsMargins(32, 24, 32, 32)
        dy_layout.setSpacing(20)
        
        dy_title = QLabel("7-Day Atmospheric Sequence")
        dy_title.setStyleSheet("font-size: 22px; font-weight: 700; color: white;")
        dy_layout.addWidget(dy_title)
        
        self.daily_scroll_area = QScrollArea()
        self.daily_scroll_area.setWidgetResizable(True)
        self.daily_scroll_area.setStyleSheet("background:transparent; border:none;")
        self.daily_scroll_widget = QWidget()
        self.daily_grid_layout = QHBoxLayout(self.daily_scroll_widget)
        self.daily_grid_layout.setSpacing(14)
        self.daily_scroll_area.setWidget(self.daily_scroll_widget)
        dy_layout.addWidget(self.daily_scroll_area)
        
        dy_scroll.setWidget(dy_content)
        v_dy_main = QVBoxLayout(self.page_daily)
        v_dy_main.setContentsMargins(0,0,0,0)
        v_dy_main.addWidget(dy_scroll)
        self.stacked.addWidget(self.page_daily)

        # ---------------- PAGE 3: ENHANCED INTERACTIVE EARTH MAP WITH DIAGRAM CHART ----------------
        self.page_map = QWidget()
        map_layout = QVBoxLayout(self.page_map)
        map_layout.setContentsMargins(32, 24, 32, 32)
        map_layout.setSpacing(16)
        
        map_hdr = QLabel("Dynamic Geospatial Earth Radar & Analytics")
        map_hdr.setStyleSheet("font-size: 22px; font-weight: 700; color: white;")
        map_layout.addWidget(map_hdr)

        # Interactive Analytics Plot Overlay Module
        self.analytics_chart = WeatherAnalyticsChart()
        map_layout.addWidget(self.analytics_chart)

        if WEBENGINE_OK:
            self.web_view = QWebEngineView()
            self.web_view.setStyleSheet("border-radius: 12px; background: #0F121D;")
            radar_url = "https://zoom.earth/maps/radar/#view=36.0671,120.3826,7z"
            self.web_view.setUrl(QUrl(radar_url))
            self.web_view.loadFinished.connect(self._clean_radar_socials)
            map_layout.addWidget(self.web_view, 1)
        else:
            fallback_label = QLabel("Interactive tracking maps require the WebEngine binary bundle package.\nRun setup: pip install PySide6-WebEngine")
            fallback_label.setAlignment(Qt.AlignCenter)
            fallback_label.setStyleSheet("font-size: 15px; color: #8F95A5; background: rgba(0,0,0,0.15); border-radius: 12px;")
            map_layout.addWidget(fallback_label, 1)
        self.stacked.addWidget(self.page_map)

        # ---------------- PAGE 4: WHAT TO WEAR ----------------
        self.page_wear = QWidget()
        wear_scroll = QScrollArea(self.page_wear)
        wear_scroll.setWidgetResizable(True)
        wear_scroll.setFrameShape(QFrame.NoFrame)
        wear_scroll.setStyleSheet("background: transparent; border: none;")

        wear_content = QWidget()
        wear_content.setStyleSheet("background: transparent;")
        wear_layout = QVBoxLayout(wear_content)
        wear_layout.setContentsMargins(32, 24, 32, 32)
        wear_layout.setSpacing(20)

        wear_title = QLabel("What to Wear Today")
        wear_title.setStyleSheet("font-size: 22px; font-weight: 700; color: white;")
        wear_subtitle = QLabel("A quick outfit call based on the live conditions in Qingdao.")
        wear_subtitle.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.55);")
        wear_layout.addWidget(wear_title)
        wear_layout.addWidget(wear_subtitle)

        # --- Outfit hero card ---
        self.outfit_hero = GlassFrame(radius=18)
        self.outfit_hero.setStyleSheet(
            "background-color: rgba(40, 55, 90, 0.5); border: 1px solid rgba(100,180,255,0.25); border-radius: 18px;"
        )
        outfit_v = QVBoxLayout(self.outfit_hero)
        outfit_v.setContentsMargins(28, 26, 28, 26)
        outfit_v.setSpacing(20)

        outfit_top_row = QHBoxLayout()
        outfit_top_row.setSpacing(20)

        icon_holder = QFrame()
        icon_holder.setFixedSize(84, 84)
        icon_holder.setStyleSheet(
            "background-color: rgba(100,180,255,0.14); border: 1px solid rgba(100,180,255,0.3); border-radius: 42px;"
        )
        icon_holder_layout = QVBoxLayout(icon_holder)
        icon_holder_layout.setContentsMargins(0, 0, 0, 0)
        self.outfit_icon = QLabel("👕")
        self.outfit_icon.setAlignment(Qt.AlignCenter)
        self.outfit_icon.setStyleSheet("font-size: 38px; background: transparent; border: none;")
        icon_holder_layout.addWidget(self.outfit_icon)

        outfit_text_col = QVBoxLayout()
        outfit_text_col.setSpacing(5)
        self.outfit_headline = QLabel("Calculating today's outfit...")
        self.outfit_headline.setWordWrap(True)
        self.outfit_headline.setStyleSheet("font-size: 19px; font-weight: 700; color: #64B4FF; background: transparent;")
        self.outfit_reason = QLabel("Hang tight while we pull the latest conditions.")
        self.outfit_reason.setWordWrap(True)
        self.outfit_reason.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.62); background: transparent;")
        outfit_text_col.addWidget(self.outfit_headline)
        outfit_text_col.addWidget(self.outfit_reason)
        outfit_top_row.addWidget(icon_holder)
        outfit_top_row.addLayout(outfit_text_col, 1)
        outfit_v.addLayout(outfit_top_row)

        outfit_divider = QFrame()
        outfit_divider.setFixedHeight(1)
        outfit_divider.setStyleSheet("background-color: rgba(255,255,255,0.08); border: none;")
        outfit_v.addWidget(outfit_divider)

        # Top / bottom / footwear breakdown as mini chip cards
        pieces_row = QHBoxLayout()
        pieces_row.setSpacing(14)
        self.outfit_piece_labels = {}
        piece_defs = [("top", "TOP", "👕"), ("bottom", "BOTTOM", "👖"), ("footwear", "FOOTWEAR", "👟")]
        for piece_key, cap_text, piece_icon in piece_defs:
            chip = QFrame()
            chip.setStyleSheet(
                "background-color: rgba(255,255,255,0.045); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px;"
            )
            chip_layout = QVBoxLayout(chip)
            chip_layout.setContentsMargins(14, 12, 14, 12)
            chip_layout.setSpacing(4)
            picon_lbl = QLabel(piece_icon)
            picon_lbl.setStyleSheet("font-size: 17px; background: transparent; border: none;")
            cap = QLabel(cap_text)
            cap.setStyleSheet("font-size: 10px; font-weight: 700; color: #7F8695; letter-spacing: 1px; background: transparent; border: none;")
            val = QLabel("--")
            val.setWordWrap(True)
            val.setStyleSheet("font-size: 13px; font-weight: 600; color: white; background: transparent; border: none;")
            chip_layout.addWidget(picon_lbl)
            chip_layout.addWidget(cap)
            chip_layout.addWidget(val)
            pieces_row.addWidget(chip, 1)
            self.outfit_piece_labels[piece_key] = val
        outfit_v.addLayout(pieces_row)

        # Accessory pills
        self.accessory_row = QHBoxLayout()
        self.accessory_row.setSpacing(8)
        self.accessory_row.addStretch()
        outfit_v.addLayout(self.accessory_row)

        wear_layout.addWidget(self.outfit_hero)

        # --- Index cards: Umbrella / Air Quality / Coastal Activity ---
        indices_title = QLabel("Today's Indices")
        indices_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #7F8695; text-transform: uppercase; letter-spacing: 1.5px;")
        wear_layout.addWidget(indices_title)

        indices_grid = QGridLayout()
        indices_grid.setHorizontalSpacing(18)
        indices_grid.setVerticalSpacing(18)
        self.wear_index_cards = {}
        index_defs = [
            ("umbrella", "Umbrella", "☂", "100,180,255"),
            ("mask", "Air Quality", "😷", "255,196,92"),
            ("coast", "Coastal Activity", "🌊", "100,224,200"),
        ]
        for idx, (key, title, icon, accent) in enumerate(index_defs):
            card = StatCard(key, f"{icon}  {title}")
            card.setStyleSheet(
                f"background-color: rgba({accent},0.07); "
                f"border: 1px solid rgba({accent},0.22); "
                f"border-left: 3px solid rgba({accent},0.8); "
                f"border-radius: 16px;"
            )
            card.value_lbl.setStyleSheet(f"font-size: 22px; font-weight: 700; color: rgb({accent}); background: transparent;")
            card.clicked.connect(lambda k=key: self._on_wear_card_clicked(k))
            indices_grid.addWidget(card, 0, idx)
            indices_grid.setColumnStretch(idx, 1)
            self.wear_index_cards[key] = card
        wear_layout.addLayout(indices_grid)
        wear_layout.addStretch()

        wear_scroll.setWidget(wear_content)
        v_wear_main = QVBoxLayout(self.page_wear)
        v_wear_main.setContentsMargins(0, 0, 0, 0)
        v_wear_main.addWidget(wear_scroll)
        self.stacked.addWidget(self.page_wear)

        # Connect Navigation Click Event Pipeline handlers seamlessly
        self.nav_dashboard.clicked.connect(lambda: self.stacked.setCurrentIndex(0))
        self.nav_hourly.clicked.connect(lambda: self.stacked.setCurrentIndex(1))
        self.nav_daily.clicked.connect(lambda: self.stacked.setCurrentIndex(2))
        self.nav_map.clicked.connect(lambda: self.stacked.setCurrentIndex(3))
        self.nav_wear.clicked.connect(lambda: self.stacked.setCurrentIndex(4))

        self.root.content.layout().addWidget(main_container)
        root_content_layout = self.root.content.layout()
        
        self.titlebar = TitleBar()
        self.titlebar.compactReq.connect(self.toggle_compact)
        self.titlebar.maxReq.connect(self.toggle_max)
        self.titlebar.settingsReq.connect(self.open_settings)
        self.titlebar.onTopReq.connect(self.set_on_top)
        self.titlebar.closeReq.connect(self.hide_to_tray)
        self.titlebar.pin_btn.setChecked(self.settings.get("always_on_top", False))
        self.titlebar.set_maximized(False)
        
        root_content_layout.insertWidget(0, self.titlebar)

        self.spinner = LoadingSpinner(self)
        self.spinner.hide()

        self._apply_style()
        self._apply_window_flags()
        set_windows_autostart(self.settings.get("auto_start",False))
        self._start_timer()
        QTimer.singleShot(500, self.refresh)

    def _clean_radar_socials(self, success):
        if success and WEBENGINE_OK:
            clean_css_js = """
            (function() {
                var style = document.createElement('style');
                style.type = 'text/css';
                style.innerHTML = `
                    #social, .social-icon, #closing-links, #community, #hd, .hd, #ft, .ft, .panel,
                    a[href*="facebook.com"], a[href*="twitter.com"], a[href*="instagram.com"], a[href*="github.com"] {
                        display: none !important; opacity: 0 !important; visibility: hidden !important;
                    }
                `;
                document.head.appendChild(style);
            })();
            """
            self.web_view.page().runJavaScript(clean_css_js)

    def _on_stat_card_clicked(self, key_type: str):
        if self.data:
            dlg = StatInsightDialog(key_type, self.data, self)
            dlg.exec()

    def _on_wear_card_clicked(self, key_type: str):
        if self.data:
            dlg = StatInsightDialog(key_type, self.data, self)
            dlg.exec()

    def _make_tray(self):
        tray = QSystemTrayIcon(app_icon(), self)
        menu = QMenu()
        menu.addAction("Show Panel", self._show_from_tray)
        menu.addAction("Mini Desk Widget", self.toggle_compact)
        menu.addAction("Configurations", self.open_settings)
        menu.addSeparator()
        menu.addAction("Terminate", self.quit_app)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        tray.show()
        return tray

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._show_from_tray()

    def _show_from_tray(self):
        self.compact.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_compact(self):
        if self.isVisible():
            self.hide()
            if self.data:
                self.compact.update_data(self.data)
            self.compact.show()
            self.compact.raise_()
        else:
            self.compact.hide()
            self.show()

    def _restore_from_compact(self):
        self.compact.hide()
        self.show()
        self.raise_()

    def toggle_max(self):
        if self.isMaximized():
            self.showNormal()
            self.titlebar.set_maximized(False)
        else:
            self.showMaximized()
            self.titlebar.set_maximized(True)

    def open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.Accepted:
            self.settings = dlg.get_values()
            save_settings(self.settings)
            self._apply_window_flags()
            self._apply_settings()
            set_windows_autostart(self.settings.get("auto_start",False))
            self.refresh()

    def set_on_top(self, enabled: bool):
        self.settings["always_on_top"] = enabled
        save_settings(self.settings)
        self._apply_window_flags()
        self.show()

    def _apply_style(self):
        self.setStyleSheet("""
            QWidget#MainWindowContainer {
                background: transparent;
            }
            QFrame#NavigationDockPanel {
                background-color: rgba(13, 17, 27, 0.45);
                border-right: 1px solid rgba(255, 255, 255, 0.05);
            }
            QLabel#NavBrandLabel {
                font-size: 16px;
                font-weight: 800;
                color: #64B4FF;
                letter-spacing: 2px;
            }
            QFrame#TitleBarPanel {
                background-color: rgba(13, 17, 27, 0.3);
                border-bottom: 1px solid rgba(255,255,255,0.04);
            }
            QLabel#TitleBarTitle {
                font-size: 14px;
                font-weight: 600;
                color: rgba(255,255,255,0.85);
            }
            QFrame#GlassFrame {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 16px;
            }
            QFrame#GlassFrame:hover {
                background-color: rgba(255, 255, 255, 0.085);
                border: 1px solid rgba(100, 180, 255, 0.28);
            }
            QLabel#HeroLocation {
                font-size: 26px;
                font-weight: 700;
                color: white;
                background: transparent;
            }
            QLabel#HeroCondition {
                font-size: 14px;
                color: rgba(255, 255, 255, 0.7);
                background: transparent;
            }
            QLabel#HeroIcon {
                font-size: 54px;
                background: transparent;
            }
            QLabel#HeroTemp {
                font-size: 48px;
                font-weight: 700;
                color: white;
                background: transparent;
            }
            QLabel#HeroFeels {
                font-size: 14px;
                color: rgba(255,255,255,0.6);
                background: transparent;
            }
            QLabel#StatTitle {
                font-size: 12px;
                font-weight: 700;
                color: #7F8695;
                text-transform: uppercase;
                letter-spacing: 1px;
                background: transparent;
            }
            QLabel#StatValue {
                font-size: 22px;
                font-weight: 700;
                color: white;
                background: transparent;
            }
            QLabel#StatSub {
                font-size: 12px;
                color: rgba(255,255,255,0.5);
                background: transparent;
            }
            QFrame#MainWindowOverlay {
                background-color: rgba(10, 14, 23, 0.2);
            }
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 8px;
            }
            QToolButton:hover {
                background-color: rgba(255,255,255,0.08);
            }
            QScrollBar:horizontal { height:5px; background:transparent; }
            QScrollBar::handle:horizontal { background:rgba(255,255,255,0.15); border-radius:3px; }
            QScrollBar:vertical { width:5px; background:transparent; }
            QScrollBar::handle:vertical { background:rgba(255,255,255,0.15); border-radius:3px; }
        """)

    def _apply_window_flags(self):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.settings.get("always_on_top",False))
        self.setWindowOpacity(self.settings.get("opacity",0.95))

    def _apply_settings(self):
        self.sound.set_volume(self.settings.get("volume",40))
        if hasattr(self, 'titlebar'):
            self.titlebar.pin_btn.setChecked(self.settings.get("always_on_top",False))

    def _start_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(max(1,self.settings.get("refresh_interval",15)) * 60 * 1000)

    def refresh(self):
        if self.worker and self.worker.isRunning():
            return
        self._set_loading(True)
        self.worker = WeatherWorker()
        self.worker.fetched.connect(self._on_data)
        self.worker.failed.connect(self._on_error)
        self.worker.start()

    def _set_loading(self, loading):
        if loading:
            self.hero_cond.setText("Fetching satellite streams...")
            self.spinner.move(self.rect().center() - self.spinner.rect().center())
            self.spinner.show()
        else:
            self.spinner.hide()
            if self.data:
                self.hero_cond.setText(self.data["current"]["label"])

    def _make_pill(self, text: str) -> QLabel:
        pill = QLabel(text)
        pill.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #64B4FF; "
            "background-color: rgba(100,180,255,0.14); border: 1px solid rgba(100,180,255,0.3); "
            "border-radius: 11px; padding: 4px 12px;"
        )
        return pill

    def _clear_accessory_row(self):
        while self.accessory_row.count():
            item = self.accessory_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _generate_smart_advice(self, data: dict):
        try:
            cur = data["current"]
            aqi = data.get("aqi", {})
            temp = cur.get("temperature", 20)
            code = cur.get("weather_code", 0)
            wind = cur.get("wind_speed", 0) or 0
            uv = cur.get("uv_index", 0) or 0
            aqi_val = aqi.get("value")
            rain_codes = (51,53,55,56,57,61,63,65,66,67,80,81,82,95,96,99)
            snow_codes = (71,73,75,77,85,86)
            is_rain = code in rain_codes
            is_snow = code in snow_codes

            headline = "Optimal Coastal Layering Formula"
            advice = "Standard comfort frameworks apply. "
            top, bottom, footwear = "T-shirt or light top", "Casual trousers", "Sneakers"

            if temp < 5:
                headline = "Severe Chill & Heavy Layering Alert"
                advice = "Heavy insulated down coats, thermals, and wind-breaking shields are necessary against cross-gale currents."
                top, bottom, footwear = "Thermal base + down coat", "Insulated/lined pants", "Insulated boots"
            elif temp < 15:
                headline = "Brisk Sea Front Winds: Light Coats"
                advice = "A trench coat, casual sweater, or structured windbreaker fits standard localized operations."
                top, bottom, footwear = "Sweater + light coat", "Jeans or chinos", "Closed-toe shoes"
            elif temp > 28:
                headline = "High Heat Index: Lightweight Fabrics"
                advice = "Opt for breathable linen or thin cotton sets. Solar protection blocks are heavily emphasized."
                top, bottom, footwear = "Breathable linen/cotton top", "Shorts or light trousers", "Sandals or breathable sneakers"
            else:
                advice += "A light layer with a jacket on hand covers most of the day comfortably."
                top, bottom, footwear = "Light top + optional layer", "Jeans or chinos", "Sneakers"

            if is_snow:
                footwear = "Waterproof winter boots"
            if is_rain:
                advice += " Waterproof shells or compact umbrellas should be kept nearby."
                footwear = "Waterproof shoes or boots"

            self.outfit_headline.setText(headline)
            self.outfit_reason.setText(advice)
            self.outfit_icon.setText(weather_icon(code, cur.get("is_day", 1)))
            self.outfit_piece_labels["top"].setText(top)
            self.outfit_piece_labels["bottom"].setText(bottom)
            self.outfit_piece_labels["footwear"].setText(footwear)

            # Accessory pills
            self._clear_accessory_row()
            accessories = []
            if is_rain:
                accessories.append("☂ Umbrella")
            if is_snow:
                accessories.append("🧤 Gloves")
            if temp < 8:
                accessories.append("🧣 Scarf")
            if uv and float(uv) >= 6:
                accessories.append("🕶 Sunglasses")
                accessories.append("🧴 Sunscreen")
            if isinstance(aqi_val, (int, float)) and aqi_val > 100:
                accessories.append("😷 Mask")
            if not accessories:
                accessories.append("👍 No extras needed")
            for a in accessories:
                self.accessory_row.addWidget(self._make_pill(a))
            self.accessory_row.addStretch()

            # Index cards: umbrella / mask / coast
            if is_rain:
                self.wear_index_cards["umbrella"].set_value("Yes", weather_label(code))
            else:
                self.wear_index_cards["umbrella"].set_value("No", weather_label(code))

            mask_val = aqi_val if aqi_val is not None else "--"
            self.wear_index_cards["mask"].set_value(str(mask_val), aqi.get("label", "Unknown"))

            try:
                wind_f = float(wind)
            except Exception:
                wind_f = 0
            if wind_f < 15:
                coast_status = "Calm"
            elif wind_f < 30:
                coast_status = "Moderate"
            else:
                coast_status = "Rough"
            self.wear_index_cards["coast"].set_value(coast_status, f"{wind} km/h wind")
        except Exception:
            self.outfit_headline.setText("Enjoy Qingdao Outdoors")
            self.outfit_reason.setText("Atmospheric layers appear nominal for standard outdoor plans.")

    def _on_data(self, data):
        self.data = data
        cur = data["current"]
        
        self.hero_icon.setText(cur.get("icon","☀"))
        self.hero_temp.setText(self._fmt_t(cur.get("temperature")))
        self.hero_feels.setText(f"Feels like {self._fmt_t(cur.get('apparent_temperature'))}")
        self.hero_loc.setText("Qingdao")
        
        # Hydrate Chart with progression sequences
        chart_points = [float(h["temperature"]) for h in data["hourly"][:12]]
        chart_labels = [h["time"].strftime("%H:%M") for h in data["hourly"][:12]]
        self.analytics_chart.set_data(chart_points, chart_labels)

        self.stat_cards["humidity"].set_value(f"{cur.get('humidity')}%", "Relative Layer")
        self.stat_cards["wind"].set_value(f"{cur.get('wind_speed')} kmh", "Yellow Sea Vectors")
        self.stat_cards["pressure"].set_value(f"{round(float(cur.get('pressure')))} hPa", "Barometric Surface")
        self.stat_cards["uv"].set_value(f"{cur.get('uv_index')}", "Radiance Multiplier")
        self.stat_cards["aqi"].set_value(f"{data['aqi']['value']}", data["aqi"]["label"])
        self.stat_cards["sun"].set_value(fmt_time(data.get("sunrise")), f"Sunset: {fmt_time(data.get('sunset'))}")

        self._populate_quick_hourly(data["hourly"])
        self._populate_full_hourly(data["hourly"])
        self._populate_full_daily(data["daily"])
        self._generate_smart_advice(data)
        self.compact.update_data(data)
        
        self._set_loading(False)
        self._update_theme_engines()

    def _on_error(self, err_msg):
        self._set_loading(False)
        self.hero_cond.setText("Network packet drop. Check connections.")

    def _populate_quick_hourly(self, rows):
        for i in reversed(range(self.quick_hourly_layout.count())):
            w = self.quick_hourly_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        count = 0
        for row in rows:
            if count >= 5:
                break
            card = GlassFrame(radius=12)
            card.setFixedSize(115, 110)
            layout = QVBoxLayout(card)
            layout.setAlignment(Qt.AlignCenter)
            layout.setSpacing(4)
            
            t_lbl = QLabel(row["time"].strftime("%H:%M"))
            t_lbl.setStyleSheet("color: #8F95A5; font-size:12px; background:transparent; border:none;")
            i_lbl = QLabel(weather_icon(row["weather_code"], row.get("is_day",1)))
            i_lbl.setStyleSheet("font-size:22px; background:transparent; border:none;")
            v_lbl = QLabel(self._fmt_t(row["temperature"]))
            v_lbl.setStyleSheet("font-weight:600; font-size:14px; background:transparent; border:none;")
            
            layout.addWidget(t_lbl, alignment=Qt.AlignCenter)
            layout.addWidget(i_lbl, alignment=Qt.AlignCenter)
            layout.addWidget(v_lbl, alignment=Qt.AlignCenter)
            self.quick_hourly_layout.addWidget(card)
            count += 1

    def _populate_full_hourly(self, rows):
        for i in reversed(range(self.hourly_grid_layout.count())):
            w = self.hourly_grid_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        for idx, row in enumerate(rows[:24]):
            card = GlassFrame(radius=12)
            card.setFixedSize(110, 135)
            layout = QVBoxLayout(card)
            layout.setAlignment(Qt.AlignCenter)
            layout.setSpacing(6)
            
            t_lbl = QLabel(row["time"].strftime("%H:%M"))
            t_lbl.setStyleSheet("color: #8F95A5; font-size:12px; background:transparent; border:none;")
            i_lbl = QLabel(weather_icon(row["weather_code"], row.get("is_day",1)))
            i_lbl.setStyleSheet("font-size:22px; background:transparent; border:none;")
            v_lbl = QLabel(self._fmt_t(row["temperature"]))
            v_lbl.setStyleSheet("font-weight:600; font-size:15px; background:transparent; border:none;")
            uv_lbl = QLabel(f"UV {self._fmt_uv(row['uv_index'])}")
            uv_lbl.setStyleSheet("font-size:11px; color: rgba(255,255,255,0.5); background:transparent; border:none;")
            
            layout.addWidget(t_lbl, alignment=Qt.AlignCenter)
            layout.addWidget(i_lbl, alignment=Qt.AlignCenter)
            layout.addWidget(v_lbl, alignment=Qt.AlignCenter)
            layout.addWidget(uv_lbl, alignment=Qt.AlignCenter)
            self.hourly_grid_layout.addWidget(card)

    def _populate_full_daily(self, rows):
        for i in reversed(range(self.daily_grid_layout.count())):
            w = self.daily_grid_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        for idx, row in enumerate(rows[:7]):
            card = GlassFrame(radius=14)
            card.setFixedSize(135, 150)
            card.setCursor(Qt.PointingHandCursor)
            
            # Clicking daily row opens drilldown breakdown dialog directly
            card.mousePressEvent = lambda e, r=row: self._open_day_dialog(r)
            
            layout = QVBoxLayout(card)
            layout.setAlignment(Qt.AlignCenter)
            layout.setSpacing(4)
            
            d_lbl = QLabel(fmt_day(row["date"])[:3].upper())
            d_lbl.setStyleSheet("color: #64B4FF; font-weight:700; font-size:12px; background:transparent; border:none;")
            sub_lbl = QLabel(row["date"].strftime("%m/%d"))
            sub_lbl.setStyleSheet("color: rgba(255,255,255,0.4); font-size:11px; background:transparent; border:none;")
            i_lbl = QLabel(weather_icon(row["weather_code"], 1))
            i_lbl.setStyleSheet("font-size:26px; background:transparent; border:none;")
            range_lbl = QLabel(f"{round(row['high'])}° / {round(row['low'])}°")
            range_lbl.setStyleSheet("font-weight:500; font-size:13px; color:white; background:transparent; border:none;")
            
            layout.addWidget(d_lbl, alignment=Qt.AlignCenter)
            layout.addWidget(sub_lbl, alignment=Qt.AlignCenter)
            layout.addWidget(i_lbl, alignment=Qt.AlignCenter)
            layout.addWidget(range_lbl, alignment=Qt.AlignCenter)
            self.daily_grid_layout.addWidget(card)

    def _open_day_dialog(self, day_data):
        if self.data and "hourly" in self.data:
            dlg = DayDetailDialog(day_data, self.data["hourly"], self)
            dlg.exec()

    def _fmt_t(self, val):
        return "--°" if val is None else f"{round(float(val))}°"

    def _fmt_uv(self, val):
        return "0" if val is None else str(round(float(val)))

    def _update_theme_engines(self):
        if not self.data:
            return
        active_theme = self.settings.get("theme_override","auto")
        if active_theme == "auto":
            active_theme = self.data["current"]["theme"]
        self.root.set_background(active_theme)
        self.sound.play_theme(active_theme)

    def hide_to_tray(self):
        self.hide()
        self.tray.showMessage(APP_NAME, "App running implicitly in system tray.", QSystemTrayIcon.Information, 1500)

    def quit_app(self):
        self.sound.stop()
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, e):
        e.ignore()
        self.hide_to_tray()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, 'spinner'):
            self.spinner.move(self.rect().center() - self.spinner.rect().center())

# ==================== SETTINGS DIALOG ====================
class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration Profiles")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setStyleSheet("background-color: #121622; color: white;")
        self.settings = dict(settings)
        
        form = QFormLayout()
        self.refresh = QSpinBox()
        self.refresh.setRange(1, 180)
        self.refresh.setValue(self.settings.get("refresh_interval", 15))
        self.refresh.setSuffix(" minutes")
        
        self.vol = QSlider(Qt.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(self.settings.get("volume", 40))
        
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(30, 100)
        self.opacity.setValue(int(self.settings.get("opacity", 0.95)*100))
        
        self.theme = QComboBox()
        self.theme.addItems(["Auto", "Sunny", "Cloudy", "Rainy", "Storm", "Snow", "Fog", "Night"])
        self.theme.setCurrentText(self.settings.get("theme_override", "auto").capitalize())
        
        self.top = QCheckBox("Force Window Stays on Top Level")
        self.top.setChecked(self.settings.get("always_on_top", False))
        
        self.auto = QCheckBox("Launch implicit during OS startup cycle")
        self.auto.setChecked(self.settings.get("auto_start", False))
        
        form.addRow("Sync Interval", self.refresh)
        form.addRow("Audio Ambience Volume", self.vol)
        form.addRow("Transparency Opacity", self.opacity)
        form.addRow("Manual Graphic Wallpaper Override", self.theme)
        form.addRow("", self.top)
        form.addRow("", self.auto)
        
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24,24,24,24)
        outer.setSpacing(20)
        
        title = QLabel("System Settings Configuration")
        title.setStyleSheet("font-size: 18px; font-weight:600; color:white;")
        outer.addWidget(title)
        outer.addLayout(form)
        outer.addSpacing(10)
        outer.addWidget(btns)

    def get_values(self):
        txt = self.theme.currentText().lower()
        return {
            "refresh_interval": self.refresh.value(),
            "volume": self.vol.value(),
            "opacity": round(self.opacity.value()/100.0,2),
            "always_on_top": self.top.isChecked(),
            "auto_start": self.auto.isChecked(),
            "theme_override": txt,
        }

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    
    win = WeatherWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()