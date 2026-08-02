from __future__ import annotations

import unittest

from pdrs import CompiledSchema
from pdrs.generators import random_tree_schema


class GeneratedSchemaTests(unittest.TestCase):
    def test_exhaustive_generated_domains(self):
        for seed in range(200):
            schema = CompiledSchema(random_tree_schema(10000 + seed, max_depth=4))
            ranks = []
            for index in range(schema.count):
                value = schema.unrank(index)
                recovered = schema.rank(value)
                self.assertEqual(recovered, index)
                ranks.append(recovered)
            self.assertEqual(ranks, list(range(schema.count)))


if __name__ == "__main__":
    unittest.main()
