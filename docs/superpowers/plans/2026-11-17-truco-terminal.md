# Truco argentino por terminal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar una partida de Truco Argentino para 2, 4 o 6 personas por terminal, en red local, con chat y señas privadas que pueden descubrirse.

**Architecture:** Un anfitrión ejecuta el motor y valida intenciones recibidas por TCP; los clientes reciben vistas filtradas y las pintan con Textual. Separar cálculo de cartas, estado de una mano, marcador/modos de partida, distribución de mensajes y entrada de terminal para probar reglas sin red ni interfaz.

**Tech Stack:** Python 3.12+, Textual, `asyncio`, TCP y `unittest` de la biblioteca estándar.

**Spec:** `docs/superpowers/specs/2026-11-17-truco-terminal-design.md`

## Global Constraints

- Python 3.12 o posterior; terminal Windows y Linux; una dependencia de ejecución: Textual.
- Solo red local de confianza; mensajes TCP de tamaño acotado y texto saneado; no prometer cifrado ni resistencia a un anfitrión malicioso.
- Baraja española de 40 cartas, tres por persona; 2, 4 o 6 personas; partida a 30 tantos sin Flor.
- Seis personas: redonda y pica-pica desde 5 hasta antes de 25 tantos; tres duelos consecutivos y Falta Envido de 6 tantos en pica-pica.
- Chat público visible durante toda la sesión; señas `1`–`9` solo a compañeros, con filtración independiente del 10 % al chat general; ninguna seña en mano a mano o pica-pica.
- Los clientes nunca reciben las cartas no jugadas de otros; excepción explícita: cartas del envido ganador reveladas al acabar esa mano.
- Al finalizar no hay revancha automática; al irse un cliente se cancela la partida, al irse el anfitrión se cierra la sala.
- No implementar bots, Flor, cuentas, torneos, persistencia, reconexión ni servicio remoto.
- El proyecto está vacío y **no es repositorio Git**: antes del primer commit, inicializar Git si sigue sin existir; no asumir commits previos.

## Review Focus

1. Nombre duplicado o sala llena: rechazar al entrante sin reemplazar una conexión existente (Task 6).
2. JSON inválido, trama mayor de 4096 bytes o texto de control: rechazar/limpiar el mensaje sin alterar estado ni ejecutar escape de terminal (Tasks 6 y 8).
3. Carta/canto enviado fuera de turno o repetido tras un cambio de estado: error visible, ningún punto ni carta alterados (Tasks 2 y 6).
4. Desconexión mientras se espera respuesta de Envido/Truco: cancelar la partida para todos y volver a sala; salida del anfitrión cierra todo (Task 7).
5. Redimensionar la terminal o escribir chat largo mientras llega una jugada: conservar el panel e historial, sin disparar atajos de juego (Task 8).

## File Map

- `requirements.txt`: única dependencia, Textual.
- `truco/cards.py`: baraja, fuerza y tantos del Envido.
- `truco/hand.py`: bazas, apuestas, turnos, puntos de una mano y vistas por participante.
- `truco/match.py`: reparto, marcador, ganador y calendario redonda/pica-pica.
- `truco/wire.py`: JSON por línea, cotas de entrada y limpieza de texto.
- `truco/room.py`: sala, equipos, chat, señas y filtrado de destinatarios.
- `truco/server.py`: conexiones TCP, salida limpia y difusión de eventos.
- `truco/ui.py`: pantalla y atajos de Textual; `truco/__main__.py`: comandos `host`/`join`.
- `tests/test_{cards,hand,match,wire,room,server,ui}.py`: una prueba enfocada por regla, más regresiones de riesgos del apartado anterior.
- `README.md`: instalación, conexión LAN y comprobación manual en ambos sistemas.

---

### Task 1: Cartas y tantos

**Files:** Create `requirements.txt`, `truco/__init__.py`, `truco/cards.py`, `tests/test_cards.py`; Git init solo si no existe.

**Interfaces:** Produce `Card(rank: int, suit: str)` inmutable (`suit` = `espada|basto|oro|copa`); `fresh_deck() -> list[Card]`; `shuffled_deck() -> list[Card]`; `truco_rank(card: Card) -> int` (mayor = más fuerte); `envido_value(cards: Sequence[Card]) -> int`.

- [ ] **Step 1: Write the failing test.** `test_deck_has_40_unique_cards_and_strength_order`: 40 cartas únicas, sin 8/9; `truco_rank(Card(1,"espada")) > truco_rank(Card(1,"basto")) > truco_rank(Card(7,"espada"))`; `test_envido_two_same_suit_and_figures`: `[7 espada, 6 espada, 12 copa] -> 33`, tres figuras de distintos palos `-> 0`.
- [ ] **Step 2: Run test to verify it fails.** `python -m unittest discover -s tests -p test_cards.py -v`; expected FAIL por import faltante.
- [ ] **Step 3: Implement the signatures in `truco/cards.py`.** Usar tabla de los 14 niveles de fuerza de la spec; validar rango y palo de la carta; `shuffled_deck` parte de `fresh_deck` y mezcla una vez. `requirements.txt` contiene `textual`.
- [ ] **Step 4: Run test to verify it passes.** Mismo comando; expected OK.
- [ ] **Step 5: Commit.** Si no hay Git, `git init`; añadir spec, plan y archivos de Task 1; `git commit -m "feat: define truco cards and scoring"`.

### Task 2: Bazas, turnos y mazo

**Files:** Create `truco/hand.py`, `tests/test_hand.py`.

**Interfaces:** Consumes `Card`, `truco_rank`, `envido_value`. Produces `Award(team: int, points: int, reason: str)` inmutable y `Hand(seats: tuple[str,...], teams: dict[str,int], dealer: int, cards: dict[str,tuple[Card,Card,Card]], score: tuple[int,int], pica: bool=False)`; `Hand.act(actor: str, kind: str, value: str|None=None) -> tuple[Award,...]`; `Hand.legal_for(actor: str) -> tuple[str,...]`; `Hand.snapshot_for(actor: str) -> dict[str,object]`; `Hand.done: bool`.

- [ ] **Step 1: Write the failing tests.** `test_first_parda_then_second_win_awards_one`: dos jugadores, dealer B, primera baza con dos 3, segunda A juega 7 oro contra 2 de B; gana A y `act` devuelve `Award(0,1,"truco")`. `test_fold_only_removes_self_until_team_empty`: cuatro jugadores después de cerrada la primera baza; se va uno y el equipo sigue, se va el segundo y rival gana 1. `test_replayed_slot_and_out_of_turn_leave_hand_unchanged`: ambas acciones se rechazan y el siguiente jugador y las cartas siguen idénticos.
- [ ] **Step 2: Run test to verify it fails.** `python -m unittest discover -s tests -p test_hand.py -v`; expected FAIL.
- [ ] **Step 3: Implement bazas/turnos/fold in `truco/hand.py`.** Posiciones originales `a/s/d`, desempate por primera baza ganada o mano si tres pardas; la mano de próxima baza es quien tiró la carta ganadora y, en parda, la mano previa. Error de acción inválida con `ValueError`; no cambiar estado antes de validar.
- [ ] **Step 4: Run tests.** `python -m unittest discover -s tests -p test_hand.py -v`; expected OK.
- [ ] **Step 5: Commit.** `git add truco/hand.py tests/test_hand.py && git commit -m "feat: resolve tricks and folds"`.

### Task 3: Envido y Falta

**Files:** Modify `truco/hand.py`, `tests/test_hand.py`.

**Interfaces:** Extends `Hand.act` with `kind="bet"` and `value="envido"|"real_envido"|"falta_envido"`, `kind="accept"|"reject"`; preserves `Award` and `legal_for` signatures from Task 2.

- [ ] **Step 1: Write failing tests.** `test_envido_accept_and_tie_go_to_mano`: puntajes iguales de 33, A es mano: `Award(0,2,"envido")`. `test_reject_after_envido_raise_awards_previously_accepted`: Envido, Real Envido, rechazo -> 2 tantos al último desafiante. `test_falta_in_malas_decides_match_and_in_pica_is_six`: con marcador `(10,9)` adjudica lo necesario para 30 al ganador; en pica adjudica 6. `test_envido_after_first_card_is_unavailable` y `test_folding_entire_team_before_envido_adds_one_point` verifican el cierre de esa apuesta.
- [ ] **Step 2: Run test to verify it fails.** `python -m unittest discover -s tests -p test_hand.py -v`; expected FAIL en los nuevos casos.
- [ ] **Step 3: Implement la subasta de Envido en `Hand.act`.** Declaración automática de tantos reales; no revelar manos rivales en `snapshot_for` y revelar solo cartas justificativas del ganador al finalizar; aceptar/escalar/rechazar según la spec.
- [ ] **Step 4: Run tests.** Mismo comando; expected OK.
- [ ] **Step 5: Commit.** `git add truco/hand.py tests/test_hand.py && git commit -m "feat: implement envido bidding"`.

### Task 4: Truco y prioridad de apuestas

**Files:** Modify `truco/hand.py`, `tests/test_hand.py`.

**Interfaces:** Extends `Hand.act(...,kind="bet",value="truco"|"retruco"|"vale_cuatro")`; `accept`/`reject` select the one pending bid and `legal_for` lists only valid actions.

- [ ] **Step 1: Write failing tests.** `test_truco_raise_accept_and_reject`: rechazar Truco da 1, rechazar Retruco querido da 2 y Vale Cuatro querido da 3; aceptar Vale Cuatro y ganar da 4. `test_only_accepting_team_can_raise`: el emisor no puede retrucarse. `test_envido_precedes_pending_truco`: en primera baza el rival responde al Truco con Envido; se adjudica Envido y se vuelve a pedir respuesta al Truco.
- [ ] **Step 2: Run test to verify it fails.** `python -m unittest discover -s tests -p test_hand.py -v`; expected FAIL.
- [ ] **Step 3: Implement apuestas de Truco y suspensión/reanudación por Envido.** Comprobar el resultado del Envido antes de adjudicar Truco; no aceptar acciones de carta mientras haya respuesta pendiente.
- [ ] **Step 4: Run tests.** Mismo comando; expected OK.
- [ ] **Step 5: Commit.** `git add truco/hand.py tests/test_hand.py && git commit -m "feat: implement truco bidding"`.

### Task 5: Partida, reparto y pica-pica

**Files:** Create `truco/match.py`, `tests/test_match.py`.

**Interfaces:** Consumes `Hand`, `Award`, `Card`, `shuffled_deck`. Produces `Match(seats: tuple[str,...], deck_factory: Callable[[],list[Card]]=shuffled_deck, initial_score: tuple[int,int]=(0,0))`, with seating team = index parity; `Match.act(actor: str, kind: str, value: str|None=None) -> tuple[Award,...]`; `Match.view(actor: str) -> dict[str,object]` (incluye `envido` y `reveal` al concluir la mano correspondiente); `Match.score: tuple[int,int]`; `Match.mode: str`; `Match.winner: int|None`.

- [ ] **Step 1: Write failing tests.** `test_each_deal_has_unique_private_cards_and_rotates_dealer`; `test_six_players_enter_pica_at_five_and_return_to_redonda_at_25`: con `initial_score=(5,0)` comienza pica; tres pares enfrentados distintos, duelos en orden, luego redonda; con `(25,0)` solo redonda. `test_first_duel_that_reaches_30_stops_remaining_duels`: no adjudicar puntos posteriores; `test_view_does_not_expose_opponents_cards`; `test_winning_envido_cards_revealed_at_hand_end_even_if_score_reaches_30`.
- [ ] **Step 2: Run test to verify it fails.** `python -m unittest discover -s tests -p test_match.py -v`; expected FAIL.
- [ ] **Step 3: Implement `Match`.** Un mazo nuevo mezclado por mano, mano/dador rotan por asiento, tres duelos de los asientos enfrentados (`i` y `i+3`), score actualizado tras cada `Award` y finalización inmediata a 30. Conservar el resultado/revelación del Envido anterior en la próxima vista pública aunque la siguiente mano ya esté repartida; no incluir cartas ajenas todavía no reveladas. `initial_score` solo facilita pruebas; el servidor siempre usa `(0,0)`.
- [ ] **Step 4: Run tests.** Mismo comando; expected OK.
- [ ] **Step 5: Commit.** `git add truco/match.py tests/test_match.py && git commit -m "feat: score matches and pica pica"`.

### Task 6: Protocolo, sala, chat y señas

**Files:** Create `truco/wire.py`, `truco/room.py`, `tests/test_wire.py`, `tests/test_room.py`.

**Interfaces:** Consumes `Match` and `Card`. Produces `clean_text(raw: str, max_len: int) -> str`, `async read_message(reader: asyncio.StreamReader) -> dict[str,object]`, `async write_message(writer: asyncio.StreamWriter, message: dict[str,object]) -> None`; `Room(host_name: str, capacity: int, rng: Callable[[],float]=random.random, deck_factory: Callable[[],list[Card]]=shuffled_deck)` with `join(name: str) -> None` (el anfitrión también se une), `seat(names: tuple[str,...]) -> None`, `start() -> None`, `dispatch(sender: str, message: dict[str,object]) -> dict[str,list[dict[str,object]]]`, `leave(name: str) -> dict[str,list[dict[str,object]]]` y `views() -> dict[str,dict[str,object]]`. Cada vista tiene `phase`, `players`, `seats`, `score`, `mode`, `turn`, `cards` (tres posiciones propias), `table`, `legal`, `chat` (historial completo), `envido`, `reveal` y `winner`; `dispatch` emite eventos `type="chat"|"signal"|"error"`.

- [ ] **Step 1: Write failing tests.** `test_invalid_or_oversize_json_rejected`: JSON distinto de objeto y más de 4096 bytes provocan error sin cambiar estado; `test_duplicate_name_or_full_room_rejected`; `test_out_of_turn_network_action_keeps_score_and_view`; `test_private_signal_only_to_teammates_then_leaks_at_threshold`: `rng=lambda:0.10` no difusión rival, `rng=lambda:0.09` chat para todos, ambos con recepción propia/equipo, y `rng` se invoca una vez por seña válida; `test_signal_rejected_in_duel_or_one_on_one`; `test_finished_room_still_accepts_chat_but_not_rematch`; `test_control_chars_and_long_chat_cleaned`, incluida secuencia ANSI.
- [ ] **Step 2: Run tests to verify they fail.** `python -m unittest discover -s tests -p "test_*room.py" -v` y `python -m unittest discover -s tests -p test_wire.py -v`; expected FAIL.
- [ ] **Step 3: Implement `wire.py` y `room.py`.** JSON UTF-8 terminado en `\n`; límite de 4096 bytes por mensaje, nombres hasta 32 y chat hasta 300 caracteres; validar tipo de cada campo, limpiar controles, limitar destinatarios por evento y escalar solo acciones legales. `seat` exige exactamente el conjunto de participantes y alternancia por posición; `dispatch` acepta `{"type":"seat","names":[...]}`, `{"type":"start"}` (solo anfitrión), `{"type":"action","kind":...,"value":...}`, `{"type":"chat","text":...}` y `{"type":"signal","code":1..9}`; los mensajes de error vuelven solo al emisor. `views()` conserva historial del chat de la sesión y filtra el estado privado de cada participante.
- [ ] **Step 4: Run tests.** `python -m unittest discover -s tests -p "test_*room.py" -v`, `python -m unittest discover -s tests -p test_wire.py -v` y `python -m unittest discover -s tests -p test_hand.py -v`; expected OK.
- [ ] **Step 5: Commit.** `git add truco/wire.py truco/room.py tests/test_wire.py tests/test_room.py && git commit -m "feat: route room events without leaking secrets"`.

### Task 7: Conexiones TCP y ciclo de vida

**Files:** Create `truco/server.py`, `tests/test_server.py`.

**Interfaces:** Consumes `Room`, `read_message`, `write_message`. Produces `async serve(room: Room, host: str, port: int) -> asyncio.AbstractServer`; connection handshake is `{"type":"join","name":str}`, then server sends events/views from `Room`; a dedicated async reader per client handles incoming messages without blocking the other clients.

- [ ] **Step 1: Write failing integration tests.** `test_loopback_two_clients_join_play_chat_and_receive_private_views`: bind `127.0.0.1:0`, conectar dos clientes con streams, iniciar solo al completar sala, jugar una carta y difundir sin cartas del contrario. `test_disconnect_during_pending_bet_returns_remaining_clients_to_lobby`: desconectar tras Truco/Envido pendiente, descartar partida y permitir rellenar plaza. `test_host_leaving_closes_room_and_clients_receive_notice`; `test_remote_client_cannot_claim_host_name`.
- [ ] **Step 2: Run test to verify it fails.** `python -m unittest discover -s tests -p test_server.py -v`; expected FAIL.
- [ ] **Step 3: Implement `serve`.** Un único event loop valida todas las intenciones; manejar desconexión, JSON inválido y cierre de sockets por cliente, sin tumbar el servidor por error remoto. Host local se une primero mediante loopback y es el único autorizado a ocupar `host_name`; tras `join`, `seat`, `start` o una acción difundir `{"type":"state","view":room.views()[name]}` por destinatario, nunca una vista compartida; transmitir aparte los eventos de `dispatch`. Salir del host cierra todos los streams.
- [ ] **Step 4: Run tests.** `python -m unittest discover -s tests -v`; expected OK.
- [ ] **Step 5: Commit.** `git add truco/server.py tests/test_server.py && git commit -m "feat: host multiplayer rooms over lan"`.

### Task 8: Interfaz de terminal y comandos

**Files:** Create `truco/ui.py`, `truco/__main__.py`, `tests/test_ui.py`, `README.md`.

**Interfaces:** Consumes wire events and the views from `Room`/`Match`. Produces `TrucoApp(send: Callable[[dict[str,object]], Awaitable[None]], initial_view: dict[str,object])` with `apply_event(event: dict[str,object]) -> None`, and `parse_args(argv: Sequence[str]|None=None) -> argparse.Namespace`; CLI: `python -m truco host --name Ana --players 4 --port 4977` and `python -m truco join --name Luis --host 192.168.1.8 --port 4977`.

- [ ] **Step 1: Install runtime dependency.** `python -m pip install -r requirements.txt`; expected Textual importable.
- [ ] **Step 2: Write failing Textual pilot and CLI tests.** `test_chat_mode_keeps_digits_as_text_and_retains_scrollable_history`; `test_play_and_bet_keys_send_only_valid_actions`; `test_resize_and_long_chat_keep_table_and_chat_visible_without_markup_execution` (aplicar vista entrante mientras se escribe); `test_cli_host_join_arguments_and_invalid_capacity`.
- [ ] **Step 3: Run test to verify it fails.** `python -m unittest discover -s tests -p test_ui.py -v`; expected FAIL por interfaz aún no implementada.
- [ ] **Step 4: Implement terminal interface/CLI.** Pantalla con panel de mesa, mano, puntaje, ayuda y chat desplazable; `a/s/d`, `e/t`, `m`, `c`, `Enter`, `Esc`, `q`, `1`–`9` según spec. `e/t` muestran menú de acciones legales, nunca opciones imposibles. Renderizar texto remoto como texto literal, no markup. En host, listar IPv4 locales candidatos y puerto (puede haber varias interfaces); permitir usar la IP indicada manualmente cuando la autodetección no acierte. `README.md` documenta instalación en Windows/Linux, firewall, LAN confiable y prueba con 2/4/6 terminales.
- [ ] **Step 5: Run tests and manual checks.** `python -m unittest discover -s tests -v` expected OK; ejecutar dos instancias locales y comprobar chat, teclas y victoria; repetir manualmente en terminales Windows y Linux antes de afirmar soporte probado.
- [ ] **Step 6: Commit.** `git add truco/ui.py truco/__main__.py tests/test_ui.py README.md && git commit -m "feat: play truco in windows and linux terminals"`.

## Final acceptance

- [ ] Ejecutar `python -m unittest discover -s tests -v` y confirmar salida OK.
- [ ] Realizar partida de prueba con 2, 4 y 6 procesos; confirmar privacidad, chat, señales en redonda, bloqueo en pica-pica, fin a 30, desconexión y pantalla de ganador.
- [ ] Inspeccionar `git status --short` y los cambios respecto de spec; no declarar verificaciones Windows/Linux que no se hayan ejecutado en esos sistemas.
