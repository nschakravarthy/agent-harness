from __future__ import annotations

from typing import Any, Mapping

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


def freeze(value: Any) -> Any:
    """Recursively convert a value into a hashable equivalent.

    Mappings become FrozenDicts, sequences become tuples, sets become
    frozensets. Scalars are returned unchanged.
    """
    if isinstance(value, FrozenDict):
        return value
    if isinstance(value, Mapping):
        return FrozenDict(value)
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze(v) for v in value)
    return value


class FrozenDict(dict):
    """An immutable, hashable mapping.

    Subclasses `dict` on purpose: it stays JSON-serializable, pydantic
    serializes it as an ordinary object, and `isinstance(x, dict)` holds for
    anything downstream that type-checks. Values are frozen recursively on
    construction so `hash()` cannot trip over a nested list or dict.

    Freezing changes nested sequences to tuples, so a FrozenDict compares
    equal to a plain dict only when no nested sequences are involved. A
    JSON round-trip is stable: lists thaw back to tuples on validation.
    """

    def __init__(self, data: Mapping[str, Any] | Any = (), **kwargs: Any) -> None:
        super().__init__(
            {k: freeze(v) for k, v in dict(data, **kwargs).items()}
        )

    def __hash__(self) -> int:  # type: ignore[override]
        return hash(frozenset(self.items()))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self)!r})"

    # --- mutation is rejected ------------------------------------------------

    def _immutable(self, *args: Any, **kwargs: Any) -> Any:
        raise TypeError(f"{type(self).__name__} is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __ior__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable

    # --- pydantic integration ------------------------------------------------

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any,
                                     handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.dict_schema(core_schema.str_schema(),
                                    core_schema.any_schema()),
        )
