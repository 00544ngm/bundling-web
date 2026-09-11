from __future__ import annotations

from backend.config import BackendSettings
from backend.security.provider_crypto import ProviderCrypto


def create_provider_crypto(settings: BackendSettings) -> ProviderCrypto:
    """Build the Fernet cipher that protects provider API keys at rest."""
    return ProviderCrypto(
        key_file=settings.provider_key_file,
        configured_key=settings.provider_encryption_key,
    )


__all__ = ["create_provider_crypto"]
