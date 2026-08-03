from __future__ import annotations

import csv
import json
from pathlib import Path
import random
import sys
import importlib.metadata
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from model import CompiledSchema, benchmark_schemas

RAW=ROOT/'results'/'raw'; PROCESSED=ROOT/'results'/'processed'
RAW.mkdir(parents=True,exist_ok=True); PROCESSED.mkdir(parents=True,exist_ok=True)
SEED=20260804

ASN_MODULES={
'permit':('Permit',r'''PDRSV3 DEFINITIONS AUTOMATIC TAGS ::= BEGIN
Permit ::= CHOICE {
 standard SEQUENCE { zone INTEGER (1..40), serial INTEGER (0..79) },
 temporary SEQUENCE { days INTEGER (1..30), serial INTEGER (0..19) },
 experimental SEQUENCE { lab INTEGER (1..10), serial INTEGER (0..19) }
}
END'''),
'fix_order':('FixOrder',r'''PDRSV3 DEFINITIONS AUTOMATIC TAGS ::= BEGIN
FixOrder ::= CHOICE {
 newOrder SEQUENCE { side ENUMERATED { buy(0), sell(1) }, quantity INTEGER (1..64), price INTEGER (1..128) },
 cancel SEQUENCE { side ENUMERATED { buy(0), sell(1) }, quantity INTEGER (1..32) },
 replace SEQUENCE { side ENUMERATED { buy(0), sell(1) }, quantity INTEGER (1..32), price INTEGER (1..128) },
 marketData SEQUENCE { symbol INTEGER (0..31), depth INTEGER (1..10) }
}
END'''),
'iso_payment':('Payment',r'''PDRSV3 DEFINITIONS AUTOMATIC TAGS ::= BEGIN
CurrencyPain ::= ENUMERATED { eur(0), usd(1), gbp(2) }
CurrencyPacs ::= ENUMERATED { eur(0), usd(1), inr(2) }
Payment ::= CHOICE {
 pain SEQUENCE { currency CurrencyPain, amount INTEGER (1..500), day INTEGER (1..31) },
 pacs SEQUENCE { currency CurrencyPacs, amount INTEGER (1..800), day INTEGER (1..31), priority ENUMERATED { norm(0), high(1) } }
}
END'''),
'quant_option':('Option',r'''PDRSV3 DEFINITIONS AUTOMATIC TAGS ::= BEGIN
OptionData ::= SEQUENCE { spot INTEGER (50..150), strike INTEGER (50..150), volatility INTEGER (1..20), maturity INTEGER (1..12) }
Option ::= CHOICE { call OptionData, put OptionData }
END'''),
'imbalanced':('Imbalanced',r'''PDRSV3 DEFINITIONS AUTOMATIC TAGS ::= BEGIN
Imbalanced ::= CHOICE { common INTEGER (0..4095), rare INTEGER (0..7) }
END'''),
}


def to_asn(name:str,record:dict[str,Any])->Any:
    if name=='permit':
        kind=record['permit_type']; payload={k:v for k,v in record.items() if k!='permit_type'}
        return (kind,payload)
    if name=='fix_order':
        kind={'D':'newOrder','F':'cancel','G':'replace','V':'marketData'}[record['message_type']]
        if kind=='marketData': return (kind,{'symbol':record['symbol_id'],'depth':record['market_depth']})
        payload={'side':{'1':'buy','2':'sell'}[record['side']],'quantity':record['quantity_bucket']}
        if 'price_tick' in record: payload['price']=record['price_tick']
        return (kind,payload)
    if name=='iso_payment':
        kind='pain' if record['message']=='pain.001' else 'pacs'
        payload={'currency':record['currency'].lower(),'amount':record['amount_minor'],'day':record['settlement_day']}
        if kind=='pacs': payload['priority']=record['priority'].lower()
        return (kind,payload)
    if name=='quant_option':
        return (record['option_type'],{'spot':record['spot_bucket'],'strike':record['strike_bucket'],'volatility':record['vol_bucket'],'maturity':record['maturity_bucket']})
    if name=='imbalanced': return (record['kind'],record['value'])
    raise KeyError(name)


def bdd_less_than_count(n:int)->tuple[int,int]:
    from dd.autoref import BDD
    bits=max(1,(n-1).bit_length())
    bdd=BDD(); names=[f'x{i}' for i in range(bits)]; bdd.declare(*names)
    lt=bdd.false; eq=bdd.true
    const_bits=[(n>>(bits-1-i))&1 for i in range(bits)]
    for name,c in zip(names,const_bits):
        x=bdd.var(name)
        if c: lt=lt | (eq & ~x); eq=eq & x
        else: eq=eq & ~x
    count=int(round(bdd.count(lt,nvars=bits)))
    return len(bdd),count


def main()->None:
    import asn1tools
    rows=[]; bdd_rows=[]
    rng=random.Random(SEED)
    for name,document in benchmark_schemas().items():
        schema=CompiledSchema(document); type_name,module=ASN_MODULES[name]
        ranks=list(range(schema.count)) if schema.count<=2000 else sorted({0,schema.count-1,schema.count//2,*rng.sample(range(schema.count),1997)})
        for codec_name in ('uper','per'):
            codec=asn1tools.compile_string(module,codec_name)
            sizes=[]
            for rank in ranks:
                record=schema.lower(schema.unrank(rank)); value=to_asn(name,record)
                encoded=codec.encode(type_name,value); decoded=codec.decode(type_name,encoded)
                if decoded!=value: raise AssertionError((name,codec_name,rank,value,decoded))
                sizes.append(len(encoded)*8)
            rows.append({'schema':name,'codec':'ASN.1 '+codec_name.upper(),'sample_n':len(sizes),'mean_octet_rounded_bits':sum(sizes)/len(sizes),'median_octet_rounded_bits':sorted(sizes)[len(sizes)//2],'roundtrip_failures':0,'implementation':'asn1tools '+importlib.metadata.version('asn1tools')})
        nodes,count=bdd_less_than_count(schema.count)
        if count!=schema.count: raise AssertionError((name,count,schema.count))
        bdd_rows.append({'schema':name,'domain':schema.count,'rank_bits':schema.bit_length,'bdd_nodes':nodes,'model_count':count,'index_bits':schema.bit_length})
    for path,data in [(RAW/'asn1_per_actual.csv',rows),(RAW/'bdd_actual.csv',bdd_rows)]:
        with path.open('w',newline='',encoding='utf-8') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(data[0])); writer.writeheader(); writer.writerows(data)
    summary={'asn1_rows':len(rows),'asn1_roundtrip_failures':sum(r['roundtrip_failures'] for r in rows),'bdd_rows':len(bdd_rows),'bdd_count_failures':0}
    (PROCESSED/'external_baselines.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
