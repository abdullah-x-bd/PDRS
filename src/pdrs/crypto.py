from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
from typing import Sequence

from .core import CompiledSchema, SchemaError, Token


@dataclass(frozen=True)
class Ciphertext:
    value: list[Token]
    tag_hex: str
    tweak_hex: str


class DomainCipher:
    """Research-only finite-domain permutation adapter.

    The adapter conjugates an HMAC-based Feistel permutation through PDRS
    rank/unrank and cycle-walks over the smallest even-bit power-of-two domain.
    It is included for composition and measurement experiments, not as a
    standardized or deployment-ready cryptographic primitive.
    """

    def __init__(
        self,
        schema: CompiledSchema,
        key: bytes,
        *,
        rounds: int = 10,
        minimum_domain: int = 256,
    ):
        if not isinstance(key, bytes) or len(key) < 16:
            raise ValueError("key must contain at least 128 bits")
        if rounds < 6 or rounds % 2:
            raise ValueError("rounds must be an even integer of at least 6")
        if schema.count < minimum_domain:
            raise SchemaError(
                f"domain size {schema.count} is below configured minimum {minimum_domain}"
            )
        self.schema = schema
        self.rounds = rounds
        self._enc_key = hmac.new(key, b"PDRS/feistel/v1", hashlib.sha256).digest()
        self._mac_key = hmac.new(key, b"PDRS/auth/v1", hashlib.sha256).digest()
        required = max(2, (schema.count - 1).bit_length())
        self.width = required if required % 2 == 0 else required + 1
        self.half = self.width // 2
        self.mask = (1 << self.half) - 1
        self.super_domain = 1 << self.width

    def _round_function(self, right: int, round_index: int, tweak: bytes) -> int:
        payload = (
            b"PDRS-F"
            + round_index.to_bytes(2, "big")
            + len(tweak).to_bytes(2, "big")
            + tweak
            + right.to_bytes((self.half + 7) // 8, "big")
        )
        digest = hmac.new(self._enc_key, payload, hashlib.sha256).digest()
        return int.from_bytes(digest, "big") & self.mask

    def _permute_super(self, value: int, tweak: bytes) -> int:
        left = value >> self.half
        right = value & self.mask
        for round_index in range(self.rounds):
            left, right = right, left ^ self._round_function(right, round_index, tweak)
        return (left << self.half) | right

    def _invert_super(self, value: int, tweak: bytes) -> int:
        left = value >> self.half
        right = value & self.mask
        for round_index in reversed(range(self.rounds)):
            left, right = right ^ self._round_function(left, round_index, tweak), left
        return (left << self.half) | right

    def encrypt_rank(self, rank: int, tweak: bytes = b"") -> tuple[int, int]:
        if rank < 0 or rank >= self.schema.count:
            raise SchemaError("rank outside schema domain")
        output = rank
        cycles = 0
        while True:
            output = self._permute_super(output, tweak)
            cycles += 1
            if output < self.schema.count:
                return output, cycles
            if cycles > self.super_domain:
                raise AssertionError("cycle-walking failed to return to the target domain")

    def decrypt_rank(self, rank: int, tweak: bytes = b"") -> tuple[int, int]:
        if rank < 0 or rank >= self.schema.count:
            raise SchemaError("rank outside schema domain")
        output = rank
        cycles = 0
        while True:
            output = self._invert_super(output, tweak)
            cycles += 1
            if output < self.schema.count:
                return output, cycles
            if cycles > self.super_domain:
                raise AssertionError("inverse cycle-walking failed")

    def _tag(self, cipher_rank: int, tweak: bytes) -> bytes:
        payload = (
            b"PDRS-TAG-v1"
            + bytes.fromhex(self.schema.canonical_hash)
            + len(tweak).to_bytes(4, "big")
            + tweak
            + cipher_rank.to_bytes(max(1, (self.schema.bit_length + 7) // 8), "big")
        )
        return hmac.new(self._mac_key, payload, hashlib.sha256).digest()[:16]

    def encrypt(self, value: Sequence[Token], tweak: bytes = b"") -> Ciphertext:
        plain_rank = self.schema.rank(value)
        cipher_rank, _ = self.encrypt_rank(plain_rank, tweak)
        return Ciphertext(
            value=self.schema.unrank(cipher_rank),
            tag_hex=self._tag(cipher_rank, tweak).hex(),
            tweak_hex=tweak.hex(),
        )

    def decrypt(self, ciphertext: Ciphertext) -> list[Token]:
        tweak = bytes.fromhex(ciphertext.tweak_hex)
        cipher_rank = self.schema.rank(ciphertext.value)
        supplied = bytes.fromhex(ciphertext.tag_hex)
        expected = self._tag(cipher_rank, tweak)
        if not hmac.compare_digest(supplied, expected):
            raise SchemaError("authentication failed")
        plain_rank, _ = self.decrypt_rank(cipher_rank, tweak)
        return self.schema.unrank(plain_rank)
