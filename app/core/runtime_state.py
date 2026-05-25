from collections import deque
from datetime import UTC, datetime
from traceback import format_exception

MAX_ERRORS = 20
LAST_ERRORS: deque[dict[str, str]] = deque(maxlen=MAX_ERRORS)


def record_error(source: str, exc: BaseException) -> None:
    LAST_ERRORS.appendleft(
        {
            "at": datetime.now(UTC).isoformat(),
            "source": source,
            "type": exc.__class__.__name__,
            "message": str(exc),
            "traceback": "".join(format_exception(type(exc), exc, exc.__traceback__))[-1800:],
        }
    )


def get_last_errors(limit: int = 5) -> list[dict[str, str]]:
    return list(LAST_ERRORS)[:limit]
