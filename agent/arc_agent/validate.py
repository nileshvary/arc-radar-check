"""Input validation."""

import re

from .errors import AgentError

_ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40}")


def is_evm_address(value):
    return isinstance(value, str) and _ADDRESS_RE.fullmatch(value) is not None


def require_evm_address(value):
    if not is_evm_address(value):
        raise AgentError("INVALID_ADDRESS")
    return value
