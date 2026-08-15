"""Plaintext provider configuration stored beside the application bundle."""

import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from .models import Provider


class StorageError(RuntimeError):
    pass


def runtime_dir() -> Path:
    """Return the directory beside the app bundle, or the project root in development."""
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        for parent in executable.parents:
            if parent.suffix == ".app":
                return parent.parent
        return executable.parent
    return Path(__file__).resolve().parents[1]


def app_data_dir() -> Path:
    return runtime_dir() / "data"


class ProviderRepository:
    """Stores complete provider configuration, including API keys, in one JSON file."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or app_data_dir() / "providers.json"

    def list(self) -> List[Provider]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return [Provider.from_dict(item) for item in raw.get("providers", [])]
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError("Provider configuration is invalid: {0}".format(exc)) from exc

    def save_all(self, providers: List[Provider]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        payload = {"version": 1, "providers": [provider.to_dict() for provider in providers]}
        try:
            temporary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary_path, self.path)
        except OSError as exc:
            raise StorageError("Could not save provider configuration: {0}".format(exc)) from exc
