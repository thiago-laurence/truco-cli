from collections.abc import Sequence
from dataclasses import dataclass
import random


SUITS = ("espada", "basto", "oro", "copa")
RANKS = (1, 2, 3, 4, 5, 6, 7, 10, 11, 12)


@dataclass(frozen=True)
class Card:
    rank: int
    suit: str

    def __post_init__(self):
        if type(self.rank) is not int or self.rank not in RANKS:
            raise ValueError(f"invalid card rank: {self.rank}")
        if self.suit not in SUITS:
            raise ValueError(f"invalid card suit: {self.suit}")


def fresh_deck() -> list[Card]:
    return [Card(rank, suit) for suit in SUITS for rank in RANKS]


def shuffled_deck() -> list[Card]:
    deck = fresh_deck()
    random.shuffle(deck)
    return deck


def truco_rank(card: Card) -> int:
    if card.rank == 1 and card.suit == "espada":
        return 14
    if card.rank == 1 and card.suit == "basto":
        return 13
    if card.rank == 7 and card.suit == "espada":
        return 12
    if card.rank == 7 and card.suit == "oro":
        return 11
    if card.rank == 3:
        return 10
    if card.rank == 2:
        return 9
    if card.rank == 1:
        return 8
    if card.rank == 12:
        return 7
    if card.rank == 11:
        return 6
    if card.rank == 10:
        return 5
    if card.rank == 7:
        return 4
    return card.rank - 3


def envido_value(cards: Sequence[Card]) -> int:
    values = [card.rank if card.rank <= 7 else 0 for card in cards]
    by_suit = {
        suit: sorted(
            (value for card, value in zip(cards, values) if card.suit == suit),
            reverse=True,
        )
        for suit in SUITS
    }
    pairs = [
        values_for_suit
        for values_for_suit in by_suit.values()
        if len(values_for_suit) >= 2
    ]
    if pairs:
        return 20 + sum(pairs[0][:2])
    return max(values, default=0)
