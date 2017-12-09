import pytest
from _pytest.capture import CaptureResult

from util import UserError, Logger


def test_new_usererror():
    msg = f"hello!"
    e: UserError = UserError(msg)
    assert e.message == msg


@pytest.mark.parametrize("header", ["test header", None])
@pytest.mark.parametrize("indent_amount", [0, 2, 4])
@pytest.mark.parametrize("spacious", [True, False])
@pytest.mark.parametrize("content", ["some-line", None])
def test_logger_header(capsys, header: str, indent_amount: int, spacious: bool, content: str):
    with Logger(header=header, indent_amount=indent_amount, spacious=spacious) as logger:
        if content is not None:
            logger.info(content)

    captured: CaptureResult = capsys.readouterr()
    if header is not None:
        expected = f'{header}\n' + \
                   (f'\n' if spacious else '') + \
                   (f'{" " * indent_amount}{content}\n' if content else '') + \
                   (f'{" " * indent_amount}\n' if spacious else '')
        assert captured.out == expected
    elif spacious:
        expected = (f'{" " * indent_amount}{content}\n' if content else '') + \
                   (f'{" " * indent_amount}\n' if spacious else '')
        assert captured.out == expected
