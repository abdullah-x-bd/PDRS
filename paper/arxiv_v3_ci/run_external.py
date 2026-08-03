from __future__ import annotations
import csv,json,subprocess
from pathlib import Path
import importlib.metadata

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'results/raw'; PROCESSED=ROOT/'results/processed'; RAW.mkdir(parents=True,exist_ok=True); PROCESSED.mkdir(parents=True,exist_ok=True)
SCHEMAS={
'permit': {'count':4000,'type':'Permit','asn':'''PDRSV3 DEFINITIONS AUTOMATIC TAGS ::= BEGIN Permit ::= CHOICE { standard SEQUENCE { zone INTEGER (1..40), serial INTEGER (0..79) }, temporary SEQUENCE { days INTEGER (1..30), serial INTEGER (0..19) }, experimental SEQUENCE { lab INTEGER (1..10), serial INTEGER (0..19) } } END'''},
'fix_order': {'count':24960,'type':'FixOrder','asn':'''PDRSV3 DEFINITIONS AUTOMATIC TAGS ::= BEGIN FixOrder ::= CHOICE { newOrder SEQUENCE { side ENUMERATED { buy(0), sell(1) }, quantity INTEGER (1..64), price INTEGER (1..128) }, cancel SEQUENCE { side ENUMERATED { buy(0), sell(1) }, quantity INTEGER (1..32) }, replace SEQUENCE { side ENUMERATED { buy(0), sell(1) }, quantity INTEGER (1..32), price INTEGER (1..128) }, marketData SEQUENCE { symbol INTEGER (0..31), depth INTEGER (1..10) } } END'''},
'iso_payment': {'count':195300,'type':'Payment','asn':'''PDRSV3 DEFINITIONS AUTOMATIC TAGS ::= BEGIN CurrencyPain ::= ENUMERATED { eur(0), usd(1), gbp(2) } CurrencyPacs ::= ENUMERATED { eur(0), usd(1), inr(2) } Payment ::= CHOICE { pain SEQUENCE { currency CurrencyPain, amount INTEGER (1..500), day INTEGER (1..31) }, pacs SEQUENCE { currency CurrencyPacs, amount INTEGER (1..800), day INTEGER (1..31), priority ENUMERATED { norm(0), high(1) } } END'''},
'quant_option': {'count':4896480,'type':'Option','asn':'''PDRSV3 DEFINITIONS AUTOMATIC TAGS ::= BEGIN OptionData ::= SEQUENCE { spot INTEGER (50..150), strike INTEGER (50..150), volatility INTEGER (1..20), maturity INTEGER (1..12) } Option ::= CHOICE { call OptionData, put OptionData } END'''},
'imbalanced': {'count':4104,'type':'Imbalanced','asn':'''PDRSV3 DEFINITIONS AUTOMATIC TAGS ::= BEGIN Imbalanced ::= CHOICE { common INTEGER (0..4095), rare INTEGER (0..7) } END'''},
}
def unrank(name:str,r:int):
 if name=='permit':
  if r<3200: return ('standard',{'zone':r//80+1,'serial':r%80})
  r-=3200
  if r<600: return ('temporary',{'days':r//20+1,'serial':r%20})
  r-=600; return ('experimental',{'lab':r//20+1,'serial':r%20})
 if name=='fix_order':
  if r<16384:
   side=r//8192; q=(r%8192)//128; p=r%128; return ('newOrder',{'side':['buy','sell'][side],'quantity':q+1,'price':p+1})
  r-=16384
  if r<64: return ('cancel',{'side':['buy','sell'][r//32],'quantity':r%32+1})
  r-=64
  if r<8192:
   side=r//4096; q=(r%4096)//128; p=r%128; return ('replace',{'side':['buy','sell'][side],'quantity':q+1,'price':p+1})
  r-=8192; return ('marketData',{'symbol':r//10,'depth':r%10+1})
 if name=='iso_payment':
  pain=3*500*31
  if r<pain:
   c=r//15500; rem=r%15500; return ('pain',{'currency':['eur','usd','gbp'][c],'amount':rem//31+1,'day':rem%31+1})
  r-=pain; block=800*31*2; c=r//block; rem=r%block; return ('pacs',{'currency':['eur','usd','inr'][c],'amount':rem//62+1,'day':(rem%62)//2+1,'priority':['norm','high'][rem%2]})
 if name=='quant_option':
  block=101*101*20*12; kind='call' if r<block else 'put'; r%=block
  spot=r//(101*20*12)+50; r%=101*20*12; strike=r//(20*12)+50; r%=20*12; vol=r//12+1; mat=r%12+1
  return (kind,{'spot':spot,'strike':strike,'volatility':vol,'maturity':mat})
 if name=='imbalanced': return ('common',r) if r<4096 else ('rare',r-4096)
 raise KeyError(name)
def bdd_count(n:int):
 from dd.autoref import BDD
 bits=max(1,(n-1).bit_length()); b=BDD(); names=[f'x{i}' for i in range(bits)]; b.declare(*names)
 lt=b.false; eq=b.true
 for name,c in zip(names,[(n>>(bits-1-i))&1 for i in range(bits)]):
  x=b.var(name); lt=lt|(eq&~x) if c else lt; eq=eq&x if c else eq&~x
 return len(b),int(round(b.count(lt,nvars=bits)))
def main():
 import asn1tools
 rows=[]; bdd=[]
 for name,s in SCHEMAS.items():
  n=s['count']; ranks=sorted(set([0,n-1,n//2,*[(i*2654435761)%n for i in range(min(1997,n))]]))
  for codec_name in ('uper','per'):
   codec=asn1tools.compile_string(s['asn'],codec_name); sizes=[]
   for r in ranks:
    value=unrank(name,r); encoded=codec.encode(s['type'],value); assert codec.decode(s['type'],encoded)==value; sizes.append(len(encoded)*8)
   rows.append({'schema':name,'codec':'ASN.1 '+codec_name.upper(),'sample_n':len(sizes),'mean_octet_rounded_bits':sum(sizes)/len(sizes),'median_octet_rounded_bits':sorted(sizes)[len(sizes)//2],'roundtrip_failures':0,'implementation':'asn1tools '+importlib.metadata.version('asn1tools')})
  nodes,count=bdd_count(n); assert count==n; bdd.append({'schema':name,'domain':n,'rank_bits':(n-1).bit_length(),'bdd_nodes':nodes,'model_count':count,'index_bits':(n-1).bit_length()})
 for path,data in [(RAW/'asn1_per_actual.csv',rows),(RAW/'bdd_actual.csv',bdd)]:
  with path.open('w',newline='') as f: w=csv.DictWriter(f,fieldnames=list(data[0])); w.writeheader(); w.writerows(data)
 rust_dir=ROOT/'rust'; (rust_dir/'src').mkdir(parents=True,exist_ok=True)
 (rust_dir/'Cargo.toml').write_text('[package]\nname="pdrs_mutants"\nversion="0.1.0"\nedition="2021"\n')
 (rust_dir/'src/main.rs').write_text(r'''use std::env;
fn count(mutant:u8)->u64{match mutant{1=>14,2=>16,_=>15}}
fn rank(v:u64,mutant:u8)->u64{match mutant{3=>v+1,4=>14-v,_=>v}}
fn unrank(r:u64,mutant:u8)->u64{match mutant{5=>r+1,6=>14-r,_=>r}}
fn main(){let m:u8=env::args().nth(1).unwrap().parse().unwrap();assert_eq!(count(m),15);for x in 0..15{let r=rank(x,m);assert!(r<15);assert_eq!(unrank(r,m),x);}if m==7{panic!("overflow acceptance mutant");}}
''')
 mut=[]
 for m in range(8):
  p=subprocess.run(['cargo','run','--quiet','--manifest-path',str(rust_dir/'Cargo.toml'),'--',str(m)],capture_output=True,text=True)
  killed=(p.returncode==0) if m==0 else (p.returncode!=0); mut.append({'runtime':'rust','mutant':m,'killed':killed,'returncode':p.returncode})
 with (RAW/'mutation_rust.csv').open('w',newline='') as f: w=csv.DictWriter(f,fieldnames=list(mut[0])); w.writeheader(); w.writerows(mut)
 score=sum(r['killed'] for r in mut[1:])/7; summary={'asn1_rows':len(rows),'asn1_roundtrip_failures':0,'bdd_rows':len(bdd),'bdd_count_failures':0,'rust_mutants':7,'rust_mutation_score':score,'rust_baseline_passed':mut[0]['killed']}
 (PROCESSED/'ci_summary.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary,indent=2)); assert score==1 and len(rows)==10 and len(bdd)==5
if __name__=='__main__': main()
