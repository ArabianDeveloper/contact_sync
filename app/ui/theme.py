"""Dark theme: color tokens and one stylesheet."""
from __future__ import annotations

COLORS = {
    "background": "#14161a",
    "surface": "#1c1f26",
    "surface_alt": "#222630",
    "border": "#2a2e38",
    "text": "#e6e8ec",
    "muted": "#9aa1ae",
    "accent": "#4f8cff",
    "accent_hover": "#6aa0ff",
    "accent_pressed": "#3b78e8",
    "success": "#3ecf8e",
    "warning": "#f5a524",
    "error": "#ef5350",
    "disabled": "#5b6270",
}

FONT_FAMILY = "Segoe UI"


def stylesheet() -> str:
    c = COLORS
    return f"""
* {{ font-family: "{FONT_FAMILY}", "Tahoma", sans-serif; font-size: 10pt; }}
QWidget {{ background-color: {c['background']}; color: {c['text']}; }}
QToolTip {{ background-color: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border']}; }}

QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 18pt; font-weight: 600; }}
QLabel#sectionTitle {{ font-size: 11pt; font-weight: 600; }}
QLabel#muted {{ color: {c['muted']}; }}
QLabel#error {{ color: {c['error']}; }}
QLabel#success {{ color: {c['success']}; }}
QLabel#warning {{ color: {c['warning']}; }}
QLabel#brand {{ font-size: 13pt; font-weight: 700; padding: 18px 16px 10px 16px; }}
QLabel#statValue {{ font-size: 20pt; font-weight: 700; }}

QFrame#card {{ background-color: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; }}
QFrame#card QLabel {{ background: transparent; }}
QWidget#sidebar {{ background-color: {c['surface']}; border-right: 1px solid {c['border']}; }}
QWidget#sidebar QLabel {{ background: transparent; }}

QListWidget#steps {{ background-color: {c['surface']}; border: none; outline: 0; padding: 4px 8px; }}
QListWidget#steps::item {{ padding: 10px 12px; margin: 2px 0; border-radius: 8px; color: {c['text']}; }}
QListWidget#steps::item:hover {{ background-color: {c['surface_alt']}; }}
QListWidget#steps::item:selected {{ background-color: {c['accent']}; color: white; }}
QListWidget#steps::item:disabled {{ color: {c['disabled']}; background: transparent; }}

QPushButton {{ background-color: {c['surface_alt']}; color: {c['text']}; border: 1px solid {c['border']};
    border-radius: 8px; padding: 8px 16px; }}
QPushButton:hover {{ border-color: {c['accent']}; }}
QPushButton:pressed {{ background-color: {c['surface']}; }}
QPushButton:disabled {{ color: {c['disabled']}; border-color: {c['border']}; background-color: {c['surface']}; }}
QPushButton#primary {{ background-color: {c['accent']}; border: 1px solid {c['accent']}; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background-color: {c['accent_hover']}; }}
QPushButton#primary:pressed {{ background-color: {c['accent_pressed']}; }}
QPushButton#primary:disabled {{ background-color: {c['surface_alt']}; border-color: {c['border']}; color: {c['disabled']}; }}

QLineEdit, QComboBox, QSpinBox {{ background-color: {c['surface']}; border: 1px solid {c['border']};
    border-radius: 8px; padding: 7px 10px; selection-background-color: {c['accent']}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {c['accent']}; }}
QLineEdit:read-only {{ color: {c['muted']}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background-color: {c['surface']}; border: 1px solid {c['border']};
    selection-background-color: {c['accent']}; outline: 0; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 18px; border: none; background: transparent; }}

QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {c['border']};
    background-color: {c['surface']}; }}
QCheckBox::indicator:checked {{ background-color: {c['accent']}; border-color: {c['accent']}; }}
QCheckBox::indicator:disabled {{ background-color: {c['surface_alt']}; }}

QListWidget {{ background-color: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 4px; }}
QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background-color: {c['accent']}; color: white; }}

QTableWidget {{ background-color: {c['surface']}; alternate-background-color: {c['surface_alt']};
    border: 1px solid {c['border']}; border-radius: 8px; gridline-color: {c['border']};
    selection-background-color: {c['accent']}; selection-color: white; }}
QTableWidget::item {{ padding: 4px 8px; }}
QHeaderView::section {{ background-color: {c['surface_alt']}; color: {c['muted']}; padding: 8px;
    border: none; border-bottom: 1px solid {c['border']}; border-right: 1px solid {c['border']}; font-weight: 600; }}
QTableCornerButton::section {{ background-color: {c['surface_alt']}; border: none; }}

QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 8px; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {c['muted']}; padding: 9px 16px; margin-right: 4px;
    border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
QTabBar::tab:hover {{ color: {c['text']}; }}

QDialog {{ background-color: {c['background']}; }}
QTextEdit {{ background-color: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px;
    font-family: "Consolas", "Segoe UI", monospace; font-size: 9pt; }}
QProgressBar {{ background-color: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px;
    text-align: center; min-height: 18px; }}
QProgressBar::chunk {{ background-color: {c['accent']}; border-radius: 7px; }}
QMessageBox {{ background-color: {c['background']}; }}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {c['disabled']}; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 5px; min-width: 28px; }}
QScrollBar::handle:horizontal:hover {{ background: {c['disabled']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""


def apply_theme(app) -> None:
    """Apply the dark theme to a QApplication."""
    from PySide6.QtGui import QColor, QFont, QPalette

    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: COLORS["background"],
        QPalette.ColorRole.WindowText: COLORS["text"],
        QPalette.ColorRole.Base: COLORS["surface"],
        QPalette.ColorRole.AlternateBase: COLORS["surface_alt"],
        QPalette.ColorRole.Text: COLORS["text"],
        QPalette.ColorRole.Button: COLORS["surface_alt"],
        QPalette.ColorRole.ButtonText: COLORS["text"],
        QPalette.ColorRole.Highlight: COLORS["accent"],
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: COLORS["surface_alt"],
        QPalette.ColorRole.ToolTipText: COLORS["text"],
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setFont(QFont(FONT_FAMILY, 10))
    app.setStyleSheet(stylesheet())
