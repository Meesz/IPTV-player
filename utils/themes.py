"""
This module provides utilities for managing themes.
It defines the Themes class, which can get the CSS for the dark and light themes.
"""


class Themes:
    """Utility class for managing themes."""

    @staticmethod
    def get_dark_theme() -> str:
        """Get the CSS for the dark theme."""
        return """
            /* Main Window */
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            
            /* Buttons */
            QPushButton {
                background-color: #313244;
                border: 1px solid #45475a;
                padding: 8px 16px;
                border-radius: 6px;
                color: #cdd6f4;
                font-weight: 600;
                min-width: 80px;
                font-size: 13px;
            }
            
            QPushButton:hover {
                background-color: #45475a;
                border: 1px solid #585b70;
            }
            
            QPushButton:pressed {
                background-color: #585b70;
                transform: translateY(1px);
            }
            
            QPushButton:checked {
                background-color: #89b4fa;
                color: #1e1e2e;
                border: none;
            }
            
            /* Search and Input Fields */
            QLineEdit {
                background-color: #313244;
                border: 2px solid #45475a;
                padding: 8px 12px;
                border-radius: 8px;
                color: #cdd6f4;
                selection-background-color: #45475a;
                font-size: 13px;
            }
            
            QLineEdit:focus {
                border: 2px solid #89b4fa;
            }
            
            /* Dropdown */
            QComboBox {
                background-color: #313244;
                border: 2px solid #45475a;
                padding: 8px;
                border-radius: 8px;
                color: #cdd6f4;
                min-width: 150px;
                font-size: 13px;
            }
            
            QComboBox:hover {
                border: 2px solid #89b4fa;
            }
            
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            
            /* Lists */
            QListWidget {
                background-color: #313244;
                border: 2px solid #45475a;
                border-radius: 8px;
                color: #cdd6f4;
                padding: 8px;
                font-size: 13px;
            }
            
            QListWidget::item {
                padding: 10px;
                border-radius: 4px;
                margin: 2px;
            }
            
            QListWidget::item:hover {
                background-color: #45475a;
            }
            
            QListWidget::item:selected {
                background-color: #89b4fa;
                color: #1e1e2e;
            }
            
            /* Volume Slider */
            QSlider::groove:horizontal {
                background-color: #45475a;
                height: 6px;
                border-radius: 3px;
            }
            
            QSlider::handle:horizontal {
                background-color: #89b4fa;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            
            QSlider::handle:horizontal:hover {
                background-color: #b4befe;
            }
            
            /* EPG Widget */
            QFrame#epg_widget {
                background-color: #313244;
                border: 2px solid #45475a;
                border-radius: 12px;
                padding: 16px;
            }
            
            /* Labels */
            QLabel {
                padding: 4px;
                font-size: 13px;
            }
            
            QLabel#current_title {
                font-size: 16px;
                font-weight: bold;
                color: #89b4fa;
            }
            
            QLabel#current_time {
                color: #bac2de;
                font-size: 13px;
            }
            
            /* Tabs */
            QTabWidget::pane {
                border: 2px solid #45475a;
                border-radius: 8px;
                background-color: #313244;
            }
            
            QTabBar::tab {
                background-color: #313244;
                color: #cdd6f4;
                padding: 8px 16px;
                margin: 2px;
                border-radius: 6px;
                font-size: 13px;
            }
            
            QTabBar::tab:selected {
                background-color: #89b4fa;
                color: #1e1e2e;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #45475a;
            }
            
            /* Scrollbars */
            QScrollBar:vertical {
                border: none;
                background-color: #313244;
                width: 12px;
                border-radius: 6px;
                margin: 0;
            }

            QScrollBar::handle:vertical {
                background-color: #45475a;
                border-radius: 6px;
                min-height: 30px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #585b70;
            }
            
            /* Menu Bar */
            QMenuBar {
                background-color: #1e1e2e;
                color: #cdd6f4;
                padding: 4px;
                font-size: 13px;
            }
            
            QMenuBar::item:selected {
                background-color: #313244;
                border-radius: 4px;
            }
            
            QMenu {
                background-color: #313244;
                border: 2px solid #45475a;
                border-radius: 8px;
                padding: 4px;
            }
            
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
            }
            
            QMenu::item:selected {
                background-color: #89b4fa;
                color: #1e1e2e;
            }
        """

    @staticmethod
    def get_light_theme() -> str:
        """Get the CSS for the light theme."""
        return """
            QMainWindow, QWidget {
                background-color: #f5f5f5;
                color: #333333;
            }
            
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #dddddd;
                padding: 8px 16px;
                border-radius: 4px;
                color: #333333;
                font-weight: 500;
                min-width: 80px;
            }
            
            QPushButton:hover {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
            }
            
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
            
            QPushButton:checked {
                background-color: #e0e0e0;
                border: 2px solid #999999;
            }
            
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #dddddd;
                padding: 8px 12px;
                border-radius: 4px;
                color: #333333;
                selection-background-color: #e0e0e0;
            }
            
            QLineEdit:focus {
                border: 2px solid #999999;
            }
            
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #dddddd;
                padding: 8px;
                border-radius: 4px;
                color: #333333;
                min-width: 120px;
            }
            
            QComboBox:hover {
                border: 1px solid #cccccc;
            }
            
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #dddddd;
                border-radius: 4px;
                color: #333333;
                padding: 4px;
            }
            
            QListWidget::item {
                padding: 8px;
                border-radius: 2px;
            }
            
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
            
            QListWidget::item:selected {
                background-color: #e0e0e0;
            }
            
            QSlider::groove:horizontal {
                background-color: #dddddd;
                height: 4px;
                border-radius: 2px;
            }
            
            QSlider::handle:horizontal {
                background-color: #ffffff;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
                border: 1px solid #cccccc;
            }
            
            QSlider::handle:horizontal:hover {
                background-color: #f0f0f0;
                border: 1px solid #bbbbbb;
            }
            
            QFrame#epg_widget {
                background-color: #ffffff;
                border: 1px solid #dddddd;
                border-radius: 4px;
                padding: 12px;
            }
            
            QLabel {
                padding: 4px;
            }
            
            QLabel#current_title {
                font-size: 14px;
                font-weight: bold;
                color: #333333;
            }
            
            QLabel#current_time {
                color: #666666;
            }
        """
