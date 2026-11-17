import unittest

from truco.cards import Card
from truco.hand import Award, Hand


class HandTests(unittest.TestCase):
    def test_truco_raise_accept_and_reject(self):
        cards = {
            "A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
            "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto")),
        }
        rejected_truco = Hand(("A", "B"), {"A": 0, "B": 1}, 1, cards, (0, 0))
        rejected_truco.act("A", "bet", "truco")
        self.assertEqual(rejected_truco.act("B", "reject"), (Award(0, 1, "truco"),))

        rejected_retruco = Hand(("A", "B"), {"A": 0, "B": 1}, 1, cards, (0, 0))
        rejected_retruco.act("A", "bet", "truco")
        rejected_retruco.act("B", "bet", "retruco")
        self.assertEqual(rejected_retruco.act("A", "reject"), (Award(1, 2, "truco"),))

        accepted = Hand(("A", "B"), {"A": 0, "B": 1}, 1, cards, (0, 0))
        accepted.act("A", "bet", "truco")
        accepted.act("B", "bet", "retruco")
        accepted.act("A", "bet", "vale_cuatro")
        accepted.act("B", "accept")
        for slot in ("a", "s", "d"):
            actor = accepted.snapshot_for("B")["turn"]
            accepted.act(actor, "play", slot)
            accepted.act("A" if actor == "B" else "B", "play", slot)
        self.assertEqual(accepted.score, (0, 4))

    def test_only_accepting_team_can_raise(self):
        hand = Hand(
            ("A", "B", "C", "D"),
            {"A": 0, "B": 1, "C": 0, "D": 1},
            3,
            {
                "A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
                "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto")),
                "C": (Card(5, "copa"), Card(6, "basto"), Card(4, "oro")),
                "D": (Card(4, "copa"), Card(6, "oro"), Card(3, "basto")),
            },
            (0, 0),
        )
        hand.act("A", "bet", "truco")
        self.assertIn("bet:retruco", hand.legal_for("B"))
        hand.act("B", "accept")
        hand.act("B", "play", "a")
        self.assertNotIn("bet:retruco", hand.legal_for("C"))

    def test_envido_precedes_pending_truco(self):
        hand = Hand(
            ("A", "B"),
            {"A": 0, "B": 1},
            1,
            {
                "A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
                "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto")),
            },
            (0, 0),
        )
        hand.act("A", "bet", "truco")
        self.assertIn("bet:envido", hand.legal_for("B"))
        hand.act("B", "bet", "envido")
        self.assertEqual(hand.act("A", "accept"), (Award(0, 2, "envido"),))
        self.assertEqual(hand.snapshot_for("B")["turn"], "B")
        self.assertIn("bet:retruco", hand.legal_for("B"))
        hand.act("B", "bet", "retruco")
        self.assertEqual(hand.legal_for("A")[:2], ("accept", "reject"))

    def test_folding_after_accepted_truco_awards_accepted_stake(self):
        hand = Hand(
            ("A", "B"),
            {"A": 0, "B": 1},
            1,
            {
                "A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
                "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto")),
            },
            (0, 0),
        )
        hand.act("A", "bet", "truco")
        hand.act("B", "accept")
        self.assertEqual(
            hand.act("B", "fold"),
            (Award(0, 2, "truco"), Award(0, 1, "envido")),
        )

    def test_envido_accept_and_tie_go_to_mano(self):
        hand = Hand(
            seats=("A", "B"),
            teams={"A": 0, "B": 1},
            dealer=1,
            cards={
                "A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
                "B": (Card(6, "copa"), Card(7, "copa"), Card(3, "basto")),
            },
            score=(28, 28),
        )

        self.assertIn("bet:envido", hand.legal_for("A"))
        self.assertEqual(hand.act("A", "bet", "envido"), ())
        self.assertEqual(hand.act("B", "accept"), (Award(0, 2, "envido"),))
        self.assertEqual(
            hand.snapshot_for("B")["envido_reveal"],
            ("A", (Card(7, "oro"), Card(6, "oro"))),
        )

    def test_reject_after_envido_raise_awards_previously_accepted(self):
        hand = Hand(
            seats=("A", "B"),
            teams={"A": 0, "B": 1},
            dealer=1,
            cards={
                "A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
                "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto")),
            },
            score=(0, 0),
        )

        hand.act("A", "bet", "envido")
        hand.act("B", "bet", "real_envido")
        with self.assertRaises(ValueError):
            hand.act("A", "fold")
        self.assertEqual(hand.act("A", "reject"), (Award(1, 2, "envido"),))

    def test_falta_in_malas_decides_match_and_in_pica_is_six(self):
        cards = {
            "A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
            "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto")),
        }
        hand = Hand(("A", "B"), {"A": 0, "B": 1}, 1, cards, (10, 9))
        hand.act("A", "bet", "falta_envido")
        self.assertEqual(hand.act("B", "accept"), (Award(0, 20, "envido"),))
        self.assertEqual(hand.score, (30, 9))

        pica = Hand(("A", "B"), {"A": 0, "B": 1}, 1, cards, (5, 5), pica=True)
        pica.act("A", "bet", "falta_envido")
        self.assertEqual(pica.act("B", "accept"), (Award(0, 6, "envido"),))

    def test_envido_is_available_after_opponent_card_before_own_card(self):
        hand = Hand(
            ("A", "B"),
            {"A": 0, "B": 1},
            1,
            {
                "A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
                "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto")),
            },
            (0, 0),
        )
        hand.act("A", "play", "a")
        self.assertIn("bet:envido", hand.legal_for("B"))
        self.assertEqual(hand.act("B", "bet", "envido"), ())

    def test_multiplayer_envido_after_opponent_card_resumes_bidders_turn(self):
        hand = Hand(
            ("A", "B", "C", "D"),
            {"A": 0, "B": 1, "C": 0, "D": 1},
            3,
            {
                "A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
                "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto")),
                "C": (Card(5, "copa"), Card(6, "basto"), Card(4, "oro")),
                "D": (Card(4, "copa"), Card(6, "oro"), Card(3, "basto")),
            },
            (0, 0),
        )
        hand.act("A", "play", "a")
        self.assertIn("bet:envido", hand.legal_for("B"))

        hand.act("B", "bet", "envido")
        self.assertEqual(hand.act("C", "accept"), (Award(0, 2, "envido"),))
        self.assertEqual(hand.snapshot_for("B")["turn"], "B")

    def test_envido_reveals_cards_by_envido_value_not_raw_rank(self):
        hand = Hand(
            ("A", "B"),
            {"A": 0, "B": 1},
            1,
            {
                "A": (Card(12, "oro"), Card(7, "oro"), Card(3, "oro")),
                "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto")),
            },
            (28, 28),
        )
        hand.act("A", "bet", "envido")
        hand.act("B", "accept")

        self.assertEqual(
            hand.snapshot_for("A")["envido_reveal"],
            ("A", (Card(7, "oro"), Card(3, "oro"))),
        )

    def test_folding_entire_team_before_envido_adds_one_point(self):
        hand = Hand(
            ("A", "B"),
            {"A": 0, "B": 1},
            1,
            {
                "A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
                "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto")),
            },
            (0, 0),
        )
        self.assertEqual(
            hand.act("A", "fold"),
            (Award(1, 1, "truco"), Award(1, 1, "envido")),
        )
        self.assertEqual(hand.score, (0, 2))

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
        self.assertEqual(hand.legal_for("A"), ("play", "fold", "bet:truco"))

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
        self.assertEqual(snapshot["legal"][:2], ("play", "fold"))
        self.assertIn("bet:envido", snapshot["legal"])
        self.assertEqual(hand.legal_for("B"), ())


if __name__ == "__main__":
    unittest.main()
