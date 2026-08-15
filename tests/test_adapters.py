import json
import unittest

import httpx

from llm_tester.adapters import AnthropicAdapter, OpenAIAdapter, endpoint, iter_sse_data
from llm_tester.models import Message, MessageRole, Protocol, Provider, RequestSettings


class SseDecoderTests(unittest.TestCase):
    def test_collects_multiline_data_and_ignores_metadata(self):
        lines = ["event: update", "data: first", "data: second", "", "data: last"]
        self.assertEqual(list(iter_sse_data(lines)), ["first\nsecond", "last"])

    def test_endpoint_preserves_version_segment(self):
        self.assertEqual(endpoint("https://gateway.example/v1/", "/chat/completions"), "https://gateway.example/v1/chat/completions")


class OpenAIAdapterTests(unittest.TestCase):
    def setUp(self):
        self.provider = Provider("Gateway", "https://gateway.example/v1", Protocol.OPENAI)

    def test_fetch_models_sorts_ids(self):
        def handler(request):
            self.assertEqual(request.url.path, "/v1/models")
            self.assertEqual(request.headers["authorization"], "Bearer test-key")
            return httpx.Response(200, json={"data": [{"id": "zeta"}, {"id": "alpha"}, {"id": "zeta"}]})

        adapter = OpenAIAdapter(httpx.Client(transport=httpx.MockTransport(handler)))
        result = adapter.fetch_models(self.provider, "test-key")
        self.assertEqual(result.models, ["alpha", "zeta"])

    def test_streams_delta_and_usage(self):
        packets = [
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " world"}}]},
            {"choices": [], "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}},
        ]
        content = "".join("data: {0}\n\n".format(json.dumps(packet)) for packet in packets) + "data: [DONE]\n\n"

        def handler(request):
            self.assertEqual(request.url.path, "/v1/chat/completions")
            self.assertTrue(json.loads(request.content)["stream"])
            return httpx.Response(200, content=content)

        adapter = OpenAIAdapter(httpx.Client(transport=httpx.MockTransport(handler)))
        events = list(
            adapter.stream_chat(
                self.provider,
                "test-key",
                [Message(MessageRole.USER, "Hi")],
                RequestSettings(model="test-model", stream=True),
            )
        )
        self.assertEqual("".join(event.text for event in events if event.kind == "delta"), "Hello world")
        done = events[-1]
        self.assertEqual(done.kind, "done")
        self.assertEqual(done.usage.total_tokens, 5)
        self.assertIsNotNone(done.ttft_seconds)


class AnthropicAdapterTests(unittest.TestCase):
    def test_streams_text_delta(self):
        provider = Provider("Anthropic", "https://anthropic.example/v1", Protocol.ANTHROPIC)
        content = "\n".join(
            [
                'event: content_block_delta',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Bonjour"}}',
                '',
                'event: message_delta',
                'data: {"type":"message_delta","usage":{"output_tokens":1}}',
                '',
            ]
        )

        def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(request.url.path, "/v1/messages")
            self.assertEqual(request.headers["x-api-key"], "test-key")
            self.assertEqual(payload["system"], "Be concise")
            return httpx.Response(200, content=content)

        adapter = AnthropicAdapter(httpx.Client(transport=httpx.MockTransport(handler)))
        events = list(
            adapter.stream_chat(
                provider,
                "test-key",
                [Message(MessageRole.USER, "Salut")],
                RequestSettings(model="claude-test", system_prompt="Be concise", stream=True),
            )
        )
        self.assertEqual("".join(event.text for event in events if event.kind == "delta"), "Bonjour")
        self.assertEqual(events[-1].usage.output_tokens, 1)
