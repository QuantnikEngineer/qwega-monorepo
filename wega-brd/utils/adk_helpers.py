from __future__ import annotations

from typing import Any

from google.genai import types


def make_tool_list(toolset: Any) -> list[Any]:
    return [toolset] if toolset else []


async def ensure_session(
    session_service: Any,
    *,
    app_name: str,
    user_id: str,
    session_id: str,
) -> None:
    try:
        await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        pass


async def run_runner_to_text(
    runner: Any,
    *,
    user_id: str,
    session_id: str,
    prompt: str,
    timeout_seconds: float,
) -> str:
    async def _drive() -> str:
        output_parts: list[str] = []
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
        ):
            if event.is_final_response() and event.content:
                output_parts.extend(
                    part.text for part in event.content.parts if getattr(part, "text", None)
                )
        return "".join(output_parts)

    import asyncio

    return await asyncio.wait_for(_drive(), timeout=timeout_seconds)