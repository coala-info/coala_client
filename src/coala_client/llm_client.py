"""LLM client module with OpenAI-compatible API support."""

import json
from typing import AsyncIterator, Callable

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
    ChatCompletionToolMessageParam,
)

from .config import Config, LLMProviderConfig


class LLMClient:
    """Client for OpenAI-compatible LLM APIs."""

    def __init__(
        self,
        config: Config,
        provider: str | None = None,
    ) -> None:
        """Initialize the LLM client.

        Args:
            config: Application configuration.
            provider: Provider name (openai, gemini, ollama, custom).
        """
        self.config = config
        self.provider_name = provider or config.provider
        self.provider_config = config.get_provider_config(self.provider_name)
        self._client: AsyncOpenAI | None = None
        self.messages: list[ChatCompletionMessageParam] = []

    @property
    def client(self) -> AsyncOpenAI:
        """Get or create the OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.provider_config.api_key,
                base_url=self.provider_config.base_url,
            )
        return self._client

    async def close(self) -> None:
        """Close the client connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    def reset_messages(self) -> None:
        """Reset the conversation history."""
        self.messages = []

    def add_system_message(self, content: str) -> None:
        """Add a system message to the conversation."""
        self.messages.append({"role": "system", "content": content})

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the conversation."""
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """Add a tool result message to the conversation."""
        tool_msg: ChatCompletionToolMessageParam = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }
        self.messages.append(tool_msg)

    async def chat(
        self,
        user_message: str,
        tools: list[ChatCompletionToolParam] | None = None,
        tool_executor: Callable[[str, dict], str] | None = None,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        """Send a chat message and stream the response.

        Args:
            user_message: The user's message.
            tools: Optional list of tools available for the model.
            tool_executor: Callback to execute tool calls.
            stream: Whether to stream the response.

        Yields:
            Response text chunks.
        """
        self.add_user_message(user_message)

        while True:
            if stream:
                async for chunk in self._stream_response(tools):
                    yield chunk
            else:
                response = await self._get_response(tools)
                yield response

            # Check if we need to handle tool calls
            if not self._has_pending_tool_calls():
                break

            # Execute tool calls
            if tool_executor and self._has_pending_tool_calls():
                await self._execute_tool_calls(tool_executor)
            else:
                break

    async def _stream_response(
        self,
        tools: list[ChatCompletionToolParam] | None = None,
    ) -> AsyncIterator[str]:
        """Stream a response from the LLM.

        Args:
            tools: Optional list of tools.

        Yields:
            Response text chunks.
        """
        kwargs = {
            "model": self.provider_config.model,
            "messages": self.messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }

        if tools:
            kwargs["tools"] = tools

        stream = await self.client.chat.completions.create(**kwargs)

        full_content = ""
        tool_calls_data: dict[int, dict] = {}

        async for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Handle content
            if delta.content:
                full_content += delta.content
                yield delta.content

            # Handle tool calls
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    idx = tool_call.index
                    if idx not in tool_calls_data:
                        tool_calls_data[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }

                    if tool_call.id:
                        tool_calls_data[idx]["id"] = tool_call.id
                    if tool_call.function:
                        if tool_call.function.name:
                            tool_calls_data[idx]["function"]["name"] = tool_call.function.name
                        if tool_call.function.arguments:
                            tool_calls_data[idx]["function"]["arguments"] += (
                                tool_call.function.arguments
                            )

        # Build the assistant message
        assistant_msg: dict = {"role": "assistant"}
        if full_content:
            assistant_msg["content"] = full_content
        if tool_calls_data:
            assistant_msg["tool_calls"] = [
                tool_calls_data[idx] for idx in sorted(tool_calls_data.keys())
            ]

        self.messages.append(assistant_msg)

    async def _get_response(
        self,
        tools: list[ChatCompletionToolParam] | None = None,
    ) -> str:
        """Get a non-streaming response from the LLM.

        Args:
            tools: Optional list of tools.

        Returns:
            The response text.
        """
        kwargs = {
            "model": self.provider_config.model,
            "messages": self.messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        if tools:
            kwargs["tools"] = tools

        response = await self.client.chat.completions.create(**kwargs)

        message = response.choices[0].message
        assistant_msg: dict = {"role": "assistant"}

        if message.content:
            assistant_msg["content"] = message.content
        if message.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        self.messages.append(assistant_msg)
        return message.content or ""

    def _has_pending_tool_calls(self) -> bool:
        """Check if there are pending tool calls to execute."""
        if not self.messages:
            return False

        last_msg = self.messages[-1]
        if last_msg.get("role") != "assistant":
            return False

        return bool(last_msg.get("tool_calls"))

    async def _execute_tool_calls(
        self,
        tool_executor: Callable[[str, dict], str],
    ) -> None:
        """Execute pending tool calls.

        Args:
            tool_executor: Callback to execute tool calls.
        """
        last_msg = self.messages[-1]
        tool_calls = last_msg.get("tool_calls", [])

        for tool_call in tool_calls:
            name = tool_call["function"]["name"]
            try:
                args = json.loads(tool_call["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}

            result = tool_executor(name, args)
            self.add_tool_result(tool_call["id"], result)
