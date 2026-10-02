"""Credential-free provider diagnostics used by the gateway and runtime."""


class ProviderFailure(Exception):
    def __init__(self, code: str, *, retryable: bool = False, usage_unknown: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.usage_unknown = usage_unknown
