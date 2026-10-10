"""Hlavni okno editoru piktogramu."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QKeySequence,
    QPainter,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from . import svgio
from .canvas import CanvasScene, CanvasView
from .commands import CommandError, run_line, template_name
from .journal import Journal, color, number, point, quoted, shape_ids, style_args
from .nodes import join_subpaths, path_to_subpaths, subpaths_to_path
from .panels import (
    CaptionPanel,
    ColorButton,
    HistoryPanel,
    LayersPanel,
    PalettePanel,
    PropertiesPanel,
    ReferencePanel,
    TemplatePanel,
)
from .shapes import (
    LineShape,
    PathShape,
    ReferenceImage,
    ShapeMixin,
    TextShape,
    to_path_shape,
)
from .style import Style
from .svgio import Document
from .tools import TOOL_CLASSES, NodeTool, SelectTool
from .undo import SnapshotManager

from .paths import DRAWING_DIR, PROJECT_DIR, REFERENCE_DIR, TEMPLATE_DIR

TOOL_BUTTONS = [
    ("vyber", "Sipka", "V", "Vyber, posun, zmena velikosti (V)"),
    ("uzly", "Uzly", "N", "Editace krivky po uzlech; S hladky, C rohovy uzel (N)"),
    ("cara", "Cara", "L", "Rovna cara, Shift drzi smer po 45° (L)"),
    ("lomena", "Lomena", "P", "Lomena cara po bodech, Enter ukonci (P)"),
    ("mnohouhelnik", "Mnohouhelnik", "G", "Uzavreny obrazec po bodech (G)"),
    ("krivka", "Krivka", "K", "Pero: klik = roh, tazeni = hladky uzel (K)"),
    ("spline", "Hladka", "H", "Hladka krivka podle bodu (H)"),
    ("obdelnik", "Obdelnik", "R", "Obdelnik, Shift drzi ctverec (R)"),
    ("elipsa", "Elipsa", "E", "Elipsa, Shift drzi kruh (E)"),
    ("tuzka", "Tuzka", "B", "Kresleni od ruky (B)"),
    ("vypln", "Kyblik", "F", "Klik prebarvi vypln, Shift obrys, Alt nabere barvu (F)"),
    ("nuz", "Nuz", "Z", "Rez krivky v krizeni; Shift jen rozdeli, tazeni reze carou (Z)"),
    ("guma", "Guma", "X", "Guma; Shift maze cele objekty (X)"),
    ("text", "Text", "T", "Textovy popisek (T)"),
]


class DocumentDialog(QDialog):
    """Rozmery kresby, pozadi a krok mrizky."""

    def __init__(self, document: Document, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nastaveni kresby")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.width_spin = QDoubleSpinBox(self)
        self.width_spin.setRange(16.0, 8000.0)
        self.width_spin.setValue(document.width)
        self.height_spin = QDoubleSpinBox(self)
        self.height_spin.setRange(16.0, 8000.0)
        self.height_spin.setValue(document.height)
        self.grid_spin = QDoubleSpinBox(self)
        self.grid_spin.setRange(1.0, 400.0)
        self.grid_spin.setValue(document.grid_size)
        self.background_button = ColorButton(document.background, "Pozadi", self)

        form.addRow("Sirka", self.width_spin)
        form.addRow("Vyska", self.height_spin)
        form.addRow("Mrizka", self.grid_spin)
        form.addRow("Pozadi", self.background_button)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_to(self, document: Document) -> None:
        document.width = self.width_spin.value()
        document.height = self.height_spin.value()
        document.grid_size = self.grid_spin.value()
        document.background = self.background_button.color


class MainWindow(QMainWindow):
    def __init__(self, path: str | None = None):
        super().__init__()
        self.setWindowTitle("PiktoEdit")
        self.resize(1500, 950)

        self.document = Document(width=1024.0, height=1024.0, grid_size=16.0)
        self.scene = CanvasScene(self.document, self)
        self.view = CanvasView(self.scene, self)
        self.view.default_style = Style(fill=QColor("#ffffff"), stroke=QColor("#000000"),
                                        stroke_width=8.0)
        self.setCentralWidget(self.view)

        self.path: Path | None = None
        self.reference: ReferenceImage | None = None
        self.journal = Journal()
        self.undo = SnapshotManager(self.capture_state, self.restore_state, self)
        self.view.snapshot = self.snapshot

        self._build_actions()
        self._build_toolbars()
        self._build_docks()
        self._build_statusbar()

        self.scene.selectionChanged.connect(self.refresh_panels)
        self.view.zoom_changed.connect(self._show_zoom)
        self.view.mouse_moved.connect(self._show_position)
        self.view.tool_done.connect(self._after_tool)
        self.view.convert_request.connect(self._convert_and_edit)
        self.view.style_picked.connect(self.properties.refresh)
        self.view.message.connect(lambda text: self.statusBar().showMessage(text, 7000))
        self.undo.stack.cleanChanged.connect(self._on_clean_changed)

        self.select_tool("vyber")
        self.undo.reset()
        self._update_title()
        # Prizpusobit oknu ma smysl az kdyz okno zna svou velikost, jinak by
        # se kresba smrskla na tecku uprostred plochy.
        self._first_show = True

        if path:
            self.open_path(Path(path))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            QTimer.singleShot(0, self.view.zoom_fit)

    # ------------------------------------------------------------------
    # Sestaveni rozhrani
    # ------------------------------------------------------------------
    def _action(self, text: str, slot, shortcut: str | None = None,
                checkable: bool = False, tip: str = "") -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setCheckable(checkable)
        if tip:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if checkable:
            action.toggled.connect(slot)
        else:
            action.triggered.connect(slot)
        self.addAction(action)
        return action

    def _build_actions(self) -> None:
        self.action_new = self._action("&Nova kresba", self.new_document, "Ctrl+N")
        self.action_open = self._action("&Otevrit…", self.open_dialog, "Ctrl+O")
        self.action_save = self._action("&Ulozit", self.save, "Ctrl+S")
        self.action_save_as = self._action("Ulozit &jako…", self.save_as, "Ctrl+Shift+S")
        self.action_export_png = self._action("Export do PNG…", self.export_png)
        self.action_quit = self._action("&Konec", self.close, "Ctrl+Q")

        self.action_undo = self.undo.stack.createUndoAction(self, "Zpet")
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.action_redo = self.undo.stack.createRedoAction(self, "Znovu")
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)

        self.action_copy = self._action("Kopirovat", self.copy_selection, "Ctrl+C")
        self.action_paste = self._action("Vlozit", self.paste, "Ctrl+V")
        self.action_duplicate = self._action("Duplikovat", self.duplicate, "Ctrl+D")
        self.action_delete = self._action("Smazat", self.delete_selection, "Delete")
        self.action_select_all = self._action("Vybrat vse", self.select_all, "Ctrl+A")

        self.action_front = self._action("Uplne dopredu", lambda: self.reorder(999999), "Ctrl+Shift+Up")
        self.action_back = self._action("Uplne dozadu", lambda: self.reorder(-999999), "Ctrl+Shift+Down")
        self.action_unite = self._action("Sjednotit", lambda: self.boolean_op("unite"),
                                         "Ctrl+Shift+U")
        self.action_subtract = self._action("Odecist (orezat)",
                                            lambda: self.boolean_op("subtract"), "Ctrl+Shift+O")
        self.action_intersect = self._action("Prunik", lambda: self.boolean_op("intersect"),
                                             "Ctrl+Shift+I")
        self.action_exclude = self._action("Vyloucit", lambda: self.boolean_op("exclude"),
                                           "Ctrl+Shift+X")
        self.action_join = self._action("Napojit krivky", self.join_selected, "Ctrl+J")
        self.action_close_path = self._action("Uzavrit a vyplnit", self.close_selected,
                                              "Ctrl+Shift+J")
        self.action_to_path = self._action("Prevest na krivku", self.convert_to_path,
                                           "Ctrl+Shift+K")
        self.action_center_h = self._action("Na stred vodorovne", lambda: self.center_on_page(True))
        self.action_center_v = self._action("Na stred svisle", lambda: self.center_on_page(False))
        self.action_caption = self._action("Popisek pod obrazkem", self.focus_caption, "Ctrl+L")

        self.action_zoom_in = self._action("Priblizit", lambda: self.view.zoom_by(1.25), "Ctrl++")
        self.action_zoom_out = self._action("Oddalit", lambda: self.view.zoom_by(0.8), "Ctrl+-")
        self.action_zoom_reset = self._action("Skutecna velikost", self.view.zoom_reset, "Ctrl+0")
        self.action_zoom_fit = self._action("Prizpusobit oknu", self.view.zoom_fit, "Ctrl+9")

        self.action_grid = self._action("Mrizka", self.toggle_grid, "Ctrl+G", checkable=True,
                                        tip="Zobrazit mrizku")
        self.action_grid.setChecked(True)
        self.action_snap_grid = self._action("Prichytit k mrizce", self.toggle_snap_grid,
                                             "F9", checkable=True)
        self.action_snap_grid.setChecked(True)
        self.action_snap_objects = self._action("Prichytit k objektum", self.toggle_snap_objects,
                                                "F3", checkable=True)
        self.action_snap_objects.setChecked(True)
        self.action_document = self._action("Nastaveni kresby…", self.edit_document)

        self.tool_group = QActionGroup(self)
        self.tool_actions: dict[str, QAction] = {}
        for key, label, shortcut, tip in TOOL_BUTTONS:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setShortcut(QKeySequence(shortcut))
            action.setToolTip(tip)
            action.setStatusTip(tip)
            action.triggered.connect(lambda _checked=False, name=key: self.select_tool(name))
            self.tool_group.addAction(action)
            self.tool_actions[key] = action
            self.addAction(action)

    def _build_toolbars(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("&Soubor")
        for action in (self.action_new, self.action_open, self.action_save,
                       self.action_save_as):
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction(self.action_export_png)
        file_menu.addSeparator()
        file_menu.addAction(self.action_quit)

        edit_menu = menu.addMenu("&Upravy")
        for action in (self.action_undo, self.action_redo):
            edit_menu.addAction(action)
        edit_menu.addSeparator()
        for action in (self.action_copy, self.action_paste, self.action_duplicate,
                       self.action_delete, self.action_select_all):
            edit_menu.addAction(action)

        object_menu = menu.addMenu("&Objekt")
        for action in (self.action_front, self.action_back, self.action_center_h,
                       self.action_center_v):
            object_menu.addAction(action)
        object_menu.addSeparator()
        for action in (self.action_unite, self.action_subtract, self.action_intersect,
                       self.action_exclude):
            object_menu.addAction(action)
        object_menu.addSeparator()
        for action in (self.action_join, self.action_close_path, self.action_to_path):
            object_menu.addAction(action)
        object_menu.addSeparator()
        object_menu.addAction(self.action_caption)

        view_menu = menu.addMenu("&Zobrazeni")
        for action in (self.action_zoom_in, self.action_zoom_out, self.action_zoom_reset,
                       self.action_zoom_fit):
            view_menu.addAction(action)
        view_menu.addSeparator()
        for action in (self.action_grid, self.action_snap_grid, self.action_snap_objects):
            view_menu.addAction(action)
        view_menu.addSeparator()
        view_menu.addAction(self.action_document)

        top = QToolBar("Hlavni", self)
        top.setIconSize(QSize(18, 18))
        top.setMovable(False)
        for action in (self.action_new, self.action_open, self.action_save):
            top.addAction(action)
        top.addSeparator()
        top.addAction(self.action_undo)
        top.addAction(self.action_redo)
        top.addSeparator()
        top.addAction(self.action_zoom_out)
        top.addAction(self.action_zoom_reset)
        top.addAction(self.action_zoom_in)
        top.addAction(self.action_zoom_fit)
        top.addSeparator()
        top.addAction(self.action_grid)
        top.addAction(self.action_snap_grid)
        top.addAction(self.action_snap_objects)
        top.addSeparator()

        top.addWidget(QLabel(" Guma ", self))
        self.eraser_spin = QDoubleSpinBox(self)
        self.eraser_spin.setRange(1.0, 400.0)
        self.eraser_spin.setValue(self.view.eraser_size)
        self.eraser_spin.setSuffix(" px")
        self.eraser_spin.setToolTip("Prumer gumy")
        self.eraser_spin.valueChanged.connect(self._set_eraser_size)
        top.addWidget(self.eraser_spin)

        top.addWidget(QLabel("  Hladka krivka ", self))
        self.spline_combo = QComboBox(self)
        self.spline_combo.addItem("prochazi body", "prochazi")
        self.spline_combo.addItem("body jen ridi (B-spline)", "ridici")
        self.spline_combo.setToolTip(
            "Jak se maji body pouzit pri kresleni hladke krivky")
        self.spline_combo.currentIndexChanged.connect(self._set_spline_mode)
        top.addWidget(self.spline_combo)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, top)
        self.top_toolbar = top

        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        shapes_bar = QToolBar("Krivky", self)
        shapes_bar.setMovable(False)
        shapes_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        for action in (self.action_unite, self.action_subtract, self.action_intersect,
                       self.action_exclude):
            shapes_bar.addAction(action)
        shapes_bar.addSeparator()
        for action in (self.action_join, self.action_close_path, self.action_to_path):
            shapes_bar.addAction(action)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, shapes_bar)

        for bar in (self.top_toolbar, shapes_bar):
            bar.setStyleSheet(
                "QToolButton { color: #14181d; padding: 4px 9px; }"
                "QToolButton:disabled { color: #9aa1aa; }"
                "QToolButton:hover { background: #d8e2ef; border-radius: 4px; }")

        tools = QToolBar("Nastroje", self)
        tools.setMovable(False)
        tools.setOrientation(Qt.Orientation.Vertical)
        tools.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        # Vychozi styl kresli popisky slabe a aktivni nastroj je skoro
        # k nerozeznani. Cerny text a modre zvyrazneni to resi.
        tools.setStyleSheet("""
            QToolBar { background: #eceff3; border-right: 1px solid #c3c9d2;
                       padding: 4px; spacing: 2px; }
            QToolButton { color: #14181d; font-size: 13px; text-align: left;
                          padding: 7px 14px; min-width: 104px;
                          border: 1px solid transparent; border-radius: 4px; }
            QToolButton:hover { background: #d8e2ef; border-color: #a9bcd4; }
            QToolButton:checked { background: #1668c1; color: #ffffff;
                                  font-weight: bold; border-color: #0d4b8f; }
            QToolButton:checked:hover { background: #1b74d4; }
        """)
        for key, *_ in TOOL_BUTTONS:
            tools.addAction(self.tool_actions[key])
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tools)

    def _scrollable(self, widget: QWidget) -> QScrollArea:
        """Panel do rolovaci plochy, aby okno slo zmensit i na nizsi obrazovku."""
        area = QScrollArea(self)
        area.setWidget(widget)
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        return area

    def _build_docks(self) -> None:
        self.properties = PropertiesPanel(self.view, self)
        self.properties.changed.connect(self.snapshot)
        self.palette_panel = PalettePanel(self)
        self.palette_panel.fill_picked.connect(
            lambda color: self._quick_color("fill", color))
        self.palette_panel.stroke_picked.connect(
            lambda color: self._quick_color("stroke", color))

        style_widget = QWidget(self)
        layout = QVBoxLayout(style_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.palette_panel)
        layout.addWidget(self.properties, 1)

        style_dock = QDockWidget("Vlastnosti", self)
        style_dock.setWidget(self._scrollable(style_widget))
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, style_dock)

        self.layers = LayersPanel(self.view, self)
        self.layers.changed.connect(self.snapshot)

        self.reference_panel = ReferencePanel(self)
        self.reference_panel.reference_requested.connect(self.set_reference)
        self.reference_panel.opacity_changed.connect(self.set_reference_opacity)
        self.reference_panel.visibility_changed.connect(self.set_reference_visible)
        self.reference_panel.remove_requested.connect(self.remove_reference)
        if REFERENCE_DIR.is_dir():
            self.reference_panel.load_folder(REFERENCE_DIR)

        self.templates = TemplatePanel(TEMPLATE_DIR, self)
        self.templates.insert_requested.connect(self.insert_template)
        self.templates.part_requested.connect(self.insert_part)
        self.templates.new_from_template.connect(self.new_from_template)
        self.view.part_dropped.connect(self.insert_part)

        self.caption_panel = CaptionPanel(self)
        self.caption_panel.apply_requested.connect(self.apply_caption)
        self.caption_panel.remove_requested.connect(self.remove_caption)

        self.history_panel = HistoryPanel(self)
        self.history_panel.save_requested.connect(self.save_journal_as)
        self.history_panel.command_entered.connect(self.run_command)

        tabs = QTabWidget(self)
        tabs.addTab(self._scrollable(self.caption_panel), "Popisek")
        tabs.addTab(self.layers, "Objekty")
        tabs.addTab(self.history_panel, "Historie")
        tabs.addTab(self._scrollable(self.reference_panel), "Predloha")
        tabs.addTab(self._scrollable(self.templates), "Sablony")
        self.side_tabs = tabs

        side_dock = QDockWidget("Kresba", self)
        side_dock.setWidget(tabs)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, side_dock)

    def _build_statusbar(self) -> None:
        self.position_label = QLabel("0; 0", self)
        self.zoom_label = QLabel("100 %", self)
        self.tool_label = QLabel(self)
        self.tool_label.setStyleSheet(
            "color: #ffffff; background: #1668c1; border-radius: 4px;"
            " padding: 2px 10px; font-weight: bold;")
        self.hint_label = QLabel("Kolecko = zoom, prostredni tlacitko nebo mezernik = posun", self)
        bar = self.statusBar()
        bar.addWidget(self.tool_label)
        bar.addWidget(self.hint_label, 1)
        bar.addPermanentWidget(self.position_label)
        bar.addPermanentWidget(self.zoom_label)

    # ------------------------------------------------------------------
    # Stav a undo
    # ------------------------------------------------------------------
    def capture_state(self) -> str:
        return svgio.to_string(self.document, self.scene.shapes())

    def restore_state(self, text: str) -> None:
        document, shapes = svgio.from_string(text)
        self.apply_document(document, shapes)

    def snapshot(self, label: str = "Zmena", detail: str | None = None) -> None:
        """Zapise krok zpet a radek do viditelne historie operaci."""
        before = self.undo.stack.count()
        self.undo.snapshot(label)
        if self.undo.stack.count() != before:
            self.journal.record(detail or label.lower())
            self.history_panel.refresh(self.journal)
        self.refresh_panels()

    def reset_journal(self, reason: str = "") -> None:
        """Nova nebo otevrena kresba zacina s prazdnou historii."""
        self.journal.clear(f"# {reason}" if reason else "")
        self.history_panel.refresh(self.journal)

    # ------------------------------------------------------------------
    # Prikazy
    # ------------------------------------------------------------------
    def run_command(self, line: str) -> bool:
        """Provede jeden prikaz z prikazoveho radku v panelu historie."""
        try:
            message = run_line(self, line)
        except CommandError as error:
            self.history_panel.show_result(f"{line}  ->  {error}", False)
            self.statusBar().showMessage(f"Prikaz: {error}", 8000)
            return False
        except Exception as error:  # noqa: BLE001
            self.history_panel.show_result(
                f"{line}  ->  {type(error).__name__}: {error}", False)
            return False

        lines = (message or "").splitlines()
        if len(lines) > 1:
            # Delsi vypis (napriklad prehled prikazu) se vejde jen do okna.
            self.history_panel.show_result(lines[0])
            self.history_panel.show_listing(message)
        else:
            self.history_panel.show_result(message or "Hotovo.")
            self.statusBar().showMessage(message or "Hotovo.", 6000)
        self.refresh_panels()
        return True

    def refresh_panels(self) -> None:
        self.properties.refresh()
        self.layers.refresh()
        self.caption_panel.load_from(self.caption_shape())
        self.view.viewport().update()

    def apply_document(self, document: Document, shapes: list[ShapeMixin]) -> None:
        for item in list(self.scene.items()):
            if isinstance(item, ShapeMixin):
                self.scene.removeItem(item)

        self.document.width = document.width
        self.document.height = document.height
        self.document.background = document.background
        self.document.grid_size = document.grid_size
        self.document.title = document.title
        self.document.reference_opacity = document.reference_opacity

        for index, shape in enumerate(shapes):
            shape.setZValue(float(index))
            self.scene.addItem(shape)

        if document.reference_path != self.document.reference_path:
            if document.reference_path:
                self.set_reference(document.reference_path, record=False)
            else:
                self.remove_reference(record=False)

        self.scene.update_page()
        self.refresh_panels()

    # ------------------------------------------------------------------
    # Nastroje
    # ------------------------------------------------------------------
    def select_tool(self, name: str) -> None:
        tool_class = TOOL_CLASSES.get(name, SelectTool)
        self.view.set_tool(tool_class(self.view))
        action = self.tool_actions.get(name)
        if action is not None and not action.isChecked():
            action.setChecked(True)
        label = next((title for key, title, *_ in TOOL_BUTTONS if key == name), name)
        self.tool_label.setText(f"Nastroj: {label}")

    def _after_tool(self) -> None:
        pending = self.view.pending_text_edit
        self.view.pending_text_edit = None
        self.select_tool("vyber")
        if pending is not None and isinstance(self.view.tool, SelectTool):
            self.view.tool.start_editing(pending)
        self.refresh_panels()

    def _set_eraser_size(self, value: float) -> None:
        self.view.eraser_size = value
        self.view.viewport().update()

    def _set_spline_mode(self, _index: int) -> None:
        self.view.spline_mode = self.spline_combo.currentData()

    # ------------------------------------------------------------------
    # Krivky: orezani, napojeni, uzavreni
    # ------------------------------------------------------------------
    def boolean_op(self, operation: str) -> None:
        shapes = self.scene.selected_shapes()
        if len(shapes) < 2:
            self.statusBar().showMessage(
                "Vyber alespon dva objekty. Spodni je zaklad, ostatni se od nej odectou.",
                5000)
            return

        # Poradi tvaru se musi zapsat jeste pred zmenou - po slouceni uz
        # puvodni tvary v kresbe nejsou.
        ids = shape_ids(shapes, self.scene.shapes())
        base = shapes[0]
        result = base.scene_path()
        for other in shapes[1:]:
            path = other.scene_path()
            if operation == "unite":
                result = result.united(path)
            elif operation == "subtract":
                result = result.subtracted(path)
            elif operation == "intersect":
                result = result.intersected(path)
            else:
                result = result.subtracted(path).united(path.subtracted(result))
        result = result.simplified()

        if result.elementCount() < 2:
            self.statusBar().showMessage("Vysledek by byl prazdny, nic se nezmenilo.", 5000)
            return

        style = base.style.copy()
        if style.fill is None:
            style.fill = QColor(self.view.default_style.fill or QColor("#ffffff"))
        replacement = PathShape(result, style, True, base.name)
        replacement.setZValue(base.zValue())
        for shape in shapes:
            self.scene.removeItem(shape)
        self.scene.addItem(replacement)
        self.scene.clearSelection()
        replacement.setSelected(True)
        names = {"unite": "sjednotit", "subtract": "odecist",
                 "intersect": "prunik", "exclude": "vyloucit"}
        self.snapshot({"unite": "Sjednoceni", "subtract": "Odecteni",
                       "intersect": "Prunik"}.get(operation, "Vylouceni"),
                      f"{names.get(operation, operation)} {ids} "
                      f"--vysledek {quoted(replacement.name)}")

    def join_selected(self) -> None:
        shapes = [shape for shape in self.scene.selected_shapes()
                  if isinstance(shape, (PathShape, LineShape))]
        if len(shapes) < 2:
            self.statusBar().showMessage(
                "Napojeni potrebuje aspon dve krivky nebo cary.", 5000)
            return

        ids = shape_ids(shapes, self.scene.shapes())
        subpaths: list = []
        for shape in shapes:
            subpaths.extend(path_to_subpaths(shape.scene_path()))
        joined = join_subpaths(subpaths, self.view.join_tolerance)
        path = subpaths_to_path(joined)
        closed = any(part.closed for part in joined)

        style = shapes[0].style.copy()
        if closed and style.fill is None:
            style.fill = QColor(self.view.default_style.fill or QColor("#ffffff"))
        replacement = PathShape(path, style, closed, shapes[0].name)
        replacement.setZValue(shapes[0].zValue())
        for shape in shapes:
            self.scene.removeItem(shape)
        self.scene.addItem(replacement)
        self.scene.clearSelection()
        replacement.setSelected(True)

        parts = len(joined)
        if parts > 1:
            self.statusBar().showMessage(
                f"Napojeno, ale zbyly {parts} nespojene casti. Konce musi byt bliz nez "
                f"{self.view.join_tolerance:.0f} px.", 6000)
        self.snapshot("Napojeni krivek",
                      f"napojit {ids} --casti {parts} "
                      f"--uzavrene {'ano' if closed else 'ne'}")

    def close_selected(self) -> None:
        shapes = [shape for shape in self.scene.selected_shapes()
                  if isinstance(shape, PathShape)]
        if not shapes:
            self.statusBar().showMessage("Uzavrit jde jen krivku.", 4000)
            return
        ids = shape_ids(shapes, self.scene.shapes())
        for shape in shapes:
            shape.set_closed(True)
            if shape.style.fill is None:
                style = shape.style.copy()
                style.fill = QColor(self.view.default_style.fill or QColor("#ffffff"))
                shape.set_style(style)
        self.snapshot("Uzavreni krivky",
                      f"uzavrit {ids} --vypln {color(shapes[0].style.fill)}")

    def convert_to_path(self, shape: ShapeMixin | None = None) -> None:
        targets = [shape] if isinstance(shape, ShapeMixin) else self.scene.selected_shapes()
        if not targets:
            self.statusBar().showMessage(
                "Nejdriv vyber tvar, ktery se ma prevest na krivku - sipkou (V) "
                "na nej klikni.", 6000)
            return None

        ids = shape_ids(targets, self.scene.shapes())
        converted = []
        changed = 0
        for item in targets:
            if isinstance(item, PathShape):
                converted.append(item)
                continue
            replacement = to_path_shape(item)
            self.scene.removeItem(item)
            self.scene.addItem(replacement)
            converted.append(replacement)
            changed += 1

        self.scene.clearSelection()
        for item in converted:
            item.setSelected(True)

        if not changed:
            self.statusBar().showMessage(
                "Tohle uz krivka je. Uzly se upravuji nastrojem Uzly (N).", 6000)
            return converted[0] if converted else None

        nodes = sum(len(part.nodes)
                    for item in converted if isinstance(item, PathShape)
                    for part in path_to_subpaths(item.path()))
        self.snapshot("Prevod na krivku",
                      f"na-krivku {ids} --uzlu {nodes}")
        self.statusBar().showMessage(
            f"Prevedeno na krivku: {changed} objektu, celkem {nodes} uzlu. "
            f"Uprav je nastrojem Uzly (N).", 6000)
        return converted[0] if converted else None

    def _convert_and_edit(self, shape: ShapeMixin) -> None:
        """Uzlovy nastroj narazil na tvar, ktery jeste neni krivka."""
        replacement = self.convert_to_path(shape)
        tool = self.view.tool
        if replacement is not None and isinstance(tool, NodeTool):
            tool.load(replacement)

    def _quick_color(self, field: str, value: QColor) -> None:
        shapes = self.scene.selected_shapes()
        if not shapes:
            setattr(self.view.default_style, field, value)
            self.properties.refresh()
            return
        for shape in shapes:
            style = shape.style.copy()
            setattr(style, field, value)
            shape.set_style(style)
        setattr(self.view.default_style, field, value)
        option = "vypln" if field == "fill" else "obrys"
        self.snapshot("Zmena barvy",
                      f"barva --{option} {color(value)} "
                      f"{shape_ids(shapes, self.scene.shapes())}")

    # ------------------------------------------------------------------
    # Prace se soubory
    # ------------------------------------------------------------------
    def _confirm_discard(self) -> bool:
        if self.undo.stack.isClean():
            return True
        answer = QMessageBox.question(
            self, "Neulozene zmeny",
            "Kresba obsahuje neulozene zmeny. Ulozit je pred pokracovanim?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return True

    def new_document(self) -> None:
        if not self._confirm_discard():
            return
        fresh = Document(width=1024.0, height=1024.0, grid_size=16.0)
        self.remove_reference(record=False)
        self.apply_document(fresh, [])
        self.path = None
        self.undo.reset()
        self.undo.stack.setClean()
        self.reset_journal("nova kresba")
        self._update_title()
        self.view.zoom_fit()

    def open_dialog(self) -> None:
        if not self._confirm_discard():
            return
        start = str(DRAWING_DIR if DRAWING_DIR.is_dir() else PROJECT_DIR)
        path, _ = QFileDialog.getOpenFileName(self, "Otevrit SVG", start,
                                              "SVG (*.svg);;Vsechny soubory (*)")
        if path:
            self.open_path(Path(path))

    def open_path(self, path: Path) -> None:
        try:
            document, shapes = svgio.load(path)
        except Exception as error:  # noqa: BLE001 - uzivatel potrebuje vedet duvod
            QMessageBox.critical(self, "Nelze otevrit", f"{path}\n\n{error}")
            return
        self.apply_document(document, shapes)
        self.path = path
        self.undo.reset()
        self.undo.stack.setClean()
        self.reset_journal(f"otevreno {quoted(path.name)}")
        self._update_title()
        self.view.zoom_fit()

    def save(self) -> bool:
        if self.path is None:
            return self.save_as()
        return self._write(self.path)

    def save_as(self) -> bool:
        DRAWING_DIR.mkdir(parents=True, exist_ok=True)
        suggested = str(self.path or DRAWING_DIR / "piktogram.svg")
        path, _ = QFileDialog.getSaveFileName(self, "Ulozit SVG", suggested, "SVG (*.svg)")
        if not path:
            return False
        target = Path(path)
        if target.suffix.lower() != ".svg":
            target = target.with_suffix(".svg")
        return self._write(target)

    def journal_path(self, path: Path) -> Path:
        return path.with_suffix(path.suffix + ".historie.txt")

    def save_journal_as(self) -> None:
        suggested = str(self.journal_path(self.path) if self.path
                        else DRAWING_DIR / "historie.txt")
        path, _ = QFileDialog.getSaveFileName(self, "Ulozit historii operaci",
                                              suggested, "Textovy soubor (*.txt)")
        if not path:
            return
        self.journal.save(path, self.path.name if self.path else "kresba")
        self.statusBar().showMessage(f"Historie ulozena: {path}", 5000)

    def _write(self, path: Path) -> bool:
        try:
            svgio.save(path, self.document, self.scene.shapes())
        except OSError as error:
            QMessageBox.critical(self, "Nelze ulozit", f"{path}\n\n{error}")
            return False
        try:
            self.journal.save(self.journal_path(path), path.name)
        except OSError:
            # Historie je jen doprovod, kvuli ni se ulozeni kresby nekazi.
            pass
        self.path = path
        self.undo.last = self.capture_state()
        self.undo.stack.setClean()
        self._update_title()
        self.statusBar().showMessage(f"Ulozeno: {path}", 4000)
        return True

    def export_png(self) -> None:
        scale, ok = QInputDialog.getDouble(
            self, "Export do PNG", "Nasobek velikosti:", 1.0, 0.1, 8.0, 1)
        if not ok:
            return
        suggested = str((self.path.with_suffix(".png")) if self.path
                        else DRAWING_DIR / "piktogram.png")
        path, _ = QFileDialog.getSaveFileName(self, "Export do PNG", suggested, "PNG (*.png)")
        if not path:
            return

        rect = self.document.rect()
        image = QImage(int(rect.width() * scale), int(rect.height() * scale),
                       QImage.Format.Format_ARGB32)
        image.fill(self.document.background or Qt.GlobalColor.transparent)

        reference_visible = self.reference is not None and self.reference.isVisible()
        if reference_visible:
            self.reference.setVisible(False)
        selection = self.scene.selectedItems()
        self.scene.clearSelection()

        painter = QPainter(image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing
                               | QPainter.RenderHint.TextAntialiasing)
        self.scene.render(painter, QRectF(image.rect()), rect)
        painter.end()

        for item in selection:
            item.setSelected(True)
        if reference_visible:
            self.reference.setVisible(True)

        if image.save(path):
            self.statusBar().showMessage(f"Vyexportovano: {path}", 4000)
        else:
            QMessageBox.critical(self, "Nelze ulozit", path)

    # ------------------------------------------------------------------
    # Sablony a predloha
    # ------------------------------------------------------------------
    def insert_template(self, path: str) -> None:
        self.insert_part(path, -1)

    def insert_part(self, path: str, index: int = -1,
                    scene_pos: QPointF | None = None) -> None:
        """Vlozi celou sablonu, nebo jen jeden jeji dil."""
        try:
            _, shapes = svgio.load(Path(path))
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Nelze nacist sablonu", f"{path}\n\n{error}")
            return

        whole = index < 0
        if not whole:
            if not 0 <= index < len(shapes):
                return
            shapes = [shapes[index]]
        if not shapes:
            return

        if scene_pos is None and not whole:
            # Bez pretazeni miri dil doprostred toho, co je prave videt.
            scene_pos = self.view.mapToScene(self.view.viewport().rect().center())

        if scene_pos is not None:
            bounds = QRectF()
            for shape in shapes:
                mapped = shape.mapToScene(shape.local_rect()).boundingRect()
                bounds = mapped if bounds.isNull() else bounds.united(mapped)
            delta = scene_pos - bounds.center()
            for shape in shapes:
                shape.setPos(shape.pos() + delta)

        self.scene.clearSelection()
        base = self.scene.next_z()
        for order, shape in enumerate(shapes):
            shape.setZValue(base + order)
            self.scene.addItem(shape)
            shape.setSelected(True)
        self.snapshot(
            "Vlozeni sablony" if whole else "Vlozeni dilu",
            f"sablona {quoted(template_name(path))}"
            + ("" if whole else f" --dil {index}")
            + (f" --na {point(scene_pos.x(), scene_pos.y())}" if scene_pos else ""))

    def new_from_template(self, path: str) -> None:
        if not self._confirm_discard():
            return
        try:
            document, shapes = svgio.load(Path(path))
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "Nelze nacist sablonu", f"{path}\n\n{error}")
            return
        self.apply_document(document, shapes)
        self.path = None
        self.undo.reset()
        self.undo.stack.setClean()
        self._update_title()
        self.view.zoom_fit()

    def set_reference(self, path: str, record: bool = True) -> None:
        image = ReferenceImage.load(path)
        if image is None:
            QMessageBox.warning(self, "Predloha", f"Obrazek nelze nacist:\n{path}")
            return
        self.remove_reference(record=False)
        image.fit_into(self.document.width, self.document.height)
        image.setOpacity(self.document.reference_opacity)
        self.scene.addItem(image)
        self.reference = image
        self.scene.reference = image
        self.document.reference_path = str(path)
        if record:
            self.snapshot("Predloha", f"predloha {quoted(Path(path).as_posix())}")

    def set_reference_opacity(self, value: float) -> None:
        self.document.reference_opacity = value
        if self.reference is not None:
            self.reference.setOpacity(value)

    def set_reference_visible(self, visible: bool) -> None:
        if self.reference is not None:
            self.reference.setVisible(visible)

    def remove_reference(self, record: bool = True) -> None:
        if self.reference is not None:
            self.scene.removeItem(self.reference)
        self.reference = None
        self.scene.reference = None
        self.document.reference_path = ""
        if record:
            self.snapshot("Odebrani predlohy", "predloha --odebrat")

    # ------------------------------------------------------------------
    # Upravy
    # ------------------------------------------------------------------
    def copy_selection(self) -> None:
        shapes = self.scene.selected_shapes()
        if not shapes:
            return
        text = svgio.shapes_to_clipboard_text(shapes)
        QGuiApplication.clipboard().setText(text)

    def paste(self) -> None:
        text = QGuiApplication.clipboard().text()
        if not text.strip().startswith("<"):
            return
        shapes = svgio.shapes_from_clipboard_text(text)
        if not shapes:
            return
        self.scene.clearSelection()
        base = self.scene.next_z()
        for index, shape in enumerate(shapes):
            shape.setPos(shape.pos() + QPointF(16.0, 16.0))
            shape.setZValue(base + index)
            self.scene.addItem(shape)
            shape.setSelected(True)
        self.snapshot("Vlozeni ze schranky", f"schranka --tvaru {len(shapes)}")

    def duplicate(self) -> None:
        shapes = self.scene.selected_shapes()
        if not shapes:
            return
        ids = shape_ids(shapes, self.scene.shapes())
        self.scene.clearSelection()
        base = self.scene.next_z()
        for index, shape in enumerate(shapes):
            copy = shape.clone()
            copy.setPos(shape.pos() + QPointF(16.0, 16.0))
            copy.setZValue(base + index)
            self.scene.addItem(copy)
            copy.setSelected(True)
        self.snapshot("Duplikace", f"duplikovat {ids}")

    def delete_selection(self) -> None:
        shapes = self.scene.selected_shapes()
        if not shapes:
            return
        ids = shape_ids(shapes, self.scene.shapes())
        names = " ".join(quoted(shape.name) for shape in shapes[:4])
        for shape in shapes:
            self.scene.removeItem(shape)
        self.snapshot("Smazani", f"smazat {ids}  # {names}")

    def select_all(self) -> None:
        for shape in self.scene.shapes():
            shape.setSelected(True)
        self.refresh_panels()

    def reorder(self, direction: int) -> None:
        shapes = self.scene.selected_shapes()
        ids = shape_ids(shapes, self.scene.shapes())
        self.layers._reorder(direction)
        self.snapshot("Zmena poradi",
                      "poradi " + ("--nahoru" if direction > 0 else "--dolu")
                      + (f" {ids}" if ids else ""))

    def center_on_page(self, horizontal: bool) -> None:
        shapes = self.scene.selected_shapes()
        if not shapes:
            return
        # Vice objektu se srovnava jako celek. Kdyby se kazdy sam, slozena
        # kresba by se smackla na jednu hromadu.
        bounds = QRectF()
        for shape in shapes:
            mapped = shape.mapToScene(shape.local_rect()).boundingRect()
            bounds = mapped if bounds.isNull() else bounds.united(mapped)

        if horizontal:
            delta = QPointF((self.document.width - bounds.width()) / 2.0 - bounds.x(), 0.0)
        else:
            delta = QPointF(0.0, (self.document.height - bounds.height()) / 2.0 - bounds.y())
        for shape in shapes:
            shape.setPos(shape.pos() + delta)
        self.snapshot("Zarovnani",
                      "zarovnat " + ("--vodorovne" if horizontal else "--svisle")
                      + f" {shape_ids(shapes, self.scene.shapes())}")

    def show_tab(self, panel: QWidget) -> None:
        """Prepne na zalozku s danym panelem, i kdyz je v rolovaci plose."""
        for index in range(self.side_tabs.count()):
            widget = self.side_tabs.widget(index)
            if widget is panel or (isinstance(widget, QScrollArea)
                                   and widget.widget() is panel):
                self.side_tabs.setCurrentIndex(index)
                return

    def focus_caption(self) -> None:
        """Ctrl+L skoci do policka s popiskem pod obrazkem."""
        self.show_tab(self.caption_panel)
        self.caption_panel.text_edit.setFocus()
        self.caption_panel.text_edit.selectAll()

    def caption_shape(self) -> TextShape | None:
        for shape in self.scene.shapes():
            if isinstance(shape, TextShape) and shape.role == "caption":
                return shape
        return None

    def apply_caption(self) -> None:
        values = self.caption_panel.values()
        if not values["text"]:
            return

        font = QFont(values["font"])
        font.setPointSizeF(values["size"])
        font.setBold(values["bold"])

        shape = self.caption_shape()
        if shape is None:
            style = Style(fill=QColor(values["color"]), stroke=None, stroke_width=0.0)
            shape = TextShape(values["text"], style, font, "Popisek")
            shape.role = "caption"
            shape.setZValue(self.scene.next_z())
            self.scene.addItem(shape)
        else:
            shape.setFont(font)
            shape.set_text(values["text"])
            style = shape.style.copy()
            style.fill = QColor(values["color"])
            style.stroke = None
            shape.set_style(style)

        self._place_caption(shape, values["margin"])
        self.snapshot("Popisek",
                      f"popisek {quoted(values['text'])} "
                      f"--velikost {number(values['size'])} "
                      f"--odsazeni {number(values['margin'])}")

    def _place_caption(self, shape: TextShape, margin: float) -> None:
        shape.setRotation(0.0)
        bounds = shape.local_rect()
        shape.setPos((self.document.width - bounds.width()) / 2.0,
                     self.document.height - margin - bounds.height())
        shape.sync_origin()

    def remove_caption(self) -> None:
        shape = self.caption_shape()
        if shape is None:
            return
        self.scene.removeItem(shape)
        self.snapshot("Odebrani popisku", "popisek --odebrat")

    # ------------------------------------------------------------------
    # Zobrazeni
    # ------------------------------------------------------------------
    def toggle_grid(self, checked: bool) -> None:
        self.scene.show_grid = checked
        self.scene.update()

    def toggle_snap_grid(self, checked: bool) -> None:
        self.view.snap_to_grid = checked

    def toggle_snap_objects(self, checked: bool) -> None:
        self.view.snap_to_objects = checked

    def edit_document(self) -> None:
        dialog = DocumentDialog(self.document, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        dialog.apply_to(self.document)
        if self.reference is not None:
            self.reference.fit_into(self.document.width, self.document.height)
        self.scene.update_page()
        self.snapshot("Nastaveni kresby",
                      f"strana {number(self.document.width)} "
                      f"{number(self.document.height)} "
                      f"--mrizka {number(self.document.grid_size)} "
                      f"--pozadi {color(self.document.background)}")

    def _show_position(self, point: QPointF) -> None:
        self.position_label.setText(f"{point.x():.0f}; {point.y():.0f} px")

    def _show_zoom(self, scale: float) -> None:
        self.zoom_label.setText(f"{scale * 100:.0f} %")

    def _on_clean_changed(self, _clean: bool) -> None:
        self._update_title()

    def _update_title(self) -> None:
        name = self.path.name if self.path else "bez nazvu"
        dirty = "" if self.undo.stack.isClean() else " *"
        self.setWindowTitle(f"PiktoEdit — {name}{dirty}")

    def closeEvent(self, event) -> None:
        if not self._confirm_discard():
            event.ignore()
            return
        # Pri zaviraní uz nas stav zasobniku nezajima a jeho signal by dorazil
        # do rozestaveneho okna.
        try:
            self.undo.stack.cleanChanged.disconnect(self._on_clean_changed)
        except (RuntimeError, TypeError):
            pass
        event.accept()
