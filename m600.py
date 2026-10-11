#!/usr/bin/env python3
"""Lenovo Legion M600 Configuration Tool — Linux"""

import hid
import sys
import time
import json
import os
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QRadioButton, QComboBox,
    QColorDialog, QMessageBox, QTabWidget, QSpinBox, QProgressBar,
    QLineEdit,
)
from PyQt5.QtCore import Qt, QTimer

# ════════════════════════════════════════════════════════════════════════════════
# Protocol constants
# ════════════════════════════════════════════════════════════════════════════════

VENDOR_ID = 0x17EF
PRODUCT_ID = 0x60E6
CONFIG_FILE = os.path.expanduser("~/.m600_config.json")

# M600 DPI sensor table — non-linear mapping recovered from the Windows driver.
# DPI value = (index + 1) * 100;  sensor register = DPI_SENSOR_INDICES[index].
# The firmware expects the sensor register, NOT the DPI value.
DPI_SENSOR_INDICES = [
    0, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 16, 17, 18,
    19, 20, 22, 23, 24, 25, 26, 27, 29, 30, 31, 32, 33, 35, 37, 38,
    39, 40, 41, 42, 44, 45, 46, 47, 48, 50, 51, 52, 53, 54, 56, 57,
    58, 59, 60, 62, 63, 64, 65, 66, 68, 69, 70, 71, 72, 74, 75, 76,
    77, 78, 80, 81, 82, 83, 84, 86, 87, 88, 89, 90, 92, 93, 94, 95,
    96, 98, 99, 100, 101, 102, 104, 105, 106, 107, 108, 110, 111, 112,
    113, 114, 116, 117, 118, 119, 120, 122, 123, 124, 125, 126, 128, 129,
    130, 131, 132, 134, 135, 136, 137, 138, 140, 141, 142, 143, 144, 146,
    147, 148, 149, 150, 152, 153, 154, 155, 156, 158, 159, 160, 161, 162,
    164, 165, 166, 167, 168, 170, 171, 172, 173, 174, 176, 177, 178, 179,
    180, 181, 182, 183, 184, 185, 186, 187, 188, 189,
]


def dpi_to_sensor(dpi):
    """Convert a DPI value (100-16000, step 100) to the M600 sensor register."""
    if dpi < 100 or dpi > 16000 or dpi % 100 != 0:
        return None
    return DPI_SENSOR_INDICES[(dpi // 100) - 1]


# Button action bytes — HID usage codes for the M600 key-action matrix.
BUTTON_ACTIONS = {
    "Left Click":     [0xB0, 0x00, 0x00, 0x00, 0x00],
    "Right Click":    [0xB1, 0x00, 0x00, 0x00, 0x00],
    "Middle Click":   [0xB2, 0x00, 0x00, 0x00, 0x00],
    "Forward":        [0xB4, 0x00, 0x00, 0x00, 0x00],
    "Back":           [0xB3, 0x00, 0x00, 0x00, 0x00],
    "DPI Cycle":      [0xC1, 0x00, 0x00, 0x00, 0x00],
    "Play":           [0x93, 0x00, 0x00, 0x00, 0x00],
    "Pause":          [0x94, 0x00, 0x00, 0x00, 0x00],
    "Previous Track": [0x99, 0x00, 0x00, 0x00, 0x00],
    "Next Track":     [0x96, 0x00, 0x00, 0x00, 0x00],
    "Volume Up":      [0x90, 0x00, 0x00, 0x00, 0x00],
    "Volume Down":    [0x91, 0x00, 0x00, 0x00, 0x00],
    "Mute":           [0x92, 0x00, 0x00, 0x00, 0x00],
    "Disabled":       [0x00, 0x00, 0x00, 0x00, 0x00],
}

BUTTON_DEFS = [
    ("1 - Left Click", 0),
    ("2 - Right Click", 1),
    ("3 - Middle Click", 2),
    ("4 - DPI Switch", 9),
    ("5 - Forward", 6),
    ("6 - Backward", 5),
    ("7 - Right Rear", 7),
    ("8 - Right Front", 8),
]

DEFAULT_ACTIONS = {
    0: "Left Click", 1: "Right Click", 2: "Middle Click",
    9: "DPI Cycle", 6: "Forward", 5: "Back",
    7: "Disabled", 8: "Disabled",
}

EFFECTS = ["Static", "Breathing", "Rainbow", "Random", "Off"]

LEGION_BLUE = (0, 180, 255)


# ════════════════════════════════════════════════════════════════════════════════
# udev helper
# ════════════════════════════════════════════════════════════════════════════════

def install_udev_rule():
    rule = (
        'SUBSYSTEM=="usb", ATTRS{idVendor}=="17ef", ATTRS{idProduct}=="60e6", MODE="0666"\n'
        'KERNEL=="hidraw*", ATTRS{idVendor}=="17ef", ATTRS{idProduct}=="60e6", MODE="0666"'
    )
    cmd = (
        f"echo '{rule}' > /etc/udev/rules.d/99-legion-m600.rules "
        "&& udevadm control --reload-rules && udevadm trigger"
    )
    try:
        subprocess.run(["pkexec", "sh", "-c", cmd], check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# ════════════════════════════════════════════════════════════════════════════════
# HID device
# ════════════════════════════════════════════════════════════════════════════════

class LegionM600:
    def __init__(self):
        target = None
        for dev in hid.enumerate(VENDOR_ID, PRODUCT_ID):
            if dev["usage_page"] == 0x01 and dev["usage"] == 0x00:
                target = dev["path"]
                break
            if dev.get("interface_number") in (1, 2):
                target = dev["path"]
        if not target:
            raise RuntimeError("Dongle not found — plug in the 2.4 GHz receiver.")
        self._d = hid.device()
        try:
            self._d.open_path(target)
            self._d.set_nonblocking(1)
        except IOError as exc:
            raise RuntimeError(f"HID open failed: {exc}")

    # -- low level ------------------------------------------------------------

    def _send(self, payload, length=64, checksum=False):
        buf = list(payload) + [0x00] * (length - len(payload))
        if checksum:
            buf[63] = sum(buf[:63]) & 0xFF
        self._d.write([0x00] + buf)

    def _read(self):
        time.sleep(0.05)
        return self._d.read(64)

    # -- queries --------------------------------------------------------------

    def connected(self):
        self._send([0x0E], length=3)
        r = self._read()
        return bool(r and r[2] != 0)

    def battery_pct(self):
        self._send([0x0B], length=2)
        r = self._read()
        return r[4] if r else None

    # -- DPI ------------------------------------------------------------------

    def set_dpi_stage(self, stage):
        self._send([0x04, 0x01, 0x01, stage])

    def set_dpi_value(self, stage, dpi):
        idx = dpi_to_sensor(dpi)
        if idx is None:
            return
        le = list(idx.to_bytes(2, "little"))
        self._send([0x04, 0x01, 0x00, stage] + le + le)

    # -- button mapping -------------------------------------------------------

    def set_button(self, offset, action_bytes):
        self._send([0x02, 0x00, offset] + action_bytes, checksum=True)

    # -- lighting (per-zone) --------------------------------------------------

    def set_lighting(self, z0, z1):
        """z0, z1 are 12-byte zone records."""
        self._send([0x25, 0x00, 0x01, 0x01, 0x18] + z0 + z1, checksum=True)

    @staticmethod
    def zone_bytes(effect, color, color2):
        r, g, b = color
        r2, g2, b2 = color2
        if effect == "Static":
            return [0x03, 0x64, 0x00, r, g, b, 0, 0, 0, 0, 0, 0]
        if effect == "Breathing":
            mode = 0x01 if (r2, g2, b2) == (0, 0, 0) else 0x03
            return [0x02, 0x64, 0x00, 0x02, mode, 0, r, g, b, r2, g2, b2]
        if effect == "Rainbow":
            return [0x01, 0x64, 0x00, 0x0A, 0, 0, 0, 0, 0, 0, 0, 0]
        if effect == "Random":
            return [0x03, 0x64, 0x01, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        return [0x03, 0x00, 0x00, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # Off

    # -- commit ---------------------------------------------------------------

    def commit(self):
        self._send([0x05, 0x00, 0x00], length=3)
        time.sleep(0.1)


# ════════════════════════════════════════════════════════════════════════════════
# Modern dark theme
# ════════════════════════════════════════════════════════════════════════════════

THEME = """
QMainWindow, QWidget {
    background-color: #12121f;
    color: #c8c8dc;
    font-family: 'Segoe UI', 'Cantarell', 'Noto Sans', sans-serif;
    font-size: 13px;
}

/* tabs */
QTabWidget::pane {
    background: #181828;
    border: 1px solid #2a2a42;
    border-radius: 8px;
    margin: 6px;
}
QTabBar::tab {
    background: #1c1c30;
    color: #6e6e8e;
    border: 1px solid #2a2a42;
    border-bottom: none;
    border-radius: 7px 7px 0 0;
    padding: 9px 22px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #181828;
    color: #7ec8e3;
    border-bottom: 2px solid #7ec8e3;
}
QTabBar::tab:hover:!selected {
    background: #222238;
    color: #a0a0c0;
}

/* buttons */
QPushButton {
    background: #222238;
    color: #c8c8dc;
    border: 1px solid #343452;
    border-radius: 7px;
    padding: 8px 18px;
}
QPushButton:hover { background: #2a2a46; border-color: #4a4a70; }
QPushButton:pressed { background: #1e1e34; }
QPushButton#applyBtn {
    background: #2a5a8a;
    color: #e8f4ff;
    border: none;
    padding: 10px 22px;
    font-weight: 600;
}
QPushButton#applyBtn:hover { background: #3470a8; }

/* group box */
QGroupBox {
    background: #181828;
    border: 1px solid #2a2a42;
    border-radius: 8px;
    margin-top: 14px;
    padding: 18px 14px 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #7ec8e3;
}

/* combo box */
QComboBox {
    background: #222238;
    color: #c8c8dc;
    border: 1px solid #343452;
    border-radius: 6px;
    padding: 6px 12px;
    min-width: 100px;
}
QComboBox:hover { border-color: #4a4a70; }
QComboBox:focus  { border-color: #7ec8e3; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow {
    width: 0; height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #6e6e8e;
}
QComboBox QAbstractItemView {
    background: #222238;
    color: #c8c8dc;
    border: 1px solid #343452;
    selection-background-color: #2a4a68;
    selection-color: #7ec8e3;
    outline: none;
}

/* spin box */
QSpinBox {
    background: #222238;
    color: #c8c8dc;
    border: 1px solid #343452;
    border-radius: 6px;
    padding: 5px 10px;
}
QSpinBox:hover { border-color: #4a4a70; }
QSpinBox:focus  { border-color: #7ec8e3; }
QSpinBox::up-button, QSpinBox::down-button {
    background: #2a2a42;
    border: none;
    width: 20px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background: #343452;
}

/* radio button */
QRadioButton { color: #c8c8dc; spacing: 8px; }
QRadioButton::indicator {
    width: 16px; height: 16px;
    border-radius: 8px;
    border: 2px solid #3a3a58;
    background: #222238;
}
QRadioButton::indicator:checked {
    border: 2px solid #7ec8e3;
    background: #7ec8e3;
}

/* progress bar */
QProgressBar {
    background: #222238;
    border: 1px solid #2a2a42;
    border-radius: 10px;
    text-align: center;
    color: #ffffff;
    font-weight: 600;
    min-height: 26px;
}
QProgressBar::chunk {
    background: #3a8ab8;
    border-radius: 9px;
}

/* labels */
QLabel { background: transparent; }
"""


# ════════════════════════════════════════════════════════════════════════════════
# Application
# ════════════════════════════════════════════════════════════════════════════════

class M600App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lenovo Legion M600")
        self.setMinimumSize(540, 600)

        self.cfg = self._load_cfg()

        # Lighting state
        self.z0_effect = "Rainbow"
        self.z0_color = LEGION_BLUE
        self.z0_color2 = (0, 0, 0)
        self.z1_effect = "Rainbow"
        self.z1_color = LEGION_BLUE
        self.z1_color2 = (0, 0, 0)

        try:
            self.mouse = LegionM600()
        except RuntimeError as exc:
            self._handle_conn_error(str(exc))
            sys.exit(1)

        self._build_ui()

        self.battery_val = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(3000)

    # -- config ---------------------------------------------------------------

    @staticmethod
    def _load_cfg():
        defaults = {"dpi": [400, 800, 1600, 3200], "polling": 8}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
                defaults.update(data)
            except Exception:
                pass
        return defaults

    def _save_cfg(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.cfg, f)
        except Exception:
            pass

    # -- connection error -----------------------------------------------------

    def _handle_conn_error(self, msg):
        if "not found" in msg.lower():
            reply = QMessageBox.question(
                self, "Permissions Required",
                "The app needs access to the mouse dongle.\n\n"
                "Install udev rules automatically?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                if install_udev_rule():
                    QMessageBox.information(
                        self, "Done",
                        "Rules installed! Unplug/re-plug the dongle, then restart.",
                    )
                else:
                    QMessageBox.critical(self, "Failed", "Could not install udev rules.")
        else:
            QMessageBox.critical(self, "Error", msg)

    # -- UI -------------------------------------------------------------------

    def _build_ui(self):
        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        tabs.addTab(self._tab_dashboard(), "Dashboard")
        tabs.addTab(self._tab_performance(), "Performance")
        tabs.addTab(self._tab_buttons(), "Buttons")
        tabs.addTab(self._tab_lighting(), "Lighting")

    # ── Dashboard ───────────────────────────────────────────────────────────

    def _tab_dashboard(self):
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        # status card
        card = QGroupBox("Connection")
        cl = QVBoxLayout(card)

        row = QHBoxLayout()
        self._dot = QLabel("\u25cf")
        self._dot.setStyleSheet("color: #444; font-size:20px;")
        row.addWidget(self._dot)

        self._status = QLabel("Checking\u2026")
        self._status.setStyleSheet("font-size:14px; color:#6e6e8e;")
        row.addWidget(self._status)
        row.addStretch()
        cl.addLayout(row)
        root.addWidget(card)

        # battery card
        card2 = QGroupBox("Battery")
        bl = QVBoxLayout(card2)
        bl.setSpacing(10)

        self._batt_pct = QLabel("--%")
        self._batt_pct.setAlignment(Qt.AlignCenter)
        self._batt_pct.setStyleSheet("font-size:38px; font-weight:700; color:#7ec8e3;")
        bl.addWidget(self._batt_pct)

        self._batt_bar = QProgressBar()
        self._batt_bar.setRange(0, 100)
        self._batt_bar.setValue(0)
        self._batt_bar.setFormat("")
        bl.addWidget(self._batt_bar)

        root.addWidget(card2)
        root.addStretch()
        return w

    # ── Performance ─────────────────────────────────────────────────────────

    def _tab_performance(self):
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # DPI
        dpi_box = QGroupBox("DPI Stages (click to activate)")
        dv = QVBoxLayout(dpi_box)
        self._dpi_spins = []
        self._dpi_radios = []
        for i in range(4):
            row = QHBoxLayout()
            rb = QRadioButton(f"Stage {i + 1}")
            rb.clicked.connect(lambda _, s=i: self._select_dpi(s))
            spin = QSpinBox()
            spin.setRange(100, 16000)
            spin.setSingleStep(100)
            spin.setValue(self.cfg["dpi"][i])
            spin.setFixedWidth(100)
            row.addWidget(rb)
            row.addStretch()
            row.addWidget(QLabel("DPI:"))
            row.addWidget(spin)
            dv.addLayout(row)
            self._dpi_spins.append(spin)
            self._dpi_radios.append(rb)
        self._dpi_radios[0].setChecked(True)
        # Auto-apply on radio click or when a spin box loses focus
        for spin in self._dpi_spins:
            spin.editingFinished.connect(self._auto_apply_perf)
        root.addWidget(dpi_box)

        root.addStretch()
        return w

    # ── Buttons ─────────────────────────────────────────────────────────────

    def _tab_buttons(self):
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        box = QGroupBox("Button Mapping")
        bv = QVBoxLayout(box)
        self._btn_combos = {}
        self._btn_hex_inputs = {}

        for label, offset in BUTTON_DEFS:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(130)
            row.addWidget(lbl)

            combo = QComboBox()
            for act_name in BUTTON_ACTIONS:
                combo.addItem(act_name)
            combo.addItem("Custom (0xXX)")
            default = DEFAULT_ACTIONS.get(offset, "Disabled")
            combo.setCurrentIndex(combo.findText(default))
            row.addWidget(combo)
            self._btn_combos[offset] = combo

            hex_input = QLineEdit()
            hex_input.setFixedWidth(60)
            hex_input.setPlaceholderText("hex")
            hex_input.setVisible(False)
            row.addWidget(hex_input)
            self._btn_hex_inputs[offset] = hex_input

            combo.currentTextChanged.connect(
                lambda text, h=hex_input: h.setVisible(text == "Custom (0xXX)"))
            bv.addLayout(row)

        root.addWidget(box)

        hint = QLabel("Custom: type a hex code like 95, 99, 9A, etc.")
        hint.setStyleSheet("color: #6e6e8e; font-size: 12px;")
        root.addWidget(hint)

        btn = QPushButton("Apply Mappings")
        btn.setObjectName("applyBtn")
        btn.clicked.connect(self._apply_btns)
        root.addWidget(btn)
        root.addStretch()
        return w

    # ── Lighting ────────────────────────────────────────────────────────────

    def _tab_lighting(self):
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # Zone 1
        z1_box = QGroupBox("Zone 1 \u00b7 Scroll Wheel")
        z1 = QVBoxLayout(z1_box)
        self._z0_eff = QComboBox()
        self._z0_eff.addItems(EFFECTS)
        self._z0_eff.setCurrentText(self.z0_effect)
        z1.addWidget(self._make_labeled("Effect:", self._z0_eff))

        self._z0_cbtn = QPushButton("  Pick Color  ")
        self._z0_cbtn.setCursor(Qt.PointingHandCursor)
        self._z0_cbtn.clicked.connect(lambda: self._pick_color(0, False))
        self._style_cbtn(self._z0_cbtn, self.z0_color)
        z1.addWidget(self._make_labeled("Primary:", self._z0_cbtn))

        self._z0_cbtn2 = QPushButton("  Pick Color  ")
        self._z0_cbtn2.setCursor(Qt.PointingHandCursor)
        self._z0_cbtn2.clicked.connect(lambda: self._pick_color(0, True))
        self._style_cbtn(self._z0_cbtn2, self.z0_color2)
        z1.addWidget(self._make_labeled("Alternate:", self._z0_cbtn2))
        root.addWidget(z1_box)

        # Zone 2
        z2_box = QGroupBox("Zone 2 \u00b7 Legion Logo")
        z2 = QVBoxLayout(z2_box)
        self._z1_eff = QComboBox()
        self._z1_eff.addItems(EFFECTS)
        self._z1_eff.setCurrentText(self.z1_effect)
        z2.addWidget(self._make_labeled("Effect:", self._z1_eff))

        self._z1_cbtn = QPushButton("  Pick Color  ")
        self._z1_cbtn.setCursor(Qt.PointingHandCursor)
        self._z1_cbtn.clicked.connect(lambda: self._pick_color(1, False))
        self._style_cbtn(self._z1_cbtn, self.z1_color)
        z2.addWidget(self._make_labeled("Primary:", self._z1_cbtn))

        self._z1_cbtn2 = QPushButton("  Pick Color  ")
        self._z1_cbtn2.setCursor(Qt.PointingHandCursor)
        self._z1_cbtn2.clicked.connect(lambda: self._pick_color(1, True))
        self._style_cbtn(self._z1_cbtn2, self.z1_color2)
        z2.addWidget(self._make_labeled("Alternate:", self._z1_cbtn2))
        root.addWidget(z2_box)

        btn = QPushButton("Apply Lighting")
        btn.setObjectName("applyBtn")
        btn.clicked.connect(self._apply_light)
        root.addWidget(btn)
        root.addStretch()
        return w

    # -- UI helpers -----------------------------------------------------------

    @staticmethod
    def _make_labeled(text, widget):
        row = QHBoxLayout()
        lbl = QLabel(text)
        lbl.setFixedWidth(80)
        row.addWidget(lbl)
        row.addWidget(widget)
        wrap = QWidget()
        wrap.setLayout(row)
        return wrap

    @staticmethod
    def _style_cbtn(btn, rgb):
        r, g, b = rgb
        lum = r * 0.299 + g * 0.587 + b * 0.114
        fg = "#12121f" if lum > 140 else "#c8c8dc"
        btn.setFixedHeight(34)
        btn.setStyleSheet(
            f"QPushButton {{ background: rgb({r},{g},{b}); color: {fg};"
            " border: 1px solid #343452; border-radius: 7px;"
            " padding: 6px 16px; }"
            "QPushButton:hover { border-color: #7ec8e3; }"
        )

    def _pick_color(self, zone, is_alt):
        color = QColorDialog.getColor(parent=self)
        if not color.isValid():
            return
        rgb = (color.red(), color.green(), color.blue())
        if zone == 0:
            if is_alt:
                self.z0_color2 = rgb
                self._style_cbtn(self._z0_cbtn2, rgb)
            else:
                self.z0_color = rgb
                self._style_cbtn(self._z0_cbtn, rgb)
        else:
            if is_alt:
                self.z1_color2 = rgb
                self._style_cbtn(self._z1_cbtn2, rgb)
            else:
                self.z1_color = rgb
                self._style_cbtn(self._z1_cbtn, rgb)

    # -- battery polling ------------------------------------------------------

    def _poll(self):
        if not self.mouse.connected():
            self._dot.setStyleSheet("color: #c86060; font-size:20px;")
            self._status.setText("Sleeping \u2014 last known battery shown")
            self._status.setStyleSheet("font-size:14px; color:#6e6e8e;")
            return

        self._dot.setStyleSheet("color: #5aaa6a; font-size:20px;")
        self._status.setText("Connected")
        self._status.setStyleSheet("font-size:14px; color:#5aaa6a;")

        pct = self.mouse.battery_pct()
        if pct is not None and 0 <= pct <= 100:
            self.battery_val = pct

        self._batt_bar.setValue(self.battery_val)
        self._batt_pct.setText(f"{self.battery_val}%")

    # -- apply actions --------------------------------------------------------

    def _select_dpi(self, stage):
        if not self.mouse.connected():
            return
        for i, spin in enumerate(self._dpi_spins):
            self.cfg["dpi"][i] = spin.value()
            self.mouse.set_dpi_value(i, spin.value())
            time.sleep(0.1)
        self.mouse.set_dpi_stage(stage)
        time.sleep(0.1)
        self.mouse.commit()
        self._save_cfg()

    def _auto_apply_perf(self):
        if not self.mouse.connected():
            return
        for i, spin in enumerate(self._dpi_spins):
            self.cfg["dpi"][i] = spin.value()
            self.mouse.set_dpi_value(i, spin.value())
            time.sleep(0.1)
        time.sleep(0.1)
        self.mouse.commit()
        self._save_cfg()

    def _apply_btns(self):
        if not self.mouse.connected():
            QMessageBox.warning(self, "Error", "Mouse is not connected.")
            return

        for offset, combo in self._btn_combos.items():
            name = combo.currentText()
            if name == "Custom (0xXX)":
                hex_text = self._btn_hex_inputs[offset].text().strip().lstrip("0x")
                try:
                    code = int(hex_text, 16)
                    action_bytes = [code, 0x00, 0x00, 0x00, 0x00]
                except ValueError:
                    QMessageBox.warning(self, "Error", f"Invalid hex: {hex_text}")
                    return
            else:
                action_bytes = BUTTON_ACTIONS.get(name, [0x00] * 5)
            self.mouse.set_button(offset, action_bytes)
            time.sleep(0.1)

        time.sleep(0.1)
        self.mouse.commit()
        QMessageBox.information(self, "Applied", "Button mappings saved to mouse.")

    def _apply_light(self):
        if not self.mouse.connected():
            QMessageBox.warning(self, "Error", "Mouse is not connected.")
            return

        self.z0_effect = self._z0_eff.currentText()
        self.z1_effect = self._z1_eff.currentText()

        z0 = LegionM600.zone_bytes(self.z0_effect, self.z0_color, self.z0_color2)
        z1 = LegionM600.zone_bytes(self.z1_effect, self.z1_color, self.z1_color2)
        self.mouse.set_lighting(z0, z1)
        time.sleep(0.15)
        QMessageBox.information(self, "Applied", "Lighting updated.")


# ════════════════════════════════════════════════════════════════════════════════
# Entry point
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(THEME)
    window = M600App()
    window.show()
    sys.exit(app.exec_())