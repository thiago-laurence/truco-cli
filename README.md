# Truco terminal

Python 3.12+ terminal Truco with a Textual interface. Use one process as host;
the host automatically joins its own table through loopback before guests can
connect.

## Install

Windows (PowerShell):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m truco host --name Ana --players 4 --port 4977
```

Linux:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m truco host --name Ana --players 4 --port 4977
```

Guests run `python -m truco join --name Luis --host 192.168.1.8 --port 4977`
(use `.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on Linux).
The host lists detected IPv4 LAN addresses and the port. If detection misses
the right interface, pass `--address 192.168.1.8` to the host to print the
address to share.

## Play

Start one process on each terminal: two players for a one-on-one game, four
players for two teams, or six players for a six-player game. The host seats
the connected players and starts the match from the lobby. Use `a`, `s`, `d`
to play a card; `e` and `t` to choose among currently legal bets; `m` then
`1`–`9` for a signal; `c` to type chat (digits remain chat text); `Esc` to
cancel chat; and `q` to leave. Chat and the table remain visible when the
terminal is resized.

## Network safety

Allow inbound TCP on the selected port (default `4977`) in the host firewall.
On Windows, approve Python on **Private networks only** or add an inbound TCP
rule for the port. On Linux, allow it in the active firewall (for example,
`ufw allow 4977/tcp`) and remove the rule when finished if it is no longer
needed. Use only a trusted LAN: this game protocol is not encrypted or
authenticated, and anyone who can reach the host port may attempt to join.
Do not expose the port directly to the public internet.
