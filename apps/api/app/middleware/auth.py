# Re-export from app.auth.dependencies for backward compatibility
from app.auth.dependencies import (  # noqa: F401
    CurrentUser,
    ShopContext,
    get_current_shop,
    get_current_user,
    require_role,
    security,
)
