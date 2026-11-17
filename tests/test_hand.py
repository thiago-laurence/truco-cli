import unittest

from truco.cards import Card
from truco.hand import Award, Hand


class HandTests(unittest.TestCase):
    def test_hand_rejects_invalid_seat_counts(self):
        for count in (0, 1, 3, 5, 7):
            with self.subTest(count=count), self.assertRaises(ValueError):
                Hand(
                    seats=tuple(str(i) for i in range(count)),
                    teams={},
                    dealer=0,
                    cards={},
                    score=(0, 0),
                )

    def test_first_parda_then_second_win_awards_one(self):
        hand = Hand(
            seats=("A", "B"),
            teams={"A": 0, "B": 1},
            dealer=1,
            cards={
                "A": (Card(3, "oro"), Card(7, "oro"), Card(4, "copa")),
                "B": (Card(3, "copa"), Card(2, "oro"), Card(5, "copa")),
            },
            score=(0, 0),
        )

        self.assertEqual(hand.act("A", "play", "a"), ())
        self.assertEqual(hand.act("B", "play", "a"), ())
        hand.act("A", "play", "s")
        awards = hand.act("B", "play", "s")

        self.assertEqual(awards, (Award(0, 1, "truco"),))
        self.assertTrue(hand.done)

    def test_fold_only_removes_self_until_team_empty(self):
        hand = Hand(
            seats=("A", "B", "C", "D"),
            teams={"A": 0, "B": 1, "C": 0, "D": 1},
            dealer=3,
            cards={
                "A": (Card(7, "oro"), Card(2, "oro"), Card(4, "oro")),
                "B": (Card(6, "copa"), Card(3, "copa"), Card(5, "copa")),
                "C": (Card(3, "oro"), Card(2, "copa"), Card(5, "oro")),
                "D": (Card(4, "copa"), Card(6, "oro"), Card(3, "basto")),
            },
            score=(0, 0),
        )
        for actor in ("A", "B", "C", "D"):
            hand.act(actor, "play", "a")

        self.assertEqual(hand.act("A", "fold"), ())
        self.assertFalse(hand.done)
        self.assertEqual(hand.act("B", "fold"), ())
        self.assertEqual(hand.act("C", "fold"), (Award(1, 1, "truco"),))
        self.assertTrue(hand.done)

    def test_replayed_slot_and_out_of_turn_leave_hand_unchanged(self):
        hand = Hand(
            seats=("A", "B"),
            teams={"A": 0, "B": 1},
            dealer=1,
            cards={
                "A": (Card(3, "oro"), Card(7, "oro"), Card(4, "copa")),
                "B": (Card(2, "oro"), Card(6, "copa"), Card(5, "copa")),
            },
            score=(0, 0),
        )
        hand.act("A", "play", "a")
        hand.act("B", "play", "a")
        before = hand.snapshot_for("B")

        with self.assertRaises(ValueError):
            hand.act("A", "play", "a")
        with self.assertRaises(ValueError):
            hand.act("B", "play", "s")

        self.assertEqual(hand.snapshot_for("B"), before)
        self.assertEqual(hand.legal_for("A"), ("play", "fold"))

    def test_snapshot_exposes_only_actor_cards_and_current_legal_actions(self):
        hand = Hand(
            seats=("A", "B"),
            teams={"A": 0, "B": 1},
            dealer=1,
            cards={
                "A": (Card(3, "oro"), Card(7, "oro"), Card(4, "copa")),
                "B": (Card(2, "oro"), Card(6, "copa"), Card(5, "copa")),
            },
            score=(0, 0),
        )

        snapshot = hand.snapshot_for("A")
        self.assertEqual(snapshot["cards"], (Card(3, "oro"), Card(7, "oro"), Card(4, "copa")))
        self.assertNotIn("B", snapshot["cards"])
        self.assertEqual(snapshot["legal"], ("play", "fold"))
        self.assertEqual(hand.legal_for("B"), ())


if __name__ == "__main__":
    unittest.main()
