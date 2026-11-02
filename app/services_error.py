"""Shared error type so paths and services can import it without a cycle."""


class JournalError(ValueError):
    """The journal can show this message back on the form."""
