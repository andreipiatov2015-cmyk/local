"""Единая тема оформления GUI — плоский тёмный стиль через QSS (Qt Style
Sheets), встроенный в PyQt5, без дополнительных зависимостей.

Раньше приложение использовало платформенный стиль виджетов Qt как есть —
никакой единой темы не было, каждая вкладка выглядела как набор системных
виджетов из 90-х. QSS применяется один раз на уровне QApplication в
main_window.main(), поэтому здесь не нужно трогать ни одну вкладку."""

from __future__ import annotations

from PyQt5.QtGui import QFont

# Палитра — плоский тёмный стиль, один акцентный цвет для интерактивных
# элементов (кнопки, выбранные строки таблиц, прогресс-бары).
_BG = "#1e2129"
_BG_ALT = "#262a35"
_SURFACE = "#2d3140"
_BORDER = "#3a3f4f"
_TEXT = "#e6e8ef"
_TEXT_DIM = "#9aa0b2"
_ACCENT = "#4f8cff"
_ACCENT_HOVER = "#6b9fff"
_ACCENT_PRESSED = "#3d70d9"

STYLESHEET = f"""
* {{
    color: {_TEXT};
    font-size: 13px;
}}

QWidget {{
    background-color: {_BG};
}}

QMainWindow {{
    background-color: {_BG};
}}

QLabel {{
    background: transparent;
}}

QTabWidget::pane {{
    border: 1px solid {_BORDER};
    border-radius: 6px;
    background-color: {_BG};
    top: -1px;
}}

QTabBar::tab {{
    background-color: {_BG_ALT};
    color: {_TEXT_DIM};
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid {_BORDER};
    border-bottom: none;
}}

QTabBar::tab:selected {{
    background-color: {_SURFACE};
    color: {_TEXT};
    border-bottom: 2px solid {_ACCENT};
}}

QTabBar::tab:hover:!selected {{
    color: {_TEXT};
}}

QPushButton {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 7px 16px;
    color: {_TEXT};
}}

QPushButton:hover {{
    background-color: {_ACCENT};
    border-color: {_ACCENT};
    color: white;
}}

QPushButton:pressed {{
    background-color: {_ACCENT_PRESSED};
    border-color: {_ACCENT_PRESSED};
}}

QPushButton:disabled {{
    background-color: {_BG_ALT};
    color: {_TEXT_DIM};
    border-color: {_BORDER};
}}

QLineEdit, QComboBox, QSpinBox {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER};
    border-radius: 5px;
    padding: 5px 8px;
    selection-background-color: {_ACCENT};
}}

QLineEdit:focus, QComboBox:focus {{
    border-color: {_ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QTableWidget {{
    background-color: {_SURFACE};
    alternate-background-color: {_BG_ALT};
    gridline-color: {_BORDER};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    selection-background-color: {_ACCENT};
    selection-color: white;
}}

QHeaderView::section {{
    background-color: {_BG_ALT};
    color: {_TEXT_DIM};
    padding: 6px;
    border: none;
    border-bottom: 1px solid {_BORDER};
    border-right: 1px solid {_BORDER};
}}

QTableWidget::item {{
    padding: 4px;
}}

QProgressBar {{
    background-color: {_BG_ALT};
    border: 1px solid {_BORDER};
    border-radius: 5px;
    text-align: center;
    color: {_TEXT};
    height: 18px;
}}

QProgressBar::chunk {{
    background-color: {_ACCENT};
    border-radius: 4px;
}}

QScrollBar:vertical {{
    background: {_BG};
    width: 12px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {_BORDER};
    border-radius: 5px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {_ACCENT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QMessageBox {{
    background-color: {_BG};
}}

QToolTip {{
    background-color: {_SURFACE};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    padding: 4px;
}}
"""


def apply(app) -> None:
    """Применяет тему ко всему приложению (один вызов на QApplication)."""
    app.setStyle("Fusion")
    app.setFont(QFont("Noto Sans", 10))
    app.setStyleSheet(STYLESHEET)
