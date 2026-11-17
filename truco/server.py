import asyncio
from dataclasses import asdict, is_dataclass
import ipaddress

from truco.room import Room
from truco.wire import clean_text, read_message, write_message


def _json_value(value):
    if is_dataclass(value) and not isinstance(value, type):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


async def serve(room: Room, host: str, port: int) -> asyncio.AbstractServer:
    writers: dict[str, asyncio.StreamWriter] = {}
    server = None

    async def send_events(events):
        for name, messages in events.items():
            writer = writers.get(name)
            if writer is None:
                continue
            for message in messages:
                try:
                    await write_message(writer, _json_value(message))
                except (ConnectionError, ValueError):
                    pass

    async def send_states():
        views = room.views()
        for name, writer in tuple(writers.items()):
            try:
                await write_message(writer, {"type": "state", "view": _json_value(views[name])})
            except (ConnectionError, ValueError):
                pass

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        name = None
        try:
            try:
                join = await read_message(reader)
            except (ValueError, UnicodeError):
                return
            if join.get("type") != "join" or not isinstance(join.get("name"), str):
                await write_message(writer, {"type": "error", "text": "invalid join"})
                return
            requested = clean_text(join["name"], 32).strip()
            peer = writer.get_extra_info("peername")
            try:
                local = bool(peer) and ipaddress.ip_address(peer[0]).is_loopback
            except ValueError:
                local = False
            if requested == room.host:
                if not local or room.host in writers:
                    await write_message(writer, {"type": "error", "text": "host must join first from loopback"})
                    return
                name = room.host
            else:
                try:
                    room.join(requested)
                except ValueError as exc:
                    await write_message(writer, {"type": "error", "text": str(exc)})
                    return
                name = requested
            writers[name] = writer
            await send_states()

            while True:
                try:
                    message = await read_message(reader)
                except (ValueError, UnicodeError):
                    break
                await send_events(room.dispatch(name, message))
                if message.get("type") in ("seat", "start", "action"):
                    await send_states()
        except (ConnectionError, ValueError):
            pass
        finally:
            if name is not None and name in room.players:
                events = room.leave(name)
                writers.pop(name, None)
                await send_events(events)
                if name == room.host:
                    server.close()
                    for client_writer in tuple(writers.values()):
                        client_writer.close()
                    writers.clear()
                else:
                    await send_states()
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, RuntimeError):
                pass

    server = await asyncio.start_server(handle, host, port)
    return server
