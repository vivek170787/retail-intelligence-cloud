"""
Consistent error envelope for EVERY route and EVERY failure mode:
{"error": {"message", "type"}} -- including the ones FastAPI/Starlette
generate automatically before a route handler ever runs (a 404 for an
unknown path, a 405 for a wrong method, a 422 for a request that fails
FastAPI's own input validation), not just the ones this project's own
code raises.

Every agent in this project already follows one convention: malformed
input (e.g. an empty sku/order_id) raises ValueError, while a well-formed-
but-unknown id is handled gracefully and returned as a normal 200 response
(e.g. {"order_found": False, ...}). So on top of FastAPI's own automatic
validation (missing/mis-typed query params and request bodies -- see
RequestValidationError below), the only exception mapping this project's
route logic itself needs is ValueError -> 400; anything else unexpected
becomes a 500 that never leaks internal exception details to the client.
"""

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Safe, generic messages for the handful of standard HTTP statuses
# Starlette/FastAPI can raise before a route handler runs. Anything not
# listed falls back to a generic "HTTP {status_code}" message -- never the
# framework's own exc.detail verbatim, which could vary.
_STATUS_MESSAGES = {
    404: "The requested resource was not found.",
    405: "This HTTP method is not allowed for this endpoint.",
}


def _envelope(message, error_type):
    return {"error": {"message": message, "type": error_type}}


async def value_error_handler(request, exc):
    return JSONResponse(status_code=400, content=_envelope(str(exc), "invalid_request"))


async def request_validation_error_handler(request, exc):
    """FastAPI's own automatic input validation (missing/mis-typed query
    params, a malformed request body) raises this before any route handler
    runs. Pydantic's error list is safe to summarize (it only ever
    describes which field was wrong and why, never internal state), so a
    short joined message is used rather than a generic placeholder."""
    details = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
    return JSONResponse(
        status_code=422, content=_envelope(f"Invalid request: {details}", "validation_error")
    )


async def http_exception_handler(request, exc):
    """Catches every other Starlette/FastAPI-raised HTTPException -- most
    commonly a 404 for an unmatched route or a 405 for a disallowed
    method -- and wraps it in the same envelope as this project's own
    errors, instead of Starlette's default {"detail": ...} shape."""
    message = _STATUS_MESSAGES.get(exc.status_code, f"HTTP {exc.status_code}.")
    error_type = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    return JSONResponse(status_code=exc.status_code, content=_envelope(message, error_type))


async def unhandled_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content=_envelope("An unexpected error occurred while processing this request.", "internal_error"),
    )


def install_error_handlers(app):
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
