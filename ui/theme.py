"""
Tema visual de ContextPack — inspirado en la paleta del logo.
Azul eléctrico #4A9FFF, violeta #7B5EDB, cyan #00D4FF sobre fondo oscuro #1A1A2E
"""

STYLESHEET = """
/* ── BASE ─────────────────────────────────────────────────────────────── */

QWidget {
    background-color: #1A1A2E;
    color: #E8E8F0;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #1A1A2E;
}

/* ── BARRA DE MENÚ ─────────────────────────────────────────────────────── */

QMenuBar {
    background-color: #12122A;
    color: #B0B0CC;
    border-bottom: 1px solid #2A2A4A;
    padding: 2px 4px;
}

QMenuBar::item:selected {
    background-color: #2A2A4A;
    color: #4A9FFF;
    border-radius: 4px;
}

QMenu {
    background-color: #1E1E38;
    border: 1px solid #2A2A4A;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #2A2A4A;
    color: #4A9FFF;
}

QMenu::separator {
    height: 1px;
    background: #2A2A4A;
    margin: 4px 8px;
}

/* ── BOTONES ───────────────────────────────────────────────────────────── */

QPushButton {
    background-color: #22223A;
    color: #C0C0E0;
    border: 1px solid #3A3A5A;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #2A2A4A;
    border-color: #4A9FFF;
    color: #4A9FFF;
}

QPushButton:pressed {
    background-color: #1E1E38;
    border-color: #7B5EDB;
    color: #7B5EDB;
}

QPushButton:disabled {
    background-color: #1A1A2E;
    color: #44445A;
    border-color: #2A2A3A;
}

/* Botón principal — Escanear */
QPushButton#btn_esc {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #4A9FFF, stop:1 #7B5EDB
    );
    color: #FFFFFF;
    font-weight: 600;
    border: none;
}

QPushButton#btn_esc:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #5AAFFF, stop:1 #8B6EEB
    );
    color: #FFFFFF;
    border: none;
}

QPushButton#btn_esc:disabled {
    background: #2A2A4A;
    color: #44445A;
}

/* ── LABELS ────────────────────────────────────────────────────────────── */

QLabel {
    color: #C0C0E0;
    background: transparent;
}

/* ── INPUTS ────────────────────────────────────────────────────────────── */

QLineEdit {
    background-color: #12122A;
    color: #E8E8F0;
    border: 1px solid #3A3A5A;
    border-radius: 6px;
    padding: 5px 10px;
    selection-background-color: #4A9FFF;
}

QLineEdit:focus {
    border-color: #4A9FFF;
}

QLineEdit::placeholder {
    color: #44445A;
}

/* ── ÁRBOL ─────────────────────────────────────────────────────────────── */

QTreeWidget {
    background-color: #12122A;
    border: 1px solid #2A2A4A;
    border-radius: 8px;
    color: #C0C0E0;
    alternate-background-color: #1A1A38;
    outline: none;
}

QTreeWidget::item {
    padding: 3px 6px;
    border-radius: 4px;
}

QTreeWidget::item:hover {
    background-color: #2A2A4A;
    color: #4A9FFF;
}

QTreeWidget::item:selected {
    background-color: #2A2A5A;
    color: #00D4FF;
}

QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {
    image: url(none);
    border-image: none;
    color: #4A9FFF;
}

QHeaderView::section {
    background-color: #1E1E38;
    color: #7B5EDB;
    border: none;
    border-bottom: 1px solid #2A2A4A;
    padding: 6px 8px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* ── VISTA PREVIA (QTextEdit) ──────────────────────────────────────────── */

QTextEdit {
    background-color: #0F0F22;
    color: #C8C8E8;
    border: 1px solid #2A2A4A;
    border-radius: 8px;
    padding: 8px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    selection-background-color: #4A9FFF;
    selection-color: #FFFFFF;
}

/* ── BARRA DE PROGRESO ─────────────────────────────────────────────────── */

QProgressBar {
    background-color: #12122A;
    border: none;
    border-radius: 3px;
    height: 6px;
}

QProgressBar::chunk {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #4A9FFF, stop:0.5 #7B5EDB, stop:1 #00D4FF
    );
    border-radius: 3px;
}

/* ── SPLITTER ──────────────────────────────────────────────────────────── */

QSplitter::handle {
    background-color: #2A2A4A;
    width: 1px;
}

QSplitter::handle:hover {
    background-color: #4A9FFF;
}

/* ── SCROLLBARS ────────────────────────────────────────────────────────── */

QScrollBar:vertical {
    background: #12122A;
    width: 8px;
    border-radius: 4px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #3A3A5A;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #4A9FFF;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #12122A;
    height: 8px;
    border-radius: 4px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #3A3A5A;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #4A9FFF;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── CHECKBOXES ────────────────────────────────────────────────────────── */

QCheckBox {
    color: #C0C0E0;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3A3A5A;
    border-radius: 4px;
    background: #12122A;
}

QCheckBox::indicator:hover {
    border-color: #4A9FFF;
}

QCheckBox::indicator:checked {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #4A9FFF, stop:1 #7B5EDB
    );
    border: none;
}

/* ── DIALOGS ───────────────────────────────────────────────────────────── */

QDialog {
    background-color: #1A1A2E;
    border: 1px solid #2A2A4A;
    border-radius: 10px;
}

QMessageBox {
    background-color: #1A1A2E;
}

/* ── FOOTER ────────────────────────────────────────────────────────────── */

QFrame#footer {
    background-color: #12122A;
    border-top: 1px solid #2A2A4A;
}
"""
