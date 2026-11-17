import random
from collections.abc import Callable

from truco.cards import Card, shuffled_deck
from truco.match import Match
from truco.wire import clean_text


class Room:
    def __init__(
        self,
        host_name: str,
        capacity: int,
        rng: Callable[[], float] = random.random,
        deck_factory: Callable[[], list[Card]] = shuffled_deck,
    ):
        if capacity not in (2, 4, 6):
            raise ValueError("room capacity must be 2, 4, or 6")
        self.capacity = capacity
        self.host = clean_text(host_name, 32).strip()
        if not self.host:
            raise ValueError("name must not be empty")
        self.rng = rng
        self.deck_factory = deck_factory
        self.players = [self.host]
        self.seats: tuple[str, ...] | None = None
        self.match: Match | None = None
        self.chat: list[dict[str, object]] = []

    def join(self, name: str) -> None:
        name = clean_text(name, 32).strip()
        if not name:
            raise ValueError("name must not be empty")
        if name in self.players:
            raise ValueError("duplicate player name")
        if len(self.players) >= self.capacity:
            raise ValueError("room is full")
        if self.match is not None:
            raise ValueError("match already started")
        self.players.append(name)

    def seat(self, names: tuple[str, ...]) -> None:
        if self.match is not None:
            raise ValueError("match already started")
        if (not isinstance(names, tuple) or len(names) != self.capacity
                or len(set(names)) != self.capacity or set(names) != set(self.players)):
            raise ValueError("seats must contain each participant exactly once")
        self.seats = names

    def start(self) -> None:
        if self.match is not None:
            raise ValueError("match already started")
        if self.seats is None or len(self.players) != self.capacity:
            raise ValueError("room must be full and seated")
        self.match = Match(self.seats, self.deck_factory)

    def views(self) -> dict[str, dict[str, object]]:
        result = {}
        for player in self.players:
            match_view = self.match.view(player) if self.match else {}
            done = self.match is not None and self.match.winner is not None
            result[player] = {
                "phase": "finished" if done else "playing" if self.match else "lobby",
                "players": tuple(self.players),
                "seats": self.seats or (),
                "score": match_view.get("score", (0, 0)),
                "mode": match_view.get("mode"),
                "turn": match_view.get("turn"),
                "cards": match_view.get("cards", ()),
                "table": match_view.get("played", ()),
                "legal": match_view.get("legal", ()),
                "chat": list(self.chat),
                "envido": match_view.get("envido", ()),
                "reveal": match_view.get("reveal"),
                "winner": match_view.get("winner"),
            }
        return result

    def dispatch(
        self, sender: str, message: dict[str, object]
    ) -> dict[str, list[dict[str, object]]]:
        def error(text: str) -> dict[str, list[dict[str, object]]]:
            return {sender: [{"type": "error", "text": text}]}

        if sender not in self.players or not isinstance(message, dict):
            return error("invalid sender or message")
        kind = message.get("type")
        if kind == "seat":
            names = message.get("names")
            if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                return error("invalid seats")
            if sender != self.host:
                return error("only the host may seat players")
            try:
                self.seat(tuple(names))
            except ValueError as exc:
                return error(str(exc))
            return {}
        if kind == "start":
            if sender != self.host:
                return error("only the host may start")
            try:
                self.start()
            except ValueError as exc:
                return error(str(exc))
            return {}
        if kind == "action":
            action_kind = message.get("kind")
            value = message.get("value")
            if not isinstance(action_kind, str) or (value is not None and not isinstance(value, str)):
                return error("invalid action")
            if self.match is None:
                return error("match has not started")
            try:
                self.match.act(sender, action_kind, value)
            except ValueError as exc:
                return error(str(exc))
            return {}
        if kind == "chat":
            text = message.get("text")
            if not isinstance(text, str):
                return error("invalid chat")
            text = clean_text(text, 300).strip()
            if not text:
                return error("empty chat")
            event = {"type": "chat", "sender": sender, "text": text}
            self.chat.append(event)
            return {player: [event.copy()] for player in self.players}
        if kind == "signal":
            code = message.get("code")
            if type(code) is not int or not 1 <= code <= 9:
                return error("invalid signal")
            if self.match is None or self.match.mode == "pica" or len(self.players) == 2:
                return error("signals are unavailable")
            if self.match.winner is not None:
                return error("match is finished")
            signal = {"type": "signal", "sender": sender, "code": code}
            team = self.seats.index(sender) % 2
            recipients = [
                player for player in self.players
                if player != sender and self.seats.index(player) % 2 == team
            ]
            events = {sender: [signal.copy()]}
            events.update({player: [signal.copy()] for player in recipients})
            if self.rng() < 0.10:
                leaked = {
                    "type": "chat", "sender": sender,
                    "text": f"Seña {code}", "signal": code,
                }
                self.chat.append(leaked)
                for player in self.players:
                    events.setdefault(player, []).append(leaked.copy())
            return events
        return error("unknown message type")

    def leave(self, name: str) -> dict[str, list[dict[str, object]]]:
        if name not in self.players:
            return {}
        self.players.remove(name)
        if name == self.host:
            return {
                player: [{"type": "error", "text": "host left"}]
                for player in self.players
            }
        return {}
