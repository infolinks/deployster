from util import UserError


def test_new_usererror():
    msg = f"hello!"
    e: UserError = UserError(msg)
    assert e.message == msg
