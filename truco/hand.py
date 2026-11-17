from dataclasses import dataclass, field

from truco.cards import Card, envido_value, truco_rank


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
    _public_played: list[tuple[str, str, Card]] = field(default_factory=list, init=False, repr=False)
    _tricks: list[tuple[int | None, str | None]] = field(default_factory=list, init=False, repr=False)
    _leader: str = field(init=False, repr=False)
    _turn: str = field(init=False, repr=False)
    _done: bool = field(default=False, init=False, repr=False)
    _envido_pending: str | None = field(default=None, init=False, repr=False)
    _envido_current_points: int = field(default=0, init=False, repr=False)
    _envido_accepted_points: int = field(default=0, init=False, repr=False)
    _envido_raises: int = field(default=0, init=False, repr=False)
    _envido_last_bidder: str | None = field(default=None, init=False, repr=False)
    _envido_resume_turn: str | None = field(default=None, init=False, repr=False)
    _envido_resolved: bool = field(default=False, init=False, repr=False)
    _envido_reveal: tuple[str, tuple[Card, ...]] | None = field(default=None, init=False, repr=False)
    _truco_pending: str | None = field(default=None, init=False, repr=False)
    _truco_current_points: int = field(default=0, init=False, repr=False)
    _truco_accepted_points: int = field(default=1, init=False, repr=False)
    _truco_last_bidder: str | None = field(default=None, init=False, repr=False)
    _truco_resume_turn: str | None = field(default=None, init=False, repr=False)

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
        if self._envido_pending:
            raises = ("bet:falta_envido",) if self._envido_pending != "falta_envido" else ()
            if self._envido_pending == "envido":
                raises = ("bet:real_envido", "bet:falta_envido")
                if self._envido_raises == 1:
                    raises = ("bet:envido", *raises)
            return ("accept", "reject", *raises)
        envido = self._envido_actions(actor)
        if self._truco_pending:
            raises = {
                "truco": ("bet:retruco",),
                "retruco": ("bet:vale_cuatro",),
                "vale_cuatro": (),
            }[self._truco_pending]
            return ("accept", "reject", *raises, *envido)
        truco = ("bet:truco",) if self._truco_accepted_points == 1 else ()
        if self._truco_accepted_points == 2:
            truco = ("bet:retruco",)
        elif self._truco_accepted_points == 3:
            truco = ("bet:vale_cuatro",)
        if truco and self._truco_last_bidder and self.teams[actor] == self.teams[self._truco_last_bidder]:
            truco = ()
        if not self._tricks and not self._envido_resolved and not any(
            player == actor for player, _ in self._used_slots
        ):
            return ("play", "fold", *envido, *truco)
        return ("play", "fold", *truco)

    def _envido_actions(self, actor: str) -> tuple[str, ...]:
        if (
            not self._tricks
            and not self._envido_resolved
            and not any(player == actor for player, _ in self._used_slots)
        ):
            return ("bet:envido", "bet:real_envido", "bet:falta_envido")
        return ()

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
                for player, slot, card in (*self._public_played, *self._played)
            ),
            "used_slots": tuple(slot for player, slot in self._used_slots if player == actor),
            "pending_bet": (self._truco_pending or self._envido_pending, self._truco_last_bidder or self._envido_last_bidder),
            "folded": tuple(player for player in self.seats if player in self._folded),
            "tricks": tuple(team for team, _ in self._tricks),
            "envido_reveal": self._envido_reveal if self._done else None,
            "legal": self.legal_for(actor),
            "done": self._done,
        }

    def act(self, actor: str, kind: str, value: str | None = None) -> tuple[Award, ...]:
        if self._done or actor not in self.seats or actor != self._turn:
            raise ValueError("action out of turn")
        if kind == "bet" and value in ("envido", "real_envido", "falta_envido"):
            if f"bet:{value}" not in self.legal_for(actor):
                raise ValueError("invalid envido bet")
            if self._envido_pending is None:
                self._envido_resume_turn = actor
                self._envido_pending = value
                self._envido_current_points = self._envido_stake(value)
            else:
                self._envido_accepted_points += self._envido_current_points
                self._envido_pending = value
                self._envido_current_points = self._envido_stake(value)
            self._envido_raises += 1
            self._envido_last_bidder = actor
            self._advance_response(actor)
            return ()
        if kind == "bet" and value in ("truco", "retruco", "vale_cuatro"):
            if f"bet:{value}" not in self.legal_for(actor):
                raise ValueError("invalid truco bet")
            if self._truco_pending is None:
                self._truco_resume_turn = actor
            self._truco_pending = value
            self._truco_current_points = {"truco": 2, "retruco": 3, "vale_cuatro": 4}[value]
            self._truco_last_bidder = actor
            self._advance_response(actor)
            return ()
        if (
            kind in ("accept", "reject")
            and value is None
            and self._truco_pending
            and not self._envido_pending
        ):
            if kind == "reject":
                award = Award(
                    self.teams[self._truco_last_bidder],
                    self._truco_current_points - 1,
                    "truco",
                )
                self._finish(award)
                return (award,)
            self._truco_accepted_points = self._truco_current_points
            self._truco_pending = None
            self._truco_current_points = 0
            self._turn = self._truco_resume_turn or actor
            self._truco_resume_turn = None
            return ()
        if kind in ("accept", "reject") and value is None and self._envido_pending:
            if kind == "reject":
                points = self._envido_accepted_points or 1
                award = Award(self.teams[self._envido_last_bidder], points, "envido")
            else:
                points = self._envido_accepted_points + self._envido_current_points
                team, player = self._envido_winner()
                award = Award(team, points, "envido")
                self._envido_reveal = (player, self._envido_justifying_cards(player))
            self._envido_resolved = True
            self._envido_pending = None
            self._apply_award(award)
            if not self._done:
                self._turn = self._envido_resume_turn
            self._envido_resume_turn = None
            return (award,)
        if kind == "fold" and value is None:
            if "fold" not in self.legal_for(actor):
                raise ValueError("invalid action")
            self._folded.add(actor)
            remaining = {self.teams[seat] for seat in self.seats if seat not in self._folded}
            if self.teams[actor] not in remaining:
                winner = next(
                    team for team in self.teams.values() if team != self.teams[actor]
                )
                awards = [Award(winner, self._truco_accepted_points, "truco")]
                if not self._tricks and not self._envido_resolved and not any(
                    (actor, slot) in self._used_slots for slot in ("a", "s", "d")
                ):
                    awards.insert(0, Award(winner, 1, "envido"))
                applied = self._apply_awards(awards)
                self._done = True
                return applied
            if self._played and len(self._played) == len(self.seats) - len(self._folded):
                award = self._close_trick()
                return (award,) if award else ()
            self._advance_turn(actor)
            return ()
        if kind != "play" or value not in ("a", "s", "d"):
            raise ValueError("invalid action")
        if "play" not in self.legal_for(actor):
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

    def _envido_stake(self, bet: str) -> int:
        if bet == "envido":
            return 2
        if bet == "real_envido":
            return 3
        if self.pica:
            return 6
        if max(self.score) >= 15:
            return 30 - max(self.score)
        team, _ = self._envido_winner()
        return 30 - self.score[team]

    def _envido_winner(self) -> tuple[int, str]:
        active = tuple(player for player in self.seats if player not in self._folded)
        values = {player: envido_value(self.cards[player]) for player in active}
        team_values = {team: max(values[p] for p in active if self.teams[p] == team) for team in (0, 1)}
        priority = tuple(p for p in self.seats[self.seats.index(self._leader):] + self.seats[:self.seats.index(self._leader)] if p in active)
        winning_team = max(team_values, key=lambda team: (team_values[team], -next(
            priority.index(p) for p in priority
            if self.teams[p] == team and values[p] == team_values[team]
        )))
        player = next(p for p in priority if self.teams[p] == winning_team and values[p] == team_values[winning_team])
        return winning_team, player

    def _envido_justifying_cards(self, player: str) -> tuple[Card, ...]:
        cards = self.cards[player]
        suits = {}
        for card in cards:
            suits.setdefault(card.suit, []).append(card)
        value = lambda card: card.rank if card.rank <= 7 else 0
        pairs = [sorted(group, key=value, reverse=True)[:2] for group in suits.values() if len(group) >= 2]
        if pairs:
            return tuple(max(pairs, key=lambda pair: sum(value(card) for card in pair)))
        return (max(cards, key=value),)

    def _apply_awards(self, awards: list[Award]) -> tuple[Award, ...]:
        applied = []
        for award in awards:
            self._apply_award(award)
            applied.append(award)
            if self._done:
                break
        return tuple(applied)

    def _apply_award(self, award: Award) -> None:
        score = list(self.score)
        score[award.team] = min(30, score[award.team] + award.points)
        self.score = tuple(score)
        if max(self.score) >= 30:
            self._done = True

    def _advance_turn(self, actor: str) -> None:
        index = self.seats.index(actor)
        for offset in range(1, len(self.seats) + 1):
            candidate = self.seats[(index + offset) % len(self.seats)]
            if candidate not in self._folded and all(p != candidate for p, _, _ in self._played):
                self._turn = candidate
                return

    def _advance_response(self, actor: str) -> None:
        index = self.seats.index(actor)
        for offset in range(1, len(self.seats) + 1):
            candidate = self.seats[(index + offset) % len(self.seats)]
            if candidate not in self._folded and self.teams[candidate] != self.teams[actor]:
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
        self._public_played.extend(self._played)
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
            award = Award(team, self._truco_accepted_points, "truco")
            self._finish(award)
            return award

        if winner_player is not None:
            self._leader = winner_player
        else:
            index = self.seats.index(self._leader)
            self._leader = next(
                self.seats[(index + offset) % len(self.seats)]
                for offset in range(1, len(self.seats) + 1)
                if self.seats[(index + offset) % len(self.seats)] not in self._folded
            )
        self._turn = self._leader
        return None

    def _finish(self, award: Award) -> None:
        self._apply_award(award)
        self._done = True
