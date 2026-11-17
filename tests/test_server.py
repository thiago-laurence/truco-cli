import asyncio
import unittest
from unittest.mock import patch

from truco.cards import fresh_deck
from truco.room import Room
from truco.server import serve
from truco.wire import read_message, write_message


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.room = Room("Host", 2, deck_factory=fresh_deck)
        self.server = await serve(self.room, "127.0.0.1", 0)
        self.host, self.port = self.server.sockets[0].getsockname()[:2]
        self.clients = []

    async def asyncTearDown(self):
        self.server.close()
        for reader, writer in self.clients:
            writer.close()
            await writer.wait_closed()
        await self.server.wait_closed()

    async def connect(self, name):
        reader, writer = await asyncio.open_connection(self.host, self.port)
        self.clients.append((reader, writer))
        await write_message(writer, {"type": "join", "name": name})
        return reader, writer

    async def next_type(self, reader, expected):
        while True:
            message = await asyncio.wait_for(read_message(reader), 1)
            if message["type"] == expected:
                return message

    async def test_loopback_two_clients_join_play_chat_and_receive_private_views(self):
        host_reader, host_writer = await self.connect("Host")
        host_state = await self.next_type(host_reader, "state")
        self.assertEqual(host_state["view"]["phase"], "lobby")

        guest_reader, guest_writer = await self.connect("Guest")
        guest_state = await self.next_type(guest_reader, "state")
        host_state = await self.next_type(host_reader, "state")
        self.assertEqual(guest_state["view"]["players"], ["Host", "Guest"])

        await write_message(host_writer, {"type": "seat", "names": ["Host", "Guest"]})
        await self.next_type(host_reader, "state")
        await self.next_type(guest_reader, "state")
        await write_message(host_writer, {"type": "start"})
        host_state = await self.next_type(host_reader, "state")
        guest_state = await self.next_type(guest_reader, "state")
        self.assertEqual(host_state["view"]["phase"], "playing")
        self.assertNotEqual(host_state["view"]["cards"], guest_state["view"]["cards"])

        turn = host_state["view"]["turn"]
        actor_writer = host_writer if turn == "Host" else guest_writer
        actor_name = "Host" if turn == "Guest" else "Guest"
        await write_message(actor_writer, {"type": "action", "kind": "play", "value": "a", "actor": actor_name})
        host_state = await self.next_type(host_reader, "state")
        guest_state = await self.next_type(guest_reader, "state")
        self.assertEqual(len(host_state["view"]["table"]), 1)
        self.assertEqual(len(guest_state["view"]["table"]), 1)
        self.assertEqual(host_state["view"]["table"][0]["player"], turn)
        self.assertNotIn(guest_state["view"]["cards"][0], host_state["view"]["cards"])

        await write_message(guest_writer, {"type": "chat", "text": "hola"})
        self.assertEqual((await self.next_type(host_reader, "chat"))["sender"], "Guest")
        self.assertEqual((await self.next_type(guest_reader, "chat"))["sender"], "Guest")

    async def test_join_replays_complete_chat_without_embedding_it_in_state(self):
        for index in range(12):
            self.room.dispatch("Host", {"type": "chat", "text": f"{index} " + "x" * 300})
        reader, host_writer = await self.connect("Host")
        state = await self.next_type(reader, "state")
        self.assertNotIn("chat", state["view"])
        history = [await self.next_type(reader, "chat") for _ in range(12)]
        self.assertEqual(history[0]["text"], "0 " + "x" * 298)
        self.assertEqual(len(history), 12)
        guest_reader, guest_writer = await self.connect("Guest")
        await self.next_type(guest_reader, "state")
        await self.next_type(reader, "state")
        await write_message(host_writer, {"type": "seat", "names": ["Host", "Guest"]})
        await self.next_type(reader, "state")
        await self.next_type(guest_reader, "state")
        await write_message(host_writer, {"type": "start"})
        state = await self.next_type(reader, "state")
        self.assertEqual(state["view"]["phase"], "playing")

    async def test_disconnect_during_pending_bet_returns_remaining_clients_to_lobby(self):
        host_reader, host_writer = await self.connect("Host")
        await self.next_type(host_reader, "state")
        guest_reader, guest_writer = await self.connect("Guest")
        await self.next_type(guest_reader, "state")
        await self.next_type(host_reader, "state")
        await write_message(host_writer, {"type": "seat", "names": ["Host", "Guest"]})
        await self.next_type(host_reader, "state")
        await self.next_type(guest_reader, "state")
        await write_message(host_writer, {"type": "start"})
        host_view = (await self.next_type(host_reader, "state"))["view"]
        await self.next_type(guest_reader, "state")
        bidder = host_writer if host_view["turn"] == "Host" else guest_writer
        await write_message(bidder, {"type": "action", "kind": "bet", "value": "truco"})
        await self.next_type(host_reader, "state")
        await self.next_type(guest_reader, "state")

        guest_writer.close()
        await guest_writer.wait_closed()
        await self.next_type(host_reader, "error")
        lobby = await self.next_type(host_reader, "state")
        self.assertEqual(lobby["view"]["phase"], "lobby")
        self.assertEqual(lobby["view"]["players"], ["Host"])

        replacement_reader, _ = await self.connect("Replacement")
        replacement_state = await self.next_type(replacement_reader, "state")
        self.assertEqual(replacement_state["view"]["players"], ["Host", "Replacement"])

    async def test_host_leaving_closes_room_and_clients_receive_notice(self):
        host_reader, host_writer = await self.connect("Host")
        await self.next_type(host_reader, "state")
        guest_reader, _ = await self.connect("Guest")
        await self.next_type(guest_reader, "state")
        await self.next_type(host_reader, "state")

        host_writer.close()
        await host_writer.wait_closed()
        notice = await self.next_type(guest_reader, "error")
        self.assertEqual(notice["text"], "host left")
        with self.assertRaises((ValueError, asyncio.IncompleteReadError)):
            await asyncio.wait_for(read_message(guest_reader), 1)
        await asyncio.wait_for(self.server.wait_closed(), 1)
        self.assertEqual(self.room.players, [])

    async def test_remote_client_cannot_claim_host_name(self):
        host_reader, _ = await self.connect("Host")
        await self.next_type(host_reader, "state")
        second_reader, _ = await self.connect("Host")
        rejection = await self.next_type(second_reader, "error")
        self.assertIn("host", rejection["text"])
        self.assertEqual(self.room.players, ["Host"])

    async def test_host_name_claim_from_simulated_non_loopback_is_rejected(self):
        address = type("Address", (), {"is_loopback": False})()
        with patch("truco.server.ipaddress.ip_address", return_value=address):
            reader, _ = await self.connect("Host")
            rejection = await self.next_type(reader, "error")
        self.assertIn("loopback", rejection["text"])
        self.assertEqual(self.room.players, ["Host"])

    async def test_non_host_must_wait_for_host_then_can_join_room(self):
        early_reader, _ = await self.connect("Guest")
        rejection = await self.next_type(early_reader, "error")
        self.assertIn("host", rejection["text"])
        self.assertEqual(self.room.players, ["Host"])

        host_reader, _ = await self.connect("Host")
        host_state = await self.next_type(host_reader, "state")
        self.assertEqual(host_state["view"]["players"], ["Host"])

        guest_reader, _ = await self.connect("Guest")
        guest_state = await self.next_type(guest_reader, "state")
        self.assertEqual(guest_state["view"]["players"], ["Host", "Guest"])
        self.assertEqual(self.room.players, ["Host", "Guest"])

    async def test_malformed_json_disconnects_only_that_client(self):
        bad_reader, bad_writer = await asyncio.open_connection(self.host, self.port)
        self.clients.append((bad_reader, bad_writer))
        bad_writer.write(b'{"type":]\n')
        await bad_writer.drain()
        with self.assertRaises((ValueError, asyncio.IncompleteReadError)):
            await asyncio.wait_for(read_message(bad_reader), 1)

        host_reader, _ = await self.connect("Host")
        state = await self.next_type(host_reader, "state")
        self.assertEqual(state["view"]["phase"], "lobby")

    async def test_oversized_frame_disconnects_only_joined_client(self):
        host_reader, host_writer = await self.connect("Host")
        await self.next_type(host_reader, "state")
        guest_reader, guest_writer = await self.connect("Guest")
        await self.next_type(guest_reader, "state")
        await self.next_type(host_reader, "state")
        guest_writer.write(b"x" * 5000 + b"\n")
        await guest_writer.drain()
        update = await self.next_type(host_reader, "state")
        self.assertEqual(update["view"]["players"], ["Host"])
        await write_message(host_writer, {"type": "chat", "text": "still here"})
        self.assertEqual((await self.next_type(host_reader, "chat"))["text"], "still here")


if __name__ == "__main__":
    unittest.main()
