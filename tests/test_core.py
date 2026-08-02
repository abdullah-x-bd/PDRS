from __future__ import annotations

import json
from pathlib import Path
import random
import unittest

from pdrs import CompiledSchema, SchemaError, SchemaLimits, load_schema
from pdrs.generators import fixed_radix_schema, layered_dag_schema

ROOT = Path(__file__).resolve().parents[1]


class StaticCorpusTests(unittest.TestCase):
    def test_expected_counts(self):
        expected = {
            "permit.json": 4000,
            "calendar.json": 731,
            "ai_actions.json": 77,
            "telecom.json": 5564,
            "compiler_ast.json": 134026,
            "administrative.json": 40568,
            "fuzz_target.json": 9911,
        }
        for filename, count in expected.items():
            with self.subTest(filename=filename):
                schema = load_schema(ROOT / "schemas" / filename)
                self.assertEqual(schema.count, count)

    def test_permit_boundaries(self):
        schema = load_schema(ROOT / "schemas" / "permit.json")
        self.assertEqual(schema.rank(["experimental", 7, 13]), 3493)
        self.assertEqual(schema.unrank(3493), ["experimental", 7, 13])
        self.assertEqual(schema.unrank(0), ["research", 0, 0])
        self.assertEqual(schema.unrank(1199), ["research", 11, 99])
        self.assertEqual(schema.unrank(1200), ["transit", 0, 0])
        self.assertEqual(schema.unrank(3999), ["experimental", 19, 39])

    def test_static_roundtrips(self):
        for path in sorted((ROOT / "schemas").glob("*.json")):
            schema = load_schema(path)
            rng = random.Random(schema.count)
            indices = range(schema.count) if schema.count <= 10_000 else rng.sample(range(schema.count), 10_000)
            for index in indices:
                value = schema.unrank(index)
                self.assertEqual(schema.rank(value), index)


class GraphAndLimitTests(unittest.TestCase):
    def test_shared_dag_is_accepted(self):
        document = layered_dag_schema("shared", depth=10, branch_factor=4, range_width=2)
        schema = CompiledSchema(document)
        self.assertEqual(schema.count, 8**10)
        self.assertEqual(schema.rank(schema.unrank(schema.count - 1)), schema.count - 1)

    def test_cycle_rejected(self):
        document = {
            "root": "a",
            "nodes": {"a": {"type": "range", "start": 0, "stop": 1, "target": "a"}},
        }
        with self.assertRaisesRegex(SchemaError, "cycle"):
            CompiledSchema(document)

    def test_unreachable_rejected(self):
        document = {
            "root": "end",
            "nodes": {"end": {"type": "terminal"}, "unused": {"type": "terminal"}},
        }
        with self.assertRaisesRegex(SchemaError, "unreachable"):
            CompiledSchema(document)

    def test_resource_limits(self):
        document = layered_dag_schema("deep", depth=100, branch_factor=2)
        with self.assertRaisesRegex(SchemaError, "depth"):
            CompiledSchema(document, limits=SchemaLimits(max_depth=50))
        with self.assertRaisesRegex(SchemaError, "bits"):
            CompiledSchema(document, limits=SchemaLimits(max_domain_bits=50))

    def test_partition_is_complete_and_disjoint(self):
        schema = load_schema(ROOT / "schemas" / "fuzz_target.json")
        intervals = [schema.partition(i, 7) for i in range(7)]
        self.assertEqual(intervals[0][0], 0)
        self.assertEqual(intervals[-1][1], schema.count)
        for left, right in zip(intervals, intervals[1:]):
            self.assertEqual(left[1], right[0])

    def test_fixed_rank_bytes(self):
        schema = load_schema(ROOT / "schemas" / "permit.json")
        value = ["transit", 2, 400]
        self.assertEqual(schema.decode_rank(schema.encode_rank(value)), value)


class CompatibilityTests(unittest.TestCase):
    def test_fixed_radix(self):
        schema = CompiledSchema(fixed_radix_schema("clock", [24, 60, 60]))
        self.assertEqual(schema.count, 86400)
        self.assertEqual(schema.rank([10, 50, 0]), 39000)
        self.assertEqual(schema.unrank(39000), [10, 50, 0])

    def test_canonical_hash(self):
        document = fixed_radix_schema("x", [2, 3])
        reordered = json.loads(json.dumps(document, sort_keys=True))
        self.assertEqual(CompiledSchema(document).canonical_hash, CompiledSchema(reordered).canonical_hash)


if __name__ == "__main__":
    unittest.main()
