from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from model import CompiledSchema, SchemaError, benchmark_schemas, canonical_decimal, canonical_json, naive_enumerate, reject_duplicate_json
from pdrs_codecs import self_contained_message, verify_message
from replay import ObjectIdentity, ExecutionIdentity, ReplayLedger, digest_manifest


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.schema=CompiledSchema(benchmark_schemas()['permit'])

    def test_exact_bijection(self):
        independent=naive_enumerate(self.schema.document)
        self.assertEqual(len(independent),self.schema.count)
        for rank,value in enumerate(independent):
            self.assertEqual(self.schema.unrank(rank),value)
            self.assertEqual(self.schema.rank(value),rank)

    def test_record_lowering_is_injective(self):
        records={canonical_json(self.schema.lower(self.schema.unrank(rank))) for rank in range(self.schema.count)}
        self.assertEqual(len(records),self.schema.count)

    def test_canonicalization(self):
        self.assertNotEqual(canonical_json(True),canonical_json(1))
        self.assertEqual(canonical_json('é'),canonical_json('e\u0301'))
        self.assertEqual(canonical_decimal('1.00'),canonical_decimal(Decimal('1e0')))
        with self.assertRaises(SchemaError): reject_duplicate_json('{"a":1,"a":2}')

    def test_integrity(self):
        for mode in ('none','crc32','mac16'):
            payload=self_contained_message(self.schema,7,mode)
            self.assertTrue(verify_message(payload,mode))
            broken=bytearray(payload); broken[-1]^=1
            if mode!='none': self.assertFalse(verify_message(bytes(broken),mode))


class ReplayTests(unittest.TestCase):
    def test_object_and_execution_replay_are_distinct(self):
        schema=CompiledSchema(benchmark_schemas()['permit'])
        with tempfile.TemporaryDirectory() as directory:
            ledger=ReplayLedger(Path(directory)/'ledger.sqlite')
            rank=12; record=schema.lower(schema.unrank(rank))
            obj=ObjectIdentity('2',schema.canonical_hash,rank,'0.2.0','commit')
            object_hash=ledger.record_object(obj,record)
            env=digest_manifest({'python':'3.13'}); oracle=digest_manifest({'oracle':'roundtrip'}); params=digest_manifest({'workers':1})
            execution=ExecutionIdentity(object_hash,'0.1.0','commit','reference','2',env,oracle,None,params)
            execution_hash=ledger.record_execution(execution,result={'ok':True})
            self.assertEqual(ledger.replay_object(schema,object_hash),record)
            self.assertEqual(ledger.verify_execution(execution_hash,environment_hash=env,oracle_config_hash=oracle,adapter_version='2',external_data_snapshot=None),'reproduced')
            self.assertEqual(ledger.verify_execution(execution_hash,environment_hash='other',oracle_config_hash=oracle,adapter_version='2',external_data_snapshot=None),'environment-mismatch')
            ledger.close()


if __name__=='__main__': unittest.main()
