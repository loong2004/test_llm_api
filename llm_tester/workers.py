"""Qt worker objects that keep network I/O outside the GUI thread."""

import json
from typing import List

from PySide6.QtCore import QObject, Signal, Slot

from .adapters import adapter_for
from .models import Message, Provider, RequestSettings, StreamEvent


class FetchModelsWorker(QObject):
    completed = Signal(list, str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, provider: Provider, api_key: str) -> None:
        super().__init__()
        self.provider = provider
        self.api_key = api_key

    @Slot()
    def run(self) -> None:
        try:
            result = adapter_for(self.provider).fetch_models(self.provider, self.api_key)
            self.completed.emit(result.models, json.dumps(result.raw, ensure_ascii=False, indent=2))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class ChatWorker(QObject):
    delta = Signal(str)
    raw = Signal(str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self, provider: Provider, api_key: str, messages: List[Message], settings: RequestSettings
    ) -> None:
        super().__init__()
        self.provider = provider
        self.api_key = api_key
        self.messages = messages
        self.settings = settings

    @Slot()
    def run(self) -> None:
        try:
            for event in adapter_for(self.provider).stream_chat(
                self.provider, self.api_key, self.messages, self.settings
            ):
                self._emit_event(event)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()

    def _emit_event(self, event: StreamEvent) -> None:
        if event.kind == "delta":
            self.delta.emit(event.text)
        elif event.kind == "raw" and event.raw is not None:
            self.raw.emit(json.dumps(event.raw, ensure_ascii=False, indent=2))
        elif event.kind == "done":
            self.completed.emit(event)
