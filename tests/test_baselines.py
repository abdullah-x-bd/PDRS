from __future__ import annotations

from pathlib import Path
import unittest

from pdrs import load_schema
from pdrs.baselines import naive_cartesian_bits, protobuf_wire_bytes, uper_subset_bits

ROOT = Path(__file__).resolve().parents[1]


class BaselineTests(unittest.TestCase):
    def test_baseline_sizes_are_positive(self):
        schema = load_schema(ROOT / "schemas" / "permit.json")
        value = ["experimental", 7, 13]
        self.assertGreater(uper_subset_bits(schema, value), 0)
        self.assertGreater(len(protobuf_wire_bytes(schema, value)), 0)
        self.assertGreaterEqual(naive_cartesian_bits(schema), schema.bit_length)

    def test_local_packing_can_be_variable(self):
        schema = load_schema(ROOT / "schemas" / "compiler_ast.json")
        literal = ["literal", "bool", 1]
        call = ["call", 3, "two", 2, 5]
        self.assertNotEqual(uper_subset_bits(schema, literal), uper_subset_bits(schema, call))


if __name__ == "__main__":
    unittest.main()
