"""The masked password prompt (``lexflow.cli.masked_input``) and its use by the CLI.

Keystrokes are scripted, and everything written to the terminal is captured,
so these tests check exactly what an operator would see. None needs a database.
"""

from __future__ import annotations

import argparse
import getpass
import io
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from lexflow.cli import masked_input, users
from lexflow.cli.masked_input import ERASE_ONE, MAX_CHARS, read_masked

PROMPT = "New password: "


class Terminal:
    """Scripted keys in, captured output out."""

    def __init__(self, keys: str | list[str]) -> None:
        self.keys = list(keys)
        self.output = ""

    def read_key(self) -> str:
        return self.keys.pop(0) if self.keys else ""

    def write(self, text: str) -> None:
        self.output += text

    def ask(self, prompt: str = PROMPT) -> str:
        return read_masked(prompt, self.read_key, self.write)


# --- what is shown ------------------------------------------------------------------


def test_one_star_per_character_and_never_the_password() -> None:
    terminal = Terminal("correct horse\r")
    assert terminal.ask() == "correct horse"
    assert terminal.output == PROMPT + "*" * 13 + "\n"


def test_backspace_removes_the_last_character_and_its_star() -> None:
    terminal = Terminal("abcd\b\bxy\r")
    assert terminal.ask() == "abxy"
    assert terminal.output == PROMPT + "****" + ERASE_ONE * 2 + "**" + "\n"


def test_delete_key_works_like_backspace() -> None:  # what macOS/Linux terminals send
    terminal = Terminal("ab\x7fc\r")
    assert terminal.ask() == "ac"
    assert terminal.output == PROMPT + "**" + ERASE_ONE + "*" + "\n"


def test_backspace_on_an_empty_line_erases_nothing() -> None:
    terminal = Terminal("\b\b\x7fa\r")
    assert terminal.ask() == "a"
    assert terminal.output == PROMPT + "*\n"  # the prompt itself is never erased


def test_ctrl_u_clears_the_line() -> None:
    terminal = Terminal("wrong\x15right\r")
    assert terminal.ask() == "right"
    assert terminal.output == PROMPT + "*****" + ERASE_ONE * 5 + "*****" + "\n"


def test_enter_may_be_a_line_feed() -> None:
    assert Terminal("abc\n").ask() == "abc"


def test_an_empty_password_is_returned_for_the_policy_to_refuse() -> None:
    terminal = Terminal("\r")
    assert terminal.ask() == ""
    assert terminal.output == PROMPT + "\n"


def test_each_unicode_character_gets_one_star() -> None:
    # Windows delivers characters outside the BMP as two UTF-16 code units.
    smile = "\U0001f600"
    units = smile.encode("utf-16-le")
    halves = [
        units[0:2].decode("utf-16-le", "surrogatepass"),
        units[2:4].decode("utf-16-le", "surrogatepass"),
    ]
    terminal = Terminal(["é", "ß", *halves, "\r"])
    assert terminal.ask() == "éß" + smile
    assert terminal.output == PROMPT + "***\n"


# --- keys that must not end up in a password ---------------------------------------


def test_arrow_and_function_keys_are_ignored() -> None:
    # Windows: "\xe0" or "\x00" then a key code; terminals: escape sequences.
    terminal = Terminal(["a", "\xe0", "K", "b", "\x00", ";", "c", *"\x1b[D", "d", *"\x1bOP", "\r"])
    assert terminal.ask() == "abcd"
    assert terminal.output == PROMPT + "****\n"


def test_a_lone_escape_does_not_swallow_the_next_key() -> None:
    assert Terminal("a\x1bb\r").ask() == "ab"


def test_tab_and_other_control_characters_are_ignored() -> None:
    terminal = Terminal("a\tb\x1ac\x07\r")
    assert terminal.ask() == "abc"
    assert terminal.output == PROMPT + "***\n"


def test_input_is_capped_far_above_the_policy_maximum() -> None:
    terminal = Terminal("x" * (MAX_CHARS + 10) + "\r")
    assert terminal.ask() == "x" * MAX_CHARS
    assert terminal.output.count("*") == MAX_CHARS


# --- cancelling ----------------------------------------------------------------------


def test_ctrl_c_cancels_and_leaves_the_cursor_on_a_new_line() -> None:
    terminal = Terminal("secret\x03more\r")
    with pytest.raises(KeyboardInterrupt):
        terminal.ask()
    assert terminal.output == PROMPT + "******\n"


def test_ctrl_d_cancels_only_on_an_empty_line() -> None:
    with pytest.raises(EOFError):
        Terminal("\x04").ask()
    assert Terminal("ab\x04c\r").ask() == "abc"


def test_end_of_input_cancels() -> None:
    with pytest.raises(EOFError):
        Terminal("abc").ask()  # no Enter before the keys run out


def test_a_broken_surrogate_pair_cancels() -> None:
    high = "\U0001f600".encode("utf-16-le")[0:2].decode("utf-16-le", "surrogatepass")
    with pytest.raises(EOFError):
        Terminal([high, "a"]).ask()


# --- choosing how to read ------------------------------------------------------------


class FakeTty(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_a_terminal_gets_the_masked_prompt_on_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    keys = iter("pass\x7fs\r")

    @contextmanager
    def fake_keys(*_: object) -> Iterator[masked_input.ReadKey]:
        yield lambda: next(keys)

    monkeypatch.setattr(masked_input, "terminal_keys", fake_keys)
    monkeypatch.setattr(sys, "stdin", FakeTty())
    err, out = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    monkeypatch.setattr(sys, "stdout", out)

    assert masked_input.prompt_password(PROMPT) == "pass"
    assert err.getvalue() == PROMPT + "****" + ERASE_ONE + "*" + "\n"
    assert out.getvalue() == ""  # stdout stays clean for the command's own output


def test_without_a_terminal_it_falls_back_to_getpass(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []

    def fake_getpass(prompt: str) -> str:
        asked.append(prompt)
        return "x"

    monkeypatch.setattr(sys, "stdin", io.StringIO("ignored\n"))
    monkeypatch.setattr(getpass, "getpass", fake_getpass)
    assert masked_input.prompt_password(PROMPT) == "x"
    assert asked == [PROMPT]


def discard(_: str) -> None:
    pass


if sys.platform != "win32":  # a POSIX pseudo-terminal; runs in CI on Linux

    def test_posix_terminal_mode_is_restored() -> None:
        import pty
        import termios

        master, slave = pty.openpty()
        tty = os.fdopen(slave, "r")
        before = termios.tcgetattr(slave)
        os.write(master, b"ab\x7fc\r")
        with masked_input.terminal_keys(tty) as read_key:
            assert read_masked(PROMPT, read_key, discard) == "ac"
        assert termios.tcgetattr(slave) == before
        os.write(master, b"x\x03")
        with pytest.raises(KeyboardInterrupt), masked_input.terminal_keys(tty) as read_key:
            read_masked(PROMPT, read_key, discard)
        assert termios.tcgetattr(slave) == before  # restored after Ctrl+C too
        tty.close()
        os.close(master)


# --- the account command line --------------------------------------------------------


def typed(*answers: str) -> tuple[users.Console, io.StringIO]:
    """A console whose prompt is the real masked prompt fed by scripted keys."""
    terminal = Terminal("".join(answers))
    screen = io.StringIO()

    def write(text: str) -> None:
        screen.write(text)

    def prompt(text: str) -> str:
        return read_masked(text, terminal.read_key, write)

    return users.Console(stdin=io.StringIO(), stdout=io.StringIO(), prompt=prompt), screen


INTERACTIVE = argparse.Namespace(password_stdin=False)


def test_matching_passwords_are_accepted() -> None:
    console, screen = typed("a long passphrase 1\r", "a long passphrase 1\r")
    assert users._read_password(INTERACTIVE, console) == "a long passphrase 1"
    assert screen.getvalue() == (
        "New password: " + "*" * 19 + "\n" + "Repeat the new password: " + "*" * 19 + "\n"
    )
    assert "passphrase" not in screen.getvalue()


def test_a_corrected_typo_still_matches() -> None:
    console, _ = typed("a long passphrasr\be 1\r", "a long passphrase 1\r")
    assert users._read_password(INTERACTIVE, console) == "a long passphrase 1"


def test_mismatched_passwords_are_refused() -> None:
    console, screen = typed("a long passphrase 1\r", "a long passphrase 2\r")
    with pytest.raises(users.CommandError, match=r"do not match\. Nothing was changed\."):
        users._read_password(INTERACTIVE, console)
    assert "passphrase" not in screen.getvalue()


def test_cancelling_at_the_prompt_changes_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[str] = []

    def create(
        args: argparse.Namespace, session: object, settings: object, c: users.Console
    ) -> str:
        users._read_password(args, c)
        seen.append("saved")  # never reached
        return "created"

    monkeypatch.setattr(users, "cmd_create", create)
    console, screen = typed("half typed\x03")
    code = users.main(
        ["create", "--email", "a@lexflow.test", "--name", "A", "--role", "Advocate"], console
    )
    assert code == 130
    assert seen == []
    assert capsys.readouterr().err.strip() == "Cancelled. Nothing was changed."
    assert screen.getvalue() == "New password: " + "*" * 10 + "\n"
