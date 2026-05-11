"""
HfAgent service — wraps the Hugging Face Transformers agent API.

The agent uses the Inference API endpoint of a hosted model (default: StarCoder)
to decide which tools to invoke and how to chain them.

Required env var:
    HF_TOKEN  — Hugging Face access token (read permission is enough)

Usage:
    from hf_agent_service import run_agent
    result = await run_agent("Describe this image and read the description aloud.")
"""

import asyncio
import os
from functools import partial

from config import HF_TOKEN, HF_AGENT_MODEL_URL

# HfAgent is the legacy Transformers agent API (transformers >= 4.29).
# It sends the task description to the hosted LLM which returns Python tool-call
# code; the agent then executes those calls locally.
from transformers import HfAgent


_agent: HfAgent | None = None


def _get_agent() -> HfAgent:
    global _agent
    if _agent is None:
        kwargs = {}
        if HF_TOKEN:
            kwargs["token"] = HF_TOKEN
        _agent = HfAgent(HF_AGENT_MODEL_URL, **kwargs)
    return _agent


def _run_sync(task: str, **kwargs) -> str:
    agent = _get_agent()
    result = agent.run(task, **kwargs)
    return str(result)


async def run_agent(task: str, **kwargs) -> str:
    """Run an HfAgent task in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_run_sync, task, **kwargs))


async def chat_agent(task: str, **kwargs) -> str:
    """Single-turn chat with the agent (uses agent.chat for stateful conversation)."""
    loop = asyncio.get_event_loop()

    def _chat():
        agent = _get_agent()
        result = agent.chat(task, **kwargs)
        return str(result)

    return await loop.run_in_executor(None, _chat)
