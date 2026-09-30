"""pseudo_brain: Pseudo's own agent loop (D15, M14), grown from playground/03_agent_loop.py.

It is an MCP client of pseudo_hands (hands.py), talks only to the providers in its allowlist
(providers.toml, D16, M16), keeps a trimmed session history (session.py), and runs THE LOOP
(loop.py) without printing, so any interface can show its events: the terminal now
(terminal.py), a React face in M18.
"""
