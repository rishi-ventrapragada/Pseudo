"""Pseudo's core: plain Python functions with the privacy rules built in.

Rule for this folder: nothing here imports MCP, Hermes, or any model SDK
(DECISIONS.md D11). Any brain or wrapper can call these functions, and the
privacy checks inside them hold no matter who the caller is.
"""
