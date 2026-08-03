from __future__ import annotations

import json
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdrs_v2 import CompiledSchema, SchemaError, naive_enumerate


def sample_schema() -> dict:
    return {
        "name": "typed-sample",
        "version": "1",
        "root": "kind",
        "nodes": {
            "kind": {
                "type": "choice",
                "field": "kind",
                "branches": [
                    {"value": "small", "target": "small_value"},
                    {"value": "large", "target": "large_value"},
                ],
            },
            "small_value": {
                "type": "range",
                "field": "value",
                "start": 0,
                "stop": 2,
                "target": "end",
            },
            "large_value": {
                "type": "range",
                "field": "value",
                "start": 10,
                "stop": 14,
                "target": "end",
            },
            "end": {"type": "terminal"},
        },
    }


class SemanticTests(unittest.TestCase):
    def test_bijection_matches_naive_semantics(self) -> None:
        document = sample_schema()
        schema = CompiledSchema(document)
        expected = naive_enumerate(document)
        self.assertEqual(schema.count, 8)
        self.assertEqual(len(expected), schema.count)
        for index, value in enumerate(expected):
            self.assertEqual(schema.rank(value), index)
            self.assertEqual(schema.unrank(index), value)

    def test_lowering_is_typed_and_injective(self) -> None:
        schema = CompiledSchema(sample_schema())
        records = {
            json.dumps(schema.lower(schema.unrank(rank)), sort_keys=True)
            for rank in range(schema.count)
        }
        self.assertEqual(len(records), schema.count)
        first = schema.lower(["small", 0])
        self.assertEqual(first["kind"], {"type": "string", "value": "small"})
        self.assertEqual(first["value"], {"type": "integer", "value": 0})

    def test_floyd_sampling_is_uniform_subset_interface(self) -> None:
        schema = CompiledSchema(sample_schema())
        selected = schema.sample_without_replacement(schema.count, random.Random(7))
        self.assertEqual(set(selected), set(range(schema.count)))
        self.assertEqual(len(selected), schema.count)
        with self.assertRaises(SchemaError):
            schema.sample_without_replacement(schema.count + 1, random.Random(7))

    def test_all_partition_policies_are_complete_and_disjoint(self) -> None:
        schema = CompiledSchema(sample_schema())
        policies = [
            schema.contiguous_partitions(3),
            schema.strided_partitions(3),
            schema.hash_partitions(3, 7),
            schema.permuted_partitions(3, 7),
        ]
        for parts in policies:
            flattened = [rank for part in parts for rank in part]
            self.assertEqual(len(flattened), schema.count)
            self.assertEqual(len(set(flattened)), schema.count)
            self.assertEqual(set(flattened), set(range(schema.count)))

    def test_repeated_field_on_path_is_rejected(self) -> None:
        document = {
            "name": "repeated-field",
            "root": "a",
            "nodes": {
                "a": {"type": "range", "field": "x", "start": 0, "stop": 1, "target": "b"},
                "b": {"type": "range", "field": "x", "start": 0, "stop": 1, "target": "end"},
                "end": {"type": "terminal"},
            },
        }
        with self.assertRaises(SchemaError):
            CompiledSchema(document)

    def test_unicode_normalization_is_canonical(self) -> None:
        left = sample_schema()
        right = sample_schema()
        left["nodes"]["kind"]["branches"][0]["value"] = "é"
        right["nodes"]["kind"]["branches"][0]["value"] = "e\u0301"
        self.assertEqual(CompiledSchema(left).canonical_hash, CompiledSchema(right).canonical_hash)

    def test_boolean_is_not_an_integer_token(self) -> None:
        schema = CompiledSchema(sample_schema())
        with self.assertRaises(SchemaError):
            schema.rank(["small", True])


if __name__ == "__main__":
    unittest.main()
