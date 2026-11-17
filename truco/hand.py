from dataclasses import dataclass, field

from truco.cards import Card, truco_rank


@dataclass(frozen=True)
class Award:
    team: int
    points: int
    reason: str


@dataclass
class Hand:
    seats: tuple[str, ...]
    teams: dict[str, int]
    dealer: int
    cards: dict[str, tuple[Card, Card, Card]]
    score: tuple[int, int]
    pica: bool = False
    _folded: set[str] = field(default_factory=set, init=False, repr=False)
    _used_slots: set[tuple[str, str]] = field(default_factory=set, init=False, repr=False)
    _played: list[tuple[str, str, Card]] = field(default_factory=list, init=False, repr=False)
    _tricks: list[tuple[int | None, str | None]] = field(default_factory=list, init=False, repr=False)
    _leader: str = field(init=False, repr=False)
    _turn: str = field(init=False, repr=False)
    _done: bool = field(default=False, init=False, repr=False)

    def __post_init__(self):
        if len(self.seats) not in (2, 4, 6):
            raise ValueError("a hand requires 2, 4, or 6 seats")
        self._leader = self.seats[(self.dealer + 1) % len(self.seats)]
        self._turn = self._leader

    @property
    def done(self) -> bool:
        return self._done

    def legal_for(self, actor: str) -> tuple[str, ...]:
        if self._done or actor != self._turn or actor in self._folded:
            return ()
        return ("play", "fold")

    def snapshot_for(self, actor: str) -> dict[str, object]:
        if actor not in self.cards:
            raise ValueError("unknown player")
        return {
            "actor": actor,
            "turn": self._turn,
            "score": self.score,
            "pica": self.pica,
            "cards": self.cards[actor],
            "played": tuple(
                {"player": player, "slot": slot, "card": card}
                for player, slot, card in self._played
            ),
            "folded": tuple(player for player in self.seats if player in self._folded),
            "tricks": tuple(team for team, _ in self._tricks),
            "legal": self.legal_for(actor),
            "done": self._done,
        }

    def act(self, actor: str, kind: str, value: str | None = None) -> tuple[Award, ...]:
        if self._done or actor not in self.seats or actor != self._turn:
            raise ValueError("action out of turn")
        if kind == "fold" and value is None:
            self._folded.add(actor)
            remaining = {self.teams[seat] for seat in self.seats if seat not in self._folded}
            if self.teams[actor] not in remaining:
                winner = next(
                    team for team in self.teams.values() if team != self.teams[actor]
                )
                award = Award(winner, 1, "truco")
                self._finish(award)
                return (award,)
            if self._played and len(self._played) == len(self.seats) - len(self._folded):
                award = self._close_trick()
                return (award,) if award else ()
            self._advance_turn(actor)
            return ()
        if kind != "play" or value not in ("a", "s", "d"):
            raise ValueError("invalid action")
        if any(player == actor for player, _, _ in self._played):
            raise ValueError("player already played this trick")
        card = self.cards[actor][("a", "s", "d").index(value)]
        if (actor, value) in self._used_slots:
            raise ValueError("card already played")

        self._used_slots.add((actor, value))
        self._played.append((actor, value, card))
        if len(self._played) == len(self.seats) - len(self._folded):
            award = self._close_trick()
            if award:
                return (award,)
            return ()
        self._advance_turn(actor)
        return ()

    def _advance_turn(self, actor: str) -> None:
        index = self.seats.index(actor)
        for offset in range(1, len(self.seats) + 1):
            candidate = self.seats[(index + offset) % len(self.seats)]
            if candidate not in self._folded and all(p != candidate for p, _, _ in self._played):
                self._turn = candidate
                return

    def _close_trick(self) -> Award | None:
        strongest = max(truco_rank(card) for _, _, card in self._played)
        winners = [entry for entry in self._played if truco_rank(entry[2]) == strongest]
        winner_team, winner_player = (None, None)
        if len({self.teams[player] for player, _, _ in winners}) == 1:
            winner_player, _, _ = next(
                entry for entry in self._played
                if entry in winners and self.teams[entry[0]] == self.teams[winners[0][0]]
            )
            winner_team = self.teams[winner_player]
        self._tricks.append((winner_team, winner_player))
        self._played.clear()

        counts = [sum(team == i for team, _ in self._tricks) for i in range(2)]
        pardas = sum(team is None for team, _ in self._tricks)
        if (
            max(counts) >= 2
            or (len(self._tricks) == 2 and pardas and max(counts))
            or len(self._tricks) == 3
        ):
            if counts[0] != counts[1]:
                team = counts.index(max(counts))
            else:
                first_winner = next(
                    (team for team, _ in self._tricks if team is not None), None
                )
                team = first_winner if first_winner is not None else self.teams[self._leader]
            award = Award(team, 1, "truco")
            self._finish(award)
            return award

        self._leader = winner_player if winner_player is not None else self._leader
        self._turn = self._leader
        return None

    def _finish(self, award: Award) -> None:
        score = list(self.score)
        score[award.team] += award.points
        self.score = tuple(score)
        self._done = True
