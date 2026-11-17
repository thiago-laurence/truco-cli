import unittest

from truco.cards import fresh_deck
from truco.hand import Award
from truco.match import Match


class MatchTests(unittest.TestCase):
    def test_face_up_card_survives_instant_next_hand_transition(self):
        match = Match(("A", "B"), deck_factory=fresh_deck)
        actor = match.view("A")["turn"]
        other = "B" if actor == "A" else "A"
        match.act(actor, "play", "a")
        match.act(other, "fold")
        view = match.view("A")
        self.assertEqual(len(view["cards"]), 3)
        self.assertEqual(view["played"][0]["player"], actor)

    def test_pica_envido_cards_stay_hidden_until_all_duels_finish(self):
        match = Match(("A", "B", "C", "D", "E", "F"), deck_factory=fresh_deck, initial_score=(5, 0))
        actor = match.view("A")["turn"]
        duel = match.view("A")["duel"]
        other = duel[0] if actor == duel[1] else duel[1]
        match.act(actor, "bet", "envido")
        match.act(other, "accept")
        match.act(actor, "fold")
        self.assertIsNone(match.view("B")["reveal"])
        for _ in range(2):
            actor = match.view("A")["turn"]
            match.act(actor, "fold")
        self.assertIsNotNone(match.view("B")["reveal"])

    def test_each_deal_has_unique_private_cards_and_rotates_dealer(self):
        deals = []

        def deck_factory():
            deck = fresh_deck()
            deals.append(deck)
            return deck

        match = Match(("A", "B"), deck_factory=deck_factory)
        first = match.view("A")
        self.assertEqual(len(set(first["cards"])), 3)
        self.assertNotIn("B", first["cards"])
        self.assertEqual(
            len(set((*first["cards"], *match.view("B")["cards"]))), 6
        )

        match.act(first["turn"], "fold")
        second = match.view("A")
        self.assertEqual(len(deals), 2)
        self.assertNotEqual(first["turn"], second["turn"])
        self.assertEqual(len(set(second["cards"])), 3)
        self.assertEqual(
            len(set((*second["cards"], *match.view("B")["cards"]))), 6
        )

    def test_six_players_enter_pica_at_five_and_return_to_redonda_at_25(self):
        seats = ("A", "B", "C", "D", "E", "F")
        match = Match(seats, initial_score=(5, 0))
        self.assertEqual(match.mode, "pica")
        for expected in (("B", "E"), ("C", "F"), ("D", "A")):
            view = match.view(expected[0])
            self.assertEqual(view["duel"], expected)
            paired_cards = (*view["cards"], *match.view(expected[1])["cards"])
            self.assertEqual(len(paired_cards), len(set(paired_cards)))
            actor = view["turn"]
            awards = match.act(actor, "fold")
            self.assertEqual(tuple(a.points for a in awards), (1, 1))
            self.assertEqual({a.team for a in awards}, {1 - match.seats.index(actor) % 2})
        self.assertEqual(match.mode, "redonda")
        self.assertEqual(match.view("A")["duel"], seats)
        self.assertEqual(Match(seats, initial_score=(25, 0)).mode, "redonda")

    def test_pica_deals_one_shared_unique_deck_to_all_players(self):
        deals = []

        def deck_factory():
            deals.append(fresh_deck())
            return deals[-1]

        match = Match(("A", "B", "C", "D", "E", "F"), deck_factory, (5, 0))
        cards = [card for seat in match.seats for card in match.view(seat)["cards"]]
        self.assertEqual(len(set(cards)), 18)
        self.assertEqual(len(deals), 1)

        for _ in range(3):
            actor = match.view(match.seats[0])["turn"]
            match.act(actor, "fold")
        self.assertEqual(len(deals), 2)

    def test_waiting_pica_player_sees_only_their_predealt_cards_without_actions(self):
        match = Match(("A", "B", "C", "D", "E", "F"), deck_factory=fresh_deck, initial_score=(5, 0))
        view = match.view("A")
        self.assertEqual(len(view["cards"]), 3)
        self.assertEqual(view["legal"], ())
        self.assertEqual(view["duel"], ("B", "E"))
        self.assertNotIn("E", view["cards"])

    def test_pica_dealer_rotates_once_after_all_three_duels(self):
        match = Match(("A", "B", "C", "D", "E", "F"), deck_factory=fresh_deck, initial_score=(5, 0))
        for _ in range(3):
            actor = match.view("A")["turn"]
            match.act(actor, "fold")
        self.assertEqual(match.view("A")["turn"], "C")

    def test_pica_pair_order_follows_rotated_dealer(self):
        match = Match(("A", "B", "C", "D", "E", "F"), deck_factory=fresh_deck, initial_score=(4, 4))
        while match.mode == "redonda":
            actor = match.view("A")["turn"]
            if match.seats.index(actor) % 2 == 0:
                match.act(actor, "fold")
            else:
                match.act(actor, "play", "a")
        self.assertEqual(match.view("A")["duel"], ("C", "F"))
        self.assertEqual(match.view("C")["turn"], "C")

    def test_first_duel_that_reaches_30_stops_remaining_duels(self):
        match = Match(
            ("A", "B", "C", "D", "E", "F"),
            deck_factory=fresh_deck,
            initial_score=(0, 24),
        )
        self.assertEqual(match.mode, "pica")
        actor = match.view("A")["turn"]
        other = "E" if actor == "B" else "B"
        match.act(actor, "bet", "falta_envido")
        awards = match.act(other, "accept")
        self.assertEqual(awards, (Award(1, 6, "envido"),))
        self.assertEqual(match.score, (0, 30))
        self.assertEqual(match.winner, 1)
        self.assertEqual(match.view("B")["duel"], ("B", "E"))

    def test_view_does_not_expose_opponents_cards(self):
        match = Match(("A", "B", "C", "D"))
        view = match.view("A")
        self.assertEqual(len(view["cards"]), 3)
        self.assertNotIn("B", view["cards"])
        self.assertNotIn("opponents_cards", view)

    def test_winning_envido_cards_revealed_at_hand_end_even_if_score_reaches_30(self):
        match = Match(("A", "B"), deck_factory=fresh_deck, initial_score=(0, 28))
        actor = match.view("A")["turn"]
        other = "A" if actor == "B" else "B"
        match.act(actor, "bet", "envido")
        awards = match.act(other, "accept")
        self.assertEqual(awards, (Award(1, 2, "envido"),))
        self.assertEqual(match.winner, 1)
        view = match.view(other)
        self.assertEqual(view["envido"], awards)
        self.assertIsNotNone(view["reveal"])
        self.assertTrue(view["done"])

    def test_envido_reveal_survives_deal_of_next_hand(self):
        match = Match(("A", "B"), deck_factory=fresh_deck)
        actor = match.view("A")["turn"]
        other = "A" if actor == "B" else "B"
        match.act(actor, "bet", "envido")
        envido_awards = match.act(other, "accept")
        match.act(actor, "fold")

        next_view = match.view("A")
        self.assertFalse(next_view["done"])
        self.assertEqual(next_view["envido"], envido_awards)
        self.assertEqual(next_view["reveal"][0], "B")
        self.assertEqual(next_view["cards"], match.view("A")["cards"])


if __name__ == "__main__":
    unittest.main()
