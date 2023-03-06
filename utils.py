from __future__ import annotations

import re

from typing import Any, TypeVar, cast

T = TypeVar("T")

CUSTOM_REACTION_PATTERN = re.compile(r"!(r(eact)?)\s+(.*)")


def split_into_chunks(lst: list[T], n: int) -> list[list[T]]:
    return [lst[i : i + n] for i in range(0, len(lst), n)]


def get_name_from_author_obj(data: dict[Any, Any]) -> str:
    username = data["username"]
    first_name = data["first_name"]
    return cast(str, username or first_name)


def extract_custom_reaction(t: str) -> str | None:
    t = t.strip()
    match = re.match(CUSTOM_REACTION_PATTERN, t)
    if match is None:
        return None

    reaction = match.group(3).strip()
    if not reaction:
        return None

    return reaction
