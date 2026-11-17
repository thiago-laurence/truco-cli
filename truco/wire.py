import asyncio
import json
import re
import unicodedata


MAX_MESSAGE_BYTES = 4096
_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|[@-Z\\-_])")


def clean_text(raw: str, max_len: int) -> str:
    if not isinstance(raw, str):
        raise ValueError("text must be a string")
    text = _ANSI.sub("", raw)
    text = "".join(
        char for char in text
        if unicodedata.category(char)[0] != "C" and char not in "\r\n"
    )
    return text[:max_len]


async def read_message(reader: asyncio.StreamReader) -> dict[str, object]:
    try:
        data = await reader.readline()
    except (asyncio.LimitOverrunError, ValueError) as exc:
        raise ValueError("invalid or oversized message") from exc
    if not data or len(data) > MAX_MESSAGE_BYTES or not data.endswith(b"\n"):
        raise ValueError("invalid or oversized message")
    try:
        message = json.loads(data[:-1].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON message") from exc
    if not isinstance(message, dict):
        raise ValueError("message must be a JSON object")
    return message


async def write_message(
    writer: asyncio.StreamWriter, message: dict[str, object]
) -> None:
    try:
        data = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("message is not JSON serializable") from exc
    if len(data) > MAX_MESSAGE_BYTES:
        raise ValueError("message is too large")
    writer.write(data)
    await writer.drain()
