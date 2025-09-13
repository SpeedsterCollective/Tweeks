import sys
import threading
from functools import partial

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


class KeyOverlay(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Window config: frameless, always on top, translucent
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowTitle("Key Overlay")
        self.setFixedSize(420, 140)

        # Central layout: arrows on top, space bar below
        vmain = QtWidgets.QVBoxLayout()
        vmain.setContentsMargins(12, 12, 12, 12)
        vmain.setSpacing(8)
        self.setLayout(vmain)

        # Top: arrow keys row
        arrows_row = QtWidgets.QHBoxLayout()
        arrows_row.setSpacing(8)
        vmain.addLayout(arrows_row)

        # Bottom: space bar centered
        space_row = QtWidgets.QHBoxLayout()
        space_row.setContentsMargins(0, 6, 0, 0)
        vmain.addLayout(space_row)

        # Create key widgets
        self.key_widgets = {}
        # store dict entries: lbl -> {"anim": QAbstractAnimation, "glow": QWidget, "shadow": QGraphicsEffect}
        self._animations = {}

        # Arrow sizes
        arrow_size = QtCore.QSize(64, 64)
        space_size = QtCore.QSize(320, 60)

        # Arrow keys order: left, up, down, right
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

        # Space bar centered below
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

        # Make window draggable (optional)
        self._drag_pos = None

        # Start keyboard listener in background thread
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.daemon = True
        self._listener.start()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

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
        # update style
        is_space = (key_name == "space")
        if active:
            lbl.setStyleSheet(self._active_style(rounded=12 if is_space else 8, space=is_space))
            # animate press
            self._animate_press(lbl)
        else:
            # immediately remove any transient visual effects when released
            lbl.setStyleSheet(self._inactive_style(rounded=12 if is_space else 8, space=is_space))
            self._stop_and_cleanup(lbl)

    def _set_key_state(self, key_name, active: bool):
        # Invoked from listener thread; forward to GUI thread
        QtCore.QMetaObject.invokeMethod(
            self,
            "_handle_key_ui",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(str, key_name),
            QtCore.Q_ARG(int, int(active)),
        )

    def _matches_space(self, key):
        # pynput sometimes gives Key.space or KeyCode(char=' ')
        if key == keyboard.Key.space:
            return True
        if hasattr(key, "char") and key.char == " ":
            return True
        return False

    def _on_press(self, key):
        for name, info in KEYS.items():
            # special-case space which may arrive as KeyCode(' ')
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
        # stop animation if running
        try:
            if anim and isinstance(anim, QtCore.QAbstractAnimation) and anim.state() == QtCore.QAbstractAnimation.Running:
                anim.stop()
        except Exception:
            pass
        # delete transient glow
        try:
            if glow is not None:
                glow.deleteLater()
        except Exception:
            pass
        # remove graphics effect (shadow)
        try:
            lbl.setGraphicsEffect(None)
        except Exception:
            pass

    def _animate_press(self, lbl: QtWidgets.QLabel):
        # ensure previous effects are removed immediately
        self._stop_and_cleanup(lbl)

        # geometry relative to parent
        start_rect = lbl.geometry()
        w = start_rect.width()
        h = start_rect.height()
        dx = max(4, int(w * 0.12))
        dy = max(2, int(h * 0.08))
        expanded = QtCore.QRect(start_rect.x() - dx, start_rect.y() - dy, w + dx * 2, h + dy * 2)

        # create transient glow overlay (we animate the glow instead of the label geometry)
        radius = 12 if lbl is self.key_widgets.get("space") else 8
        glow = QtWidgets.QLabel(lbl.parent())
        glow.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        glow.setGeometry(start_rect)
        glow.setStyleSheet(f"background: rgba(0,170,255,0.22); border-radius: {radius}px;")
        glow.show()

        # animate glow geometry (pop out and back)
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

        # fade out the glow
        glow_anim = QtCore.QPropertyAnimation(glow, b"windowOpacity")
        glow_anim.setDuration(260)
        glow_anim.setStartValue(0.9)
        glow_anim.setKeyValueAt(0.35, 0.65)
        glow_anim.setEndValue(0.0)
        glow_anim.setEasingCurve(QEasingCurve.OutQuad)

        # add a subtle drop-shadow to the label and animate its blur for "pop" feel
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

        # run geom_seq + glow fade + shadow anim in parallel
        group = QtCore.QParallelAnimationGroup(self)
        group.addAnimation(geom_seq)
        group.addAnimation(glow_anim)
        group.addAnimation(shadow_seq)

        # store references so we can stop/cleanup immediately if needed
        self._animations[lbl] = {"anim": group, "glow": glow, "shadow": shadow}

        # cleanup when done (ensures mapping entry removed and transient widget removed)
        def on_finished():
            # pop entry if still present and ensure removal
            try:
                # use helper so it behaves the same as immediate cleanup
                self._stop_and_cleanup(lbl)
            except Exception:
                pass

        group.finished.connect(on_finished)

        group.start()

def main():
    app = QtWidgets.QApplication(sys.argv)
    overlay = KeyOverlay()
    # Position overlay at top center of primary screen
    screen = app.primaryScreen().availableGeometry()
    x = screen.x() + (screen.width() - overlay.width()) // 2
    y = screen.y() + 40
    overlay.move(x, y)
    overlay.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()