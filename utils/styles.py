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
            background-color: #313244;
            border: 2px solid #45475a;
            font-size: 13px;
            color: #cdd6f4;
        }
        QLineEdit:focus {
            border: 2px solid #89b4fa;
        }
        QLineEdit:hover {
            background-color: #45475a;
        }
    """


class ToolbarStyle:
    """Styles for the toolbar."""

    TOOLBAR = """
        QToolBar {
            spacing: 12px;
            padding: 8px 20px;
            background: transparent;
            border: none;
        }
    """
