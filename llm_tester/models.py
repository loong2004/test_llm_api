"""Domain objects shared by the UI, storage, and protocol adapters."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class Protocol(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Provider:
    name: str
    base_url: str
    protocol: Protocol = Protocol.OPENAI
    models: List[str] = field(default_factory=list)
    api_key: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not isinstance(self.protocol, Protocol):
            self.protocol = Protocol(self.protocol)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the complete provider configuration for the local data file."""
        return {
            "id": self.id,
            "name": self.name,
            "base_url": self.base_url,
            "protocol": self.protocol.value,
            "models": self.models,
            "api_key": self.api_key,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Provider":
        return cls(
            id=str(value.get("id") or uuid4()),
            name=str(value.get("name", "Untitled provider")),
            base_url=str(value.get("base_url", "")),
            protocol=Protocol(value.get("protocol", Protocol.OPENAI.value)),
            models=[str(model) for model in value.get("models", [])],
            api_key=str(value.get("api_key", "")),
        )


@dataclass
class Message:
    role: MessageRole
    content: str


@dataclass
class RequestSettings:
    model: str
    system_prompt: str = ""
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 1024
    stream: bool = True


@dataclass
class TokenUsage:
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    def merge(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=other.input_tokens if other.input_tokens is not None else self.input_tokens,
            output_tokens=other.output_tokens if other.output_tokens is not None else self.output_tokens,
            total_tokens=other.total_tokens if other.total_tokens is not None else self.total_tokens,
        )


@dataclass
class StreamEvent:
    kind: str
    text: str = ""
    raw: Optional[Dict[str, Any]] = None
    usage: Optional[TokenUsage] = None
    ttft_seconds: Optional[float] = None
    elapsed_seconds: Optional[float] = None


@dataclass
class ModelFetchResult:
    models: List[str]
    raw: Dict[str, Any]
