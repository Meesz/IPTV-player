from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

CARD_WIDTH = 360


class LoadingOverlay(QFrame):
    """Blocking scrim with a compact centred card, used during long-running UI transitions."""

    cancel_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("busy_overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)

        self.card = QFrame()
        self.card.setObjectName("busy_overlay_card")
        self.card.setFixedWidth(CARD_WIDTH)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 22, 24, 20)
        card_layout.setSpacing(8)

        self.title_label = QLabel("Loading")
        self.title_label.setObjectName("busy_title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.title_label)

        self.detail_label = QLabel("Please wait.")
        self.detail_label.setObjectName("busy_detail")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setWordWrap(True)
        card_layout.addWidget(self.detail_label)

        card_layout.addSpacing(6)
        self.progress = QProgressBar()
        self.progress.setObjectName("busy_progress")
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        card_layout.addWidget(self.progress)

        card_layout.addSpacing(8)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("ghost", True)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        card_layout.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Alignment on the widget (not the layout) keeps the card compact instead of full width.
        layout.addWidget(self.card, alignment=Qt.AlignmentFlag.AlignCenter)
        self.hide()

    def show_message(self, title: str, detail: str) -> None:
        self.title_label.setText(title)
        self.detail_label.setText(detail)
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def update_detail(self, detail: str) -> None:
        self.detail_label.setText(detail)
