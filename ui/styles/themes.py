from typing import ClassVar


class Themes:
    """Utility class for managing themes."""

    _DARK: ClassVar[dict[str, str]] = {
        "window_start": "#081216",
        "window_end": "#132029",
        "text": "#edf5f7",
        "muted": "#89a2af",
        "panel": "#15232d",
        "panel_alt": "#1a2b36",
        "card": "#203440",
        "border": "#2d4958",
        "border_soft": "#243b48",
        "accent": "#4ad7c4",
        "accent_strong": "#1fb9a6",
        "accent_text": "#062c29",
        "accent_soft": "#183e43",
        "warning": "#f1b766",
        "error": "#f26d78",
        "success": "#71d6a4",
        "surface": "rgba(10, 18, 22, 0.26)",
        "surface_hover": "rgba(37, 65, 80, 0.30)",
        "selection": "#244a56",
        "input": "#1b2b35",
        "tab": "#10202a",
        "tab_active": "#1d3642",
        "tab_text_muted": "#7e95a1",
        "toolbar": "rgba(12, 22, 28, 0.82)",
        "overlay": "rgba(5, 12, 16, 0.76)",
    }

    _LIGHT: ClassVar[dict[str, str]] = {
        "window_start": "#f6fbfc",
        "window_end": "#e8f1f4",
        "text": "#20313b",
        "muted": "#627986",
        "panel": "#ffffff",
        "panel_alt": "#f4f8fa",
        "card": "#eef5f8",
        "border": "#cddbe2",
        "border_soft": "#dbe7ec",
        "accent": "#0c7a6d",
        "accent_strong": "#0f8477",
        "accent_text": "#ffffff",
        "accent_soft": "#d8f3ef",
        "warning": "#8a5f17",
        "error": "#b23a4a",
        "success": "#1f7a4d",
        "surface": "rgba(18, 48, 64, 0.04)",
        "surface_hover": "rgba(18, 48, 64, 0.08)",
        "selection": "#d7efea",
        "input": "#ffffff",
        "tab": "#edf4f7",
        "tab_active": "#ffffff",
        "tab_text_muted": "#5a6f7c",
        "toolbar": "rgba(255, 255, 255, 0.88)",
        "overlay": "rgba(238, 245, 248, 0.86)",
    }

    @classmethod
    def get_dark_theme(cls) -> str:
        return cls._build_theme(cls._DARK)

    @classmethod
    def get_light_theme(cls) -> str:
        return cls._build_theme(cls._LIGHT)

    @classmethod
    def tokens(cls, mode: str) -> dict:
        return cls._LIGHT if mode == "light" else cls._DARK

    @staticmethod
    def _build_theme(tokens: dict[str, str]) -> str:
        return """
            QMainWindow#main_window {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {window_start},
                    stop: 1 {window_end}
                );
            }}

            QDialog#playlist_dialog,
            QDialog#xtream_source_dialog {{
                background-color: {panel};
                border: 1px solid {border_soft};
            }}

            QWidget {{
                color: {text};
                font-size: 13px;
                background: transparent;
            }}

            QWidget#content_shell {{
                background: transparent;
            }}

            QFrame#library_panel,
            QFrame#player_panel,
            QFrame#filter_card,
            QFrame#now_playing_card,
            QFrame#player_surface,
            QFrame#control_bar,
            QFrame#epg_widget,
            QFrame#playlist_dialog_card,
            QFrame#playlist_detail_card,
            QFrame#collection_state,
            QFrame#busy_overlay_card {{
                background-color: {panel};
                border: 1px solid {border_soft};
                border-radius: 18px;
            }}

            QFrame#player_surface {{
                background-color: {panel_alt};
                border: 1px solid {border};
            }}

            QFrame#control_bar,
            QFrame#filter_card,
            QFrame#playlist_detail_card,
            QFrame#collection_state {{
                background-color: {panel_alt};
            }}

            QFrame#collection_state {{
                border-style: dashed;
            }}

            QFrame#busy_overlay {{
                background-color: {overlay};
                border: none;
            }}

            QToolBar#main_toolbar {{
                spacing: 12px;
                padding: 10px 14px;
                border: 1px solid {border_soft};
                border-radius: 16px;
                background: {toolbar};
            }}

            QLabel#section_title,
            QLabel#dialog_title,
            QLabel#panel_heading,
            QLabel#current_title,
            QLabel#busy_title {{
                font-size: 16px;
                font-weight: 700;
                color: {text};
            }}

            QLabel#player_channel_title {{
                font-size: 24px;
                font-weight: 700;
                color: {text};
                padding: 0;
            }}

            QLabel#player_program_title {{
                font-size: 15px;
                font-weight: 600;
                color: {text};
                padding: 0;
            }}

            QLabel#player_meta,
            QLabel#current_time,
            QLabel#epg_status,
            QLabel#playlist_detail_label,
            QLabel#placeholder_hint,
            QLabel#state_detail,
            QLabel#playlist_feedback,
            QLabel#channel_row_subtitle,
            QLabel#channel_row_meta,
            QLabel#busy_detail {{
                color: {muted};
                padding: 0;
            }}

            QLabel#state_title,
            QLabel#channel_row_title {{
                font-weight: 700;
                color: {text};
            }}

            QLabel#status_chip,
            QLabel#playlist_status_chip,
            QLabel#epg_status_chip,
            QLabel#playback_state_chip {{
                background-color: {accent_soft};
                color: {accent};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 6px 12px;
                font-weight: 700;
            }}

            QLabel#playlist_status_chip[stateTone="warning"],
            QLabel#epg_status_chip[stateTone="warning"],
            QLabel#playback_state_chip[stateTone="warning"] {{
                color: {warning};
            }}

            QLabel#playlist_status_chip[stateTone="error"],
            QLabel#epg_status_chip[stateTone="error"],
            QLabel#playback_state_chip[stateTone="error"] {{
                color: {error};
            }}

            QLabel#playlist_status_chip[stateTone="success"],
            QLabel#epg_status_chip[stateTone="success"],
            QLabel#playback_state_chip[stateTone="success"] {{
                color: {success};
            }}

            QLineEdit,
            QComboBox,
            QListWidget,
            QListView,
            QTabWidget::pane,
            QScrollArea {{
                background-color: {input};
                border: 1px solid {border_soft};
                border-radius: 14px;
            }}

            QLineEdit {{
                padding: 10px 14px;
                color: {text};
                selection-background-color: {selection};
            }}

            QLineEdit:focus,
            QComboBox:focus {{
                border: 1px solid {accent};
            }}

            QComboBox {{
                padding: 9px 12px;
                min-height: 20px;
            }}

            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}

            QPushButton {{
                background-color: {card};
                border: 1px solid {border_soft};
                border-radius: 14px;
                padding: 10px 16px;
                color: {text};
                font-weight: 600;
                min-width: 82px;
            }}

            QPushButton:hover {{
                background-color: {surface_hover};
                border: 1px solid {border};
            }}

            QPushButton:pressed {{
                background-color: {selection};
            }}

            QPushButton[accent="true"] {{
                background-color: {accent};
                color: {accent_text};
                border: 1px solid {accent_strong};
            }}

            QPushButton[accent="true"]:hover {{
                background-color: {accent_strong};
            }}

            QPushButton[ghost="true"] {{
                background-color: transparent;
                color: {muted};
            }}

            QPushButton:disabled {{
                color: {tab_text_muted};
                background-color: {surface};
            }}

            QTabBar::tab {{
                background-color: {tab};
                color: {tab_text_muted};
                border: 1px solid {border_soft};
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                padding: 10px 16px;
                margin-right: 6px;
                min-width: 88px;
                font-weight: 600;
            }}

            QTabBar::tab:selected {{
                background-color: {tab_active};
                color: {text};
                border: 1px solid {border};
            }}

            QListWidget,
            QListView {{
                padding: 8px;
                outline: none;
            }}

            QListWidget::item {{
                background-color: {surface};
                border: 1px solid transparent;
                border-radius: 14px;
                padding: 12px;
                margin: 4px 0;
            }}

            QListWidget::item:hover {{
                background-color: {surface_hover};
                border: 1px solid {border_soft};
            }}

            QListWidget::item:selected {{
                background-color: {selection};
                border: 1px solid {accent};
            }}

            QFrame#channel_row {{
                background-color: {surface};
                border: 1px solid {border_soft};
                border-radius: 14px;
            }}

            QFrame#channel_row[selected="true"] {{
                background-color: {selection};
                border: 1px solid {accent};
            }}

            QLabel#channel_logo {{
                background-color: {panel_alt};
                border: 1px solid {border_soft};
                border-radius: 12px;
            }}

            QLabel#channel_badge {{
                background-color: {accent_soft};
                color: {accent};
                border-radius: 10px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            }}

            QLabel#channel_badge[badgeTone="warning"] {{
                color: {warning};
            }}

            QLabel#channel_badge[badgeTone="accent"] {{
                color: {accent};
            }}

            QLabel#playlist_feedback[stateTone="error"] {{
                color: {error};
            }}

            QLabel#playlist_feedback[stateTone="warning"] {{
                color: {warning};
            }}

            QLabel#playlist_feedback[stateTone="ready"] {{
                color: {success};
            }}

            QSlider::groove:horizontal {{
                background-color: {surface};
                border-radius: 6px;
                height: 8px;
            }}

            QProgressBar#busy_progress {{
                background-color: {surface};
                border: 1px solid {border_soft};
                border-radius: 8px;
                min-height: 12px;
            }}

            QProgressBar#busy_progress::chunk {{
                background-color: {accent};
                border-radius: 7px;
            }}

            QSlider::handle:horizontal {{
                background-color: {accent};
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }}

            QLabel#player_placeholder {{
                color: {muted};
                font-size: 18px;
                font-weight: 600;
                padding: 16px;
            }}

            QLabel#player_overlay {{
                background-color: {overlay};
                border: 1px solid {border};
                border-radius: 16px;
                color: {text};
                font-weight: 700;
                padding: 12px 18px;
            }}

            QLabel#notification_toast {{
                border-radius: 14px;
                padding: 12px 16px;
                font-weight: 700;
            }}

            QLabel#notification_toast[stateTone="info"] {{
                background-color: #183742;
                border: 1px solid #2e6e80;
                color: #edf5f7;
            }}

            QLabel#notification_toast[stateTone="success"] {{
                background-color: #17392d;
                border: 1px solid #2b8b68;
                color: #effaf5;
            }}

            QLabel#notification_toast[stateTone="warning"] {{
                background-color: #43331a;
                border: 1px solid #b07f32;
                color: #fff3de;
            }}

            QLabel#notification_toast[stateTone="error"] {{
                background-color: #482028;
                border: 1px solid #b14858;
                color: #fff1f3;
            }}

            QMenu {{
                background-color: {panel};
                border: 1px solid {border};
                padding: 8px;
            }}

            QMenu::item {{
                padding: 8px 16px;
                border-radius: 8px;
            }}

            QMenu::item:selected {{
                background-color: {surface_hover};
            }}

            QPushButton:focus {{
                border: 2px solid {accent};
                padding: 9px 15px;
            }}

            QPushButton:checked {{
                background-color: {accent_soft};
                color: {accent};
                border: 1px solid {accent};
            }}

            QPushButton:checked:hover {{
                background-color: {selection};
            }}

            QListView:focus, QListWidget:focus {{
                border: 1px solid {accent};
            }}

            QTabBar::tab:focus {{
                border: 1px solid {accent};
            }}

            QCheckBox:focus {{
                outline: 1px solid {accent};
            }}

            QSlider::handle:horizontal:focus {{
                background-color: {accent_strong};
            }}

            QSplitter::handle:horizontal {{
                width: 10px;
                background: transparent;
            }}

            QSplitter::handle:horizontal:hover {{
                background: {surface_hover};
                border-radius: 4px;
            }}

            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 4px;
            }}

            QScrollBar::handle:vertical {{
                background: {border};
                border-radius: 5px;
                min-height: 32px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: {accent};
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}

            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}

            QFrame#player_video_surface {{
                background-color: #000000;
                border: none;
                border-radius: 14px;
            }}
        """.format(**tokens)
