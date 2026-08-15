import unittest

from PySide6.QtWidgets import QApplication, QLabel

from llm_tester.app import MainWindow, apply_style


class ChatUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_style(cls.app, dark=True)

    def test_user_and_streamed_assistant_messages_render_in_chat_flow(self):
        window = MainWindow()
        window._append_user_message("Hello")
        window._start_assistant_message()
        window._append_delta("Hello back")

        self.assertEqual(window.active_assistant_label.text(), "Hello back")
        self.assertEqual(len(window.chat_viewport.findChildren(QLabel, "userMessageText")), 1)
        self.assertEqual(len(window.chat_viewport.findChildren(QLabel, "assistantMessageText")), 1)
        window._clear_conversation()
        self.assertEqual(window.messages_layout.count(), 1)
        self.assertEqual(window.history, [])
        window.close()
