"""Validação de formato de nomes de subreddit."""

import re

SUBREDDIT_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,20}$")


def validate_subreddit_name_format(name: str) -> bool:
    """Valida formato do nome do subreddit (3-21 chars, alfanumérico + underscore)."""
    return bool(SUBREDDIT_NAME_PATTERN.match(name))


def validate_subreddit_names_format(names: list[str]) -> tuple[list[str], list[str]]:
    """Separa nomes válidos e inválidos por formato.

    Returns:
        (valid_names, invalid_names)
    """
    valid = []
    invalid = []
    for name in names:
        if validate_subreddit_name_format(name):
            valid.append(name)
        else:
            invalid.append(name)
    return valid, invalid
