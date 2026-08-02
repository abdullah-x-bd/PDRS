from __future__ import annotations

import json

from finspace import Field, Schema
from finspace.cli import main


def test_cli_inspect_and_unrank(tmp_path, capsys) -> None:
    schema_path = tmp_path / "schema.json"
    Schema(name="cli", fields=(Field.enum("value", ("a", "b")),)).save(schema_path)
    assert main(["inspect", str(schema_path)]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["count"] == 2
    assert main(["unrank", str(schema_path), "1"]) == 0
    decoded = json.loads(capsys.readouterr().out)
    assert decoded["record"] == {"value": "b"}
