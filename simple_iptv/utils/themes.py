from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

class Themes:
    @staticmethod
    def get_dark_theme() -> str:
        return """
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            
            QPushButton {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                padding: 5px 10px;
                border-radius: 3px;
                color: #ffffff;
            }
            
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            
            QPushButton:pressed {
                background-color: #4d4d4d;
            }
            
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                padding: 5px;
                border-radius: 3px;
                color: #ffffff;
            }
            
            QComboBox {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                padding: 5px;
                border-radius: 3px;
                color: #ffffff;
            }
            
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                color: #ffffff;
            }
            
            QListWidget::item:selected {
                background-color: #4d4d4d;
            }
            
            QSlider::groove:horizontal {
                background-color: #2d2d2d;
                height: 4px;
            }
            
            QSlider::handle:horizontal {
                background-color: #4d4d4d;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """
    
    @staticmethod
    def get_light_theme() -> str:
        return """
            QMainWindow, QWidget {
                background-color: #f0f0f0;
                color: #000000;
            }
            
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px 10px;
                border-radius: 3px;
                color: #000000;
            }
            
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                border-radius: 3px;
                color: #000000;
            }
            
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                padding: 5px;
                border-radius: 3px;
                color: #000000;
            }
            
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                color: #000000;
            }
            
            QListWidget::item:selected {
                background-color: #e0e0e0;
            }
            
            QSlider::groove:horizontal {
                background-color: #d0d0d0;
                height: 4px;
            }
            
            QSlider::handle:horizontal {
                background-color: #ffffff;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
                border: 1px solid #d0d0d0;
            }
        """ 