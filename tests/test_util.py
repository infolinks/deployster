import pytest
from colors import yellow, red

from util import UserError, Logger, merge_into, merge, post_process


def test_new_usererror():
    msg = f"hello!"
    e: UserError = UserError(msg)
    assert e.message == msg


@pytest.mark.parametrize("header", ["test header", None])
@pytest.mark.parametrize("indent_amount", [0, 2, 4])
@pytest.mark.parametrize("spacious", [True, False])
@pytest.mark.parametrize("info_content", ["info-line", None])
@pytest.mark.parametrize("warn_content", ["warn-line", None])
@pytest.mark.parametrize("error_content", ["error-line", None])
def test_logger_header(capsys,
                       header: str,
                       indent_amount: int,
                       spacious: bool,
                       info_content: str,
                       warn_content: str,
                       error_content):
    with Logger(header=header, indent_amount=indent_amount, spacious=spacious) as logger:
        if info_content is not None:
            logger.info(info_content)
        if warn_content is not None:
            logger.warn(warn_content)
        if error_content is not None:
            logger.error(error_content)

    expected = ''
    expected = expected + (f'{header}\n' if header is not None else '')
    expected = expected + (f'\n' if header is not None and spacious else '')
    expected = expected + (f'{" " * indent_amount}{info_content}\n' if info_content else '')
    expected = expected + (f'{" " * indent_amount}{yellow(warn_content)}\n' if warn_content else '')
    expected = expected + (f'{" " * indent_amount}\n' if spacious else '')
    readouterr = capsys.readouterr()
    assert readouterr.out == expected
    assert readouterr.err == (f'{" " * indent_amount}{red(error_content)}\n' if error_content else '')


@pytest.mark.parametrize("header", ["test header", None])
@pytest.mark.parametrize("indent_amount", [0, 2, 4])
@pytest.mark.parametrize("spacious", [True, False])
@pytest.mark.parametrize("content1", ["part1", None])
@pytest.mark.parametrize("content2", ["part2", None])
def test_logger_partial_line(capsys, header: str, indent_amount: int, spacious: bool, content1: str, content2: str):
    with Logger(header=header, indent_amount=indent_amount, spacious=spacious) as logger:
        if content1 is not None:
            logger.info(content1, newline=False)
        if content2 is not None:
            logger.info(content2, newline=True)

    expected = ''
    expected = expected + (f'{header}\n' if header is not None else '')
    expected = expected + (f'\n' if header is not None and spacious else '')
    if content1 is not None:
        expected = expected + f'{" " * indent_amount}{content1}'
        expected = expected + (f'{content2}\n' if content2 is not None else '')
        if spacious:
            expected = expected + (f'{" " * indent_amount}\n' if content2 is not None else '\n')
    else:
        expected = expected + (f'{" " * indent_amount}{content2}\n' if content2 is not None else '')
        expected = expected + (f'{" " * indent_amount}\n' if spacious else '')
    assert capsys.readouterr().out == expected


def test_merge_into():
    dst = {'k4': {'v41': 'vv41'}}
    src1 = {'k1': 'v1'}
    src2 = {'k2': 'v2'}
    src3 = {'k3': {'v3': 'vv3'}}
    src4 = {'k4': {'v4': 'vv4'}}
    result = merge_into(dst, src1, src2, src3, src4)
    assert result is dst
    assert result['k1'] == 'v1'
    assert result['k2'] == 'v2'
    assert isinstance(result['k3'], dict)
    assert result['k3']['v3'] == 'vv3'
    assert result['k4']['v41'] == 'vv41'
    assert result['k4']['v4'] == 'vv4'

    result = merge(src1, src2, src3)
    assert result is not dst
    assert result is not src1
    assert result is not src2
    assert result is not src3
    assert result['k1'] == 'v1'
    assert result['k2'] == 'v2'
    assert isinstance(result['k3'], dict)
    assert result['k3']['v3'] == 'vv3'
    assert 'k1' in src1
    assert 'k1' not in src2
    assert 'k1' not in src3
    assert 'k2' not in src1
    assert 'k2' in src2
    assert 'k2' not in src3
    assert 'k3' not in src1
    assert 'k3' not in src2
    assert 'k3' in src3


def test_post_processing():
    src = {
        'k1': 'v1',
        'k2': '{{ 1 + 2 }}',
        'k3': '{{ c1 + 1 }}',
        'k4': 'hello, {{ name }}!',
        'k5': {
            'kk51': 'vv51',
            'kk52': '{{ 1 + 2 }}',
            'kk53': '{{ c1 + 1 }}',
            'kk54': 'hello, {{ name }}!',
            'kk55': {
                'kk551': 'vv551',
                'kk552': '{{ 1 + 2 }}',
                'kk553': '{{ c1 + 1 }}',
                'kk554': 'hello, {{ name }}!',
            }
        },
        'k6': [
            'vv51',
            '{{ 1 + 2 }}',
            '{{ c1 + 1 }}',
            'hello, {{ name }}!',
        ],
        'k7': 7,
        'k8': [
            'a{{1+2}}b',
            '{{ (2+3) | string}}',
            '3+4'
        ]
    }

    context = {
        'c1': 1,
        'name': 'John'
    }

    result1 = post_process(value=src, context=context)
    assert result1['k1'] == 'v1'
    assert result1['k2'] == 3
    assert result1['k3'] == 2
    assert result1['k4'] == 'hello, John!'
    assert result1['k5'] == {
        'kk51': 'vv51',
        'kk52': 3,
        'kk53': 2,
        'kk54': 'hello, John!',
        'kk55': {
            'kk551': 'vv551',
            'kk552': 3,
            'kk553': 2,
            'kk554': 'hello, John!',
        }
    }
    assert result1['k6'] == [
        'vv51',
        3,
        2,
        'hello, John!'
    ]
    assert result1['k7'] == 7
    assert result1['k8'] == [
        'a3b',
        '5',
        '3+4'
    ]

    with pytest.raises(expected_exception=UserError, match=r'\' unknown_var \' yielded an undefined result'):
        post_process('{{ unknown_var }}', {})
