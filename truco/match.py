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
        self._duel: tuple[str, ...] = seats
        self._hand: Hand | None = None
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
            i = self._duel_index
            self._duel = (self.seats[i], self.seats[i + 3])
            teams = {seat: self.seats.index(seat) % 2 for seat in self._duel}
            dealer = next(
                self._duel.index(self.seats[(self._dealer + offset) % len(self.seats)])
                for offset in range(len(self.seats))
                if self.seats[(self._dealer + offset) % len(self.seats)] in self._duel
            )
            order = self._duel
        else:
            self._duel = self.seats
            teams = {seat: i % 2 for i, seat in enumerate(self.seats)}
            dealer = self._dealer
            order = self.seats
        deck = self._deck_factory()
        cards = {
            seat: tuple(deck.pop() for _ in range(3))
            for seat in order
        }
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
            score[award.team] += award.points
            self.score = tuple(score)
            if max(self.score) >= 30:
                self.winner = self.score.index(max(self.score))
                break
        if self._hand.done:
            if self._hand_envido:
                self._last_envido = self._hand_envido
            reveal = self._hand.snapshot_for(self._hand.seats[0])["envido_reveal"]
            if reveal:
                self._reveal = reveal
            if self.winner is None:
                self._dealer = (self._dealer + 1) % len(self.seats)
                if self.mode == "pica" and self._duel_index < 2:
                    self._duel_index += 1
                else:
                    self._set_mode()
                self._deal()
        return awards

    def view(self, actor: str) -> dict[str, object]:
        if actor not in self.seats:
            raise ValueError("unknown player")
        if self._hand is not None and actor in self._hand.seats:
            view = self._hand.snapshot_for(actor)
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
            "mode": self.mode,
            "duel": self._duel,
            "score": self.score,
            "winner": self.winner,
            "envido": self._last_envido,
            "reveal": self._reveal,
        }
