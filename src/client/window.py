import sys
import psutil
import os
from PyQt5 import QtWidgets, QtCore, QtGui


try:
    from .keyoverlay import KeyOverlay
except Exception:
    from keyoverlay import KeyOverlay


try:
    from .rpc import DiscordRPC
except Exception:
    try:
        from rpc import DiscordRPC
    except Exception:
        DiscordRPC = None



_TARGET_PATTERNS = {
    "Corporate Clash": [
        "corporateclash.exe",
        "corporateclash_client",
        "corporate-clash-client",
    ],
    "Toontown Rewritten": [
        "toontownrewritten.exe",
        "toontown rewritten.exe",
        "toontown.exe",
        "toontownrewritten",
        "toontown rewritten",
        "ttr",
        "ttr_client",
    ],
}


def any_game_running() -> bool:
    """Return True if any of the known target processes appear to be running."""
    try:
        for proc in psutil.process_iter(["name", "cmdline", "exe"]):
            info = proc.info
            hay = " ".join(filter(None, [
                (info.get("name") or ""),
                " ".join(info.get("cmdline") or []),
                (info.get("exe") or "")
            ])).lower()
            for pats in _TARGET_PATTERNS.values():
                for p in pats:
                    if p in hay:
                        return True
    except Exception:
        
        return False
    return False


class _TitleBar(QtWidgets.QWidget):
    """Custom titlebar that supports dragging and window controls."""

    HEIGHT = 48

    def __init__(self, parent: QtWidgets.QWidget, title: str):
        super().__init__(parent)
        self._window = parent
        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(12, 6, 8, 6)
        h.setSpacing(8)

        
        left = QtWidgets.QHBoxLayout()
        left.setSpacing(8)
        
        self.title_label = QtWidgets.QLabel(title, self)
        self.title_label.setStyleSheet("color:#ffecff; font-weight:bold; font-size:16px;")
        
        self.title_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        left.addWidget(self.title_label)
        left.addStretch(1)
        h.addLayout(left)

        
        self._make_button_styles("#ffffff", "rgba(255,255,255,0.04)")

        self.btn_min = QtWidgets.QToolButton(self)
        self.btn_min.setText("—")
        self.btn_min.setToolTip("Minimize")
        self.btn_min.setStyleSheet(self._btn_style)
        h.addWidget(self.btn_min)

        self.btn_max = QtWidgets.QToolButton(self)
        self.btn_max.setText("▢")
        self.btn_max.setToolTip("Maximize")
        self.btn_max.setStyleSheet(self._btn_style)
        h.addWidget(self.btn_max)

        self.btn_close = QtWidgets.QToolButton(self)
        self.btn_close.setText("✕")
        self.btn_close.setToolTip("Close")
        
        self.btn_close.setStyleSheet(self._btn_style + "QToolButton:hover { background: #d94b5b; color: #fff; }")
        h.addWidget(self.btn_close)

        
        self.btn_min.clicked.connect(self._on_min)
        self.btn_max.clicked.connect(self._on_max)
        self.btn_close.clicked.connect(self._on_close)

        
        self._drag_pos = None

        
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:#2f0426;")

    def _make_button_styles(self, color: str, hover_bg: str):
        self._btn_style = f"""
            QToolButton {{
                background: transparent;
                color: {color};
                border: none;
                padding: 6px;
                font-size: 14px;
            }}
            QToolButton:hover {{ background: {hover_bg}; border-radius:4px; }}
        """

    def set_theme(self, bg_color: str = "#2f0426", text_color: str = "#ffecff", icon_bg: str = "#3b0b3f", btn_color: str = "#ffffff", btn_hover_bg: str = "rgba(255,255,255,0.04)", close_hover: str = "#d94b5b"):
        """Apply a small theme to the titlebar (background, title color, icon bg, button colors)."""
        try:
            self.setStyleSheet(f"background:{bg_color};")
            self.title_label.setStyleSheet(f"color:{text_color}; font-weight:bold; font-size:16px;")
            
            if getattr(self, "icon", None):
                self.icon.setStyleSheet(f"background:{icon_bg}; color:{text_color}; border-radius:6px; font-weight:bold;")
            
            self._make_button_styles(btn_color, btn_hover_bg)
            close_style = self._btn_style + f"QToolButton#btn_close:hover {{ background: {close_hover}; color: #fff; }}"
            
            self.btn_close.setObjectName("btn_close")
            self.btn_min.setStyleSheet(self._btn_style)
            self.btn_max.setStyleSheet(self._btn_style)
            
            
            self.btn_close.setStyleSheet(self._btn_style + f"QToolButton:hover {{ background: {close_hover}; color: #fff; }}")
        except Exception:
            pass

    def mousePressEvent(self, ev):
        
        if ev.button() == QtCore.Qt.LeftButton:
            
            try:
                handle = self._window.windowHandle()
                if handle is not None:
                    
                    handle.startSystemMove()
                    ev.accept()
                    return
            except Exception:
                
                pass

            
            self._drag_pos = ev.globalPos()
            self._start_geom = self._window.geometry()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if self._drag_pos:
            delta = ev.globalPos() - self._drag_pos
            geom = self._start_geom.translated(delta)
            self._window.move(geom.topLeft())
            ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag_pos = None
        ev.accept()

    def mouseDoubleClickEvent(self, ev):
        
        self._on_max()

    def _on_min(self):
        self._window.showMinimized()

    def _on_max(self):
        if self._window.isMaximized():
            self._window.showNormal()
            self.btn_max.setText("▢")
        else:
            self._window.showMaximized()
            self.btn_max.setText("❐")

    def _on_close(self):
        self._window.close()


class ResizeHandle(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget, direction: str, thickness: int = 6):
        super().__init__(parent)
        self._parent_win = parent
        self._dir = direction  
        self._thickness = thickness
        self.setCursor({
            'left': QtCore.Qt.SizeHorCursor,
            'right': QtCore.Qt.SizeHorCursor,
            'top': QtCore.Qt.SizeVerCursor,
            'bottom': QtCore.Qt.SizeVerCursor,
            'top_left': QtCore.Qt.SizeFDiagCursor,
            'bottom_right': QtCore.Qt.SizeFDiagCursor,
            'top_right': QtCore.Qt.SizeBDiagCursor,
            'bottom_left': QtCore.Qt.SizeBDiagCursor,
        }.get(direction, QtCore.Qt.ArrowCursor))
        
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self._pressed = False
        self._start_pos = None
        self._start_geom = None

    def mousePressEvent(self, ev):
        if ev.button() == QtCore.Qt.LeftButton:
            self._pressed = True
            self._start_pos = ev.globalPos()
            try:
                self._start_geom = self._parent_win.geometry()
            except Exception:
                self._start_geom = QtCore.QRect(self._parent_win.x(), self._parent_win.y(), self._parent_win.width(), self._parent_win.height())
            ev.accept()

    def mouseMoveEvent(self, ev):
        if not self._pressed:
            return
        delta = ev.globalPos() - self._start_pos
        geom = QtCore.QRect(self._start_geom)
        min_w = self._parent_win.minimumWidth()
        min_h = self._parent_win.minimumHeight()

        if 'left' in self._dir:
            new_x = geom.x() + delta.x()
            new_w = geom.width() - delta.x()
            if new_w < min_w:
                
                new_x = geom.right() - (min_w - 1)
                new_w = min_w
            geom.setX(new_x)
            geom.setWidth(new_w)
        if 'right' in self._dir:
            new_w = geom.width() + delta.x()
            if new_w < min_w:
                new_w = min_w
            geom.setWidth(new_w)
        if 'top' in self._dir:
            new_y = geom.y() + delta.y()
            new_h = geom.height() - delta.y()
            if new_h < min_h:
                new_y = geom.bottom() - (min_h - 1)
                new_h = min_h
            geom.setY(new_y)
            geom.setHeight(new_h)
        if 'bottom' in self._dir:
            new_h = geom.height() + delta.y()
            if new_h < min_h:
                new_h = min_h
            geom.setHeight(new_h)

        
        self._parent_win.setGeometry(geom)
        ev.accept()

    def mouseReleaseEvent(self, ev):
        self._pressed = False
        ev.accept()


class TweaksWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(
            QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)
        self.setMinimumSize(720, 420)

        
        self.setStyleSheet(
            """
            QWidget#body {
                background: #2b0528;
                color: #f0d7ff;
                font-family: "Segoe UI", Arial;
                border: 1px solid rgba(255,255,255,0.03);
                border-radius: 6px;
            }
            QWidget#sidebar {
                background: #21021a;
                color: #cfa9d6;
            }
            QLabel#title {
                font-weight: bold;
                font-size: 28px;
                color: #ffd9ff;
            }
            QFrame#card {
                background: rgba(0,0,0,0.12);
                border-radius: 8px;
                padding: 12px;
            }
            QPushButton.menuBtn {
                text-align: left;
                padding: 12px;
                border: none;
                background: transparent;
                color: #b88bb7;
            }
            QPushButton.menuBtn:hover {
                background: rgba(255,255,255,0.02);
                color: #ffd9ff;
            }
            QPushButton.menuBtn:checked {
                background: rgba(0,0,0,0.14);
                color: #ffd9ff;
                font-weight: bold;
            }
            QCheckBox {
                spacing: 8px;
            }
            """
        )

        
        top_v = QtWidgets.QVBoxLayout(self)
        top_v.setContentsMargins(0, 0, 0, 0)
        top_v.setSpacing(0)

        
        self.titlebar = _TitleBar(self, "Speedster Tweaks")
        top_v.addWidget(self.titlebar)

        
        central_h = QtWidgets.QHBoxLayout()
        central_h.setContentsMargins(0, 0, 0, 0)
        central_h.setSpacing(0)
        top_v.addLayout(central_h)

        
        sidebar = QtWidgets.QFrame(self)
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sb_layout = QtWidgets.QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(10, 10, 10, 10)
        sb_layout.setSpacing(8)

        
        self._sidebar = sidebar

        
        
        def _make_logo_widget(parent):
            lbl = QtWidgets.QLabel(parent)
            lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            return lbl

        self.logo_widget = _make_logo_widget(sidebar)

        
        assets_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "assets"))
        self._tab_assets = {
            "TWEAKS": os.path.join(assets_dir, "stpurple.png"),
            "REPLAYS": os.path.join(assets_dir, "logo_replays.png"),
            "RANKINGS": os.path.join(assets_dir, "logo_rankings.png"),
            "OPTIONS": os.path.join(assets_dir, "logo_options.png"),
        }

        sb_layout.addWidget(self.logo_widget)
        sb_layout.addSpacing(6)

        
        self.menu_group = QtWidgets.QButtonGroup(self)
        self.menu_group.setExclusive(True)
        menu_items = ["TWEAKS", "REPLAYS", "RANKINGS", "OPTIONS"]
        for i, name in enumerate(menu_items):
            btn = QtWidgets.QPushButton(name, sidebar)
            btn.setObjectName(f"menu_{name.lower()}")
            btn.setProperty("class", "menuBtn")
            btn.setCheckable(True)
            btn.setStyleSheet("")  
            sb_layout.addWidget(btn)
            self.menu_group.addButton(btn, i)
        sb_layout.addStretch(1)

        
        exit_btn = QtWidgets.QPushButton("EXIT", sidebar)
        exit_btn.setProperty("class", "menuBtn")
        exit_btn.clicked.connect(self.close)
        sb_layout.addWidget(exit_btn)

        central_h.addWidget(sidebar)

        
        body = QtWidgets.QFrame(self)
        body.setObjectName("body")
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(12)
        central_h.addWidget(body, 1)

        
        self._body = body

        
        title = QtWidgets.QLabel("TWEAKS", body)
        title.setObjectName("title")
        body_layout.addWidget(title)

        
        search = QtWidgets.QLineEdit(body)
        search.setPlaceholderText("Click or just start typing to search.")
        search.setStyleSheet("QLineEdit{ background: rgba(255,255,255,0.03); padding:8px; border-radius:6px; }")
        body_layout.addWidget(search)

        
        card = QtWidgets.QFrame(body)
        card.setObjectName("card")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(6, 6, 6, 6)
        card_layout.setSpacing(10)

        
        row = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel("Key Overlay")
        self.overlay_switch = QtWidgets.QCheckBox()
        self.overlay_switch.setToolTip("Show an on-screen keyboard overlay")
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(self.overlay_switch)
        card_layout.addLayout(row)

        
        rpc_row = QtWidgets.QHBoxLayout()
        rpc_label = QtWidgets.QLabel("Discord RPC")
        self.rpc_switch = QtWidgets.QCheckBox()
        self.rpc_switch.setToolTip("Show Rich Presence in Discord when a supported game is running")
        rpc_row.addWidget(rpc_label)
        rpc_row.addStretch(1)
        rpc_row.addWidget(self.rpc_switch)
        card_layout.addLayout(rpc_row)

        body_layout.addWidget(card)
        body_layout.addStretch(1)

        
        self.status_lbl = QtWidgets.QLabel("", body)
        body_layout.addWidget(self.status_lbl)

        
        self._overlay = None

        
        if DiscordRPC is not None:
            try:
                
                self._rpc_manager = DiscordRPC(client_id="YOUR_DISCORD_APP_CLIENT_ID")
            except Exception:
                self._rpc_manager = None
        else:
            self._rpc_manager = None

        
        self.overlay_switch.stateChanged.connect(self._on_overlay_toggled)
        self.rpc_switch.stateChanged.connect(self._on_rpc_toggled)
        self.menu_group.buttonClicked[int].connect(self._on_menu_selected)

        
        self._update_availability()
        
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(2500)
        self._poll_timer.timeout.connect(self._update_availability)
        self._poll_timer.start()

        
        first_btn = self.menu_group.button(0)
        if first_btn:
            first_btn.setChecked(True)
            
            self._apply_theme(first_btn.text())

        
        self._create_resize_handles()

    
    def _create_resize_handles(self):
        th = 6
        dirs = [
            'top_left', 'top', 'top_right',
            'left', 'right',
            'bottom_left', 'bottom', 'bottom_right'
        ]
        self._resize_handles = {}
        for d in dirs:
            h = ResizeHandle(self, d, thickness=th)
            h.show()
            h.raise_()
            self._resize_handles[d] = h
        
        self.update()

    
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        th = 6
        w = self.width()
        h = self.height()

        
        if hasattr(self, "_resize_handles"):
            self._resize_handles['top_left'].setGeometry(0, 0, th, th)
            self._resize_handles['top'].setGeometry(th, 0, max(0, w - 2*th), th)
            self._resize_handles['top_right'].setGeometry(max(0, w - th), 0, th, th)

            self._resize_handles['left'].setGeometry(0, th, th, max(0, h - 2*th))
            self._resize_handles['right'].setGeometry(max(0, w - th), th, th, max(0, h - 2*th))

            self._resize_handles['bottom_left'].setGeometry(0, max(0, h - th), th, th)
            self._resize_handles['bottom'].setGeometry(th, max(0, h - th), max(0, w - 2*th), th)
            self._resize_handles['bottom_right'].setGeometry(max(0, w - th), max(0, h - th), th, th)

            
            for h in self._resize_handles.values():
                h.raise_()

    def _on_menu_selected(self, idx: int):
        
        btn = self.menu_group.button(idx)
        if btn:
            self.status_lbl.setText(f"Selected: {btn.text()}")
            
            self._apply_theme(btn.text())

    def _apply_theme(self, tab_name: str):
        """Update sidebar logo and full colorscheme (body, sidebar, titlebar, fonts) based on tab."""
        
        themes = {
            "TWEAKS": ("#2b0528", "#21021a", "#2f0426", "#ffd9ff", "#3b0b3f", "#b88bb7"),
            "REPLAYS": ("#052b1a", "#08321d", "#062a1a", "#bfffe8", "#0a4b34", "#48c0a0"),
            "RANKINGS": ("#1a1430", "#2a1840", "#25102f", "#f2e7ff", "#3b254d", "#c38eff"),
            "OPTIONS": ("#102733", "#081b22", "#072026", "#dff6ff", "#0d3a3e", "#5bb0c2"),
        }
        body_bg, sidebar_bg, titlebar_bg, title_text, icon_bg, accent = themes.get(tab_name, ("#2b0528", "#21021a", "#2f0426", "#ffd9ff", "#3b0b3f", "#b88bb7"))

        
        body_style = f"""
            background: {body_bg};
            color: {title_text};
            border-radius:6px;
        """
        
        sidebar_style = f"""
            background: {sidebar_bg};
            color: {title_text};
        """
        
        sidebar_style += f"""
            QPushButton.menuBtn {{ color: {accent}; }}
            QPushButton.menuBtn:hover {{ color: {title_text}; background: rgba(255,255,255,0.02); }}
            QPushButton.menuBtn:checked {{ color: {title_text}; background: rgba(0,0,0,0.14); font-weight: bold; }}
        """

        try:
            self._body.setStyleSheet(body_style)
            self._sidebar.setStyleSheet(sidebar_style)
        except Exception:
            pass

        
        asset = self._tab_assets.get(tab_name)
        if asset and os.path.exists(asset):
            pix = QtGui.QPixmap(asset)
            if not pix.isNull():
                target_w = 160
                target_h = 56
                pix = pix.scaled(target_w, target_h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self.logo_widget.setPixmap(pix)
                self.logo_widget.setFixedSize(pix.size())
                self.logo_widget.setStyleSheet("")  
        else:
            
            fallback_text = tab_name + ("\nTWEAKS" if tab_name == "TWEAKS" else "")
            self.logo_widget.setPixmap(QtGui.QPixmap())  
            self.logo_widget.setFixedHeight(48)
            self.logo_widget.setText(fallback_text)
            self.logo_widget.setStyleSheet(f"color:{title_text}; font-weight:900; font-size:16px;")

        
        
        btn_color = "#ffffff" if title_text.lower() in ("#ffd9ff", "#f2e7ff", "#dff6ff", "#bfffe8") else "#ffffff"
        btn_hover_bg = "rgba(255,255,255,0.04)"
        close_hover = "#d94b5b"  
        try:
            self.titlebar.set_theme(bg_color=titlebar_bg, text_color=title_text, icon_bg=icon_bg, btn_color=btn_color, btn_hover_bg=btn_hover_bg, close_hover=close_hover)
        except Exception:
            pass

    def _update_availability(self):
        running = any_game_running()
        if running:
            self.status_lbl.setText("Game detected: tweaks available.")
            self.overlay_switch.setEnabled(True)
            
            if self._rpc_manager is not None:
                self.rpc_switch.setEnabled(True)
                if not self.rpc_switch.isChecked():
                    
                    self.rpc_switch.setChecked(True)
                    
            else:
                self.rpc_switch.setEnabled(False)
        else:
            self.status_lbl.setText("Game not detected: tweaks are disabled.")
            self.overlay_switch.setEnabled(False)
            
            if self._rpc_manager is not None:
                if self.rpc_switch.isChecked():
                    self.rpc_switch.setChecked(False)
                self.rpc_switch.setEnabled(False)

    def _ensure_overlay_visible(self, visible: bool):
        if visible:
            if self._overlay is None:
                try:
                    self._overlay = KeyOverlay(parent=None)
                    
                    screen = QtWidgets.QApplication.instance().primaryScreen().availableGeometry()
                    x = screen.x() + (screen.width() - self._overlay.width()) // 2
                    y = screen.y() + 40
                    self._overlay.move(x, y)
                except Exception:
                    self._overlay = None
            if self._overlay:
                self._overlay.show()
                
                self._overlay.raise_()
        else:
            if self._overlay:
                try:
                    self._overlay.close()
                except Exception:
                    pass
                self._overlay = None

    def _on_overlay_toggled(self, state: int):
        enabled = bool(state)
        self._ensure_overlay_visible(enabled)

    def _on_rpc_toggled(self, state: int):
        enabled = bool(state)
        if not self._rpc_manager:
            return
        if enabled:
            
            game_name = None
            try:
                for proc in psutil.process_iter(["name", "cmdline", "exe"]):
                    info = proc.info
                    hay = " ".join(filter(None, [
                        (info.get("name") or ""),
                        " ".join(info.get("cmdline") or []),
                        (info.get("exe") or "")
                    ])).lower()
                    for name, pats in _TARGET_PATTERNS.items():
                        for p in pats:
                            if p in hay:
                                game_name = name
                                break
                        if game_name:
                            break
                    if game_name:
                        break
            except Exception:
                game_name = None

            if game_name is None:
                
                try:
                    self._rpc_manager.stop()
                except Exception:
                    pass
                return

            try:
                self._rpc_manager.start_for_game(game_name)
            except Exception:
                pass
        else:
            try:
                self._rpc_manager.stop()
            except Exception:
                pass

    def closeEvent(self, ev):
        
        try:
            if self._overlay:
                self._overlay.close()
        except Exception:
            pass
        try:
            if self._rpc_manager:
                self._rpc_manager.stop()
        except Exception:
            pass
        super().closeEvent(ev)


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = TweaksWindow()
    
    screen = app.primaryScreen().availableGeometry()
    x = screen.x() + 60
    y = screen.y() + 40
    w.move(x, y)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()