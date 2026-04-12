"""Regression tests for the trailing-slash / CORS redirect bug.

Background
----------
FastAPI's default ``redirect_slashes=True`` caused ``GET /api/v1/videos`` to
307-redirect to ``GET /api/v1/videos/`` (because routers declared
``@router.get("/")`` under a prefix like ``/videos``). The dashboard calls
every list endpoint **without** a trailing slash, and its requests include an
``Authorization: Bearer ...`` header which triggers a CORS preflight. Per the
Fetch spec, preflighted requests cannot follow redirects, so every list
fetch failed in the browser with a confusing
``No 'Access-Control-Allow-Origin' header`` error.

The fix normalized every collection-root route to an empty path (e.g.
``@router.get("")``) and disabled ``redirect_slashes`` on the FastAPI app.
These tests pin both halves of that fix so regressions are caught at
``pnpm test:py`` time instead of in the browser.
"""

from app.main import app


# Endpoints the dashboard calls without a trailing slash. If any of these
# reappear as ``/api/v1/foo/`` in the route table, the dashboard will break
# with a CORS-on-redirect error again.
EXPECTED_NO_SLASH_PATHS = {
    "/api/v1/videos",
    "/api/v1/voices",
    "/api/v1/products",
    "/api/v1/scripts",
    "/api/v1/shops",
    "/api/v1/personas",
    "/api/v1/sessions",
    "/api/v1/products/{product_id}/faqs",
}


def _registered_paths() -> set[str]:
    return {getattr(r, "path", None) for r in app.routes if getattr(r, "path", None)}


def test_redirect_slashes_disabled():
    """FastAPI must NOT auto-redirect /foo <-> /foo/.

    Preflighted CORS requests cannot follow redirects (Fetch spec), so any
    307 breaks the dashboard. See apps/api/app/main.py.
    """
    assert app.router.redirect_slashes is False


def test_collection_roots_registered_without_trailing_slash():
    """Every list endpoint the dashboard calls must be registered at the
    no-slash path, not the slash variant."""
    paths = _registered_paths()
    missing = EXPECTED_NO_SLASH_PATHS - paths
    assert not missing, (
        f"Expected these routes to be registered without a trailing slash, "
        f"but they were missing: {sorted(missing)}. "
        f"If you see /api/v1/foo/ in the route table instead of /api/v1/foo, "
        f"change the router decorator from @router.get('/') to @router.get('')."
    )


def test_no_accidental_trailing_slash_variants():
    """None of the expected no-slash paths should also have a slash variant
    registered. A duplicate means someone added ``@router.get('/')`` back."""
    paths = _registered_paths()
    dupes = {p for p in EXPECTED_NO_SLASH_PATHS if f"{p}/" in paths}
    assert not dupes, (
        f"These routes have BOTH /foo and /foo/ registered, which is the "
        f"bug this test guards against: {sorted(dupes)}"
    )
