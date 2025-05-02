"""
This module contains the XTREAMDialog class, 
which is used to get XTREAM service credentials from the user.
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt6.QtCore import Qt

class XTREAMDialog(QDialog):
    """Dialog for entering XTREAM service credentials."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.username = ""
        self.password = ""
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("XTREAM Credentials")
        self.setModal(True)
        
        # Create layouts
        main_layout = QVBoxLayout()
        form_layout = QVBoxLayout()
        button_layout = QHBoxLayout()
        
        # Username field
        username_label = QLabel("Username:")
        self.username_edit = QLineEdit()
        form_layout.addWidget(username_label)
        form_layout.addWidget(self.username_edit)
        
        # Password field
        password_label = QLabel("Password:")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addWidget(password_label)
        form_layout.addWidget(self.password_edit)
        
        # Buttons
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        # Add layouts to main layout
        main_layout.addLayout(form_layout)
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
    def accept(self):
        """Handle dialog acceptance."""
        self.username = self.username_edit.text()
        self.password = self.password_edit.text()
        super().accept() 