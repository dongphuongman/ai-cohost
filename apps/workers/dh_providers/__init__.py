"""Digital human provider abstraction.

Default provider: LiteAvatar (self-hosted, ~$0/min). Fallback: HeyGen ($0.40/min).
The router selects providers based on availability + avatar support, with
auto-fallback when the primary provider fails.

When ``LITE_AVATAR_URL`` is unset, ``LiteAvatarProvider.is_available()`` returns
False and the router transparently uses HeyGen — production behavior is identical
to the pre-refactor flow.
"""

from .base import DHProvider, GenerateRequest, GenerateResponse
from .heygen import HeyGenProvider
from .liteavatar import LiteAvatarProvider
from .router import DHProviderRouter

__all__ = [
    "DHProvider",
    "GenerateRequest",
    "GenerateResponse",
    "HeyGenProvider",
    "LiteAvatarProvider",
    "DHProviderRouter",
]
