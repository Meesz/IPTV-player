"""
Module containing stylesheet definitions for the application.
"""


class SearchBarStyle:
    """Styles for the search bar widget."""

    SEARCH_BAR = """
        QLineEdit {
            padding: 8px 12px 8px 36px;
            border-radius: 20px;
            min-width: 250px;
            background-color: #2d2d2d;
            border: 1px solid #404040;
            font-size: 13px;
        }
        QLineEdit:focus {
            border: 1px solid #666666;
            background-color: #333333;
        }
        QLineEdit:hover {
            background-color: #333333;
        }
    """


class ToolbarStyle:
    """Styles for the toolbar."""

    TOOLBAR = """
        QToolBar {
            spacing: 10px;
            padding: 5px 15px;
            background: transparent;
        }
    """
