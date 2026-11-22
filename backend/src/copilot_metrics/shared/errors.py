"""Domain errors. Modules raise these; they know nothing about HTTP.

Each module subclasses one of the categories below. The API's central handler
(``shared/adapters/inbound/http/error_handlers.py``) maps the category to a status code, so adding a
new error never touches the web layer.
"""


class DomainError(Exception):
    """Base of every expected failure. ``code`` is a stable, machine-readable name."""

    code = "domain_error"
    default_message = "The request could not be completed"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class NotAuthenticated(DomainError):
    """The caller is not (or no longer) signed in."""

    code = "not_authenticated"


class AccessDenied(DomainError):
    """The caller is signed in but may not see this."""

    code = "access_denied"


class NotFound(DomainError):
    code = "not_found"


class InvalidRequest(DomainError):
    """The caller asked for something that can never succeed as stated."""

    code = "invalid_request"
