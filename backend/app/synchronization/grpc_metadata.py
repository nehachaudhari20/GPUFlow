from __future__ import annotations

from typing import Dict, Mapping, MutableMapping


def vector_from_proto(proto_map: Mapping[str, int] | None) -> Dict[str, int]:
    if not proto_map:
        return {}
    return {str(k): int(v) for k, v in proto_map.items()}


def apply_vector_to_proto(
    target: MutableMapping[str, int], vector: Dict[str, int]
) -> None:
    target.clear()
    for key, value in vector.items():
        target[key] = int(value)
