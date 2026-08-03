from __future__ import annotations
import csv,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=ROOT/'mutants/rust/Cargo.toml'
rows=[]
for mutant in range(8):
    run=subprocess.run(['cargo','run','--quiet','--manifest-path',str(manifest),'--',str(mutant)],capture_output=True,text=True)
    killed=(run.returncode==0) if mutant==0 else (run.returncode!=0)
    rows.append({'runtime':'rust','mutant':mutant,'killed':killed,'returncode':run.returncode,'detail':(run.stdout+run.stderr)[-400:]})
path=ROOT/'results/raw/mutation_rust.csv'; path.parent.mkdir(parents=True,exist_ok=True)
with path.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
mutants=rows[1:]; summary={'mutants':len(mutants),'score':sum(r['killed'] for r in mutants)/len(mutants),'baseline_passed':rows[0]['killed']}
(ROOT/'results/processed/rust_mutation_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
if not summary['baseline_passed'] or summary['score']!=1.0: raise SystemExit(1)
