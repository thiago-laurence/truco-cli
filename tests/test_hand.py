import unittest

from truco.cards import Card
from truco.hand import Award, Hand


class HandTests(unittest.TestCase):
    def test_face_up_cards_and_original_used_slot_survive_trick_close(self):
        hand = Hand(
            ("A", "B"), {"A": 0, "B": 1}, 1,
            {"A": (Card(7, "oro"), Card(6, "oro"), Card(3, "copa")),
             "B": (Card(4, "oro"), Card(5, "copa"), Card(2, "basto"))},
            (0, 0),
        )
        hand.act("A", "play", "a")
        hand.act("B", "play", "a")
        self.assertEqual(len(hand.snapshot_for("A")["played"]), 2)
        self.assertEqual(hand.snapshot_for("A")["used_slots"], ("a",))

    def test_played_cards_include_their_trick_and_winning_player(self):
        hand = Hand(
            ("A", "B"), {"A": 0, "B": 1}, 1,
            {"A": (Card(7, "oro"), Card(6, "oro"), Card(3, "copa")),
             "B": (Card(4, "oro"), Card(5, "copa"), Card(2, "basto"))},
            (0, 0),
        )
        hand.act("A", "play", "a")
        hand.act("B", "play", "a")
        hand.act("A", "play", "s")
        hand.act("B", "play", "s")

        played = hand.snapshot_for("A")["played"]
        self.assertEqual([card["trick"] for card in played], [0, 0, 1, 1])
        self.assertEqual({card["trick_winner"] for card in played}, {"A"})

    def test_second_envido_raise_has_four_point_acceptance_and_no_third_envido(self):
        hand = Hand(
            ("A", "B"), {"A": 0, "B": 1}, 1,
            {"A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
             "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto"))},
            (0, 0),
        )
        hand.act("A", "bet", "envido")
        self.assertIn("bet:envido", hand.legal_for("B"))
        hand.act("B", "bet", "envido")
        self.assertNotIn("bet:envido", hand.legal_for("A"))
        self.assertEqual(hand.act("A", "accept"), (Award(0, 4, "envido"),))

    def test_parda_after_folded_leader_selects_next_active_leader(self):
        hand = Hand(
            ("A", "B", "C", "D"), {"A": 0, "B": 1, "C": 0, "D": 1}, 3,
            {"A": (Card(4, "oro"),) * 3, "B": (Card(4, "copa"),) * 3,
             "C": (Card(4, "basto"),) * 3, "D": (Card(4, "espada"),) * 3},
            (0, 0),
        )
        hand.act("A", "fold")
        for player in ("B", "C", "D"):
            hand.act(player, "play", "a")
        self.assertEqual(hand.snapshot_for("B")["turn"], "B")

    def test_folded_high_envido_hand_cannot_win(self):
        hand = Hand(
            ("A", "B", "C", "D"), {"A": 0, "B": 1, "C": 0, "D": 1}, 3,
            {"A": (Card(7, "oro"), Card(6, "oro"), Card(3, "copa")),
             "B": (Card(4, "oro"), Card(5, "copa"), Card(2, "basto")),
             "C": (Card(7, "copa"), Card(4, "copa"), Card(3, "oro")),
             "D": (Card(1, "espada"), Card(2, "basto"), Card(4, "oro"))},
            (0, 0),
        )
        hand.act("A", "fold")
        hand.act("B", "bet", "envido")
        hand.act("C", "accept")
        hand.act("B", "fold")
        hand.act("C", "fold")
        self.assertEqual(hand.snapshot_for("B")["envido_reveal"][0], "C")

    def test_team_fold_after_first_card_awards_undisputed_envido_before_thirty(self):
        hand = Hand(
            ("A", "B", "C", "D"), {"A": 0, "B": 1, "C": 0, "D": 1}, 3,
            {"A": (Card(4, "oro"),) * 3, "B": (Card(5, "oro"),) * 3,
             "C": (Card(6, "oro"),) * 3, "D": (Card(7, "oro"),) * 3},
            (29, 0),
        )
        hand.act("A", "play", "a")
        hand.act("B", "fold")
        hand.act("C", "fold")
        self.assertEqual(hand.act("D", "fold"), (Award(0, 1, "envido"),))
        self.assertEqual(hand.score, (30, 0))

    def test_rejected_vale_cuatro_awards_three_points(self):
        hand = Hand(
            ("A", "B"), {"A": 0, "B": 1}, 1,
            {"A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
             "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto"))},
            (0, 0),
        )
        hand.act("A", "bet", "truco")
        hand.act("B", "bet", "retruco")
        hand.act("A", "bet", "vale_cuatro")
        self.assertEqual(hand.act("B", "reject"), (Award(0, 3, "truco"),))

    def test_truco_response_never_returns_to_bidder_after_card_was_played(self):
        hand = Hand(
            ("A", "B"), {"A": 0, "B": 1}, 1,
            {"A": (Card(6, "oro"), Card(7, "oro"), Card(3, "copa")),
             "B": (Card(2, "copa"), Card(4, "copa"), Card(3, "basto"))},
            (0, 0),
        )
        hand.act("A", "play", "a")
        hand.act("B", "bet", "truco")
        self.assertEqual(hand.snapshot_for("A")["turn"], "A")
        self.assertIn("reject", hand.legal_for("A"))
        with self.assertRaises(ValueError):
            hand.act("B", "reject")
        self.assertEqual(hand.act("A", "reject"), (Award(1, 1, "truco"),))

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
        self.assertEqual(accepted.snapshot_for("A")["turn"], "A")
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
        self.assertEqual(hand.snapshot_for("C")["turn"], "B")
        self.assertEqual(hand.legal_for("C"), ())
        hand.act("B", "accept")
        hand.act("A", "play", "a")
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
        hand.act("A", "accept")
        self.assertEqual(hand.snapshot_for("B")["turn"], "A")

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
        self.assertEqual(hand.snapshot_for("A")["turn"], "A")
        self.assertEqual(
            hand.act("A", "fold"),
            (Award(1, 1, "envido"), Award(1, 2, "truco")),
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
        self.assertIn("bet:falta_envido", hand.legal_for("A"))
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
            (Award(1, 1, "envido"), Award(1, 1, "truco")),
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
        hand.act("B", "play", "s")
        awards = hand.act("A", "play", "s")

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
