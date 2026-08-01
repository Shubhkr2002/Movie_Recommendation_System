"""
Security helpers.

This API is read-only and has no authenticated user accounts, so there is
no JWT/OAuth layer here. What *does* live here is the small set of
defensive helpers every endpoint relies on: input normalization/validation
so nothing malformed reaches the recommendation engine or an outbound
TMDB request.
"""

from fastapi import HTTPException, status


def ensure_non_empty(value: str, field_name: str = "value") -> str:
    """Raise a 422-equivalent error if a required string field is blank.

    Pydantic already enforces `min_length=1` on query/body fields, but this
    guard is used defensively inside services that may receive values from
    more than one call site.
    """
    if not value or not value.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must not be empty",
        )
    return value.strip()
