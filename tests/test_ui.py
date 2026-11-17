import unittest

from textual.widgets import Input, RichLog, Static

from truco.__main__ import parse_args
from truco.ui import TrucoApp


class UiTests(unittest.IsolatedAsyncioTestCase):
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
        async with app.run_test(size=(50, 18)) as pilot:
            await pilot.press("c")
            app.apply_event({"type": "state", "view": view})
            app.apply_event({"type": "chat", "sender": "[red]Beto", "text": "[bold]" + "x" * 500})
            await pilot.resize_terminal(32, 14)
            self.assertTrue(app.query_one("#table"))
            self.assertTrue(app.query_one("#chat-history"))
            self.assertIn(
                "[bold]",
                "".join(line.text for line in app.query_one("#chat-history", RichLog).lines),
            )
            app.apply_event({"type": "state", "view": {**view, "winner": 1, "phase": "finished"}})
            self.assertIn("Ganó el equipo 2", app.query_one("#table", Static).render().plain)

    def test_cli_host_join_arguments_and_invalid_capacity(self):
        self.assertEqual(
            vars(parse_args(["host", "--name", "Ana", "--players", "4", "--port", "4977"])),
            {"command": "host", "name": "Ana", "players": 4, "port": 4977, "address": None},
        )
        self.assertEqual(
            vars(parse_args(["join", "--name", "Luis", "--host", "192.168.1.8", "--port", "4977"])),
            {"command": "join", "name": "Luis", "players": None, "port": 4977, "address": "192.168.1.8"},
        )
        with self.assertRaises(SystemExit):
            parse_args(["host", "--name", "Ana", "--players", "3"])


if __name__ == "__main__":
    unittest.main()
