import unittest
import asyncio
from contextlib import redirect_stdout
import io
from unittest.mock import AsyncMock, Mock, patch

from textual.widgets import Input, RichLog, Static

from truco.__main__ import _play, main, parse_args
from truco.ui import TrucoApp


class UiTests(unittest.IsolatedAsyncioTestCase):
    async def test_host_disconnect_is_visible_and_closes_client_writer(self):
        writer = Mock()
        writer.wait_closed = AsyncMock()
        app = Mock()

        async def run_app():
            await app.network_reader()

        app.run_async = AsyncMock(side_effect=run_app)
        with (
            patch("truco.__main__.asyncio.open_connection", new=AsyncMock(return_value=(object(), writer))),
            patch("truco.__main__.write_message", new=AsyncMock()),
            patch("truco.__main__.read_message", new=AsyncMock(side_effect=[
                {"type": "state", "view": {"players": ["Ana"]}},
                asyncio.IncompleteReadError(b"", 1),
            ])),
            patch("truco.__main__.TrucoApp", return_value=app),
        ):
            await _play("Ana", "127.0.0.1", 4977)
        self.assertEqual(app.apply_event.call_args.args[0]["type"], "error")
        writer.close.assert_called_once()
        writer.wait_closed.assert_awaited_once()

    async def test_chat_mode_keeps_digits_as_text_and_retains_scrollable_history(self):
        sent = []

        async def send(message):
            sent.append(message)

        app = TrucoApp(send, {"phase": "lobby", "players": ["Ana"], "chat": []})
        async with app.run_test() as pilot:
            await pilot.press("c")
            await pilot.press("1", "2", "3")
            self.assertEqual(app.query_one("#chat-input", Input).value, "123")
            self.assertEqual(sent, [])
            await pilot.press("escape")
            await pilot.pause()
            app.apply_event({"type": "chat", "sender": "Beto", "text": "[bold]literal"})
            log = app.query_one("#chat-history", RichLog)
            self.assertGreater(len(log.lines), 0)

    async def test_chat_input_preserves_shortcut_letters_and_digits_without_actions(self):
        sent = []

        async def send(message):
            sent.append(message)

        app = TrucoApp(send, {
            "phase": "playing", "mode": "redonda", "players": ["Ana", "Beto", "Caro", "Dani"],
            "turn": "Ana", "legal": ["play", "fold"],
        })
        async with app.run_test() as pilot:
            app.action_chat_mode()
            with (
                patch.object(app, "action_play_a", wraps=app.action_play_a) as play_a,
                patch.object(app, "action_chat_mode", wraps=app.action_chat_mode) as chat,
                patch.object(app, "action_quit", wraps=app.action_quit) as quit_action,
            ):
                await pilot.press("a", "c", "q", "m", "1", "2", "3")
                self.assertEqual((play_a.call_count, chat.call_count, quit_action.call_count), (0, 0, 0))
            self.assertFalse(any(binding.priority for binding in app.BINDINGS))
            self.assertEqual(app.query_one("#chat-input", Input).value, "acqm123")
            self.assertEqual(sent, [])
            self.assertTrue(app.is_running)

    async def test_m_sends_fold_only_when_legal(self):
        sent = []

        async def send(message):
            sent.append(message)

        app = TrucoApp(send, {"phase": "playing", "legal": ["play", "fold"]})
        async with app.run_test() as pilot:
            await pilot.press("m")
            await pilot.pause()
            self.assertEqual(sent, [{"type": "action", "kind": "fold", "value": None}])

    async def test_signal_digit_works_outside_chat_and_help_matches(self):
        sent = []

        async def send(message):
            sent.append(message)

        app = TrucoApp(send, {
            "phase": "playing", "mode": "redonda", "players": ["Ana", "Beto", "Caro", "Dani"],
        })
        async with app.run_test() as pilot:
            await pilot.press("1")
            await pilot.pause()
            self.assertEqual(sent, [{"type": "signal", "code": 1}])
            self.assertIn("1 cejas", app.query_one("#help", Static).render().plain)
            self.assertIn("9 ojos", app.query_one("#help", Static).render().plain)
            app.apply_event({"type": "signal", "sender": "Beto", "code": 1})
            self.assertIn("levantar cejas", app.history[-1])

    async def test_host_sends_explicit_alternating_seat_order(self):
        sent = []

        async def send(message):
            sent.append(message)

        app = TrucoApp(send, {
            "phase": "lobby", "players": ["A", "B", "C", "D"],
            "local_name": "A", "capacity": 4,
        })
        async with app.run_test() as pilot:
            app.query_one("#seat-order", Input).value = "A, C, B, D"
            await pilot.click("#seat")
            self.assertEqual(sent[0], {"type": "seat", "names": ["A", "C", "B", "D"]})

    async def test_seat_field_follows_players_joining_lobby(self):
        sent = []

        async def send(message):
            sent.append(message)

        app = TrucoApp(send, {
            "phase": "lobby", "players": ["Ana"], "local_name": "Ana", "capacity": 2,
        })
        async with app.run_test() as pilot:
            app.apply_event({
                "type": "state",
                "view": {"phase": "lobby", "players": ["Ana", "Luis"]},
            })
            await pilot.pause()
            self.assertEqual(app.query_one("#seat-order", Input).value, "Ana, Luis")
            await pilot.click("#seat")
            self.assertEqual(sent, [{"type": "seat", "names": ["Ana", "Luis"]}])

    async def test_oversized_chat_input_is_capped_before_send(self):
        sent = []

        async def send(message):
            sent.append(message)

        app = TrucoApp(send, {"phase": "lobby", "players": ["Ana"]})
        async with app.run_test() as pilot:
            await pilot.press("c")
            app.query_one("#chat-input", Input).value = "x" * 4100
            await pilot.press("enter")
            self.assertEqual(len(sent[0]["text"]), 300)

    async def test_chat_send_error_is_shown_without_crashing(self):
        async def send(message):
            raise ValueError("message is too large")

        app = TrucoApp(send, {"phase": "lobby", "players": ["Ana"]})
        async with app.run_test() as pilot:
            await pilot.press("c")
            app.query_one("#chat-input", Input).value = "hello"
            await pilot.press("enter")
            self.assertIn("message is too large", app.history[-1])
            self.assertTrue(app.is_running)

    async def test_pending_bid_envido_winner_reveal_and_pica_pair_render(self):
        async def send(message):
            pass

        app = TrucoApp(send, {"phase": "playing", "players": ["Ana", "Beto"]})
        async with app.run_test() as pilot:
            app.apply_event({"type": "state", "view": {
                "phase": "playing", "players": ["Ana", "Beto"], "cards": [],
                "pending_bet": ["truco", "Beto"], "duel": ["Ana", "Beto"],
                "envido": [{"team": 0, "points": 6, "reason": "envido"}],
                "reveal": ["Ana", [{"rank": 7, "suit": "oro"}]],
            }})
            text = app.query_one("#table", Static).render().plain
            self.assertIn("truco", text)
            self.assertIn("Beto", text)
            self.assertIn("Ana", text)
            self.assertIn("6", text)
            self.assertIn("oro", text)

    async def test_played_card_renders_rank_and_suit_instead_of_json(self):
        async def send(message):
            pass

        app = TrucoApp(send, {
            "phase": "playing", "players": ["Ana", "Beto"],
            "table": [{"player": "Ana", "card": {"rank": 7, "suit": "basto"}}],
        })
        async with app.run_test():
            text = app.query_one("#table", Static).render().plain
            self.assertIn("Ana: 7 de Basto 🌿", text)
            self.assertNotIn("{'rank'", text)

    async def test_quit_requires_confirmation_and_can_be_canceled(self):
        async def send(message):
            pass

        app = TrucoApp(send, {"phase": "lobby", "players": ["Ana"], "chat": []})
        async with app.run_test() as pilot:
            await pilot.press("q")
            await pilot.pause()
            self.assertTrue(app.is_running)
            self.assertNotEqual(app.screen, app.screen_stack[0])
            await pilot.press("escape")
            await pilot.pause()
            self.assertTrue(app.is_running)
            await pilot.press("q")
            await pilot.click("#confirm-quit")
            await pilot.pause()
            self.assertFalse(app.is_running)

    async def test_play_and_bet_keys_send_only_valid_actions(self):
        sent = []

        async def send(message):
            sent.append(message)

        app = TrucoApp(send, {
            "phase": "playing", "players": ["Ana", "Beto"], "turn": "Ana",
            "cards": [], "legal": ["play", "bet:truco"],
        })
        async with app.run_test() as pilot:
            await pilot.press("a")
            await pilot.pause()
            await pilot.press("e")
            self.assertEqual(sent, [{"type": "action", "kind": "play", "value": "a"}])
            await pilot.press("t")
            self.assertTrue(app.query_one("#action-menu").display)
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(len(sent), 2)
            self.assertEqual(sent[-1], {"type": "action", "kind": "bet", "value": "truco"})

    async def test_resize_and_long_chat_keep_table_and_chat_visible_without_markup_execution(self):
        async def send(message):
            pass

        view = {
            "phase": "playing", "players": ["Ana", "Beto"], "turn": "Ana",
            "score": [1, 2], "cards": [], "table": [], "legal": ["play"],
            "chat": [],
        }
        app = TrucoApp(send, view)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            self.assertGreater(app.query_one("#table").region.width, 0)
            self.assertGreater(app.query_one("#chat-history").region.width, 0)
            await pilot.press("c")
            app.apply_event({"type": "state", "view": view})
            app.apply_event({"type": "chat", "sender": "[red]Beto", "text": "[bold]" + "x" * 500})
            await pilot.resize_terminal(32, 14)
            self.assertGreater(app.query_one("#table").region.width, 0)
            self.assertGreater(app.query_one("#chat-history").region.width, 0)
            self.assertIn(
                "[bold]",
                "".join(line.text for line in app.query_one("#chat-history", RichLog).lines),
            )
            app.apply_event({"type": "state", "view": {**view, "winner": 1, "phase": "finished"}})
            self.assertIn("Ganó el equipo 2", app.query_one("#table", Static).render().plain)

    async def test_cli_host_join_arguments_manual_host_address_and_invalid_capacity(self):
        self.assertEqual(
            vars(parse_args(["host", "--name", "Ana", "--players", "4", "--port", "4977"])),
            {"command": "host", "name": "Ana", "players": 4, "port": 4977, "address": None},
        )
        self.assertEqual(
            parse_args(["host", "--name", "Ana", "--players", "4", "--address", "192.168.1.8"]).address,
            "192.168.1.8",
        )
        self.assertEqual(
            vars(parse_args(["join", "--name", "Luis", "--host", "192.168.1.8", "--port", "4977"])),
            {"command": "join", "name": "Luis", "players": None, "port": 4977, "address": "192.168.1.8"},
        )
        with self.assertRaises(SystemExit):
            parse_args(["host", "--name", "Ana", "--players", "3"])
        server = Mock()
        server.wait_closed = AsyncMock()
        writer = Mock()
        writer.wait_closed = AsyncMock()
        app = AsyncMock()
        app.run_async = AsyncMock()
        with (
            patch("truco.__main__.serve", new=AsyncMock(return_value=server)),
            patch("truco.__main__._ipv4_candidates", return_value=["10.0.0.2"]),
            patch("truco.__main__.asyncio.open_connection", new=AsyncMock(return_value=(object(), writer))) as connect,
            patch("truco.__main__.write_message", new=AsyncMock()),
            patch("truco.__main__.read_message", new=AsyncMock(return_value={"type": "state", "view": {"players": ["Ana"]}})),
            patch("truco.__main__.TrucoApp", return_value=app) as app_factory,
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                await _play(" Ana ", "127.0.0.1", 4977, capacity=2, advertised_address="192.168.1.8")
        connect.assert_awaited_once_with("127.0.0.1", 4977)
        self.assertIn("Dirección anunciada manualmente: 192.168.1.8:4977", output.getvalue())
        self.assertIn("10.0.0.2:4977", output.getvalue())
        self.assertEqual(app_factory.call_args.args[1]["local_name"], "Ana")
        with (
            patch("truco.__main__._play", new=AsyncMock()) as play,
            patch("truco.__main__.asyncio.run", side_effect=lambda coroutine: coroutine.close()),
        ):
            main(["host", "--name", "Ana", "--players", "4", "--port", "4977",
                  "--address", "192.168.1.8"])
        play.assert_called_once_with(
            "Ana", "127.0.0.1", 4977, capacity=4, advertised_address="192.168.1.8"
        )


if __name__ == "__main__":
    unittest.main()
