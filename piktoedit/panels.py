"""Postranni panely: vlastnosti, paleta, objekty, predloha, sablony."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QByteArray, QMimeData, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .shapes import RectShape, ShapeMixin, TextShape
from .style import Style

#: Barvy odpovidajici beznym AAC piktogramum.
PALETTE = [
    "#000000", "#3f3f46", "#7a7f87", "#c9ced6", "#ffffff",
    "#f6c9a0", "#f2d3ae", "#8b5a2b", "#5b3a1a", "#c0392b",
    "#e74c3c", "#e67e22", "#f1c40f", "#ffd94a", "#2ecc71",
    "#27ae60", "#3498db", "#1668c1", "#2c3e50", "#8e44ad",
    "#e84393", "#00b8d4", "#a3d977", "#d9b3ff",
]


class ColorButton(QToolButton):
    """Ctverecek s barvou. Leve tlacitko meni barvu, prave nastavi 'zadna'."""

    changed = Signal(object)

    def __init__(self, color: QColor | None, label: str, parent=None):
        super().__init__(parent)
        self.color = QColor(color) if color else None
        self.label = label
        self.setFixedSize(QSize(34, 26))
        self.setToolTip(f"{label} (prave tlacitko = zadna)")
        self.clicked.connect(self._pick)
        self._refresh()

    def set_color(self, color: QColor | None, notify: bool = False) -> None:
        self.color = QColor(color) if color else None
        self._refresh()
        if notify:
            self.changed.emit(self.color)

    def _pick(self) -> None:
        initial = self.color or QColor("#000000")
        color = QColorDialog.getColor(
            initial, self, self.label, QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self.set_color(color, notify=True)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.set_color(None, notify=True)
            event.accept()
            return
        super().mousePressEvent(event)

    def _refresh(self) -> None:
        if self.color is None:
            self.setStyleSheet(
                "QToolButton { border: 1px solid #888; border-radius: 3px;"
                " background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                " stop:0 #fff, stop:0.45 #fff, stop:0.5 #e74c3c,"
                " stop:0.55 #fff, stop:1 #fff); }")
        else:
            self.setStyleSheet(
                f"QToolButton {{ border: 1px solid #888; border-radius: 3px;"
                f" background: {self.color.name()}; }}")


class PalettePanel(QWidget):
    """Rychla paleta: levy klik vypln, pravy klik obrys."""

    fill_picked = Signal(QColor)
    stroke_picked = Signal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setSpacing(3)
        layout.setContentsMargins(4, 4, 4, 4)
        for index, name in enumerate(PALETTE):
            button = QToolButton(self)
            button.setFixedSize(QSize(22, 22))
            button.setStyleSheet(
                f"QToolButton {{ border: 1px solid #6b7280; background: {name}; }}")
            button.setToolTip(f"{name}  (levy = vypln, pravy = obrys)")
            button.clicked.connect(lambda _=False, value=name: self.fill_picked.emit(QColor(value)))
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda _pos, value=name: self.stroke_picked.emit(QColor(value)))
            layout.addWidget(button, index // 5, index % 5)
        layout.setRowStretch(layout.rowCount(), 1)


class PropertiesPanel(QWidget):
    """Vzhled a presna geometrie vybranych objektu."""

    changed = Signal(str)

    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.view = view
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)

        # -- vzhled -------------------------------------------------------
        appearance = QGroupBox("Vzhled", self)
        form = QFormLayout(appearance)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        colors = QWidget(appearance)
        colors_layout = QHBoxLayout(colors)
        colors_layout.setContentsMargins(0, 0, 0, 0)
        self.fill_button = ColorButton(QColor("#4a90d9"), "Vypln", colors)
        self.stroke_button = ColorButton(QColor("#1f2933"), "Obrys", colors)
        colors_layout.addWidget(QLabel("V:"))
        colors_layout.addWidget(self.fill_button)
        colors_layout.addSpacing(8)
        colors_layout.addWidget(QLabel("O:"))
        colors_layout.addWidget(self.stroke_button)
        colors_layout.addStretch(1)
        form.addRow("Barvy", colors)

        self.width_spin = QDoubleSpinBox(appearance)
        self.width_spin.setRange(0.0, 400.0)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setValue(8.0)
        self.width_spin.setSuffix(" px")
        form.addRow("Tloustka", self.width_spin)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal, appearance)
        self.opacity_slider.setRange(5, 100)
        self.opacity_slider.setValue(100)
        form.addRow("Kryti", self.opacity_slider)

        self.radius_spin = QDoubleSpinBox(appearance)
        self.radius_spin.setRange(0.0, 500.0)
        self.radius_spin.setSingleStep(2.0)
        form.addRow("Zaobleni", self.radius_spin)

        self.cap_combo = QComboBox(appearance)
        self.cap_combo.addItems(["round", "butt", "square"])
        form.addRow("Konce car", self.cap_combo)

        root.addWidget(appearance)

        # -- geometrie ----------------------------------------------------
        geometry = QGroupBox("Rozmery a poloha", self)
        grid = QGridLayout(geometry)
        self.x_spin = self._number(geometry)
        self.y_spin = self._number(geometry)
        self.w_spin = self._number(geometry, minimum=0.1)
        self.h_spin = self._number(geometry, minimum=0.1)
        self.angle_spin = self._number(geometry, minimum=-360.0, maximum=360.0)
        self.angle_spin.setSuffix(" °")
        grid.addWidget(QLabel("X"), 0, 0)
        grid.addWidget(self.x_spin, 0, 1)
        grid.addWidget(QLabel("Y"), 0, 2)
        grid.addWidget(self.y_spin, 0, 3)
        grid.addWidget(QLabel("Š"), 1, 0)
        grid.addWidget(self.w_spin, 1, 1)
        grid.addWidget(QLabel("V"), 1, 2)
        grid.addWidget(self.h_spin, 1, 3)
        grid.addWidget(QLabel("Uhel"), 2, 0)
        grid.addWidget(self.angle_spin, 2, 1)
        self.ratio_check = QCheckBox("Zachovat pomer", geometry)
        grid.addWidget(self.ratio_check, 2, 2, 1, 2)
        root.addWidget(geometry)

        # -- pismo --------------------------------------------------------
        self.text_group = QGroupBox("Pismo", self)
        text_form = QFormLayout(self.text_group)
        self.font_combo = QFontComboBox(self.text_group)
        self.font_combo.setCurrentFont(QFont("Arial"))
        text_form.addRow("Font", self.font_combo)
        self.font_size = QDoubleSpinBox(self.text_group)
        self.font_size.setRange(4.0, 800.0)
        self.font_size.setValue(96.0)
        text_form.addRow("Velikost", self.font_size)
        style_row = QWidget(self.text_group)
        style_layout = QHBoxLayout(style_row)
        style_layout.setContentsMargins(0, 0, 0, 0)
        self.bold_check = QCheckBox("Tucne", style_row)
        self.bold_check.setChecked(True)
        self.italic_check = QCheckBox("Kurziva", style_row)
        style_layout.addWidget(self.bold_check)
        style_layout.addWidget(self.italic_check)
        style_layout.addStretch(1)
        text_form.addRow("Rez", style_row)
        self.upper_button = QPushButton("VELKA PISMENA", self.text_group)
        text_form.addRow("", self.upper_button)
        root.addWidget(self.text_group)

        root.addStretch(1)

        # -- propojeni ----------------------------------------------------
        # Zmena se projevi hned pri psani, do historie se zapise az po
        # dokonceni upravy. Jinak by tazeni posuvnikem nadelalo desitky
        # kroku zpet.
        self.fill_button.changed.connect(
            lambda color: self._apply_style("fill", color, record=True))
        self.stroke_button.changed.connect(
            lambda color: self._apply_style("stroke", color, record=True))
        self.width_spin.valueChanged.connect(
            lambda value: self._apply_style("stroke_width", value))
        self.width_spin.editingFinished.connect(
            lambda: self._record("Tloustka cary"))
        self.opacity_slider.valueChanged.connect(
            lambda value: self._apply_style("opacity", value / 100.0))
        self.opacity_slider.sliderReleased.connect(lambda: self._record("Kryti"))
        self.cap_combo.currentTextChanged.connect(
            lambda value: self._apply_style("linecap", value, record=True))
        self.radius_spin.valueChanged.connect(self._apply_radius)
        self.radius_spin.editingFinished.connect(lambda: self._record("Zaobleni rohu"))

        for spin in (self.x_spin, self.y_spin, self.w_spin, self.h_spin, self.angle_spin):
            spin.valueChanged.connect(lambda _: self._apply_geometry())
            spin.editingFinished.connect(lambda: self._record("Zmena geometrie"))

        self.font_combo.currentFontChanged.connect(lambda _: self._apply_font(record=True))
        self.font_size.valueChanged.connect(lambda _: self._apply_font())
        self.font_size.editingFinished.connect(lambda: self._record("Velikost pisma"))
        self.bold_check.toggled.connect(lambda _: self._apply_font(record=True))
        self.italic_check.toggled.connect(lambda _: self._apply_font(record=True))
        self.upper_button.clicked.connect(self._to_upper)

    def _record(self, label: str) -> None:
        if not self._loading:
            self.changed.emit(label)

    def _number(self, parent, minimum: float = -20000.0, maximum: float = 20000.0):
        spin = QDoubleSpinBox(parent)
        spin.setRange(minimum, maximum)
        spin.setDecimals(1)
        spin.setSingleStep(1.0)
        # Sledovani klavesnice necháváme zapnute, aby se kresba menila uz
        # pri psani, ne az po Enteru.
        spin.setKeyboardTracking(True)
        return spin

    # -- nacteni hodnot ---------------------------------------------------
    def refresh(self) -> None:
        shapes = self.view.canvas_scene.selected_shapes()
        self._loading = True
        try:
            style = shapes[0].style if shapes else self.view.default_style
            self.fill_button.set_color(style.fill)
            self.stroke_button.set_color(style.stroke)
            self.width_spin.setValue(style.stroke_width)
            self.opacity_slider.setValue(int(round(style.opacity * 100)))
            index = self.cap_combo.findText(style.linecap)
            if index >= 0:
                self.cap_combo.setCurrentIndex(index)

            rect_shapes = [s for s in shapes if isinstance(s, RectShape)]
            self.radius_spin.setEnabled(bool(rect_shapes) or not shapes)
            if rect_shapes:
                self.radius_spin.setValue(rect_shapes[0].radius)
            elif not shapes:
                self.radius_spin.setValue(self.view.corner_radius)

            enabled = bool(shapes)
            for spin in (self.x_spin, self.y_spin, self.w_spin, self.h_spin, self.angle_spin):
                spin.setEnabled(enabled)
            if len(shapes) == 1:
                shape = shapes[0]
                bounds = shape.mapToScene(shape.local_rect()).boundingRect()
                self.x_spin.setValue(bounds.x())
                self.y_spin.setValue(bounds.y())
                self.w_spin.setValue(shape.local_rect().width())
                self.h_spin.setValue(shape.local_rect().height())
                self.angle_spin.setValue(shape.rotation())

            texts = [s for s in shapes if isinstance(s, TextShape)]
            self.text_group.setVisible(bool(texts) or not shapes)
            font = texts[0].font() if texts else self.view.text_font
            self.font_combo.setCurrentFont(font)
            self.font_size.setValue(font.pointSizeF())
            self.bold_check.setChecked(font.bold())
            self.italic_check.setChecked(font.italic())
        finally:
            self._loading = False

    # -- zmeny ------------------------------------------------------------
    def _apply_style(self, field: str, value, record: bool = False) -> None:
        if self._loading:
            return
        shapes = self.view.canvas_scene.selected_shapes()
        setattr(self.view.default_style, field, value)
        if not shapes:
            return
        for shape in shapes:
            style = shape.style.copy()
            setattr(style, field, value)
            shape.set_style(style)
        if record:
            self.changed.emit("Zmena vzhledu")

    def _apply_radius(self, value: float) -> None:
        if self._loading:
            return
        self.view.corner_radius = value
        for shape in self.view.canvas_scene.selected_shapes():
            if isinstance(shape, RectShape):
                shape.set_radius(value)

    def _apply_geometry(self) -> None:
        if self._loading:
            return
        shapes = self.view.canvas_scene.selected_shapes()
        if len(shapes) != 1:
            return
        shape = shapes[0]
        rect = QRectF(shape.local_rect())
        width = max(0.1, self.w_spin.value())
        height = max(0.1, self.h_spin.value())
        if self.ratio_check.isChecked() and rect.width() > 0 and rect.height() > 0:
            if abs(width - rect.width()) > 0.05:
                height = width * rect.height() / rect.width()
            elif abs(height - rect.height()) > 0.05:
                width = height * rect.width() / rect.height()
        if abs(width - rect.width()) > 0.05 or abs(height - rect.height()) > 0.05:
            shape.set_local_rect(QRectF(rect.x(), rect.y(), width, height))

        shape.setRotation(self.angle_spin.value())
        shape.sync_origin()
        bounds = shape.mapToScene(shape.local_rect()).boundingRect()
        delta = QPointF(self.x_spin.value() - bounds.x(), self.y_spin.value() - bounds.y())
        shape.setPos(shape.pos() + delta)
        self.view.viewport().update()

    def _apply_font(self, record: bool = False) -> None:
        if self._loading:
            return
        font = QFont(self.font_combo.currentFont())
        font.setPointSizeF(self.font_size.value())
        font.setBold(self.bold_check.isChecked())
        font.setItalic(self.italic_check.isChecked())
        self.view.text_font = QFont(font)
        shapes = [s for s in self.view.canvas_scene.selected_shapes()
                  if isinstance(s, TextShape)]
        if not shapes:
            return
        for shape in shapes:
            shape.setFont(QFont(font))
            shape.sync_origin()
        if record:
            self.changed.emit("Zmena pisma")

    def _to_upper(self) -> None:
        shapes = [s for s in self.view.canvas_scene.selected_shapes()
                  if isinstance(s, TextShape)]
        if not shapes:
            return
        for shape in shapes:
            shape.set_text(shape.text().upper())
        self.changed.emit("Velka pismena")


class LayersPanel(QWidget):
    """Seznam objektu s poradim vykresleni. Nahore je to, co je nahore."""

    changed = Signal(str)

    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.view = view
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        layout.addWidget(self.list)

        buttons = QWidget(self)
        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 0, 0, 0)
        self.up_button = QPushButton("↑", buttons)
        self.down_button = QPushButton("↓", buttons)
        self.top_button = QPushButton("⇈", buttons)
        self.bottom_button = QPushButton("⇊", buttons)
        for button, tip in ((self.up_button, "O uroven vys"),
                            (self.down_button, "O uroven niz"),
                            (self.top_button, "Uplne nahoru"),
                            (self.bottom_button, "Uplne dolu")):
            button.setToolTip(tip)
            button.setFixedWidth(34)
            row.addWidget(button)
        row.addStretch(1)
        layout.addWidget(buttons)

        self.list.itemSelectionChanged.connect(self._sync_selection_to_scene)
        self.list.itemChanged.connect(self._rename)
        self.up_button.clicked.connect(lambda: self._reorder(1))
        self.down_button.clicked.connect(lambda: self._reorder(-1))
        self.top_button.clicked.connect(lambda: self._reorder(999999))
        self.bottom_button.clicked.connect(lambda: self._reorder(-999999))

    def refresh(self) -> None:
        self._loading = True
        try:
            self.list.clear()
            for shape in reversed(self.view.canvas_scene.shapes()):
                item = QListWidgetItem(shape.name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                item.setData(Qt.ItemDataRole.UserRole, shape)
                self.list.addItem(item)
                item.setSelected(shape.isSelected())
        finally:
            self._loading = False

    def _items(self) -> list[ShapeMixin]:
        return [self.list.item(row).data(Qt.ItemDataRole.UserRole)
                for row in range(self.list.count())]

    def _sync_selection_to_scene(self) -> None:
        if self._loading:
            return
        selected = {item.data(Qt.ItemDataRole.UserRole)
                    for item in self.list.selectedItems()}
        scene = self.view.canvas_scene
        for shape in scene.shapes():
            shape.setSelected(shape in selected)

    def _rename(self, item: QListWidgetItem) -> None:
        if self._loading:
            return
        shape = item.data(Qt.ItemDataRole.UserRole)
        if shape is not None and item.text().strip():
            shape.name = item.text().strip()
            self.changed.emit("Prejmenovani")

    def _reorder(self, direction: int) -> None:
        shapes = self.view.canvas_scene.selected_shapes()
        if not shapes:
            return
        ordered = self.view.canvas_scene.shapes()
        for shape in (shapes if direction < 0 else reversed(shapes)):
            index = ordered.index(shape)
            target = max(0, min(len(ordered) - 1, index + direction))
            ordered.pop(index)
            ordered.insert(target, shape)
        for z, shape in enumerate(ordered):
            shape.setZValue(float(z))
        self.changed.emit("Zmena poradi")


class ReferencePanel(QWidget):
    """Predloha k obkresleni plus rychly vyber obrazku ze slozky."""

    reference_requested = Signal(str)
    opacity_changed = Signal(float)
    visibility_changed = Signal(bool)
    remove_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        buttons = QHBoxLayout()
        self.open_button = QPushButton("Nacist obrazek…", self)
        self.folder_button = QPushButton("Slozka…", self)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.folder_button)
        layout.addLayout(buttons)

        self.visible_check = QCheckBox("Zobrazit predlohu", self)
        self.visible_check.setChecked(True)
        layout.addWidget(self.visible_check)

        row = QHBoxLayout()
        row.addWidget(QLabel("Kryti", self))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.opacity_slider.setRange(5, 100)
        self.opacity_slider.setValue(45)
        row.addWidget(self.opacity_slider)
        layout.addLayout(row)

        self.thumbs = QListWidget(self)
        self.thumbs.setViewMode(QListWidget.ViewMode.IconMode)
        self.thumbs.setIconSize(QSize(88, 88))
        self.thumbs.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.thumbs.setMovement(QListWidget.Movement.Static)
        self.thumbs.setSpacing(4)
        layout.addWidget(self.thumbs, 1)

        self.remove_button = QPushButton("Odebrat predlohu", self)
        layout.addWidget(self.remove_button)

        self.open_button.clicked.connect(self._open_file)
        self.folder_button.clicked.connect(self._open_folder)
        self.thumbs.itemDoubleClicked.connect(
            lambda item: self.reference_requested.emit(item.data(Qt.ItemDataRole.UserRole)))
        self.thumbs.itemClicked.connect(
            lambda item: self.reference_requested.emit(item.data(Qt.ItemDataRole.UserRole)))
        self.opacity_slider.valueChanged.connect(
            lambda value: self.opacity_changed.emit(value / 100.0))
        self.visible_check.toggled.connect(self.visibility_changed.emit)
        self.remove_button.clicked.connect(self.remove_requested.emit)

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Predloha k obkresleni", "",
            "Obrazky (*.png *.jpg *.jpeg *.bmp *.webp);;Vsechny soubory (*)")
        if path:
            self.reference_requested.emit(path)

    def _open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Slozka s obrazky")
        if folder:
            self.load_folder(folder)

    def load_folder(self, folder: str | Path) -> None:
        self.thumbs.clear()
        base = Path(folder)
        if not base.is_dir():
            return
        patterns = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp")
        files: list[Path] = []
        for pattern in patterns:
            files.extend(sorted(base.glob(pattern)))
        for file in files[:400]:
            pixmap = QPixmap(str(file))
            if pixmap.isNull():
                continue
            icon = QIcon(pixmap.scaled(QSize(88, 88), Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation))
            item = QListWidgetItem(icon, file.stem)
            item.setData(Qt.ItemDataRole.UserRole, str(file))
            item.setToolTip(str(file))
            self.thumbs.addItem(item)


class CaptionPanel(QWidget):
    """Popisek pod piktogramem: jeden text drzeny na stredu u spodni hrany."""

    apply_requested = Signal()
    remove_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Text pod obrazkem:", self))
        self.text_edit = QLineEdit(self)
        self.text_edit.setPlaceholderText("napr. MAMA")
        layout.addWidget(self.text_edit)

        form = QFormLayout()
        self.upper_check = QCheckBox("Prevest na velka pismena", self)
        self.upper_check.setChecked(True)
        form.addRow("", self.upper_check)

        self.font_combo = QFontComboBox(self)
        self.font_combo.setCurrentFont(QFont("Arial"))
        form.addRow("Font", self.font_combo)

        self.size_spin = QDoubleSpinBox(self)
        self.size_spin.setRange(8.0, 600.0)
        self.size_spin.setValue(96.0)
        self.size_spin.setSuffix(" px")
        form.addRow("Velikost", self.size_spin)

        self.bold_check = QCheckBox("Tucne", self)
        self.bold_check.setChecked(True)
        form.addRow("Rez", self.bold_check)

        self.color_button = ColorButton(QColor("#000000"), "Barva popisku", self)
        form.addRow("Barva", self.color_button)

        self.margin_spin = QDoubleSpinBox(self)
        self.margin_spin.setRange(0.0, 2000.0)
        self.margin_spin.setValue(60.0)
        self.margin_spin.setSuffix(" px")
        form.addRow("Odsazeni zdola", self.margin_spin)
        layout.addLayout(form)

        self.apply_button = QPushButton("Pouzit popisek", self)
        self.remove_button = QPushButton("Odebrat popisek", self)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.remove_button)
        layout.addWidget(QLabel(
            "Popisek zustava vodorovne na stredu. Dal se s nim da pracovat\n"
            "jako s beznym textem v seznamu objektu.", self))
        layout.addStretch(1)

        self.text_edit.editingFinished.connect(self._emit_apply)
        self.text_edit.returnPressed.connect(self._emit_apply)
        self.upper_check.toggled.connect(self._emit_apply)
        self.font_combo.currentFontChanged.connect(lambda _: self._emit_apply())
        self.size_spin.valueChanged.connect(lambda _: self._emit_apply())
        self.bold_check.toggled.connect(self._emit_apply)
        self.color_button.changed.connect(lambda _: self._emit_apply())
        self.margin_spin.valueChanged.connect(lambda _: self._emit_apply())
        self.apply_button.clicked.connect(self._emit_apply)
        self.remove_button.clicked.connect(self.remove_requested.emit)

    def _emit_apply(self) -> None:
        if self._loading:
            return
        if not self.text_edit.text().strip():
            return
        self.apply_requested.emit()

    def values(self) -> dict:
        text = self.text_edit.text().strip()
        return {
            "text": text.upper() if self.upper_check.isChecked() else text,
            "font": self.font_combo.currentFont().family(),
            "size": self.size_spin.value(),
            "bold": self.bold_check.isChecked(),
            "color": self.color_button.color or QColor("#000000"),
            "margin": self.margin_spin.value(),
        }

    def load_from(self, shape: TextShape | None) -> None:
        self._loading = True
        try:
            if shape is None:
                if not self.text_edit.hasFocus():
                    self.text_edit.clear()
                return
            self.text_edit.setText(shape.text())
            font = shape.font()
            self.font_combo.setCurrentFont(font)
            self.size_spin.setValue(font.pointSizeF())
            self.bold_check.setChecked(font.bold())
            self.color_button.set_color(shape.style.fill or QColor("#000000"))
        finally:
            self._loading = False


#: Hezci nazvy slozek se sablonami.
CATEGORY_TITLES = {
    "oblicej": "Oblicej",
    "postavy": "Postavy",
    "zvirata": "Zvirata",
    "doprava": "Dopravni prostredky",
    "prostredi": "Prostredi",
    "karty": "Karty a platna",
    "tvary": "Zakladni tvary",
    "": "Ostatni",
}

CATEGORY_ORDER = ["oblicej", "postavy", "zvirata", "doprava", "prostredi",
                  "karty", "tvary", ""]


#: Format pro tazeni sablony nebo dilu na platno.
PART_MIME = "application/x-piktoedit-part"

#: Role, ve kterych si polozky seznamu nesou, co maji vlozit.
ROLE_FILE = Qt.ItemDataRole.UserRole
ROLE_INDEX = Qt.ItemDataRole.UserRole + 1


class DragListWidget(QListWidget):
    """Seznam, ze ktereho jde polozku pretahnout na platno."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def mimeData(self, items):  # type: ignore[override]
        data = QMimeData()
        for item in items:
            payload = {
                "file": item.data(ROLE_FILE),
                "index": item.data(ROLE_INDEX),
            }
            data.setData(PART_MIME, QByteArray(json.dumps(payload).encode("utf-8")))
            break
        return data


class TemplatePanel(QWidget):
    """Sablony s nahledy.

    Prvni uroven jsou soubory podle kategorii (podslozek), druha jednotlive
    dily uvnitr sablony. Vlozit jde oboji, bud tlacitkem, nebo pretazenim
    primo na misto na platne.
    """

    insert_requested = Signal(str)
    part_requested = Signal(str, int)
    new_from_template = Signal(str)

    def __init__(self, folder: Path, parent=None):
        super().__init__(parent)
        self.folder = Path(folder)
        self._files: dict[str, list[Path]] = {}
        self._opened: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.category_combo = QComboBox(self)
        layout.addWidget(self.category_combo)

        self.back_button = QPushButton("← Zpet na sablony", self)
        self.back_button.setVisible(False)
        layout.addWidget(self.back_button)

        self.title_label = QLabel(self)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.list = DragListWidget(self)
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(104, 104))
        self.list.setGridSize(QSize(126, 140))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setWordWrap(True)
        self.list.setSpacing(4)
        layout.addWidget(self.list, 1)

        self.insert_button = QPushButton("Vlozit do kresby", self)
        self.new_button = QPushButton("Nova kresba ze sablony", self)
        self.reload_button = QPushButton("Obnovit seznam", self)
        layout.addWidget(self.insert_button)
        layout.addWidget(self.new_button)
        layout.addWidget(self.reload_button)

        self.list.itemDoubleClicked.connect(self._activate)
        self.category_combo.currentIndexChanged.connect(lambda _: self._show_category())
        self.back_button.clicked.connect(self._show_category)
        self.insert_button.clicked.connect(self._insert_current)
        self.new_button.clicked.connect(self._new_from_current)
        self.reload_button.clicked.connect(self.reload)
        self.reload()

    # -- ovladani ---------------------------------------------------------
    def _activate(self, item: QListWidgetItem) -> None:
        index = item.data(ROLE_INDEX)
        path = item.data(ROLE_FILE)
        if index is not None and index >= 0:
            self.part_requested.emit(path, index)
        else:
            self.open_template(Path(path))

    def _insert_current(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        index = item.data(ROLE_INDEX)
        if index is not None and index >= 0:
            self.part_requested.emit(item.data(ROLE_FILE), index)
        else:
            self.insert_requested.emit(item.data(ROLE_FILE))

    def _new_from_current(self) -> None:
        item = self.list.currentItem()
        if item is not None:
            self.new_from_template.emit(item.data(ROLE_FILE))
        elif self._opened is not None:
            self.new_from_template.emit(str(self._opened))

    def open_template(self, path: Path) -> None:
        """Rozbali sablonu na jednotlive dily."""
        from .preview import part_preview, template_parts

        parts = template_parts(path)
        if not parts:
            self.insert_requested.emit(str(path))
            return

        self._opened = Path(path)
        self.list.clear()
        self.back_button.setVisible(True)
        self.title_label.setText(
            f"Dily ze sablony {path.stem.replace('_', ' ')} "
            f"({len(parts)}) - dvojklik vlozi, nebo pretahni na platno")

        for index, name in parts:
            item = QListWidgetItem(name)
            item.setData(ROLE_FILE, str(path))
            item.setData(ROLE_INDEX, index)
            item.setToolTip(f"{name} - {path.name}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            pixmap = part_preview(path, index)
            if pixmap is not None:
                item.setIcon(QIcon(pixmap))
            self.list.addItem(item)

    def reload(self) -> None:
        self._files = {}
        if self.folder.is_dir():
            for file in sorted(self.folder.rglob("*.svg")):
                relative = file.parent.relative_to(self.folder)
                category = "" if str(relative) == "." else relative.parts[0]
                self._files.setdefault(category, []).append(file)

        keys = [key for key in CATEGORY_ORDER if key in self._files]
        keys += sorted(key for key in self._files if key not in CATEGORY_ORDER)

        current = self.category_combo.currentData()
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        total = sum(len(items) for items in self._files.values())
        self.category_combo.addItem(f"Vsechny sablony ({total})", None)
        for key in keys:
            title = CATEGORY_TITLES.get(key, key.replace("_", " ").capitalize())
            self.category_combo.addItem(f"{title} ({len(self._files[key])})", key)
        index = self.category_combo.findData(current)
        self.category_combo.setCurrentIndex(max(0, index))
        self.category_combo.blockSignals(False)
        self._show_category()

    def _show_category(self) -> None:
        from .preview import template_preview

        selected = self.category_combo.currentData()
        self._opened = None
        self.back_button.setVisible(False)
        self.title_label.setText(
            "Dvojklik rozbali sablonu na dily. Sablonu i dil lze pretahnout "
            "primo na platno.")
        self.list.clear()

        if selected is None:
            files = [file for key in self._files for file in self._files[key]]
            files.sort(key=lambda item: (str(item.parent), item.name))
        else:
            files = self._files.get(selected, [])

        for file in files:
            item = QListWidgetItem(file.stem.replace("_", " "))
            item.setData(ROLE_FILE, str(file))
            item.setData(ROLE_INDEX, -1)
            item.setToolTip(str(file))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            pixmap = template_preview(file)
            if pixmap is not None:
                item.setIcon(QIcon(pixmap))
            self.list.addItem(item)
