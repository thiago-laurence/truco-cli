from collections.abc import Callable

from truco.cards import Card, shuffled_deck
from truco.hand import Award, Hand


class Match:
    def __init__(
        self,
        seats: tuple[str, ...],
        deck_factory: Callable[[], list[Card]] = shuffled_deck,
        initial_score: tuple[int, int] = (0, 0),
    ):
        if len(seats) not in (2, 4, 6) or len(set(seats)) != len(seats):
            raise ValueError("a match requires 2, 4, or 6 unique seats")
        if len(initial_score) != 2:
            raise ValueError("score must contain two team totals")
        self.seats = seats
        self.score = initial_score
        self.winner = next((i for i, score in enumerate(initial_score) if score >= 30), None)
        self._deck_factory = deck_factory
        self._dealer = 0
        self._duel_index = 0
        self._last_envido: tuple[Award, ...] = ()
        self._hand_envido: tuple[Award, ...] = ()
        self._reveal = None
        self._pica_reveal = None
        self._duel: tuple[str, ...] = seats
        self._hand: Hand | None = None
        self._pica_cards: dict[str, tuple[Card, Card, Card]] | None = None
        self._last_table: tuple[dict[str, object], ...] = ()
        self.mode = "redonda"
        if self.winner is None:
            self._set_mode()
            self._deal()

    def _set_mode(self) -> None:
        if len(self.seats) == 6 and max(self.score) < 25:
            self.mode = "pica" if max(self.score) >= 5 and self.mode != "pica" else "redonda"
            if self.mode == "pica":
                self._duel_index = 0
        else:
            self.mode = "redonda"

    def _deal(self) -> None:
        if self.mode == "pica":
            if self._pica_cards is None:
                deck = self._deck_factory()
                self._pica_cards = {
                    seat: tuple(deck.pop() for _ in range(3))
                    for seat in self.seats
                }
            mano = (self._dealer + 1 + self._duel_index) % len(self.seats)
            self._duel = (self.seats[mano], self.seats[(mano + 3) % len(self.seats)])
            teams = {seat: self.seats.index(seat) % 2 for seat in self._duel}
            dealer = 1
            order = self._duel
            cards = {seat: self._pica_cards[seat] for seat in order}
        else:
            self._duel = self.seats
            teams = {seat: i % 2 for i, seat in enumerate(self.seats)}
            dealer = self._dealer
            order = self.seats
            deck = self._deck_factory()
            cards = {seat: tuple(deck.pop() for _ in range(3)) for seat in order}
            self._pica_cards = None
        self._hand = Hand(
            order,
            teams,
            dealer,
            cards,
            self.score,
            pica=self.mode == "pica",
        )
        self._hand_envido = ()

    def act(self, actor: str, kind: str, value: str | None = None) -> tuple[Award, ...]:
        if self._hand is None or self.winner is not None:
            raise ValueError("match is over")
        awards = self._hand.act(actor, kind, value)
        envido_awards = tuple(award for award in awards if award.reason == "envido")
        if envido_awards:
            self._hand_envido = envido_awards
        for award in awards:
            score = list(self.score)
            score[award.team] = min(30, score[award.team] + award.points)
            self.score = tuple(score)
            if max(self.score) >= 30:
                self.winner = self.score.index(max(self.score))
                break
        if self._hand.done:
            self._last_table = tuple(
                self._hand.snapshot_for(self._hand.seats[0])["played"]
            )
            if self._hand_envido:
                self._last_envido = self._hand_envido
            reveal = self._hand.snapshot_for(self._hand.seats[0])["envido_reveal"]
            if reveal:
                if self.mode == "pica" and self._duel_index < 2 and self.winner is None:
                    self._pica_reveal = reveal
                else:
                    self._reveal = reveal or self._pica_reveal
                    self._pica_reveal = None
            if self.mode == "pica" and self._pica_reveal and (
                self._duel_index == 2 or self.winner is not None
            ):
                self._reveal = self._pica_reveal
                self._pica_reveal = None
            if self.winner is None:
                if self.mode == "pica" and self._duel_index < 2:
                    self._duel_index += 1
                    self._deal()
                else:
                    self._dealer = (self._dealer + 1) % len(self.seats)
                    self._pica_cards = None
                    self._set_mode()
                    self._deal()
        return awards

    def view(self, actor: str) -> dict[str, object]:
        if actor not in self.seats:
            raise ValueError("unknown player")
        if self._hand is not None and actor in self._hand.seats:
            view = self._hand.snapshot_for(actor)
        elif self.mode == "pica" and self._pica_cards is not None:
            view = self._hand.snapshot_for(self._hand.seats[0])
            view.update(actor=actor, cards=self._pica_cards[actor], legal=())
        else:
            view = {
                "actor": actor,
                "turn": None,
                "score": self.score,
                "pica": self.mode == "pica",
                "cards": (),
                "played": (),
                "folded": (),
                "tricks": (),
                "legal": (),
                "done": self.winner is not None,
            }
        return {
            **view,
            "played": view.get("played") or self._last_table,
            "mode": self.mode,
            "duel": self._duel,
            "score": self.score,
            "winner": self.winner,
            "envido": self._last_envido,
            "reveal": self._reveal,
        }
