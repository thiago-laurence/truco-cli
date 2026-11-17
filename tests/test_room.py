import unittest

from truco.cards import fresh_deck
from truco.room import Room
from truco.wire import clean_text


def started_room(names=("A", "B"), **kwargs):
    room = Room(names[0], len(names), deck_factory=fresh_deck, **kwargs)
    for name in names[1:]:
        room.join(name)
    room.seat(names)
    room.start()
    return room


class RoomTests(unittest.TestCase):
    def test_duplicate_name_or_full_room_rejected(self):
        room = Room("A", 2)
        with self.assertRaises(ValueError):
            room.join("A")
        room.join("B")
        with self.assertRaises(ValueError):
            room.join("C")

    def test_views_wrap_match_view_with_private_cards_and_chat(self):
        room = started_room()
        views = room.views()
        self.assertEqual(
            set(views["A"]),
            {"phase", "players", "seats", "score", "mode", "turn", "cards", "table",
             "legal", "chat", "envido", "reveal", "winner"},
        )
        self.assertEqual(len(views["A"]["cards"]), 3)
        self.assertNotIn(views["B"]["cards"][0], views["A"]["cards"])
        self.assertEqual(views["A"]["chat"], [])

    def test_out_of_turn_network_action_keeps_score_and_view(self):
        room = started_room()
        turn = room.views()["A"]["turn"]
        sender = "B" if turn == "A" else "A"
        before = room.views()
        events = room.dispatch(sender, {"type": "action", "kind": "fold", "actor": turn})
        self.assertEqual([e["type"] for e in events[sender]], ["error"])
        self.assertEqual(room.views()["A"]["score"], before["A"]["score"])
        self.assertEqual(room.views()["B"]["score"], before["B"]["score"])

    def test_private_signal_only_to_teammates_then_leaks_at_threshold(self):
        for chance, leaks in ((0.10, False), (0.09, True)):
            draws = []

            def rng():
                draws.append(None)
                return chance

            room = started_room(("A", "B", "C", "D"), rng=rng)
            events = room.dispatch("A", {"type": "signal", "code": 1})
            self.assertEqual(len(draws), 1)
            self.assertEqual(events["A"][0]["type"], "signal")
            self.assertEqual(events["C"][0]["type"], "signal")

            if leaks:
                self.assertEqual([e["type"] for e in events["D"]], ["chat"])
                self.assertEqual(room.views()["D"]["chat"][-1]["type"], "chat")
                self.assertEqual([e["type"] for e in events["C"]], ["signal", "chat"])
            else:
                self.assertNotIn("D", events)
                self.assertNotIn("B", events)
                self.assertEqual(room.views()["D"]["chat"], [])

    def test_signal_rejected_in_duel_or_one_on_one(self):
        room = started_room()
        self.assertEqual(room.dispatch("A", {"type": "signal", "code": 1})["A"][0]["type"], "error")

        seats = ("A", "B", "C", "D", "E", "F")
        pica = Room("A", 6, deck_factory=fresh_deck)
        for name in seats[1:]:
            pica.join(name)
        pica.seat(seats)
        pica.start()
        pica.match.score = (5, 0)
        pica.match._set_mode()
        pica.match._deal()
        self.assertEqual(pica.views()["A"]["mode"], "pica")
        self.assertEqual(pica.dispatch("A", {"type": "signal", "code": 1})["A"][0]["type"], "error")

    def test_finished_room_still_accepts_chat_but_not_rematch(self):
        room = started_room()
        turn = room.views()["A"]["turn"]
        room.dispatch(turn, {"type": "action", "kind": "fold"})
        turn = room.views()["A"]["turn"]
        room.dispatch(turn, {"type": "action", "kind": "fold"})
        # Force the match over through a public legal action at a 29-point score.
        room = Room("A", 2, deck_factory=fresh_deck)
        room.join("B")
        room.seat(("A", "B"))
        room.start()
        room.match.score = (29, 0)
        turn = room.views()["A"]["turn"]
        room.dispatch(turn, {"type": "action", "kind": "fold"})
        events = room.dispatch("A", {"type": "chat", "text": "gg"})
        self.assertEqual(events["A"][0]["type"], "chat")
        self.assertEqual(events["B"][0]["type"], "chat")
        self.assertEqual(room.views()["A"]["phase"], "finished")
        self.assertEqual(room.dispatch("A", {"type": "start"})["A"][0]["type"], "error")

    def test_control_chars_and_long_chat_cleaned(self):
        room = started_room()
        events = room.dispatch("A", {"type": "chat", "text": "\x1b[31m" + "x" * 400})
        text = events["A"][0]["text"]
        self.assertNotIn("\x1b", text)
        self.assertLessEqual(len(text), 300)
        self.assertEqual(room.views()["B"]["chat"][-1]["text"], text)
        self.assertEqual(clean_text("\x1b[31mhi\x1b[0m\n", 32), "hi")

    def test_bad_json_frame_does_not_change_room_state(self):
        for message in ({"type": "chat", "text": None}, {"type": "unknown"}):
            room = started_room()
            before = room.views()
            events = room.dispatch("A", message)
            self.assertEqual(events["A"][0]["type"], "error")
            self.assertEqual(room.views()["A"]["score"], before["A"]["score"])


if __name__ == "__main__":
    unittest.main()
