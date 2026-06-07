"""Base Auth Types — AuthProvider ABC and UserIdentity."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class UserIdentity:
    """Verified external identity from an auth provider."""

    provider: str
    subject_id: str
    email: str
    display_name: Optional[str] = None


class AuthProvider(ABC):
    """Abstract base for authentication providers (password, SSO)."""

    @abstractmethod
    async def authenticate(self, **kwargs) -> UserIdentity:
        """Validate credentials and return a verified identity."""
        ...

