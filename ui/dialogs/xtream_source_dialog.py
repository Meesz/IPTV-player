from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStyle,
    QStyleOption,
    QVBoxLayout,
)

from core.models import PlaylistReference, PlaylistSourceType, XtreamCredentials


class XtreamSourceDialog(QDialog):
    """Structured form for creating or editing Xtream playlist sources."""

    def __init__(self, parent=None, reference: PlaylistReference | None = None):
        super().__init__(parent)
        self.setObjectName("xtream_source_dialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._reference = reference
        self._init_ui()
        self._populate(reference)

    def paintEvent(self, event) -> None:
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

    def _init_ui(self) -> None:
        self.setWindowTitle("Xtream Codes Source")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        hint = QLabel(
            "Enter the Xtream-compatible server URL and credentials. "
            "The password remains hidden and will be preserved if you leave it blank while editing."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(10)

        self.name_input = QLineEdit()
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("https://provider.example")
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Leave blank to keep the saved password")
        self.output_combo = QComboBox()
        self.output_combo.addItems(["ts", "m3u8"])

        form.addRow("Display name", self.name_input)
        form.addRow("Server URL", self.server_input)
        form.addRow("Username", self.username_input)
        form.addRow("Password", self.password_input)
        form.addRow("Output", self.output_combo)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setObjectName("playlist_feedback")
        self.error_label.setProperty("stateTone", "error")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, reference: PlaylistReference | None) -> None:
        if reference is None or reference.source_type != PlaylistSourceType.XTREAM:
            self.output_combo.setCurrentText("ts")
            return

        xtream = reference.xtream or XtreamCredentials("", "", "", "ts")
        self.name_input.setText(reference.name)
        self.server_input.setText(xtream.server_url)
        self.username_input.setText(xtream.username)
        self.output_combo.setCurrentText(xtream.output or "ts")

    def accept(self) -> None:
        self.error_label.clear()
        if not self.name_input.text().strip():
            self.error_label.setText("Display name is required.")
            self.name_input.setFocus()
            return
        if not self.server_input.text().strip():
            self.error_label.setText("Server URL is required.")
            self.server_input.setFocus()
            return
        if not self.username_input.text().strip():
            self.error_label.setText("Username is required.")
            self.username_input.setFocus()
            return

        preserved_password = ""
        if self._reference and self._reference.source_type == PlaylistSourceType.XTREAM and self._reference.xtream:
            preserved_password = self._reference.xtream.password
        password = self.password_input.text() or preserved_password
        if not password:
            self.error_label.setText("Password is required.")
            self.password_input.setFocus()
            return

        super().accept()

    def to_reference(self) -> PlaylistReference:
        preserved_password = ""
        if self._reference and self._reference.source_type == PlaylistSourceType.XTREAM and self._reference.xtream:
            preserved_password = self._reference.xtream.password
        password = self.password_input.text() or preserved_password
        xtream = XtreamCredentials(
            server_url=self.server_input.text().strip(),
            username=self.username_input.text().strip(),
            password=password,
            output=self.output_combo.currentText(),
        )
        base_reference = self._reference or PlaylistReference(name="", source_type=PlaylistSourceType.XTREAM)
        return PlaylistReference(
            name=self.name_input.text().strip(),
            path="",
            source_type=PlaylistSourceType.XTREAM,
            xtream=xtream,
            channel_count=base_reference.channel_count,
            last_loaded_at=base_reference.last_loaded_at,
            last_status=base_reference.last_status,
            last_error=base_reference.last_error,
        )
