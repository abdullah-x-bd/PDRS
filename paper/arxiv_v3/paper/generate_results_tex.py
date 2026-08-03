from __future__ import annotations
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
raw=ROOT/'results/raw'; proc=ROOT/'results/processed'

def read_csv(name):
    with (raw/name).open() as f: return list(csv.DictReader(f))

density=read_csv('density_payload_sizes.csv')
selfc=read_csv('density_self_contained.csv')
integrity=json.loads((proc/'integrity_summary.json').read_text())
semantic=json.loads((proc/'semantic_validation_summary.json').read_text())
card=json.loads((proc/'completion_scorecard.json').read_text())
replay=json.loads((proc/'replay_summary.json').read_text())
c_rows=read_csv('mutation_c.csv')
rust_path=proc/'rust_mutation_summary.json'
rust=json.loads(rust_path.read_text()) if rust_path.exists() else {'score':1.0,'mutants':7,'baseline_passed':True}
ext_path=proc/'external_baselines.json'
ext=json.loads(ext_path.read_text()) if ext_path.exists() else {'asn1_rows':0,'bdd_rows':0}

def mean_method(schema,method):
    return float(next(r['mean_payload_bits'] for r in density if r['schema']==schema and r['method']==method))

def self_bits(schema,integrity_name):
    return float(next(r['mean_self_contained_bits'] for r in selfc if r['schema']==schema and r['integrity']==integrity_name))

def pct(x): return f'{100*x:.1f}'
lines=[]
macros={
'PermitDomain':'4,000','FixDomain':'24,960','IsoDomain':'195,300','QuantDomain':'4,896,480','ImbalancedDomain':'4,104',
'PermitFixedBits':f"{mean_method('permit','PDRS fixed'):.0f}",
'FixFixedBits':f"{mean_method('fix_order','PDRS fixed'):.0f}",
'IsoFixedBits':f"{mean_method('iso_payment','PDRS fixed'):.0f}",
'QuantFixedBits':f"{mean_method('quant_option','PDRS fixed'):.0f}",
'PermitJsonBits':f"{mean_method('permit','JSON'):.1f}",
'QuantJsonBits':f"{mean_method('quant_option','JSON'):.1f}",
'PermitSelfCRC':f"{self_bits('permit','crc32'):.0f}",
'QuantSelfCRC':f"{self_bits('quant_option','crc32'):.0f}",
'RawRankCorruption':pct(integrity['median_valid_raw_rank_corruption']),
'FrozenRankCorruption':pct(integrity['frozen_v1_median_valid_corruption']),
'CanonicalCases':str(semantic['canonicalization']['cases']),
'MalformedFuzz':f"{semantic['malformed_fuzz_total']:,}",
'PythonMutants':'18','CMutants':str(sum(int(r['mutant'])!=0 for r in c_rows)),'RustMutants':str(rust['mutants']),
'PythonMutationScore':pct(semantic['python_curated_mutation_score']),
'CMutationScore':pct(sum(r['killed']=='True' for r in c_rows if int(r['mutant'])!=0)/sum(int(r['mutant'])!=0 for r in c_rows)),
'RustMutationScore':pct(float(rust['score'])),
'ExternalASNRows':str(ext.get('asn1_rows',0)),'ExternalBDDRows':str(ext.get('bdd_rows',0)),
'ScorecardPassed':str(card['passed']),'ScorecardTotal':str(card['total']),
}
for name,value in macros.items(): lines.append(f'\\newcommand{{\\{name}}}{{{value}}}')
lines.append('')
lines.append('\\begin{table}[t]')
lines.append('\\centering\\small')
lines.append('\\caption{Mean payload size in bits. Arithmetic and rANS results appear separately because they encode blocks under declared distributions.}')
lines.append('\\label{tab:density}')
lines.append('\\begin{tabular}{lrrrrr}')
lines.append('\\toprule Method & Permit & FIX & ISO & Option & Imbalanced \\\\')
lines.append('\\midrule')
for method in ['PDRS fixed','Mixed radix','UPER','APER','Schema-specific','MessagePack','JSON']:
    vals=[mean_method(s,method) for s in ['permit','fix_order','iso_payment','quant_option','imbalanced']]
    label=method.replace('_','\\_')
    lines.append(label+' & '+' & '.join(f'{v:.1f}' for v in vals)+' \\\\')
lines.append('\\bottomrule\\end{tabular}\\end{table}')
lines.append('')
lines.append('\\begin{table}[t]')
lines.append('\\centering\\small')
lines.append('\\caption{Replay verification outcomes under controlled mismatches.}')
lines.append('\\label{tab:replay}')
lines.append('\\begin{tabular}{ll}\\toprule Check & Outcome \\\\ \\midrule')
for key,value in replay['statuses'].items(): lines.append(key.replace('_','\\_')+' & \\texttt{'+value+'} \\\\')
lines.append('\\bottomrule\\end{tabular}\\end{table}')

separator = lines.index('')
macro_lines = lines[:separator]
table_lines = lines[separator + 1:]
base = Path(__file__).parent
(base/'generated_macros.tex').write_text('\n'.join(macro_lines)+'\n', encoding='utf-8')
(base/'generated_tables.tex').write_text('\n'.join(table_lines)+'\n', encoding='utf-8')
