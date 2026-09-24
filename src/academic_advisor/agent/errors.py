"""Credential-free errors shared by provider adapters."""


class ProviderError(RuntimeError):
    """A sanitized provider failure safe to display and eligible for fallback."""
