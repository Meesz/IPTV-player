"""
Module containing the SearchBar widget for the IPTV Player.
"""

# pylint: disable=no-name-in-module
from PyQt6.QtWidgets import QLineEdit
from utils.styles import SearchBarStyle


class SearchBar(QLineEdit):
    """A custom search bar widget with styled appearance."""

    def __init__(self):
        super().__init__()
        self.setPlaceholderText("🔍 Search channels...")
        self.setStyleSheet(SearchBarStyle.SEARCH_BAR)
