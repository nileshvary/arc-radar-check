import pytest

from arc_agent.errors import AgentError
from arc_agent.validate import is_evm_address, require_evm_address

VALID = "0x7777777777777777777777777777777777777777"


@pytest.mark.parametrize("value", [VALID, "0xAbCdEf0123456789abcdef0123456789ABCDEF01"])
def test_valid_addresses(value):
    assert is_evm_address(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "nonsense",
        "7777777777777777777777777777777777777777",  # no 0x
        "0x777",  # too short
        VALID + "7",  # too long
        "0xZZ77777777777777777777777777777777777777",  # not hex
        VALID + "\n",  # trailing newline
        " " + VALID,
        VALID + "/../../x",
        None,
        123,
    ],
)
def test_invalid_addresses(value):
    assert not is_evm_address(value)


def test_require_raises_invalid_address():
    with pytest.raises(AgentError) as exc:
        require_evm_address("0x123")
    assert exc.value.code == "INVALID_ADDRESS"
