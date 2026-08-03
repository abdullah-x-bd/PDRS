from pathlib import Path

ROOT = Path(__file__).resolve().parent

def assemble(pattern: str, target: str) -> None:
    parts = sorted((ROOT / "source_parts").glob(pattern))
    if not parts:
        raise SystemExit(f"missing source parts for {pattern}")
    destination = ROOT / target
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"".join(path.read_bytes() for path in parts))
    print(destination, destination.stat().st_size)

assemble("model.part*", "src/model.py")
assemble("run_all.part*", "experiments/run_all.py")
