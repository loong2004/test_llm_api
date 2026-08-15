"""PySide6 desktop UI for interactive model comparison."""

import sys
from typing import List, Optional

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .models import Message, MessageRole, Protocol, Provider, RequestSettings, StreamEvent
from .storage import ProviderRepository, StorageError
from .workers import ChatWorker, FetchModelsWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.repository = ProviderRepository()
        self.providers: List[Provider] = []
        self.history: List[Message] = []
        self.current_models: List[str] = []
        self.chat_thread: Optional[QThread] = None
        self.fetch_thread: Optional[QThread] = None
        self.chat_worker: Optional[ChatWorker] = None
        self.fetch_worker: Optional[FetchModelsWorker] = None
        self.pending_reply = ""
        self.active_assistant_label: Optional[QLabel] = None

        self.setWindowTitle("LLM API Lab")
        self.resize(1280, 820)
        self._build_ui()
        self._load_providers()

    def _build_ui(self) -> None:
        root = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(self._build_provider_panel())
        root.addWidget(self._build_console_panel())
        root.setSizes([382, 898])
        root.setStretchFactor(0, 0)
        root.setStretchFactor(1, 1)
        root.setCollapsible(0, False)
        root.setHandleWidth(6)
        self.setCentralWidget(root)

    def _build_provider_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("providerPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 20, 20)
        layout.setSpacing(14)

        heading = QLabel("服务商")
        heading.setObjectName("panelHeading")
        layout.addWidget(heading)

        selector_layout = QHBoxLayout()
        self.provider_select = QComboBox()
        self.provider_select.setObjectName("providerSelect")
        self.provider_select.currentIndexChanged.connect(self._select_provider)
        self.new_button = QToolButton()
        self.new_button.setText("+")
        self.new_button.setObjectName("newProviderButton")
        self.new_button.setFixedSize(36, 36)
        self.new_button.setToolTip("新建服务商")
        self.new_button.clicked.connect(self._new_provider)
        selector_layout.addWidget(self.provider_select, 1)
        selector_layout.addWidget(self.new_button)
        layout.addLayout(selector_layout)

        form_group = QGroupBox("连接配置")
        form_group.setObjectName("connectionGroup")
        form = QFormLayout(form_group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(11)
        self.provider_name = QLineEdit()
        self.protocol = QComboBox()
        self.protocol.addItem("OpenAI 兼容", Protocol.OPENAI.value)
        self.protocol.addItem("Anthropic 兼容", Protocol.ANTHROPIC.value)
        self.protocol.currentIndexChanged.connect(self._protocol_changed)
        self.base_url = QLineEdit()
        self.base_url.setPlaceholderText("https://api.openai.com/v1")
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("保存至 data/providers.json")
        reveal_key = QToolButton()
        reveal_key.setText("显示")
        reveal_key.setObjectName("revealButton")
        reveal_key.setFixedWidth(58)
        reveal_key.setToolTip("显示或隐藏 API 密钥")
        reveal_key.setCheckable(True)
        reveal_key.toggled.connect(
            lambda visible: self.api_key.setEchoMode(
                QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
            )
        )
        key_layout = QHBoxLayout()
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.addWidget(self.api_key)
        key_layout.addWidget(reveal_key)
        key_widget = QWidget()
        key_widget.setLayout(key_layout)
        form.addRow("名称", self.provider_name)
        form.addRow("协议", self.protocol)
        form.addRow("接口地址", self.base_url)
        form.addRow("API 密钥", key_widget)
        layout.addWidget(form_group)

        model_group = QGroupBox("模型")
        model_group.setObjectName("modelGroup")
        model_layout = QVBoxLayout(model_group)
        model_layout.setSpacing(10)
        self.model_search = QLineEdit()
        self.model_search.setObjectName("modelSearch")
        self.model_search.setPlaceholderText("输入关键词筛选模型")
        self.model_search.setClearButtonEnabled(True)
        self.model_search.textChanged.connect(self._filter_model_list)
        model_layout.addWidget(self.model_search)
        self.model_select = QComboBox()
        self.model_select.setEditable(True)
        self.model_select.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.model_select.setToolTip("选择已拉取的模型，或手动输入模型名称")
        self.model_select.currentTextChanged.connect(lambda _: self._update_model_context())
        self.model_menu_button = QToolButton()
        self.model_menu_button.setObjectName("modelMenuButton")
        self.model_menu_button.setFixedSize(36, 36)
        self.model_menu_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.model_menu_button.setToolTip("展开已拉取的模型")
        self.model_menu_button.clicked.connect(self.model_select.showPopup)
        self.fetch_button = QPushButton("拉取模型")
        self.fetch_button.setObjectName("secondaryButton")
        self.fetch_button.setFixedHeight(36)
        self.fetch_button.clicked.connect(self._fetch_models)
        self.model_count = QLabel("尚未加载模型")
        self.model_count.setObjectName("modelCount")
        model_row = QHBoxLayout()
        model_row.setContentsMargins(0, 0, 0, 0)
        model_row.addWidget(self.model_select, 1)
        model_row.addWidget(self.model_menu_button)
        model_layout.addLayout(model_row)
        model_layout.addWidget(self.fetch_button)
        model_layout.addWidget(self.model_count)
        layout.addWidget(model_group)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.save_button = QPushButton("保存服务商")
        self.save_button.setObjectName("primaryButton")
        self.save_button.setFixedHeight(38)
        self.save_button.clicked.connect(self._save_provider)
        self.delete_button = QPushButton("删除")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.setFixedHeight(38)
        self.delete_button.clicked.connect(self._delete_provider)
        actions.addWidget(self.save_button)
        actions.addWidget(self.delete_button)
        layout.addLayout(actions)
        layout.addStretch(1)

        security = QLabel("服务商配置和 API 密钥保存在 data/providers.json。")
        security.setObjectName("securityNote")
        security.setWordWrap(True)
        layout.addWidget(security)
        return panel

    def _build_console_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("consolePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(34, 28, 34, 26)
        layout.setSpacing(18)

        top = QHBoxLayout()
        heading = QLabel("对话")
        heading.setObjectName("panelHeading")
        top.addWidget(heading)
        top.addStretch(1)
        self.status = QLabel("就绪", panel)
        self.status.setObjectName("statusPill")
        top.addWidget(self.status)
        layout.addLayout(top)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setObjectName("chatScroll")
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chat_viewport = QWidget()
        self.chat_viewport.setObjectName("chatViewport")
        self.messages_layout = QVBoxLayout(self.chat_viewport)
        self.messages_layout.setContentsMargins(26, 18, 26, 28)
        self.messages_layout.setSpacing(22)
        self.messages_layout.addStretch(1)
        self.chat_scroll.setWidget(self.chat_viewport)
        layout.addWidget(self.chat_scroll, 1)

        composer = QFrame()
        composer.setObjectName("composerFrame")
        composer.setMinimumHeight(148)
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(18, 16, 16, 14)
        composer_layout.setSpacing(9)
        self.user_message = QPlainTextEdit()
        self.user_message.setObjectName("composerInput")
        self.user_message.setPlaceholderText("输入消息")
        self.user_message.setMinimumHeight(92)
        composer_layout.addWidget(self.user_message)
        composer_actions = QHBoxLayout()
        composer_actions.setContentsMargins(3, 0, 0, 0)
        self.model_context = QLabel("请选择服务商和模型")
        self.model_context.setObjectName("composerContext")
        self.clear_button = QToolButton()
        self.clear_button.setObjectName("clearButton")
        self.clear_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.clear_button.setToolTip("清空对话")
        self.clear_button.clicked.connect(self._clear_conversation)
        self.send_button = QToolButton()
        self.send_button.setObjectName("sendButton")
        self.send_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.send_button.setToolTip("发送消息")
        self.send_button.clicked.connect(self._send_message)
        composer_actions.addWidget(self.model_context)
        composer_actions.addStretch(1)
        composer_actions.addWidget(self.clear_button)
        composer_actions.addWidget(self.send_button)
        composer_layout.addLayout(composer_actions)
        layout.addWidget(composer)

        return panel

    def _load_providers(self) -> None:
        try:
            self.providers = self.repository.list()
        except StorageError as exc:
            self._show_error(str(exc))
            self.providers = []
        self._refresh_provider_select()
        if self.providers:
            self.provider_select.setCurrentIndex(0)
            self._select_provider(0)
        else:
            self._new_provider()

    def _refresh_provider_select(self) -> None:
        current_id = self.provider_select.currentData()
        self.provider_select.blockSignals(True)
        self.provider_select.clear()
        for provider in self.providers:
            self.provider_select.addItem(provider.name, provider.id)
        self.provider_select.blockSignals(False)
        if current_id:
            index = self.provider_select.findData(current_id)
            if index >= 0:
                self.provider_select.setCurrentIndex(index)

    def _new_provider(self) -> None:
        self.provider_select.blockSignals(True)
        self.provider_select.setCurrentIndex(-1)
        self.provider_select.blockSignals(False)
        self.provider_name.setText("新建服务商")
        self.protocol.setCurrentIndex(0)
        self.base_url.clear()
        self.api_key.clear()
        self.current_models = []
        self._refresh_model_select()
        self._update_model_context()
        self.status.setText("新建服务商")

    def _select_provider(self, index: int) -> None:
        if index < 0 or index >= len(self.providers):
            return
        provider = self.providers[index]
        self.provider_name.setText(provider.name)
        protocol_index = self.protocol.findData(provider.protocol.value)
        self.protocol.setCurrentIndex(max(protocol_index, 0))
        self.base_url.setText(provider.base_url)
        self.current_models = provider.models[:]
        self._refresh_model_select()
        self.api_key.setText(provider.api_key)
        self._update_model_context()
        self.status.setText("已加载：{0}".format(provider.name))

    def _protocol_changed(self) -> None:
        is_openai = self.protocol.currentData() == Protocol.OPENAI.value
        self.fetch_button.setEnabled(is_openai)
        self.fetch_button.setToolTip("拉取 /models" if is_openai else "Anthropic 模型需手动输入")
        if not self.base_url.text().strip():
            self.base_url.setPlaceholderText(
                "https://api.openai.com/v1" if is_openai else "https://api.anthropic.com/v1"
            )

    def _refresh_model_select(self) -> None:
        self.model_search.blockSignals(True)
        self.model_search.clear()
        self.model_search.blockSignals(False)
        self._filter_model_list()
        self._update_model_context()

    def _filter_model_list(self, query: str = "") -> None:
        """Filter the visible list by one or more keywords without changing stored models."""
        keywords = query.casefold().split()
        previous = self.model_select.currentText().strip()
        filtered = [
            model for model in self.current_models
            if all(keyword in model.casefold() for keyword in keywords)
        ]

        self.model_select.blockSignals(True)
        self.model_select.clear()
        self.model_select.addItems(filtered)
        if filtered:
            selected_index = filtered.index(previous) if previous in filtered else 0
            self.model_select.setCurrentIndex(selected_index)
        else:
            self.model_select.setEditText("")
        self.model_select.blockSignals(False)

        if not self.current_models:
            self.model_count.setText("尚未加载模型，可手动输入模型名称")
        elif keywords:
            self.model_count.setText("显示 {0} / {1} 个模型".format(len(filtered), len(self.current_models)))
        else:
            self.model_count.setText("已加载 {0} 个模型".format(len(self.current_models)))
        self._update_model_context()

    def _draft_provider(self) -> Provider:
        current_id = self.provider_select.currentData()
        return Provider(
            id=current_id or "",
            name=self.provider_name.text().strip(),
            base_url=self.base_url.text().strip(),
            protocol=Protocol(self.protocol.currentData() or Protocol.OPENAI.value),
            models=self._models_with_current_entry(),
            api_key=self.api_key.text().strip(),
        )

    def _models_with_current_entry(self) -> List[str]:
        models = self.current_models[:]
        selected = self.model_select.currentText().strip()
        if selected and selected not in models:
            models.append(selected)
        return models

    def _save_provider(self) -> Optional[Provider]:
        provider = self._draft_provider()
        if not provider.name or not provider.base_url:
            self._show_error("请填写服务商名称和接口地址。")
            return None
        if not provider.api_key:
            self._show_error("保存服务商前请填写 API 密钥。")
            return None
        if not provider.id:
            provider = Provider(
                name=provider.name,
                base_url=provider.base_url,
                protocol=provider.protocol,
                models=provider.models,
                api_key=provider.api_key,
            )
        self.current_models = provider.models[:]
        existing_index = next((i for i, item in enumerate(self.providers) if item.id == provider.id), -1)
        if existing_index >= 0:
            self.providers[existing_index] = provider
        else:
            self.providers.append(provider)
        try:
            self.repository.save_all(self.providers)
        except StorageError as exc:
            self._show_error(str(exc))
            return None
        self._refresh_provider_select()
        self.provider_select.setCurrentIndex(self.provider_select.findData(provider.id))
        self.status.setText("已保存：{0}".format(provider.name))
        return provider

    def _delete_provider(self) -> None:
        provider_id = self.provider_select.currentData()
        if not provider_id:
            self._new_provider()
            return
        provider = next((item for item in self.providers if item.id == provider_id), None)
        if provider is None:
            return
        answer = QMessageBox.question(self, "删除服务商", "确定删除 {0} 吗？".format(provider.name))
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.providers = [item for item in self.providers if item.id != provider_id]
        try:
            self.repository.save_all(self.providers)
        except StorageError as exc:
            self._show_error(str(exc))
            return
        self._refresh_provider_select()
        self._new_provider()
        self.status.setText("服务商已删除")

    def _fetch_models(self) -> None:
        if self.protocol.currentData() != Protocol.OPENAI.value:
            self._show_error("只有 OpenAI 兼容协议支持标准 /models 接口。")
            return
        provider = self._draft_provider()
        api_key = self.api_key.text().strip()
        if not provider.base_url or not api_key:
            self._show_error("拉取模型前请填写接口地址和 API 密钥。")
            return
        # A refresh is authoritative: do not keep stale or manually entered models.
        self.current_models = []
        self._refresh_model_select()
        self.fetch_button.setEnabled(False)
        self.status.setText("正在拉取模型...")
        worker = FetchModelsWorker(provider, api_key)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._models_fetched)
        worker.failed.connect(self._worker_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._fetch_finished)
        self.fetch_thread = thread
        self.fetch_worker = worker
        thread.start()

    def _models_fetched(self, models: List[str], _raw: str) -> None:
        self.current_models = models
        self._refresh_model_select()
        self.status.setText("已拉取 {0} 个模型".format(len(models)))

    def _fetch_finished(self) -> None:
        self.fetch_button.setEnabled(self.protocol.currentData() == Protocol.OPENAI.value)
        self.fetch_thread = None
        self.fetch_worker = None

    def _send_message(self) -> None:
        provider = self._provider_for_request()
        if provider is None:
            return
        text = self.user_message.toPlainText().strip()
        model = self.model_select.currentText().strip()
        if not text or not model:
            self._show_error("请选择模型并输入消息。")
            return
        api_key = self.api_key.text().strip()
        if not api_key:
            self._show_error("请填写 API 密钥。")
            return
        self.history.append(Message(MessageRole.USER, text))
        self.pending_reply = ""
        self.user_message.clear()
        self._append_user_message(text)
        self._start_assistant_message()
        self.model_context.setText("{0} / {1}".format(provider.name, model))
        self.status.setText("正在请求...")
        self.send_button.setEnabled(False)
        self.clear_button.setEnabled(False)

        settings = RequestSettings(model=model, stream=True)
        worker = ChatWorker(provider, api_key, self.history[:], settings)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.delta.connect(self._append_delta)
        worker.completed.connect(self._chat_completed)
        worker.failed.connect(self._worker_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._chat_finished)
        self.chat_thread = thread
        self.chat_worker = worker
        thread.start()

    def _provider_for_request(self) -> Optional[Provider]:
        provider = self._draft_provider()
        if not provider.name or not provider.base_url:
            self._show_error("请选择或新建包含接口地址的服务商。")
            return None
        return provider

    def _append_delta(self, text: str) -> None:
        self.pending_reply += text
        if self.active_assistant_label is not None:
            self.active_assistant_label.setText(self.pending_reply)
        self._scroll_chat_to_bottom()

    def _chat_completed(self, _event: StreamEvent) -> None:
        if self.pending_reply:
            self.history.append(Message(MessageRole.ASSISTANT, self.pending_reply))
        self.status.setText("已完成")

    def _chat_finished(self) -> None:
        self.send_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.chat_thread = None
        self.chat_worker = None

    def _worker_failed(self, message: str) -> None:
        self.status.setText("请求失败")
        if self.active_assistant_label is not None and not self.pending_reply:
            self.active_assistant_label.setText("请求失败：{0}".format(message))
        self._show_error(message)

    def _clear_conversation(self) -> None:
        self.history = []
        self.pending_reply = ""
        self.active_assistant_label = None
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.status.setText("对话已清空")

    def _update_model_context(self) -> None:
        if not hasattr(self, "model_context"):
            return
        provider_name = self.provider_name.text().strip()
        model_name = self.model_select.currentText().strip()
        if provider_name and model_name:
            self.model_context.setText("{0} / {1}".format(provider_name, model_name))
        else:
            self.model_context.setText("请选择服务商和模型")

    def _append_user_message(self, text: str) -> None:
        row = QWidget()
        row.setObjectName("userMessageRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addStretch(1)
        bubble = QFrame()
        bubble.setObjectName("userBubble")
        bubble.setMaximumWidth(720)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(16, 11, 16, 11)
        content = QLabel(text)
        content.setObjectName("userMessageText")
        content.setWordWrap(True)
        content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble_layout.addWidget(content)
        row_layout.addWidget(bubble)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)
        self._scroll_chat_to_bottom()

    def _start_assistant_message(self) -> None:
        message = QFrame()
        message.setObjectName("assistantMessage")
        message.setMaximumWidth(920)
        message_layout = QVBoxLayout(message)
        message_layout.setContentsMargins(2, 2, 2, 2)
        message_layout.setSpacing(0)
        content = QLabel("正在思考...")
        content.setObjectName("assistantMessageText")
        content.setWordWrap(True)
        content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        message_layout.addWidget(content)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, message)
        self.active_assistant_label = content
        self._scroll_chat_to_bottom()

    def _scroll_chat_to_bottom(self) -> None:
        QTimer.singleShot(0, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "LLM API Lab", message)


def _is_dark_mode(application: QApplication) -> bool:
    scheme = application.styleHints().colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return True
    if scheme == Qt.ColorScheme.Light:
        return False
    return application.palette().color(QPalette.ColorRole.Window).lightness() < 128


def _theme_palette(dark: bool) -> QPalette:
    colors = (
        {
            "window": "#161819", "surface": "#202326", "base": "#1a1d1f", "input": "#141617",
            "text": "#f1f4f2", "muted": "#aab3ad", "border": "#383e3a", "accent": "#35b978",
            "accent_text": "#07150d", "disabled": "#69716c",
        }
        if dark
        else {
            "window": "#f5f7f5", "surface": "#ffffff", "base": "#eef1ef", "input": "#ffffff",
            "text": "#17211b", "muted": "#66736a", "border": "#d5dcd7", "accent": "#1b8d58",
            "accent_text": "#ffffff", "disabled": "#9da7a0",
        }
    )
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["input"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["base"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["surface"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["accent_text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["surface"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(colors["disabled"]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(colors["disabled"]))
    return palette


def _theme_style(dark: bool) -> str:
    colors = (
        {
            "window": "#111315", "sidebar": "#191d1f", "surface": "#202528", "input": "#15191b",
            "text": "#f4f7f5", "muted": "#9aa7a0", "border": "#303a36", "border_focus": "#54d39a",
            "accent": "#48d597", "accent_hover": "#63e0a8", "accent_text": "#07150d", "danger": "#ff9c91",
            "hover": "#293330", "pressed": "#0d1112", "selection": "#204f3b", "scroll": "#42534b",
        }
        if dark
        else {
            "window": "#f4f7f5", "sidebar": "#e9efeb", "surface": "#ffffff", "input": "#fbfdfc",
            "text": "#16211b", "muted": "#68766e", "border": "#d0dad4", "border_focus": "#188b58",
            "accent": "#188b58", "accent_hover": "#147447", "accent_text": "#ffffff", "danger": "#b42318",
            "hover": "#eef5f0", "pressed": "#e2ebe5", "selection": "#c8ecd7", "scroll": "#aabbb0",
        }
    )
    return """
        QWidget {{
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
            font-size: 13px;
            color: {text};
            background: {window};
        }}
        QMainWindow, QWidget#consolePanel {{ background: {window}; }}
        QWidget#providerPanel {{ background: {sidebar}; border-right: 1px solid {border}; }}
        QLabel {{ background: transparent; color: {text}; }}
        QLabel#panelHeading {{ font-size: 23px; font-weight: 700; color: {text}; padding-bottom: 2px; }}
        QLabel#mutedText {{ color: {muted}; font-size: 12px; }}
        QLabel#securityNote {{ color: {muted}; font-size: 11px; line-height: 1.35; padding-top: 8px; }}
        QLabel#modelCount {{ color: {muted}; font-size: 11px; padding: 1px 2px; }}
        QLabel#statusPill {{ color: {accent}; font-size: 11px; font-weight: 600; padding: 5px 10px; background: {surface}; border: 1px solid {border}; border-radius: 11px; }}
        QGroupBox {{
            background: {surface}; border: 1px solid {border}; border-radius: 10px;
            margin-top: 13px; padding: 17px 12px 13px 12px; font-weight: 600;
        }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px; color: {muted}; background: {surface}; }}
        QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            color: {text}; background: {input}; border: 1px solid {border}; border-radius: 7px; padding: 7px 9px;
            selection-background-color: {selection}; selection-color: {text};
        }}
        QLineEdit::placeholder, QPlainTextEdit::placeholder {{ color: {muted}; }}
        QLineEdit:hover, QPlainTextEdit:hover, QComboBox:hover {{ border-color: {border_focus}; }}
        QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {border_focus}; background: {surface}; }}
        QLineEdit#modelSearch {{ background: {surface}; border-color: transparent; padding-left: 9px; }}
        QLineEdit#modelSearch:hover, QLineEdit#modelSearch:focus {{ border-color: {border}; }}
        QScrollArea#chatScroll {{ border: 0; background: transparent; }}
        QWidget#chatViewport {{ background: transparent; }}
        QFrame#userBubble {{ background: {selection}; border: 1px solid {accent}; border-radius: 16px; }}
        QLabel#userMessageText {{ color: {text}; font-size: 15px; line-height: 1.5; background: transparent; }}
        QFrame#assistantMessage {{ background: transparent; border: 0; }}
        QLabel#assistantMessageText {{ color: {text}; font-size: 16px; line-height: 1.62; background: transparent; padding: 4px 3px; }}
        QFrame#composerFrame {{ background: {surface}; border: 1px solid {border}; border-radius: 16px; }}
        QFrame#composerFrame:hover {{ border-color: {border_focus}; }}
        QPlainTextEdit#composerInput {{ background: transparent; border: 0; padding: 3px 4px; font-size: 15px; line-height: 1.4; }}
        QPlainTextEdit#composerInput:focus {{ border: 0; }}
        QLabel#composerContext {{ color: {muted}; font-size: 12px; padding: 4px 5px; }}
        QComboBox::drop-down {{ width: 26px; border: 0; }}
        QComboBox QAbstractItemView {{ color: {text}; background: {surface}; border: 1px solid {border}; selection-background-color: {selection}; }}
        QPushButton, QToolButton {{
            color: {text}; background: {surface}; border: 1px solid {border}; border-radius: 7px; min-height: 20px; padding: 7px 12px;
        }}
        QPushButton:hover, QToolButton:hover {{ background: {hover}; border-color: {border_focus}; }}
        QPushButton:pressed, QToolButton:pressed {{ background: {pressed}; }}
        QPushButton:disabled, QToolButton:disabled {{ color: {muted}; background: {window}; border-color: {border}; }}
        QPushButton#primaryButton {{ color: {accent_text}; background: {accent}; border-color: {accent}; font-weight: 700; min-width: 130px; }}
        QPushButton#primaryButton:hover {{ background: {accent_hover}; border-color: {accent_hover}; }}
        QPushButton#secondaryButton {{ background: transparent; border-color: {border}; font-weight: 600; }}
        QPushButton#secondaryButton:hover {{ background: {hover}; border-color: {border_focus}; }}
        QPushButton#dangerButton {{ color: {danger}; background: transparent; }}
        QToolButton {{ min-width: 20px; padding: 5px 8px; }}
        QToolButton#newProviderButton, QToolButton#modelMenuButton {{ color: {accent}; background: {surface}; font-size: 17px; font-weight: 600; padding: 0; }}
        QToolButton#revealButton {{ font-size: 12px; padding: 0 7px; }}
        QToolButton#sendButton {{
            min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px;
            padding: 0; border-radius: 20px; color: {accent_text}; background: {accent}; border-color: {accent};
        }}
        QToolButton#sendButton:hover {{ background: {accent_hover}; border-color: {accent_hover}; }}
        QToolButton#sendButton:disabled {{ background: {border}; border-color: {border}; color: {muted}; }}
        QToolButton#clearButton {{
            min-width: 32px; max-width: 32px; min-height: 32px; max-height: 32px;
            padding: 0; border: 0; background: transparent; color: {muted};
        }}
        QToolButton#clearButton:hover {{ background: {hover}; color: {text}; }}
        QScrollBar:vertical {{ width: 9px; background: transparent; margin: 3px; }}
        QScrollBar::handle:vertical {{ min-height: 28px; border-radius: 4px; background: {scroll}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QSplitter::handle {{ background: {border}; }}
    """.format(**colors)


def apply_style(application: QApplication, dark: Optional[bool] = None) -> None:
    """Apply a complete palette so macOS appearance changes do not mix themes."""
    active_dark = _is_dark_mode(application) if dark is None else dark
    application.setPalette(_theme_palette(active_dark))
    application.setStyleSheet(_theme_style(active_dark))


def main() -> None:
    application = QApplication(sys.argv)
    application.setStyle("Fusion")
    application.setApplicationName("LLM API Lab")
    application.setOrganizationName("LLM API Lab")
    apply_style(application)
    application.styleHints().colorSchemeChanged.connect(lambda _: apply_style(application))
    window = MainWindow()
    window.showMaximized()
    sys.exit(application.exec())


if __name__ == "__main__":
    main()
