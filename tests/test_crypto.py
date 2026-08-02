from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

from pdrs import SchemaError, load_schema
from pdrs.crypto import Ciphertext, DomainCipher

ROOT = Path(__file__).resolve().parents[1]


class DomainCipherTests(unittest.TestCase):
    def setUp(self):
        self.schema = load_schema(ROOT / "schemas" / "permit.json")
        self.cipher = DomainCipher(self.schema, hashlib.sha256(b"test-key").digest())

    def test_exhaustive_permutation_and_inverse(self):
        encrypted = set()
        for rank in range(self.schema.count):
            cipher_rank, _ = self.cipher.encrypt_rank(rank, b"ctx")
            plain_rank, _ = self.cipher.decrypt_rank(cipher_rank, b"ctx")
            self.assertEqual(plain_rank, rank)
            encrypted.add(cipher_rank)
        self.assertEqual(encrypted, set(range(self.schema.count)))

    def test_structured_roundtrip_and_tag(self):
        value = ["experimental", 7, 13]
        ciphertext = self.cipher.encrypt(value, b"record-1")
        self.assertEqual(self.cipher.decrypt(ciphertext), value)
        bad = Ciphertext(ciphertext.value, "00" + ciphertext.tag_hex[2:], ciphertext.tweak_hex)
        if bad.tag_hex == ciphertext.tag_hex:
            bad = Ciphertext(ciphertext.value, "ff" + ciphertext.tag_hex[2:], ciphertext.tweak_hex)
        with self.assertRaisesRegex(SchemaError, "authentication"):
            self.cipher.decrypt(bad)

    def test_minimum_domain_gate(self):
        schema = load_schema(ROOT / "schemas" / "ai_actions.json")
        with self.assertRaisesRegex(SchemaError, "below"):
            DomainCipher(schema, hashlib.sha256(b"test-key").digest())


if __name__ == "__main__":
    unittest.main()
