from __future__ import annotations

import json
import math
from typing import Iterable, Sequence

from .core import ChoiceNode, CompiledSchema, RangeNode, SchemaError, TerminalNode, Token


def bits_for_cardinality(cardinality: int) -> int:
    if cardinality <= 0:
        raise ValueError("cardinality must be positive")
    return max(0, (cardinality - 1).bit_length())


def token_codes(schema: CompiledSchema, value: Sequence[Token]) -> list[tuple[int, int]]:
    """Return each token as a zero-based code and its local alphabet size."""
    tokens = list(value)
    position = 0
    node_name = schema.root
    output: list[tuple[int, int]] = []
    while True:
        node = schema.nodes[node_name]
        if isinstance(node, TerminalNode):
            if position != len(tokens):
                raise SchemaError("trailing tokens")
            return output
        if position >= len(tokens):
            raise SchemaError("missing token")
        token = tokens[position]
        position += 1
        if isinstance(node, ChoiceNode):
            for index, branch in enumerate(node.branches):
                if branch.value == token:
                    output.append((index, len(node.branches)))
                    node_name = branch.target
                    break
            else:
                raise SchemaError(f"invalid choice {token!r}")
        elif isinstance(node, RangeNode):
            if not isinstance(token, int) or isinstance(token, bool):
                raise SchemaError("range token must be an integer")
            if not node.start <= token <= node.stop:
                raise SchemaError("range token outside bounds")
            output.append((token - node.start, node.stop - node.start + 1))
            node_name = node.target
        else:
            raise AssertionError("unknown node")


def uper_subset_bits(schema: CompiledSchema, value: Sequence[Token]) -> int:
    """Bit count for the X.691-style subset used by the benchmark.

    It encodes CHOICE indices and fully constrained whole numbers using the
    minimum local bit width, without octet alignment. It is not a full ASN.1
    implementation and is labelled as a subset throughout the evidence.
    """
    return sum(bits_for_cardinality(cardinality) for _, cardinality in token_codes(schema, value))


def _varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("varint requires a non-negative integer")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def protobuf_wire_bytes(schema: CompiledSchema, value: Sequence[Token]) -> bytes:
    """Schema-independent Protocol Buffers wire-format baseline.

    Every selected choice or range offset is encoded as a varint field. Field
    numbers follow path positions. This is a valid protobuf wire message and a
    conservative field-oriented baseline, but it is not claimed to be the
    smallest hand-optimized .proto for each schema.
    """
    out = bytearray()
    for position, (code, _) in enumerate(token_codes(schema, value), start=1):
        tag = (position << 3) | 0
        out.extend(_varint(tag))
        out.extend(_varint(code))
    return bytes(out)


def json_bytes(value: Sequence[Token]) -> bytes:
    return json.dumps(list(value), separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def rank_varint_bytes(schema: CompiledSchema, value: Sequence[Token]) -> bytes:
    return _varint(schema.rank(value))


def fixed_rank_bytes(schema: CompiledSchema, value: Sequence[Token]) -> bytes:
    return schema.encode_rank(value)


def naive_cartesian_bits(schema: CompiledSchema) -> int:
    """Fixed-field superset allocation inferred from all reachable depths.

    If some paths terminate before a depth where others continue, one sentinel
    value is reserved at that depth to represent absence.
    """
    current: set[str] = {schema.root}
    total = 0
    while current:
        next_nodes: set[str] = set()
        cardinalities: list[int] = []
        terminal_present = False
        for name in current:
            node = schema.nodes[name]
            if isinstance(node, TerminalNode):
                terminal_present = True
                continue
            if isinstance(node, ChoiceNode):
                cardinalities.append(len(node.branches))
                next_nodes.update(branch.target for branch in node.branches)
            else:
                cardinalities.append(node.stop - node.start + 1)
                next_nodes.add(node.target)
        if cardinalities:
            max_cardinality = max(cardinalities)
            if terminal_present:
                max_cardinality += 1
            total += bits_for_cardinality(max_cardinality)
        current = next_nodes
    return total


def average_metric(
    schema: CompiledSchema,
    metric,
    *,
    sample_limit: int = 20_000,
    sample_indices: Iterable[int] | None = None,
) -> float:
    if sample_indices is None:
        if schema.count <= sample_limit:
            indices = range(schema.count)
        else:
            step = schema.count / sample_limit
            indices = (min(schema.count - 1, int(i * step)) for i in range(sample_limit))
    else:
        indices = sample_indices
    total = 0.0
    count = 0
    for index in indices:
        total += metric(schema, schema.unrank(index))
        count += 1
    return total / count if count else math.nan
