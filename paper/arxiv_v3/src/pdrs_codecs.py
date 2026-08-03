from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import struct
import zlib
from typing import Any, Iterable, Mapping, Sequence

import msgpack

from model import CompiledSchema, Choice, Range, Terminal, canonical_json


def varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("negative varint")
    output = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        output.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(output)


def fixed_rank(schema: CompiledSchema, rank: int) -> bytes:
    width = max(1, (schema.bit_length + 7) // 8)
    return rank.to_bytes(width, "big")


def mixed_radix_bits(schema: CompiledSchema, tokens: Sequence[Any]) -> int:
    name = schema.root
    total = 0
    position = 0
    while True:
        node = schema.nodes[name]
        if isinstance(node, Terminal):
            return total
        token = tokens[position]
        position += 1
        if isinstance(node, Choice):
            total += math.ceil(math.log2(len(node.branches))) if len(node.branches) > 1 else 0
            for branch in node.branches:
                if branch.value == token:
                    name = branch.target
                    break
            else:
                raise ValueError("invalid choice")
        else:
            width = node.stop - node.start + 1
            total += math.ceil(math.log2(width)) if width > 1 else 0
            name = node.target


def uper_bits(schema: CompiledSchema, tokens: Sequence[Any]) -> int:
    # Exact bit count for the fully constrained CHOICE and whole-number subset used here.
    return mixed_radix_bits(schema, tokens)


def aper_bits(schema: CompiledSchema, tokens: Sequence[Any]) -> int:
    # Aligned PER-style octet alignment at each constrained field boundary.
    name = schema.root
    total = 0
    position = 0
    while True:
        node = schema.nodes[name]
        if isinstance(node, Terminal):
            return total
        token = tokens[position]
        position += 1
        if isinstance(node, Choice):
            width = math.ceil(math.log2(len(node.branches))) if len(node.branches) > 1 else 0
            total += width
            if width and total % 8:
                total += 8 - total % 8
            branch = next(branch for branch in node.branches if branch.value == token)
            name = branch.target
        else:
            width = math.ceil(math.log2(node.stop - node.start + 1)) if node.stop > node.start else 0
            total += width
            if width and total % 8:
                total += 8 - total % 8
            name = node.target


def tagged_json(record: Mapping[str, Any]) -> bytes:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def tagged_msgpack(record: Mapping[str, Any]) -> bytes:
    return msgpack.packb(record, use_bin_type=True)


def schema_specific_bits(schema_name: str, record: Mapping[str, Any]) -> int:
    # Hand-packed layouts for the benchmark schema class. The layout omits field names but preserves type tags.
    if schema_name == "permit":
        return {"standard": 2 + 6 + 7, "temporary": 2 + 5 + 5, "experimental": 2 + 4 + 5}[record["permit_type"]]
    if schema_name == "fix_order":
        kind = record["message_type"]
        return {"D": 2 + 1 + 6 + 7, "F": 2 + 1 + 5, "G": 2 + 1 + 5 + 7, "V": 2 + 5 + 4}[kind]
    if schema_name == "iso_payment":
        base = 1 + 2
        if record["message"] == "pain.001":
            return base + 9 + 5
        return base + 10 + 5 + 1
    if schema_name == "quant_option":
        return 1 + 7 + 7 + 5 + 4
    if schema_name == "imbalanced":
        return 1 + (12 if record["kind"] == "common" else 3)
    raise KeyError(schema_name)


def shannon_code_length(probability: float) -> int:
    if probability <= 0:
        raise ValueError("probability must be positive")
    return math.ceil(-math.log2(probability))


def arithmetic_expected_bits(probabilities: Sequence[float], block_size: int) -> float:
    # Ideal arithmetic/range coding plus a conservative 2-bit interval termination overhead per block.
    entropy = -sum(p * math.log2(p) for p in probabilities if p > 0)
    return block_size * entropy + 2.0


def ans_expected_bits(probabilities: Sequence[float], block_size: int) -> float:
    # rANS with 12-bit normalized frequency table and 32-bit final state.
    table_overhead = 12 * len(probabilities)
    entropy = -sum(p * math.log2(p) for p in probabilities if p > 0)
    return block_size * entropy + 32 + table_overhead


def distribution_probabilities(schema: CompiledSchema, mode: str) -> list[float]:
    n = schema.count
    if mode == "uniform":
        return [1 / n] * n
    if mode == "zipf":
        weights = [1.0 / (rank + 1) for rank in range(n)]
    elif mode == "branch_skew":
        intervals = schema.root_intervals()
        factors = {label: 0.7 ** index for index, (label, _, _) in enumerate(intervals)}
        weights = []
        for rank in range(n):
            factor = next(factors[label] for label, start, stop in intervals if start <= rank < stop)
            weights.append(factor)
    elif mode == "finance_style":
        center = (n - 1) / 2
        scale = max(1.0, n / 8)
        weights = [math.exp(-abs(rank - center) / scale) + 0.05 for rank in range(n)]
    else:
        raise KeyError(mode)
    total = sum(weights)
    return [weight / total for weight in weights]


def expected_code_length(schema: CompiledSchema, mode: str, length_fn) -> float:
    probs = distribution_probabilities(schema, mode)
    return sum(probs[rank] * length_fn(rank) for rank in range(schema.count))


def self_contained_message(schema: CompiledSchema, rank: int, integrity: str, *, version: int = 2, key: bytes = b"PDRS-v3-research-key") -> bytes:
    rank_bytes = fixed_rank(schema, rank)
    schema_id = bytes.fromhex(schema.canonical_hash)[:16]
    body = bytes([version]) + schema_id + varint(len(rank_bytes)) + rank_bytes
    if integrity == "none":
        trailer = b""
    elif integrity == "crc32":
        trailer = struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    elif integrity == "mac16":
        trailer = hmac.new(key, body, hashlib.sha256).digest()[:16]
    else:
        raise KeyError(integrity)
    framed = varint(len(body) + len(trailer)) + body + trailer
    return framed


def verify_message(payload: bytes, integrity: str, *, key: bytes = b"PDRS-v3-research-key") -> bool:
    # This verifier assumes one-byte length prefixes for the experiment messages.
    if not payload:
        return False
    length = payload[0]
    if length != len(payload) - 1:
        return False
    content = payload[1:]
    if integrity == "none":
        return True
    trailer_len = 4 if integrity == "crc32" else 16
    if len(content) < trailer_len:
        return False
    body, trailer = content[:-trailer_len], content[-trailer_len:]
    if integrity == "crc32":
        expected = struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        return hmac.compare_digest(trailer, expected)
    if integrity == "mac16":
        expected = hmac.new(key, body, hashlib.sha256).digest()[:16]
        return hmac.compare_digest(trailer, expected)
    raise KeyError(integrity)


@dataclass(frozen=True)
class ReducedDecisionDiagram:
    nodes: int
    edges: int
    count: int
    index_bits: int


def reduced_mdd_summary(schema: CompiledSchema) -> ReducedDecisionDiagram:
    # Hash-cons nodes by semantic continuation. This is exact for the PDRS DAG class.
    signatures: dict[str, int] = {}
    memo: dict[str, str] = {}
    edges = 0
    for name in schema._postorder:
        node = schema.nodes[name]
        if isinstance(node, Terminal):
            signature = "T"
        elif isinstance(node, Choice):
            signature = "Q:" + node.field + ":" + ";".join(f"{b.value}->{memo[b.target]}" for b in node.branches)
            edges += len(node.branches)
        else:
            signature = f"R:{node.field}:{node.start}:{node.stop}->{memo[node.target]}"
            edges += node.stop - node.start + 1
        digest = hashlib.sha256(signature.encode()).hexdigest()
        memo[name] = digest
        signatures.setdefault(digest, len(signatures))
    return ReducedDecisionDiagram(len(signatures), edges, schema.count, schema.bit_length)
