import unittest

from truco.cards import Card, envido_value, fresh_deck, shuffled_deck, truco_rank


class CardTests(unittest.TestCase):
    def test_all_fourteen_truco_strength_tiers_and_ties(self):
        tiers = [
            [Card(1, "espada")], [Card(1, "basto")], [Card(7, "espada")],
            [Card(7, "oro")], [Card(3, suit) for suit in ("espada", "basto", "oro", "copa")],
            [Card(2, suit) for suit in ("espada", "basto", "oro", "copa")],
            [Card(1, suit) for suit in ("oro", "copa")],
            [Card(12, suit) for suit in ("espada", "basto", "oro", "copa")],
            [Card(11, suit) for suit in ("espada", "basto", "oro", "copa")],
            [Card(10, suit) for suit in ("espada", "basto", "oro", "copa")],
            [Card(7, suit) for suit in ("copa", "basto")],
            [Card(6, suit) for suit in ("espada", "basto", "oro", "copa")],
            [Card(5, suit) for suit in ("espada", "basto", "oro", "copa")],
            [Card(4, suit) for suit in ("espada", "basto", "oro", "copa")],
        ]
        ranks = [truco_rank(tier[0]) for tier in tiers]
        self.assertEqual(ranks, sorted(ranks, reverse=True))
        self.assertTrue(all(len({truco_rank(card) for card in tier}) == 1 for tier in tiers))

    def test_deck_has_40_unique_cards_and_strength_order(self):
        deck = fresh_deck()

        self.assertEqual(len(deck), 40)
        self.assertEqual(len(set(deck)), 40)
        self.assertFalse(any(card.rank in (8, 9) for card in deck))
        self.assertGreater(
            truco_rank(Card(1, "espada")), truco_rank(Card(1, "basto"))
        )
        self.assertGreater(
            truco_rank(Card(1, "basto")), truco_rank(Card(7, "espada"))
        )

    def test_shuffled_deck_contains_the_fresh_deck_cards(self):
        self.assertCountEqual(shuffled_deck(), fresh_deck())

    def test_envido_two_same_suit_and_figures(self):
        self.assertEqual(
            envido_value([Card(7, "espada"), Card(6, "espada"), Card(12, "copa")]),
            33,
        )
        self.assertEqual(
            envido_value(
                [Card(10, "espada"), Card(11, "basto"), Card(12, "oro")]
            ),
            0,
        )

    def test_card_rejects_invalid_rank_and_suit(self):
        with self.assertRaises(ValueError):
            Card(8, "espada")
        with self.assertRaises(ValueError):
            Card(1, "invalid")


if __name__ == "__main__":
    unittest.main()
