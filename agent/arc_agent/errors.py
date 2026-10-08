"""Error type shared by all modules. Messages are written here, in code."""

MESSAGES = {
    "INVALID_ADDRESS": "The input is not a valid EVM address (expected 0x followed by 40 hex characters).",
    "TOKEN_NOT_FOUND": "No token contract was found at this address on Arc.",
    "EXPLORER_TIMEOUT": "The Arc explorer did not respond in time.",
    "EXPLORER_UNAVAILABLE": "The Arc explorer refused the request or is unavailable.",
    "BAD_RESPONSE": "The Arc explorer returned data in an unexpected format.",
    "CONFIG_ERROR": "Configuration is invalid: ARC_EXPLORER_URL must be an https URL and ARC_CHAIN_ID a positive whole number.",
}


class AgentError(Exception):
    """A failure with a fixed code; the message never contains remote data."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code
        self.message = MESSAGES[code]
