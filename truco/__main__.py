import argparse
import asyncio
import socket
from collections.abc import Sequence

from truco.room import Room
from truco.server import serve
from truco.ui import TrucoApp
from truco.wire import read_message, write_message


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m truco")
    commands = parser.add_subparsers(dest="command", required=True)
    host = commands.add_parser("host", help="crear una mesa")
    host.add_argument("--name", required=True)
    host.add_argument("--players", required=True, type=int, choices=(2, 4, 6))
    host.add_argument("--port", type=int, default=4977)
    host.add_argument("--address", help="IP LAN anunciada manualmente")
    join = commands.add_parser("join", help="unirse a una mesa")
    join.add_argument("--name", required=True)
    join.add_argument("--host", dest="address", required=True)
    join.add_argument("--port", type=int, default=4977)
    join.set_defaults(players=None)
    return parser.parse_args(argv)


def _ipv4_candidates() -> list[str]:
    addresses = set()
    try:
        for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = entry[4][0]
            if not address.startswith("127.") and not address.startswith("169.254."):
                addresses.add(address)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            address = probe.getsockname()[0]
            if not address.startswith("127.") and not address.startswith("169.254."):
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)


async def _play(
    name: str,
    address: str,
    port: int,
    *,
    capacity: int | None = None,
    advertised_address: str | None = None,
) -> None:
    server = None
    if capacity is not None:
        server = await serve(Room(name, capacity), "0.0.0.0", port)
        candidates = _ipv4_candidates()
        print(f"Mesa Truco en puerto {port} (LAN):")
        for candidate in candidates:
            print(f"  {candidate}:{port}")
        if not candidates:
            print("No se detectó IP IPv4 LAN; indica --address manualmente.")
        if advertised_address:
            print(f"Dirección anunciada manualmente: {advertised_address}:{port}")
    try:
        reader, writer = await asyncio.open_connection(address, port)
        await write_message(writer, {"type": "join", "name": name})
        first = await read_message(reader)
        if first.get("type") != "state":
            raise RuntimeError(str(first.get("text", "No se pudo entrar a la mesa")))
        view = dict(first["view"])
        view.update(local_name=name)
        if capacity is not None:
            view["capacity"] = capacity
        app = TrucoApp(
            lambda message: write_message(writer, message),
            view,
        )

        async def receive() -> None:
            while True:
                app.apply_event(await read_message(reader))

        app.network_reader = receive
        await app.run_async()
        writer.close()
        await writer.wait_closed()
    finally:
        if server is not None:
            server.close()
            await server.wait_closed()


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.command == "host":
        asyncio.run(_play(
            args.name, "127.0.0.1", args.port, capacity=args.players,
            advertised_address=args.address,
        ))
    else:
        asyncio.run(_play(args.name, args.address, args.port))


if __name__ == "__main__":
    main()
