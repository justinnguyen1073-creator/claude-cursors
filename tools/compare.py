#!/usr/bin/env python3
"""Cursor Compare: show two cursors from an installed theme side by side.

Each cursor plays at its real frame timing, drawn on its own canvas so the two line up the
way they do on screen (same canvas, same spot). Pick any theme in ~/.icons, any cursor
name, the size setting, and a zoom. Options: show click points, outline the left cursor
on top of the right one, light or dark background. The hover strip at the bottom switches
your real cursor so you can compare the live ones too.

Usage: python3 tools/compare.py [left_name] [right_name]
"""
import os
import struct
import sys

from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QColor, QImage, QPainter, QPen
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
                             QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget)

ICONS = os.path.expanduser("~/.icons")


def read_xcursor(path, size):
    """Frames [(QImage, hx, hy, delay_ms)] for the nominal size closest to `size`."""
    d = open(path, "rb").read()
    n = struct.unpack("<I", d[12:16])[0]
    by = {}
    for i in range(n):
        typ, nominal, pos = struct.unpack("<III", d[16 + i * 12:28 + i * 12])
        if typ != 0xFFFD0002:
            continue
        _, _, _, _, w, h, hx, hy, delay = struct.unpack("<9I", d[pos:pos + 36])
        img = QImage(d[pos + 36:pos + 36 + w * h * 4], w, h, w * 4,
                     QImage.Format.Format_ARGB32_Premultiplied).copy()
        by.setdefault(nominal, []).append((img, hx, hy, delay))
    best = min(by, key=lambda s: abs(s - size))
    return by[best]


def themes():
    return sorted(t for t in os.listdir(ICONS) if os.path.isdir(os.path.join(ICONS, t, "cursors")))


def cursor_names(theme):
    return sorted(os.listdir(os.path.join(ICONS, theme, "cursors")))


class CursorView(QWidget):
    """One animated cursor, drawn at `zoom` with nearest-neighbor pixels."""

    def __init__(self, title):
        super().__init__()
        self.title = title
        self.frames = []
        self.index = 0
        self.zoom = 6
        self.dark = False
        self.show_hot = True
        self.overlay = None  # (QImage, hx, hy) outline to draw on top
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._next)
        self.setMinimumSize(260, 300)

    def load(self, path, size):
        self.frames = read_xcursor(path, size) if os.path.exists(path) else []
        self.restart()

    def restart(self):
        self.index = 0
        self.timer.stop()
        if self.frames:
            self._schedule()
        self.update()

    def _schedule(self):
        delay = self.frames[self.index][3]
        if len(self.frames) > 1 and delay < 60_000:  # a very long last frame means "hold"
            self.timer.start(max(10, delay))

    def _next(self):
        self.index = (self.index + 1) % len(self.frames)
        self._schedule()
        self.update()

    def current(self):
        return self.frames[self.index] if self.frames else None

    def paintEvent(self, event):
        p = QPainter(self)
        bg = QColor(35, 35, 35) if self.dark else QColor(240, 238, 232)
        fg = QColor(230, 230, 230) if self.dark else QColor(40, 40, 40)
        p.fillRect(self.rect(), bg)
        p.setPen(fg)
        p.drawText(QRect(0, 6, self.width(), 20), Qt.AlignmentFlag.AlignHCenter, self.title)
        cur = self.current()
        if not cur:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "(no such cursor)")
            return
        img, hx, hy, _ = cur
        z = self.zoom
        w, h = img.width() * z, img.height() * z
        x0 = (self.width() - w) // 2
        y0 = 34
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.drawImage(QRect(x0, y0, w, h), img)
        # canvas frame, so you can see where each image sits
        p.setPen(QPen(QColor(128, 128, 128, 90), 1, Qt.PenStyle.DashLine))
        p.drawRect(x0, y0, w - 1, h - 1)
        if self.overlay:
            oimg, ohx, ohy = self.overlay
            # place the other cursor so its click point lands on this one's
            ox, oy = x0 + (hx - ohx) * z, y0 + (hy - ohy) * z
            p.setPen(QPen(QColor(0, 150, 255), 2))
            for yy in range(oimg.height()):
                for xx in range(oimg.width()):
                    if not self._solid(oimg, xx, yy):
                        continue
                    # draw each edge where a solid pixel meets an empty one
                    if not self._solid(oimg, xx + 1, yy):
                        p.drawLine(ox + (xx + 1) * z, oy + yy * z, ox + (xx + 1) * z, oy + (yy + 1) * z)
                    if not self._solid(oimg, xx - 1, yy):
                        p.drawLine(ox + xx * z, oy + yy * z, ox + xx * z, oy + (yy + 1) * z)
                    if not self._solid(oimg, xx, yy + 1):
                        p.drawLine(ox + xx * z, oy + (yy + 1) * z, ox + (xx + 1) * z, oy + (yy + 1) * z)
                    if not self._solid(oimg, xx, yy - 1):
                        p.drawLine(ox + xx * z, oy + yy * z, ox + (xx + 1) * z, oy + yy * z)
        if self.show_hot:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 150, 255))
            p.drawEllipse(x0 + hx * z + z // 2 - 4, y0 + hy * z + z // 2 - 4, 8, 8)
        p.setPen(fg)
        info = f"frame {self.index + 1}/{len(self.frames)}  ·  {img.width()}×{img.height()} px  ·  click {hx},{hy}"
        p.drawText(QRect(0, y0 + h + 8, self.width(), 20), Qt.AlignmentFlag.AlignHCenter, info)

    @staticmethod
    def _solid(img, x, y):
        return 0 <= x < img.width() and 0 <= y < img.height() and QColor.fromRgba(img.pixel(x, y)).alpha() > 250


class HoverZone(QLabel):
    """A box that switches your real cursor when you hover it."""

    def __init__(self, text, shape):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFrameShape(QFrame.Shape.Box)
        self.setMinimumHeight(70)
        self.setCursor(shape)


class Compare(QWidget):
    def __init__(self, left, right):
        super().__init__()
        self.setWindowTitle("Cursor Compare")
        ts = themes()
        self.theme = QComboBox()
        self.theme.addItems(ts)
        self.theme.setCurrentText("claude-cursors" if "claude-cursors" in ts else ts[0])
        self.size = QSpinBox()
        self.size.setRange(12, 72)
        self.size.setSingleStep(6)
        self.size.setValue(24)
        self.zoom = QSlider(Qt.Orientation.Horizontal)
        self.zoom.setRange(1, 14)
        self.zoom.setValue(8)
        self.dark = QCheckBox("Dark background")
        self.hot = QCheckBox("Click points")
        self.hot.setChecked(True)
        self.overlay = QCheckBox("Outline left cursor on right")
        replay = QPushButton("Replay")

        self.left_name, self.right_name = QComboBox(), QComboBox()
        self.left_view, self.right_view = CursorView("left"), CursorView("right")
        self._fill_names(left, right)

        top = QHBoxLayout()
        for w in (QLabel("Theme"), self.theme, QLabel("Size"), self.size, QLabel("Zoom"), self.zoom,
                  self.dark, self.hot, self.overlay, replay):
            top.addWidget(w)
        pickers = QHBoxLayout()
        pickers.addWidget(self.left_name)
        pickers.addWidget(self.right_name)
        views = QHBoxLayout()
        views.addWidget(self.left_view)
        views.addWidget(self.right_view)
        zones = QHBoxLayout()
        for text, shape in (("Hover: link", Qt.CursorShape.PointingHandCursor),
                            ("Hover: help", Qt.CursorShape.WhatsThisCursor),
                            ("Hover: busy", Qt.CursorShape.BusyCursor),
                            ("Hover: text", Qt.CursorShape.IBeamCursor),
                            ("Hover: normal", Qt.CursorShape.ArrowCursor)):
            zones.addWidget(HoverZone(text, shape))
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(pickers)
        layout.addLayout(views, 1)
        layout.addWidget(QLabel("Your real cursor (whatever theme is active in System Settings):"))
        layout.addLayout(zones)

        self.theme.currentTextChanged.connect(lambda _: (self._fill_names(self.left_name.currentText(),
                                                                          self.right_name.currentText()), self.reload()))
        for sig in (self.size.valueChanged, self.left_name.currentTextChanged, self.right_name.currentTextChanged):
            sig.connect(lambda *_: self.reload())
        for sig in (self.zoom.valueChanged, self.dark.toggled, self.hot.toggled, self.overlay.toggled):
            sig.connect(lambda *_: self.restyle())
        replay.clicked.connect(lambda: (self.left_view.restart(), self.right_view.restart()))
        self.reload()
        self.resize(900, 620)

    def _fill_names(self, left, right):
        names = cursor_names(self.theme.currentText())
        for box, want in ((self.left_name, left), (self.right_name, right)):
            box.blockSignals(True)
            box.clear()
            box.addItems(names)
            box.setCurrentText(want if want in names else names[0])
            box.blockSignals(False)

    def reload(self):
        cur = os.path.join(ICONS, self.theme.currentText(), "cursors")
        for box, view in ((self.left_name, self.left_view), (self.right_name, self.right_view)):
            view.title = box.currentText()
            view.load(os.path.join(cur, box.currentText()), self.size.value())
        self.restyle()

    def restyle(self):
        for view in (self.left_view, self.right_view):
            view.zoom = self.zoom.value()
            view.dark = self.dark.isChecked()
            view.show_hot = self.hot.isChecked()
        left = self.left_view.frames[-1] if self.left_view.frames else None  # the left cursor's settled frame
        self.right_view.overlay = (left[0], left[1], left[2]) if (self.overlay.isChecked() and left) else None
        self.left_view.overlay = None
        self.left_view.update()
        self.right_view.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    args = sys.argv[1:]
    w = Compare(args[0] if args else "pointer", args[1] if len(args) > 1 else "help")
    w.show()
    sys.exit(app.exec())
