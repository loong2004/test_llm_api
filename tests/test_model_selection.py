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
