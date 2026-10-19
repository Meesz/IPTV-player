"""Category picker: search field in the popup filters items while 'All' stays pinned."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from ui.widgets.searchable_combo_box import SearchableComboBox

CATEGORIES = [
    "NL| ALGEMEEN HD/4K",
    "NL| ZIGGO ᴿᴬᵂ",
    "UK| SPORTS",
    "US| 24/7 COMEDY ᴿᴬᵂ ⁶⁰ᶠᵖˢ",
    "Netherlands Kids",
]


@pytest.fixture
def combo(qapp):
    widget = SearchableComboBox(empty_text="No matching categories", pinned_texts=("All",))
    widget.addItem("All")
    widget.addItems(CATEGORIES)
    widget.resize(300, 32)
    widget.show()
    yield widget
    widget.hidePopup()
    widget.close()
    widget.deleteLater()


def _visible_texts(combo: SearchableComboBox) -> list[str]:
    model = combo.popup_list.model()
    return [model.index(row, 0).data() for row in range(model.rowCount())]


def test_popup_opens_with_empty_search_and_all_items(combo):
    combo.showPopup()
    combo.search_field.setText("leftover")
    combo.hidePopup()

    combo.showPopup()

    assert combo.is_popup_visible()
    assert combo.search_field.text() == ""
    assert _visible_texts(combo) == ["All", *CATEGORIES]
    assert not combo.empty_label.isVisibleTo(combo.empty_label.parentWidget())


def test_filter_matches_any_part_case_insensitively_and_keeps_all(combo):
    combo.showPopup()

    combo.search_field.setText("nl")
    assert _visible_texts(combo) == ["All", "NL| ALGEMEEN HD/4K", "NL| ZIGGO ᴿᴬᵂ"]

    combo.search_field.setText("comedy")
    assert _visible_texts(combo) == ["All", "US| 24/7 COMEDY ᴿᴬᵂ ⁶⁰ᶠᵖˢ"]

    combo.search_field.setText("nether")
    assert _visible_texts(combo) == ["All", "Netherlands Kids"]


def test_no_match_shows_message(combo):
    combo.showPopup()
    combo.search_field.setText("zzz")

    assert _visible_texts(combo) == ["All"]
    assert combo.empty_label.isVisibleTo(combo.empty_label.parentWidget())

    combo.search_field.setText("uk")
    assert not combo.empty_label.isVisibleTo(combo.empty_label.parentWidget())


def test_enter_picks_first_match_and_emits_text_change(combo):
    changes: list[str] = []
    combo.currentTextChanged.connect(changes.append)
    combo.showPopup()

    QTest.keyClicks(combo.search_field, "ziggo")
    QTest.keyClick(combo.search_field, Qt.Key.Key_Return)

    assert combo.currentText() == "NL| ZIGGO ᴿᴬᵂ"
    assert changes == ["NL| ZIGGO ᴿᴬᵂ"]
    assert not combo.is_popup_visible()


def test_arrow_keys_move_through_matches(combo):
    combo.showPopup()
    QTest.keyClicks(combo.search_field, "nl")

    QTest.keyClick(combo.search_field, Qt.Key.Key_Down)
    QTest.keyClick(combo.search_field, Qt.Key.Key_Return)
    assert combo.currentText() == "NL| ZIGGO ᴿᴬᵂ"

    combo.showPopup()
    QTest.keyClicks(combo.search_field, "nl")
    QTest.keyClick(combo.search_field, Qt.Key.Key_Up)
    QTest.keyClick(combo.search_field, Qt.Key.Key_Up)
    QTest.keyClick(combo.search_field, Qt.Key.Key_Return)
    assert combo.currentText() == "All"


def test_escape_closes_without_changing_selection(combo):
    combo.setCurrentText("UK| SPORTS")
    combo.showPopup()

    QTest.keyClicks(combo.search_field, "nl")
    QTest.keyClick(combo.search_field, Qt.Key.Key_Escape)

    assert not combo.is_popup_visible()
    assert combo.currentText() == "UK| SPORTS"


def test_unfiltered_popup_highlights_current_item(combo):
    combo.setCurrentText("UK| SPORTS")
    combo.showPopup()

    assert combo.popup_list.currentIndex().data() == "UK| SPORTS"


def test_clicking_an_item_selects_it(combo):
    combo.showPopup()
    combo.search_field.setText("sports")
    view = combo.popup_list
    index = view.model().index(1, 0)

    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=view.visualRect(index).center())

    assert combo.currentText() == "UK| SPORTS"
    assert not combo.is_popup_visible()


def test_items_repopulated_after_clear_are_filterable(combo):
    combo.clear()
    combo.addItem("All")
    combo.addItems(["DE| NEWS", "FR| CINEMA"])
    combo.showPopup()

    combo.search_field.setText("news")

    assert _visible_texts(combo) == ["All", "DE| NEWS"]


def test_empty_combo_does_not_open(qapp):
    widget = SearchableComboBox()
    widget.showPopup()
    assert not widget.is_popup_visible()
    widget.deleteLater()
