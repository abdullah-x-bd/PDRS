from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
from typing import Any, Mapping

from model import CompiledSchema, canonical_json


@dataclass(frozen=True)
class ObjectIdentity:
    canonicalization_version: str
    schema_hash: str
    rank: int
    pdrs_version: str
    pdrs_commit: str

    @property
    def identity_hash(self) -> str:
        return hashlib.sha256(canonical_json(asdict(self))).hexdigest()


@dataclass(frozen=True)
class ExecutionIdentity:
    object_identity_hash: str
    finspace_version: str
    finspace_commit: str
    adapter_name: str
    adapter_version: str
    environment_hash: str
    oracle_config_hash: str
    external_data_snapshot: str | None
    execution_parameters_hash: str

    @property
    def identity_hash(self) -> str:
        return hashlib.sha256(canonical_json(asdict(self))).hexdigest()


def environment_manifest(extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    packages = {}
    try:
        from importlib.metadata import distributions
        for dist in distributions():
            name = dist.metadata.get("Name")
            if name:
                packages[name.lower()] = dist.version
    except Exception:
        packages = {}
    manifest = {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "byteorder": sys.byteorder,
        "locale": os.environ.get("LC_ALL") or os.environ.get("LANG"),
        "timezone": os.environ.get("TZ"),
        "packages": dict(sorted(packages.items())),
    }
    if extra:
        manifest["extra"] = dict(extra)
    return manifest


def digest_manifest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


class ReplayLedger:
    SCHEMA_VERSION = 2

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def _migrate(self) -> None:
        with self.connection:
            self.connection.execute("CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            row = self.connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            version = int(row[0]) if row else 0
            if version < 1:
                self.connection.execute("""
                    CREATE TABLE IF NOT EXISTS object_identity(
                        identity_hash TEXT PRIMARY KEY,
                        canonicalization_version TEXT NOT NULL,
                        schema_hash TEXT NOT NULL,
                        rank INTEGER NOT NULL,
                        pdrs_version TEXT NOT NULL,
                        pdrs_commit TEXT NOT NULL,
                        canonical_object_json TEXT NOT NULL
                    )
                """)
                version = 1
            if version < 2:
                self.connection.execute("""
                    CREATE TABLE IF NOT EXISTS execution_identity(
                        identity_hash TEXT PRIMARY KEY,
                        object_identity_hash TEXT NOT NULL,
                        finspace_version TEXT NOT NULL,
                        finspace_commit TEXT NOT NULL,
                        adapter_name TEXT NOT NULL,
                        adapter_version TEXT NOT NULL,
                        environment_hash TEXT NOT NULL,
                        oracle_config_hash TEXT NOT NULL,
                        external_data_snapshot TEXT,
                        execution_parameters_hash TEXT NOT NULL,
                        result_hash TEXT,
                        status TEXT NOT NULL,
                        FOREIGN KEY(object_identity_hash) REFERENCES object_identity(identity_hash)
                    )
                """)
                version = 2
            self.connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('schema_version',?)", (str(version),))

    def record_object(self, identity: ObjectIdentity, record: Mapping[str, Any]) -> str:
        payload = canonical_json(record).decode("utf-8")
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO object_identity VALUES(?,?,?,?,?,?,?)",
                (identity.identity_hash, identity.canonicalization_version, identity.schema_hash, identity.rank,
                 identity.pdrs_version, identity.pdrs_commit, payload),
            )
        return identity.identity_hash

    def record_execution(self, identity: ExecutionIdentity, *, result: Any = None, status: str = "recorded") -> str:
        result_hash = None if result is None else hashlib.sha256(canonical_json(result)).hexdigest()
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO execution_identity VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (identity.identity_hash, identity.object_identity_hash, identity.finspace_version, identity.finspace_commit,
                 identity.adapter_name, identity.adapter_version, identity.environment_hash, identity.oracle_config_hash,
                 identity.external_data_snapshot, identity.execution_parameters_hash, result_hash, status),
            )
        return identity.identity_hash

    def replay_object(self, schema: CompiledSchema, identity_hash: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT canonicalization_version,schema_hash,rank,canonical_object_json FROM object_identity WHERE identity_hash=?",
            (identity_hash,),
        ).fetchone()
        if row is None:
            raise KeyError(identity_hash)
        canonicalization_version, schema_hash, rank, stored_json = row
        if canonicalization_version != "2":
            raise ValueError("unsupported canonicalization version")
        if schema_hash != schema.canonical_hash:
            raise ValueError("schema mismatch")
        record = schema.lower(schema.unrank(rank))
        if canonical_json(record).decode("utf-8") != stored_json:
            raise ValueError("object divergence")
        return record

    def verify_execution(self, identity_hash: str, *, environment_hash: str, oracle_config_hash: str,
                         adapter_version: str, external_data_snapshot: str | None) -> str:
        row = self.connection.execute(
            "SELECT environment_hash,oracle_config_hash,adapter_version,external_data_snapshot FROM execution_identity WHERE identity_hash=?",
            (identity_hash,),
        ).fetchone()
        if row is None:
            raise KeyError(identity_hash)
        expected_env, expected_oracle, expected_adapter, expected_snapshot = row
        if expected_adapter != adapter_version:
            return "adapter-mismatch"
        if expected_env != environment_hash:
            return "environment-mismatch"
        if expected_oracle != oracle_config_hash:
            return "oracle-mismatch"
        if expected_snapshot != external_data_snapshot:
            return "external-data-unavailable"
        return "reproduced"
