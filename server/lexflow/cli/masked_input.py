"""A password prompt that shows one ``*`` per character typed.

``getpass`` shows nothing at all while a password is typed, which on Windows
makes it hard to tell whether keys are arriving. This prompt echoes a mask
instead, never the password: the characters stay in memory only and are
returned to the caller.

How keys are read:

- Windows (PowerShell, cmd, the VS Code terminal): ``msvcrt.getwch()``, which
  reads one key from the console without echoing it (what ``getpass`` uses).
- macOS and Linux: the terminal is switched to non-echoing, non-canonical
  mode for the prompt and always restored afterwards, even on errors.
- Input that is not a terminal (piped or redirected): falls back to
  ``getpass.getpass`` unchanged. Scripts should use ``--password-stdin``.

Keys: Enter finishes; Backspace (or Delete) removes the last character and its
``*``; Ctrl+U clears the line; Ctrl+C cancels (``KeyboardInterrupt``); Ctrl+D
on an empty line cancels (``EOFError``). Arrow, function and other special keys
and other control characters (including Tab) are ignored, so they never end up
in a password by accident.
"""

from __future__ import annotations

import getpass
import os
import sys
import unicodedata
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TextIO

ReadKey = Callable[[], str]
Write = Callable[[str], None]

ENTER = frozenset({"\r", "\n"})
BACKSPACE = frozenset({"\x08", "\x7f"})
CTRL_C, CTRL_D, CTRL_U, ESC = "\x03", "\x04", "\x15", "\x1b"
# Windows reports arrow and function keys as one of these, then a key code.
WINDOWS_SPECIAL_PREFIX = frozenset({"\x00", "\xe0"})
# Far above the password policy's maximum: a stuck key cannot use up memory.
MAX_CHARS = 1024
ERASE_ONE = "\b \b"


def read_masked(prompt: str, read_key: ReadKey, write: Write) -> str:
    """Read a line from ``read_key`` one key at a time, echoing ``*`` per character.

    ``read_key`` returns one key (``""`` at end of input); ``write`` puts text
    on the terminal. Only the prompt, masks, erasures and a final newline are
    ever written.
    """
    chars: list[str] = []
    pending: list[str] = []

    def next_key() -> str:
        return pending.pop() if pending else read_key()

    write(prompt)
    try:
        while True:
            key = next_key()
            if key == "":
                raise EOFError
            if key in ENTER:
                return "".join(chars)
            if key == CTRL_C:
                raise KeyboardInterrupt
            if key == CTRL_D:
                if not chars:
                    raise EOFError
                continue
            if key in BACKSPACE:
                if chars:
                    chars.pop()
                    write(ERASE_ONE)
                continue
            if key == CTRL_U:
                write(ERASE_ONE * len(chars))
                chars.clear()
                continue
            if key in WINDOWS_SPECIAL_PREFIX:
                next_key()  # the key code of an arrow or function key
                continue
            if key == ESC:
                follower = next_key()
                if follower in ("[", "O"):  # a terminal escape sequence: skip it
                    while not ("@" <= next_key() <= "~"):
                        pass
                elif follower:
                    pending.append(follower)  # a lone Escape: keep the next key
                continue
            if "\ud800" <= key <= "\udbff":  # Windows: first half of a surrogate pair
                low = next_key()
                if not "\udc00" <= low <= "\udfff":
                    raise EOFError  # a broken pair: input ended or is corrupt
                key = (key + low).encode("utf-16", "surrogatepass").decode("utf-16")
            if unicodedata.category(key[0]) == "Cc":
                continue  # Tab and other control characters
            if len(chars) < MAX_CHARS:
                chars.append(key)
                write("*")
    finally:
        write("\n")


# One reader per platform. ``sys.platform`` checks let mypy check each branch
# on its own platform (locally on Windows, in CI on Linux).
if sys.platform == "win32":
    import msvcrt

    @contextmanager
    def terminal_keys(stream: TextIO) -> Iterator[ReadKey]:
        """Keys straight from the console, without echo."""
        yield msvcrt.getwch

else:
    import codecs
    import termios

    @contextmanager
    def terminal_keys(stream: TextIO) -> Iterator[ReadKey]:
        """Keys from the terminal in non-echoing raw mode, restored afterwards."""
        fd = stream.fileno()
        saved = termios.tcgetattr(fd)
        raw = termios.tcgetattr(fd)
        # No echo, keys one at a time, and Ctrl+C/Ctrl+Z/Ctrl+V arrive as keys
        # (handled above) instead of signals, so the terminal is always restored.
        raw[3] &= ~(termios.ECHO | termios.ICANON | termios.ISIG | termios.IEXTEN)
        raw[6][termios.VMIN] = 1
        raw[6][termios.VTIME] = 0
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        def read_key() -> str:
            while True:
                byte = os.read(fd, 1)
                if not byte:
                    return ""
                text = decoder.decode(byte)
                if text:
                    return text

        termios.tcsetattr(fd, termios.TCSAFLUSH, raw)
        try:
            yield read_key
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, saved)


def prompt_password(prompt: str = "Password: ") -> str:
    """Ask for a password on the terminal, showing ``*`` for each character."""
    stdin, out = sys.stdin, sys.stderr
    if stdin is None or not stdin.isatty():
        return getpass.getpass(prompt)

    def write(text: str) -> None:
        out.write(text)
        out.flush()

    with terminal_keys(stdin) as read_key:
        return read_masked(prompt, read_key, write)
