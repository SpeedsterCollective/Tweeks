import sys
import threading
from functools import partial
import subprocess
import shutil
import psutil

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QEasingCurve
from pynput import keyboard


KEYS = {
    "left": {"label": "←", "key": keyboard.Key.left},
    "right": {"label": "→", "key": keyboard.Key.right},
    "up": {"label": "↑", "key": keyboard.Key.up},
    "down": {"label": "↓", "key": keyboard.Key.down},
    "space": {"label": "Space", "key": keyboard.Key.space},
}


_GAME_PATTERNS = [
    
    "toontownrewritten.exe",
    "toontown rewritten.exe",
    "toontown.exe",
    "toontownrewritten",
    "toontown rewritten",
    "ttr",
    "ttr_client",
    
    "corporateclash.exe",
    "corporateclash_client",
    "corporate-clash-client",
]


class KeyOverlay(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        
        try:
            self.setWindowFlag(QtCore.Qt.WindowDoesNotAcceptFocus, True)
        except Exception:
            pass
        
        
        if sys.platform.startswith("linux"):
            try:
                self.setWindowFlag(QtCore.Qt.X11BypassWindowManagerHint, True)
            except Exception:
                pass
        
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        
        self._settings = QtCore.QSettings("SpeedsterTweaks", "KeyOverlay")
        pos_val = self._settings.value("pos")
        try:
            if pos_val and isinstance(pos_val, (list, tuple)) and len(pos_val) >= 2:
                self.move(int(pos_val[0]), int(pos_val[1]))
        except Exception:
            
            pass

        
        self._last_target_geom = None

        
        vmain = QtWidgets.QVBoxLayout()
        vmain.setContentsMargins(12, 12, 12, 12)
        vmain.setSpacing(8)
        self.setLayout(vmain)

        
        arrows_row = QtWidgets.QHBoxLayout()
        arrows_row.setSpacing(8)
        vmain.addLayout(arrows_row)

        
        space_row = QtWidgets.QHBoxLayout()
        space_row.setContentsMargins(0, 6, 0, 0)
        vmain.addLayout(space_row)

        
        self.key_widgets = {}
        
        self._animations = {}

        
        arrow_size = QtCore.QSize(64, 64)
        space_size = QtCore.QSize(320, 60)

        
        arrow_order = ["left", "up", "down", "right"]
        for key_name in arrow_order:
            info = KEYS[key_name]
            lbl = QtWidgets.QLabel(info["label"], self)
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            lbl.setFixedSize(arrow_size)
            lbl.setStyleSheet(self._inactive_style(rounded=8))
            lbl.setFont(QtGui.QFont("Segoe UI", 14, QtGui.QFont.Bold))
            arrows_row.addWidget(lbl)
            self.key_widgets[key_name] = lbl

        
        spacer_left = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        spacer_right = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        space_row.addItem(spacer_left)

        space_lbl = QtWidgets.QLabel(KEYS["space"]["label"], self)
        space_lbl.setAlignment(QtCore.Qt.AlignCenter)
        space_lbl.setFixedSize(space_size)
        space_lbl.setStyleSheet(self._inactive_style(rounded=12, space=True))
        space_lbl.setFont(QtGui.QFont("Segoe UI", 13, QtGui.QFont.Bold))
        space_row.addWidget(space_lbl)
        space_row.addItem(spacer_right)
        self.key_widgets["space"] = space_lbl

        
        self._drag_pos = None

        
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.daemon = True
        self._listener.start()

        
        self._follow_timer = QtCore.QTimer(self)
        self._follow_timer.setInterval(500)
        self._follow_timer.timeout.connect(self._follow_target)
        self._follow_timer.start()

    def _find_game_window(self):
        """
        Try to find a window that belongs to a supported game (Toontown / Corporate Clash).
        Returns dict {'winid': int, 'geom': QRect, 'title': str} or None.

        Linux: uses wmctrl if available.
        Windows: uses pywin32 (win32gui/win32process) if available.
        """
        
        if sys.platform.startswith("win"):
            try:
                import win32gui, win32process  
                results = []

                def _cb(hwnd, extra):
                    try:
                        if not win32gui.IsWindowVisible(hwnd):
                            return True
                        title = (win32gui.GetWindowText(hwnd) or "").lower()
                        tid, pid = win32process.GetWindowThreadProcessId(hwnd)
                        try:
                            proc = psutil.Process(pid)
                            name = (proc.name() or "").lower()
                            cmdline = " ".join(proc.cmdline() or []).lower()
                        except Exception:
                            name = ""
                            cmdline = ""
                        hay = " ".join([name, cmdline, title])
                        for pat in _GAME_PATTERNS:
                            if pat in hay:
                                try:
                                    l, t, r, b = win32gui.GetWindowRect(hwnd)
                                    geom = QtCore.QRect(int(l), int(t), int(r - l), int(b - t))
                                    results.append({"winid": int(hwnd), "geom": geom, "title": win32gui.GetWindowText(hwnd)})
                                    return True
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    return True

                win32gui.EnumWindows(_cb, None)
                if results:
                    return results[0]
            except Exception:
                
                pass

        
        if sys.platform.startswith("linux"):
            wmctrl_path = shutil.which("wmctrl")
            if wmctrl_path:
                try:
                    out = subprocess.check_output([wmctrl_path, "-lpG"], stderr=subprocess.DEVNULL).decode(errors="ignore")
                    for line in out.splitlines():
                        parts = line.split(None, 8)
                        if len(parts) < 8:
                            continue
                        win_hex = parts[0]
                        try:
                            pid = int(parts[2])
                        except Exception:
                            continue
                        try:
                            x = int(parts[3]); y = int(parts[4]); w = int(parts[5]); h = int(parts[6])
                        except Exception:
                            continue
                        title = parts[8] if len(parts) >= 9 else ""
                        
                        try:
                            proc = psutil.Process(pid)
                            name = (proc.name() or "").lower()
                            cmdline = " ".join(proc.cmdline() or []).lower()
                        except Exception:
                            name = ""
                            cmdline = ""
                        hay = " ".join([name, cmdline, title.lower()])
                        for pat in _GAME_PATTERNS:
                            if pat in hay:
                                try:
                                    winid = int(win_hex, 16)
                                except Exception:
                                    try:
                                        winid = int(win_hex, 0)
                                    except Exception:
                                        winid = None
                                geom = QtCore.QRect(x, y, w, h)
                                return {"winid": winid, "geom": geom, "title": title}
                except Exception:
                    pass
        
        return None

    def _ensure_raised(self):
        """
        Try multiple ways to keep the overlay above the target window.
        Uses Qt raise_(); on Linux tries xdotool/wmctrl; on Windows uses SetWindowPos via pywin32.
        """
        try:
            self.raise_()
        except Exception:
            pass

        
        if sys.platform.startswith("win"):
            try:
                import win32gui, win32con  
                hwnd = int(self.winId())
                flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
                
                try:
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, flags)
                except Exception:
                    pass
            except Exception:
                pass

        
        if sys.platform.startswith("linux"):
            winid = int(self.winId())
            xdotool_path = shutil.which("xdotool")
            if xdotool_path:
                try:
                    subprocess.Popen([xdotool_path, "windowraise", str(winid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
                except Exception:
                    pass
            wmctrl_path = shutil.which("wmctrl")
            if wmctrl_path:
                try:
                    subprocess.Popen([wmctrl_path, "-i", "-r", str(winid), "-b", "add,above"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
                except Exception:
                    pass

    def _follow_target(self):
        try:
            found = self._find_game_window()
        except Exception:
            found = None

        if not found:
            
            
            if not self.isVisible():
                try:
                    self.show()
                    self.raise_()
                except Exception:
                    pass
            return

        geom = found["geom"]
        self._last_target_geom = geom

        
        if not self.isVisible():
            try:
                
                self.show()
                self.raise_()
            except Exception:
                pass

        
        target_x = geom.x() + max(0, (geom.width() - self.width()) // 2)
        target_y = geom.y() + 40  
        
        tx = max(geom.x(), min(target_x, geom.right() - self.width()))
        ty = max(geom.y(), min(target_y, geom.bottom() - self.height()))
        try:
            self.move(int(tx), int(ty))
        except Exception:
            pass

        
        try:
            self._ensure_raised()
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & QtCore.Qt.LeftButton:
            
            pos = event.globalPos() - self._drag_pos
            self.move(pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()
        
        try:
            
            if self._last_target_geom:
                g = self._last_target_geom
                nx = max(g.x(), min(self.x(), g.right() - self.width()))
                ny = max(g.y(), min(self.y(), g.bottom() - self.height()))
                self.move(nx, ny)
            self._settings.setValue("pos", [self.x(), self.y()])
        except Exception:
            pass

    def _active_style(self, rounded=8, space=False):
        if space:
            return f"""
            QLabel {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(0,170,255,0.95), stop:1 rgba(0,120,200,0.95));
                color: white;
                border-radius: {rounded}px;
                border: 2px solid rgba(255,255,255,0.12);
                padding-left: 8px;
                padding-right: 8px;
            }}
            """
        return f"""
        QLabel {{
            background: rgba(0, 150, 255, 0.95);
            color: white;
            border-radius: {rounded}px;
            border: 2px solid rgba(255,255,255,0.08);
        }}
        """

    def _inactive_style(self, rounded=8, space=False):
        if space:
            return f"""
            QLabel {{
                background: rgba(30, 30, 30, 0.7);
                color: rgba(230,230,230,0.95);
                border-radius: {rounded}px;
                border: 1px solid rgba(255,255,255,0.04);
                padding-left: 8px;
                padding-right: 8px;
            }}
            """
        return f"""
        QLabel {{
            background: rgba(20, 20, 20, 0.6);
            color: rgba(230,230,230,0.9);
            border-radius: {rounded}px;
            border: 1px solid rgba(255,255,255,0.04);
        }}
        """

    @QtCore.pyqtSlot(str, int)
    def _handle_key_ui(self, key_name: str, active_int: int):
        active = bool(active_int)
        lbl = self.key_widgets.get(key_name)
        if not lbl:
            return
        
        is_space = (key_name == "space")
        if active:
            lbl.setStyleSheet(self._active_style(rounded=12 if is_space else 8, space=is_space))
            
            self._animate_press(lbl)
        else:
            
            lbl.setStyleSheet(self._inactive_style(rounded=12 if is_space else 8, space=is_space))
            self._stop_and_cleanup(lbl)

    def _set_key_state(self, key_name, active: bool):
        
        QtCore.QMetaObject.invokeMethod(
            self,
            "_handle_key_ui",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(str, key_name),
            QtCore.Q_ARG(int, int(active)),
        )

    def _matches_space(self, key):
        
        if key == keyboard.Key.space:
            return True
        if hasattr(key, "char") and key.char == " ":
            return True
        return False

    def _on_press(self, key):
        for name, info in KEYS.items():
            
            if name == "space":
                if self._matches_space(key):
                    self._set_key_state(name, True)
            else:
                if key == info["key"]:
                    self._set_key_state(name, True)

    def _on_release(self, key):
        for name, info in KEYS.items():
            if name == "space":
                if self._matches_space(key):
                    self._set_key_state(name, False)
            else:
                if key == info["key"]:
                    self._set_key_state(name, False)

    def _stop_and_cleanup(self, lbl: QtWidgets.QLabel):
        """
        Stop any running animation for lbl and remove transient widgets/effects.
        Safe to call from GUI thread.
        """
        entry = self._animations.pop(lbl, None)
        if not entry:
            return
        anim = entry.get("anim")
        glow = entry.get("glow")
        
        try:
            if anim and isinstance(anim, QtCore.QAbstractAnimation) and anim.state() == QtCore.QAbstractAnimation.Running:
                anim.stop()
        except Exception:
            pass
        
        try:
            if glow is not None:
                glow.deleteLater()
        except Exception:
            pass
        
        try:
            lbl.setGraphicsEffect(None)
        except Exception:
            pass

    def _animate_press(self, lbl: QtWidgets.QLabel):
        
        self._stop_and_cleanup(lbl)

        
        start_rect = lbl.geometry()
        w = start_rect.width()
        h = start_rect.height()
        dx = max(4, int(w * 0.12))
        dy = max(2, int(h * 0.08))
        expanded = QtCore.QRect(start_rect.x() - dx, start_rect.y() - dy, w + dx * 2, h + dy * 2)

        
        radius = 12 if lbl is self.key_widgets.get("space") else 8
        glow = QtWidgets.QLabel(lbl.parent())
        glow.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        glow.setGeometry(start_rect)
        glow.setStyleSheet(f"background: rgba(0,170,255,0.22); border-radius: {radius}px;")
        glow.show()

        
        geom_up = QtCore.QPropertyAnimation(glow, b"geometry")
        geom_up.setDuration(110)
        geom_up.setStartValue(start_rect)
        geom_up.setEndValue(expanded)
        geom_up.setEasingCurve(QEasingCurve.OutCubic)

        geom_down = QtCore.QPropertyAnimation(glow, b"geometry")
        geom_down.setDuration(160)
        geom_down.setStartValue(expanded)
        geom_down.setEndValue(start_rect)
        geom_down.setEasingCurve(QEasingCurve.OutElastic)

        geom_seq = QtCore.QSequentialAnimationGroup(self)
        geom_seq.addAnimation(geom_up)
        geom_seq.addAnimation(geom_down)

        
        glow_anim = QtCore.QPropertyAnimation(glow, b"windowOpacity")
        glow_anim.setDuration(260)
        glow_anim.setStartValue(0.9)
        glow_anim.setKeyValueAt(0.35, 0.65)
        glow_anim.setEndValue(0.0)
        glow_anim.setEasingCurve(QEasingCurve.OutQuad)

        
        shadow = QtWidgets.QGraphicsDropShadowEffect(lbl)
        shadow.setBlurRadius(0)
        shadow.setColor(QtGui.QColor(0, 170, 255, 200))
        shadow.setOffset(0, 0)
        lbl.setGraphicsEffect(shadow)

        shadow_anim_up = QtCore.QPropertyAnimation(shadow, b"blurRadius")
        shadow_anim_up.setDuration(110)
        shadow_anim_up.setStartValue(0)
        shadow_anim_up.setEndValue(18)
        shadow_anim_up.setEasingCurve(QEasingCurve.OutCubic)

        shadow_anim_down = QtCore.QPropertyAnimation(shadow, b"blurRadius")
        shadow_anim_down.setDuration(200)
        shadow_anim_down.setStartValue(18)
        shadow_anim_down.setEndValue(0)
        shadow_anim_down.setEasingCurve(QEasingCurve.OutQuad)

        shadow_seq = QtCore.QSequentialAnimationGroup(self)
        shadow_seq.addAnimation(shadow_anim_up)
        shadow_seq.addAnimation(shadow_anim_down)

        
        group = QtCore.QParallelAnimationGroup(self)
        group.addAnimation(geom_seq)
        group.addAnimation(glow_anim)
        group.addAnimation(shadow_seq)

        
        self._animations[lbl] = {"anim": group, "glow": glow, "shadow": shadow}

        
        def on_finished():
            
            try:
                
                self._stop_and_cleanup(lbl)
            except Exception:
                pass

        group.finished.connect(on_finished)

        group.start()

    def closeEvent(self, event):
        
        try:
            self._settings.setValue("pos", [self.x(), self.y()])
        except Exception:
            pass
        super().closeEvent(event)

def main():
    app = QtWidgets.QApplication(sys.argv)
    overlay = KeyOverlay()
    
    screen = app.primaryScreen().availableGeometry()
    x = screen.x() + (screen.width() - overlay.width()) // 2
    y = screen.y() + 40
    overlay.move(x, y)
    overlay.show()
    
    overlay.raise_()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()