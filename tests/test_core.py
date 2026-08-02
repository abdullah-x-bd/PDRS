import json
from pathlib import Path
import random
import unittest

from pdrs import CompiledSchema, SchemaError, load_schema
from pdrs.examples import fixed_radix_schema


ROOT = Path(__file__).resolve().parents[1]


class PermitSchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema = load_schema(ROOT / "schemas" / "permit.json")

    def test_count(self):
        self.assertEqual(self.schema.count, 4000)
        self.assertEqual(self.schema.bit_length, 12)

    def test_known_rank(self):
        self.assertEqual(self.schema.rank(["experimental", 7, 13]), 3493)
        self.assertEqual(self.schema.unrank(3493), ["experimental", 7, 13])

    def test_boundaries(self):
        self.assertEqual(self.schema.unrank(0), ["research", 0, 0])
        self.assertEqual(self.schema.unrank(1199), ["research", 11, 99])
        self.assertEqual(self.schema.unrank(1200), ["transit", 0, 0])
        self.assertEqual(self.schema.unrank(3199), ["transit", 3, 499])
        self.assertEqual(self.schema.unrank(3999), ["experimental", 19, 39])

    def test_all_round_trips(self):
        for index in range(self.schema.count):
            value = self.schema.unrank(index)
            self.assertEqual(self.schema.rank(value), index)

    def test_invalid_values(self):
        with self.assertRaises(SchemaError):
            self.schema.rank(["research", 12, 0])
        with self.assertRaises(SchemaError):
            self.schema.rank(["unknown", 0, 0])
        with self.assertRaises(SchemaError):
            self.schema.unrank(4000)

    def test_sampling_produces_valid_values(self):
        rng = random.Random(7)
        for _ in range(1000):
            value = self.schema.sample(rng)
            rank = self.schema.rank(value)
            self.assertGreaterEqual(rank, 0)
            self.assertLess(rank, self.schema.count)


class FixedRadixTests(unittest.TestCase):
    def test_fixed_radix_equivalence(self):
        schema = CompiledSchema(fixed_radix_schema("clock", [24, 60, 60]))
        self.assertEqual(schema.count, 86400)
        self.assertEqual(schema.rank([10, 50, 0]), 39000)
        self.assertEqual(schema.unrank(39000), [10, 50, 0])

    def test_hash_is_canonical(self):
        a = fixed_radix_schema("x", [2, 3])
        b = json.loads(json.dumps(a, sort_keys=True))
        self.assertEqual(CompiledSchema(a).canonical_hash, CompiledSchema(b).canonical_hash)


class ValidationTests(unittest.TestCase):
    def test_cycle_rejected(self):
        document = {
            "root": "a",
            "nodes": {
                "a": {"type": "range", "start": 0, "stop": 1, "target": "a"}
            },
        }
        with self.assertRaisesRegex(SchemaError, "cycle"):
            CompiledSchema(document)

    def test_duplicate_choice_rejected(self):
        document = {
            "root": "a",
            "nodes": {
                "a": {
                    "type": "choice",
                    "branches": [
                        {"value": "x", "target": "end"},
                        {"value": "x", "target": "end"},
                    ],
                },
                "end": {"type": "terminal"},
            },
        }
        with self.assertRaisesRegex(SchemaError, "duplicate"):
            CompiledSchema(document)

    def test_unreachable_node_rejected(self):
        document = {
            "root": "end",
            "nodes": {
                "end": {"type": "terminal"},
                "unused": {"type": "terminal"},
            },
        }
        with self.assertRaisesRegex(SchemaError, "unreachable"):
            CompiledSchema(document)


if __name__ == "__main__":
    unittest.main()
