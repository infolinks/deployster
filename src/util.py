import collections
import termios
import tty
from contextlib import AbstractContextManager
from typing import Any, Callable

import emoji
from colors import *
from jinja2 import Environment, Template
from jinja2.exceptions import TemplateSyntaxError


class UserError(Exception):
    def __init__(self, message) -> None:
        super().__init__(message)
        self.message = message


class Logger(AbstractContextManager):
    _global_indent: int = 0

    def __init__(self, header: str = None, indent_amount: int = 6, spacious: bool = True) -> None:
        super().__init__()
        self._header: str = header
        self._indent_amount: int = indent_amount
        self._spacious: bool = spacious
        self._indent: int = Logger._global_indent
        self._line_ended: bool = True

    def __enter__(self) -> 'Logger':
        if self._header:
            self.info(self._header)
            if self._spacious:
                self.info('')

        Logger._global_indent += self._indent_amount
        self._indent: int = Logger._global_indent
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> Any:
        if self._spacious:
            self.info('')

        Logger._global_indent -= self._indent_amount
        self._indent: int = Logger._global_indent

        # returning None means that exception should be handled as normal by the caller; if we returned True then
        # the exception would be SUPPRESSED and not raised onward. (you normally wouldn't want that)
        return None

    def _wrap_message(self, message: str, color: Callable[[str], str] = None) -> str:
        if color: message = color(message)
        lines: list = message.split('\n')
        if self._line_ended:
            return "\n".join([(' ' * self._indent) + emoji.emojize(line, use_aliases=True) for line in lines])
        else:
            first_line = emoji.emojize(lines.pop(0), use_aliases=True)
            rest_lines = "\n".join([emoji.emojize(line, use_aliases=True) for line in lines])
            return first_line + rest_lines

    def info(self, message: str, newline: bool = True) -> None:
        print(self._wrap_message(message), file=sys.stdout, end='\n' if newline else '')
        sys.stdout.flush()
        self._line_ended: bool = newline

    def warn(self, message: str, newline: bool = True) -> None:
        print(self._wrap_message(message, yellow), file=sys.stdout, end='\n' if newline else '')
        sys.stdout.flush()
        self._line_ended: bool = newline

    def error(self, message: str, newline: bool = True) -> None:
        print(self._wrap_message(message, red), file=sys.stderr, end='\n' if newline else '')
        sys.stderr.flush()
        self._line_ended: bool = newline


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


def ask(logger: Logger, message: str, chars: str, default: str) -> str:
    def getch() -> None:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    prompt = message + ' ['
    for c in chars:
        prompt = prompt + (c.upper() if c == default else c.lower())
        prompt = prompt + '/'
    prompt = prompt[0:len(prompt) - 1] + '] '
    logger.info(prompt, newline=False)

    while True:
        ch = getch().lower()
        if ord(ch[0]) == 3 or ord(ch[0]) == 4:
            raise KeyboardInterrupt()
        elif ch.lower()[0] in chars.lower():
            logger.info(bold(ch.lower()))
            return ch


def post_process(value: Any, context: dict) -> Any:

    def _evaluate(expr: str)->Any:
        environment: Environment = Environment()
        try:
            if expr.startswith('{{') and expr.endswith('}}') and expr.find('{{') == expr.rfind('{{'):
                # line is a single expression (only one '{{' token at the beginning, and '}}' at the end)
                expr = expr[2:len(expr) - 2]
                result = environment.compile_expression(expr)(context)
                return result
            elif expr.find('{{') >= 0:
                # given string contains a jinja expression, use normal templating
                template: Template = environment.from_string(expr, globals=context)
                return template.render(context)
            else:
                return expr
        except TemplateSyntaxError as e:
            raise UserError(f"expression error in '{expr}': {e.message}") from e

    def _post_process_config(value) -> Any:
        if isinstance(value, str):
            return _evaluate(value)

        elif isinstance(value, dict):
            copy: dict = {}
            for k, v in value.items():
                copy[k] = _post_process_config(value=v)
            return copy
        elif isinstance(value, list):
            copy: list = []
            for item in value:
                copy.append(_post_process_config(value=item))
            return copy
        else:
            return value

    return _post_process_config(value=value)
