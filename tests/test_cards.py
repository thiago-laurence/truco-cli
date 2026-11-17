import unittest

from truco.cards import Card, envido_value, fresh_deck, shuffled_deck, truco_rank


class CardTests(unittest.TestCase):
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
