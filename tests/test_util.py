import pytest
from _pytest.capture import CaptureResult

from util import UserError, Logger


def test_new_usererror():
    msg = f"hello!"
    e: UserError = UserError(msg)
    assert e.message == msg


@pytest.mark.parametrize("header", ["test header"])
@pytest.mark.parametrize("indent_amount", [0, 2, 4])
@pytest.mark.parametrize("spacious", [True, False])
def test_logger_header(capsys, header: str, indent_amount: int, spacious: bool):
    with Logger(header=header, indent_amount=indent_amount, spacious=spacious):
        pass

    captured: CaptureResult = capsys.readouterr()
    assert captured.out == f'{header}\n' + (f'\n{" " * indent_amount}\n' if spacious else '')
