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
            QMainWindow, QWidget {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            
            QPushButton {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                padding: 8px 16px;
                border-radius: 4px;
                color: #ffffff;
                font-weight: 500;
                min-width: 80px;
            }
            
            QPushButton:hover {
                background-color: #404040;
                border: 1px solid #505050;
            }
            
            QPushButton:pressed {
                background-color: #505050;
            }
            
            QPushButton:checked {
                background-color: #404040;
                border: 2px solid #666666;
            }
            
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                padding: 8px 12px;
                border-radius: 4px;
                color: #ffffff;
                selection-background-color: #404040;
            }
            
            QLineEdit:focus {
                border: 2px solid #666666;
            }
            
            QComboBox {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                padding: 8px;
                border-radius: 4px;
                color: #ffffff;
                min-width: 120px;
            }
            
            QComboBox:hover {
                border: 1px solid #505050;
            }
            
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 4px;
                color: #ffffff;
                padding: 4px;
            }
            
            QListWidget::item {
                padding: 8px;
                border-radius: 2px;
            }
            
            QListWidget::item:hover {
                background-color: #383838;
            }
            
            QListWidget::item:selected {
                background-color: #404040;
            }
            
            QSlider::groove:horizontal {
                background-color: #404040;
                height: 4px;
                border-radius: 2px;
            }
            
            QSlider::handle:horizontal {
                background-color: #666666;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            
            QSlider::handle:horizontal:hover {
                background-color: #808080;
            }
            
            QFrame#epg_widget {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 12px;
            }
            
            QLabel {
                padding: 4px;
            }
            
            QLabel#current_title {
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
            }
            
            QLabel#current_time {
                color: #aaaaaa;
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
