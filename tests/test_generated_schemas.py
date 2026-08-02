import random
import unittest

from pdrs import CompiledSchema
from pdrs.examples import fixed_radix_schema


class GeneratedSchemaTests(unittest.TestCase):
    def test_random_fixed_radix_domains_exhaustively(self):
        rng = random.Random(20260802)
        for case in range(80):
            depth = rng.randint(1, 5)
            radices = [rng.randint(1, 5) for _ in range(depth)]
            schema = CompiledSchema(fixed_radix_schema(f"case-{case}", radices))
            expected = 1
            for radix in radices:
                expected *= radix
            self.assertEqual(schema.count, expected)
            for index in range(expected):
                self.assertEqual(schema.rank(schema.unrank(index)), index)

    def test_dependent_branch_sizes(self):
        document = {
            "name": "dependent",
            "version": "1",
            "root": "kind",
            "nodes": {
                "kind": {
                    "type": "choice",
                    "branches": [
                        {"value": "small", "target": "small"},
                        {"value": "large", "target": "large"},
                    ],
                },
                "small": {"type": "range", "start": 0, "stop": 1, "target": "end"},
                "large": {"type": "range", "start": 0, "stop": 6, "target": "end"},
                "end": {"type": "terminal"},
            },
        }
        schema = CompiledSchema(document)
        self.assertEqual(schema.count, 9)
        expected = [
            ["small", 0], ["small", 1],
            ["large", 0], ["large", 1], ["large", 2], ["large", 3],
            ["large", 4], ["large", 5], ["large", 6],
        ]
        self.assertEqual([schema.unrank(i) for i in range(9)], expected)


if __name__ == "__main__":
    unittest.main()
