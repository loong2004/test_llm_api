"""OpenAI and Anthropic API adapters with incremental SSE decoding."""

import json
import time
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence

import httpx

from .models import Message, MessageRole, ModelFetchResult, Provider, RequestSettings, StreamEvent, TokenUsage


class ApiError(RuntimeError):
    pass


def endpoint(base_url: str, path: str) -> str:
    """Join a user supplied API root and an API path without dropping /v1."""
    return "{0}/{1}".format(base_url.strip().rstrip("/"), path.lstrip("/"))


def iter_sse_data(lines: Iterable[str]) -> Iterator[str]:
    """Yield complete SSE data payloads, including multi-line data events."""
    data_lines: List[str] = []
    for raw_line in lines:
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if line == "":
            if data_lines:
                yield "\n".join(data_lines)
                data_lines = []
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if data_lines:
        yield "\n".join(data_lines)


def _content_as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def _usage(value: Optional[Dict[str, Any]]) -> Optional[TokenUsage]:
    if not value:
        return None
    input_tokens = value.get("prompt_tokens", value.get("input_tokens"))
    output_tokens = value.get("completion_tokens", value.get("output_tokens"))
    total_tokens = value.get("total_tokens")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)


class BaseAdapter:
    def __init__(self, client: Optional[httpx.Client] = None) -> None:
        self._client = client

    def _new_client(self) -> httpx.Client:
        return self._client or httpx.Client(timeout=httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=30.0))

    def _close_owned_client(self, client: httpx.Client) -> None:
        if self._client is None:
            client.close()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                body = response.read().decode("utf-8", errors="replace")[:800]
            except httpx.HTTPError:
                body = ""
            raise ApiError("HTTP {0}: {1}".format(exc.response.status_code, body or exc.response.reason_phrase)) from exc


class OpenAIAdapter(BaseAdapter):
    def fetch_models(self, provider: Provider, api_key: str) -> ModelFetchResult:
        client = self._new_client()
        try:
            response = client.get(
                endpoint(provider.base_url, "models"),
                headers={"Authorization": "Bearer {0}".format(api_key), "Accept": "application/json"},
            )
            self._raise_for_status(response)
            raw = response.json()
            data = raw.get("data")
            if not isinstance(data, list):
                raise ApiError("Model response does not contain a data array.")
            models = sorted(
                {item.get("id") for item in data if isinstance(item, dict) and isinstance(item.get("id"), str)},
                key=str.lower,
            )
            return ModelFetchResult(models=models, raw=raw)
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiError("Unable to fetch models: {0}".format(exc)) from exc
        finally:
            self._close_owned_client(client)

    def stream_chat(
        self, provider: Provider, api_key: str, messages: Sequence[Message], settings: RequestSettings
    ) -> Iterator[StreamEvent]:
        payload_messages: List[Dict[str, str]] = []
        if settings.system_prompt.strip():
            payload_messages.append({"role": "system", "content": settings.system_prompt.strip()})
        payload_messages.extend({"role": message.role.value, "content": message.content} for message in messages)
        payload: Dict[str, Any] = {
            "model": settings.model,
            "messages": payload_messages,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "max_tokens": settings.max_tokens,
            "stream": settings.stream,
        }
        if settings.stream:
            payload["stream_options"] = {"include_usage": True}
        yield from self._stream_openai(provider, api_key, payload, settings.stream)

    def _stream_openai(
        self, provider: Provider, api_key: str, payload: Dict[str, Any], stream: bool
    ) -> Iterator[StreamEvent]:
        client = self._new_client()
        started = time.perf_counter()
        first_token_at: Optional[float] = None
        usage = TokenUsage()
        try:
            with client.stream(
                "POST",
                endpoint(provider.base_url, "chat/completions"),
                headers={"Authorization": "Bearer {0}".format(api_key), "Content-Type": "application/json"},
                json=payload,
            ) as response:
                self._raise_for_status(response)
                if not stream:
                    packet = json.loads(response.read())
                    yield StreamEvent(kind="raw", raw=packet)
                    choices = packet.get("choices", [])
                    text = _content_as_text(choices[0].get("message", {}).get("content")) if choices else ""
                    elapsed = time.perf_counter() - started
                    if text:
                        first_token_at = elapsed
                        yield StreamEvent(kind="delta", text=text, ttft_seconds=first_token_at)
                    usage = usage.merge(_usage(packet.get("usage")) or TokenUsage())
                else:
                    for data in iter_sse_data(response.iter_lines()):
                        if data == "[DONE]":
                            break
                        try:
                            packet = json.loads(data)
                        except ValueError as exc:
                            raise ApiError("Received malformed SSE JSON: {0}".format(data[:300])) from exc
                        yield StreamEvent(kind="raw", raw=packet)
                        usage = usage.merge(_usage(packet.get("usage")) or TokenUsage())
                        choices = packet.get("choices", [])
                        if choices:
                            text = _content_as_text(choices[0].get("delta", {}).get("content"))
                            if text:
                                elapsed = time.perf_counter() - started
                                if first_token_at is None:
                                    first_token_at = elapsed
                                yield StreamEvent(kind="delta", text=text, ttft_seconds=first_token_at)
            yield StreamEvent(
                kind="done",
                usage=usage,
                ttft_seconds=first_token_at,
                elapsed_seconds=time.perf_counter() - started,
            )
        except httpx.HTTPError as exc:
            raise ApiError("OpenAI-compatible request failed: {0}".format(exc)) from exc
        finally:
            self._close_owned_client(client)


class AnthropicAdapter(BaseAdapter):
    def fetch_models(self, provider: Provider, api_key: str) -> ModelFetchResult:
        raise ApiError("Anthropic does not expose a portable models-list endpoint. Add models manually.")

    def stream_chat(
        self, provider: Provider, api_key: str, messages: Sequence[Message], settings: RequestSettings
    ) -> Iterator[StreamEvent]:
        payload: Dict[str, Any] = {
            "model": settings.model,
            "max_tokens": settings.max_tokens,
            "stream": settings.stream,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in messages
                if message.role != MessageRole.SYSTEM
            ],
        }
        # Anthropic treats temperature and top_p as alternatives. Keep the UI
        # simple while emitting one compatible sampling control per request.
        if settings.top_p != 1.0:
            payload["top_p"] = settings.top_p
        else:
            payload["temperature"] = settings.temperature
        if settings.system_prompt.strip():
            payload["system"] = settings.system_prompt.strip()

        client = self._new_client()
        started = time.perf_counter()
        first_token_at: Optional[float] = None
        usage = TokenUsage()
        try:
            with client.stream(
                "POST",
                endpoint(provider.base_url, "messages"),
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "anthropic-dangerous-direct-browser-access": "true",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                self._raise_for_status(response)
                if not settings.stream:
                    packet = json.loads(response.read())
                    yield StreamEvent(kind="raw", raw=packet)
                    text = _content_as_text(packet.get("content"))
                    elapsed = time.perf_counter() - started
                    if text:
                        first_token_at = elapsed
                        yield StreamEvent(kind="delta", text=text, ttft_seconds=first_token_at)
                    usage = usage.merge(_usage(packet.get("usage")) or TokenUsage())
                else:
                    for data in iter_sse_data(response.iter_lines()):
                        try:
                            packet = json.loads(data)
                        except ValueError as exc:
                            raise ApiError("Received malformed SSE JSON: {0}".format(data[:300])) from exc
                        yield StreamEvent(kind="raw", raw=packet)
                        usage = usage.merge(_usage(packet.get("usage")) or TokenUsage())
                        if packet.get("type") == "content_block_delta":
                            text = _content_as_text(packet.get("delta", {}).get("text"))
                            if text:
                                elapsed = time.perf_counter() - started
                                if first_token_at is None:
                                    first_token_at = elapsed
                                yield StreamEvent(kind="delta", text=text, ttft_seconds=first_token_at)
            yield StreamEvent(
                kind="done",
                usage=usage,
                ttft_seconds=first_token_at,
                elapsed_seconds=time.perf_counter() - started,
            )
        except httpx.HTTPError as exc:
            raise ApiError("Anthropic request failed: {0}".format(exc)) from exc
        finally:
            self._close_owned_client(client)


def adapter_for(provider: Provider, client: Optional[httpx.Client] = None) -> BaseAdapter:
    if provider.protocol.value == "anthropic":
        return AnthropicAdapter(client)
    return OpenAIAdapter(client)
