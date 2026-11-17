from collections.abc import Awaitable, Callable

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, RichLog, Static


class TrucoApp(App[None]):
    """Small keyboard-first terminal client for a single Truco room."""

    CSS = """
    Screen { layout: vertical; }
    #title { height: 1; text-style: bold; }
    #main { height: 1fr; min-height: 5; }
    #board { width: 2fr; border: round $primary; padding: 0 1; }
    #side { width: 1fr; min-width: 16; }
    #chat-history { height: 1fr; border: round $secondary; padding: 0 1; }
    #help { height: auto; min-height: 2; }
    #chat-input { display: none; }
    #action-menu { height: auto; }
    #host-controls { height: auto; }
    """

    BINDINGS = [
        Binding("a", "play_a", "Jugar A", priority=True),
        Binding("s", "play_s", "Jugar S", priority=True),
        Binding("d", "play_d", "Jugar D", priority=True),
        Binding("e", "menu_envido", "Envido", priority=True),
        Binding("t", "menu_truco", "Truco", priority=True),
        Binding("m", "signal_menu", "Seña", priority=True),
        Binding("c", "chat_mode", "Chat", priority=True),
        Binding("escape", "cancel_mode", "Cancelar", priority=True),
        Binding("q", "quit", "Salir", priority=True),
    ]

    def __init__(
        self,
        send: Callable[[dict[str, object]], Awaitable[None]],
        initial_view: dict[str, object],
    ):
        super().__init__()
        self.send = send
        self.view = dict(initial_view)
        self.chat_mode = False
        self.menu: list[tuple[str, str, str | None]] = []
        self.history = [
            f"{item.get('sender', '?')}: {item.get('text', '')}"
            for item in self.view.get("chat", ()) if isinstance(item, dict)
        ]

    def compose(self) -> ComposeResult:
        yield Static("TRUCO", id="title", markup=False)
        with Horizontal(id="main"):
            yield Static("", id="table", markup=False)
            with Vertical(id="side"):
                yield RichLog(id="chat-history", wrap=True, markup=False, highlight=False)
                yield Static("", id="help", markup=False)
        yield Static("", id="action-menu", markup=False)
        yield Horizontal(Button("Sentar jugadores", id="seat"), Button("Empezar", id="start"), id="host-controls")
        yield Input(placeholder="Escribe en el chat y pulsa Enter", id="chat-input")

    def on_mount(self) -> None:
        self.set_focus(None)
        self.query_one("#host-controls").display = self._is_host()
        self._render()
        for line in self.history:
            self.query_one("#chat-history", RichLog).write(line)
        if hasattr(self, "network_reader"):
            self.run_worker(self.network_reader, name="network-reader")

    def _is_host(self) -> bool:
        players = self.view.get("players", [])
        name = self.view.get("local_name")
        return bool(players and name and players[0] == name)

    def _render(self) -> None:
        cards = self.view.get("cards", ())
        hand = "  ".join(
            f"{slot.upper()}: {getattr(card, 'rank', card.get('rank') if isinstance(card, dict) else '?')} "
            f"{getattr(card, 'suit', card.get('suit') if isinstance(card, dict) else '')}"
            for slot, card in zip("asd", cards)
        )
        table = self.view.get("table", ())
        played = "  ".join(
            f"{item.get('player')}: {item.get('card')}" for item in table if isinstance(item, dict)
        ) or "—"
        players = ", ".join(map(str, self.view.get("players", ())))
        score = self.view.get("score", (0, 0))
        winner = self.view.get("winner")
        status = f"Ganó el equipo {int(winner) + 1}" if winner is not None else (
            "Tu turno" if self.view.get("turn") == self.view.get("local_name") else
            f"Turno: {self.view.get('turn') or '—'}"
        )
        self.query_one("#title", Static).update(
            f"TRUCO  |  {self.view.get('phase', 'lobby')} · {self.view.get('mode') or 'mesa'}"
        )
        self.query_one("#table", Static).update(
            f"Jugadores: {players}\nPuntaje: {score}\nMesa: {played}\n"
            f"Tu mano: {hand or '—'}\n{status}"
        )
        legal = set(self.view.get("legal", ()))
        help_text = "a/s/d jugar · e envido · t truco · m seña · c chat · q salir"
        if self.chat_mode:
            help_text = "Chat: escribe y pulsa Enter (Esc cancela)"
        elif legal:
            help_text += f"\nAcciones legales: {', '.join(sorted(legal))}"
        self.query_one("#help", Static).update(help_text)
        self.query_one("#host-controls").display = self._is_host()
        self.query_one("#seat", Button).disabled = len(self.view.get("players", ())) != self.view.get("capacity")
        self.query_one("#start", Button).disabled = self.view.get("phase") != "lobby" or not self.view.get("seats")

    def apply_event(self, event: dict[str, object]) -> None:
        kind = event.get("type")
        if kind == "state" and isinstance(event.get("view"), dict):
            local_name = self.view.get("local_name")
            capacity = self.view.get("capacity")
            self.view = dict(event["view"])
            if local_name:
                self.view["local_name"] = local_name
            if capacity:
                self.view["capacity"] = capacity
            self._render()
        elif kind in ("chat", "signal"):
            text = (
                f"{event.get('sender', '?')}: {event.get('text')}"
                if kind == "chat" else f"Seña de {event.get('sender', '?')}: {event.get('code')}"
            )
            self.history.append(text)
            if self.is_mounted:
                self.query_one("#chat-history", RichLog).write(text)
        elif kind == "error":
            text = f"Error: {event.get('text', 'desconocido')}"
            self.history.append(text)
            if self.is_mounted:
                self.query_one("#chat-history", RichLog).write(text)

    def _action(self, kind: str, value: str | None = None) -> None:
        if f"bet:{value}" not in self.view.get("legal", ()) and kind == "bet":
            return
        if kind in ("play", "fold", "accept", "reject") and kind not in self.view.get("legal", ()):
            return
        self.run_worker(self.send({"type": "action", "kind": kind, "value": value}))

    def _open_menu(self, prefix: str) -> None:
        legal = list(self.view.get("legal", ()))
        if prefix in ("envido", "truco"):
            actions = [action for action in legal if action in ("accept", "reject") or (
                action.startswith("bet:") and (
                    action[4:] in ("envido", "real_envido", "falta_envido")
                ) == (prefix == "envido")
            )]
        else:
            actions = [action for action in ("accept", "reject") if action in legal]
        self.menu = [(action, action.replace("bet:", ""), "bet" if action.startswith("bet:") else None)
                     for action in actions]
        self.query_one("#action-menu", Static).update(
            "Acciones (Enter/1–9): " + "  ".join(f"{i+1}. {label}" for i, (_, label, _) in enumerate(self.menu))
            if self.menu else "No hay acciones legales para este menú"
        )

    def _select_menu(self, index: int) -> None:
        if not self.menu or index >= len(self.menu):
            return
        action, _, kind = self.menu[index]
        self.query_one("#action-menu", Static).update("")
        self.menu = []
        if kind:
            self._action(kind, action.removeprefix("bet:"))
        else:
            self._action(action)

    def on_key(self, event: events.Key) -> None:
        if self.chat_mode:
            return
        if self.menu and event.key in ("enter", *tuple(str(i) for i in range(1, 10))):
            self._select_menu(0 if event.key == "enter" else int(event.key) - 1)
            event.stop()
            event.prevent_default()
        elif event.key in tuple(str(i) for i in range(1, 10)):
            if (self.view.get("phase") == "playing" and self.view.get("mode") != "pica"
                    and len(self.view.get("players", ())) > 2):
                self.run_worker(self.send({"type": "signal", "code": int(event.key)}))
            event.stop()
            event.prevent_default()

    def action_play_a(self) -> None:
        if not self.chat_mode:
            self._action("play", "a")

    def action_play_s(self) -> None:
        if not self.chat_mode:
            self._action("play", "s")

    def action_play_d(self) -> None:
        if not self.chat_mode:
            self._action("play", "d")

    def action_menu_envido(self) -> None:
        if not self.chat_mode:
            self._open_menu("envido")

    def action_menu_truco(self) -> None:
        if not self.chat_mode:
            self._open_menu("truco")

    def action_signal_menu(self) -> None:
        if not self.chat_mode:
            self.query_one("#action-menu", Static).update("Señas: pulsa 1–9")

    def action_chat_mode(self) -> None:
        if self.chat_mode:
            return
        self.chat_mode = True
        field = self.query_one("#chat-input", Input)
        field.value = ""
        field.display = True
        field.focus()
        self._render()

    def action_cancel_mode(self) -> None:
        if self.chat_mode:
            self.chat_mode = False
            field = self.query_one("#chat-input", Input)
            field.value = ""
            field.display = False
            self.set_focus(None)
        self.menu = []
        self.query_one("#action-menu", Static).update("")
        self._render()

    def action_quit(self) -> None:
        if not self.chat_mode:
            self.exit()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if message:
            await self.send({"type": "chat", "text": message})
        event.input.value = ""
        self.chat_mode = False
        event.input.display = False
        self.set_focus(None)
        self._render()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "seat":
            await self.send({"type": "seat", "names": list(self.view.get("players", ()))})
        elif event.button.id == "start":
            await self.send({"type": "start"})
