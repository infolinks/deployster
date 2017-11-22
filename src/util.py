import argparse
import collections
import termios
import tty

import emoji
from colors import *


def merge(*args):
    return merge_into({}, args)


def merge_into(target: dict, *args) -> dict:
    for source in args:
        for k, v in source.items():
            if k in target and isinstance(target[k], dict) and isinstance(source[k], collections.Mapping):
                merge_into(target[k], source[k])
            else:
                target[k] = source[k]
    return target


class _Indent:

    def __init__(self) -> None:
        super().__init__()
        self._indent = 0

    def indent(self) -> None:
        self._indent = self._indent + 5

    def unindent(self) -> None:
        self._indent = self._indent - 5

    @property
    def level(self) -> int:
        return self._indent


_indent = _Indent()


def indent() -> None:
    _indent.indent()


def unindent() -> None:
    _indent.unindent()


def _msg(message) -> str:
    indent = " " * _indent.level
    return "\n".join([indent + line for line in message.split("\n")])


def log(message) -> None:
    print(emoji.emojize(_msg(message), use_aliases=True), flush=True)


def logp(message) -> None:
    print(emoji.emojize(_msg(message), use_aliases=True), flush=True, end='')


def err(message) -> None:
    print(emoji.emojize(_msg(message), use_aliases=True), flush=True, file=sys.stderr)


def ask(message, chars, default) -> str:
    prompt = message + ' ['
    for c in chars:
        prompt = prompt + (c.upper() if c == default else c.lower())
        prompt = prompt + '/'
    prompt = emoji.emojize(_msg(prompt[0:len(prompt) - 1] + '] '), use_aliases=True)
    print(prompt, flush=True, end='')

    while True:
        ch = getch().lower()
        if ord(ch[0]) == 3 or ord(ch[0]) == 4:
            log(underline(bold(red('ABORTED\n'))))
            exit(1)
        elif ch.lower()[0] in chars.lower():
            log(bold(ch.lower()))
            return ch


def getch() -> None:
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
