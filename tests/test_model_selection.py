import unittest

from PySide6.QtWidgets import QApplication

from llm_tester.app import MainWindow, apply_style


class ModelSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_style(cls.app, dark=True)

    def test_refresh_replaces_stale_manual_model_and_selects_first_result(self):
        window = MainWindow()
        window.model_select.setEditText("stale-model")
        window.current_models = ["model-b", "model-a", "model-c"]

        window._refresh_model_select()

        self.assertEqual(window.model_select.count(), 3)
        self.assertEqual(window.model_select.currentText(), "model-b")
        self.assertEqual(window.model_count.text(), "已加载 3 个模型")
        window.close()

    def test_model_search_filters_visible_models_and_reports_match_count(self):
        window = MainWindow()
        window.current_models = ["gpt-4o", "claude-3-5-sonnet", "claude-3-haiku", "deepseek-chat"]
        window._refresh_model_select()

        window.model_search.setText("CLAUDE")

        self.assertEqual(window.model_select.count(), 2)
        self.assertEqual(window.model_select.itemText(0), "claude-3-5-sonnet")
        self.assertEqual(window.model_select.itemText(1), "claude-3-haiku")
        self.assertEqual(window.model_select.currentText(), "claude-3-5-sonnet")
        self.assertEqual(window.model_count.text(), "显示 2 / 4 个模型")

        window.model_search.clear()
        self.assertEqual(window.model_select.count(), 4)
        self.assertEqual(window.model_count.text(), "已加载 4 个模型")
        window.close()

    def test_model_search_requires_all_space_separated_keywords(self):
        window = MainWindow()
        window.current_models = [
            "claude-3-5-sonnet",
            "claude-3-5-haiku",
            "claude-3-opus",
        ]
        window._refresh_model_select()

        window.model_search.setText("claude sonnet")

        self.assertEqual(window.model_select.count(), 1)
        self.assertEqual(window.model_select.currentText(), "claude-3-5-sonnet")
        self.assertEqual(window.model_count.text(), "显示 1 / 3 个模型")
        window.close()
