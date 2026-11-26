"""Blocked measurements of the connected lowest-momentum Wilson correlator."""
import csv
import json
import gzip
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
T = 16

def cosh_energy(ca, cb, t):
    if not ca > cb > 0:
        return None
    ratio = ca/cb
    lo, hi = 0., 32.
    for _ in range(70):
        m = (lo+hi)/2
        value = math.cosh(m*(T/2-t))/math.cosh(m*(T/2-t-1))
        if value > ratio:
            hi = m
        else:
            lo = m
    return (hi+lo)/2

def stats(blocks):
    count = len(blocks)
    avg = [statistics.mean(col) for col in zip(*blocks)]
    se = [statistics.stdev(col)/math.sqrt(count) for col in zip(*blocks)]
    loo = [[(count*a-v)/(count-1) for a,v in zip(avg,row)] for row in blocks]

    def jack(fn):
        central = fn(avg)
        values = [fn(x) for x in loo]
        if central is None or any(v is None for v in values):
            return [central,None]
        mid = statistics.mean(values)
        err = math.sqrt((count-1)/count * sum((v-mid)**2 for v in values))
        return [central,err]

    def eff(x,t):
        return cosh_energy(x[t+1],x[t+2],t)

    def diff(x):
        a,b = eff(x,1),eff(x,2)
        return None if a is None or b is None else a-b

    return {"mean":avg,"se":se,"effective":[jack(lambda x:eff(x,1)),jack(lambda x:eff(x,2))],
            "effective_difference":jack(diff)}

def batch(chain, size):
    return [[statistics.mean(col) for col in zip(*chain[i:i+size])]
            for i in range(0,len(chain),size)]

SAMPLES = {"pilot":{4:512,8:512,16:512}, "confirm":{4:8192,8:4096,16:1536}, "extra":{4:65536}}
FIELDS = ("plaquette","c0","c1","c2","c3","c4","c5")

def pack(label):
    """Nonoverlapping 16-sweep means suffice for every result reported here."""
    target=ROOT/f"{label}_blocks.csv.gz"
    with gzip.open(target,"wt",newline="") as out:
        writer=csv.writer(out)
        writer.writerow(("L","start","block")+FIELDS)
        for n, samples in SAMPLES[label].items():
            for start in ("cold","hot"):
                prefix="" if label=="pilot" else label+"_"
                with (ROOT/f"{prefix}L{n}_{start}.csv").open() as f:
                    rows=list(csv.DictReader(f))
                warm=160 if label=="pilot" else 256
                assert [int(r["sweep"]) for r in rows]==list(range(warm+1,warm+samples+1))
                vals=[[float(r[k]) for k in FIELDS] for r in rows]
                for i,block in enumerate(batch(vals,16)):
                    writer.writerow((n,start,i,*block))

def analyze(n,label):
    with gzip.open(ROOT/f"{label}_blocks.csv.gz","rt") as f:
        rows=[r for r in csv.DictReader(f) if int(r["L"])==n]
    chains=[]
    for start in ("cold","hot"):
        group=[r for r in rows if r["start"]==start]
        assert [int(r["block"]) for r in group] == list(range(SAMPLES[label][n]//16))
        chains.append([[float(r[k]) for k in FIELDS] for r in group])
    trials = {}
    for b in (16,32,64):
        grouped = [batch(chain,b//16) for chain in chains]
        trials[str(b)] = stats(grouped[0]+grouped[1])
    per_chain = [stats(batch(chain,2)) for chain in chains]
    flags=[]
    for b in ("32","64"):
        data=trials[b]
        if any(data["mean"][k] <= 3*data["se"][k] for k in (2,3,4)):
            flags.append(f"weak C(1..3) at block {b}")
        delta,err=data["effective_difference"]
        if err is None or abs(delta)>2*err:
            flags.append(f"no two-window plateau at block {b}")
    for k,name in ((0,"plaquette"),(2,"C1"),(3,"C2"),(4,"C3")):
        spread=math.hypot(*(s["se"][k] for s in per_chain))
        if abs(per_chain[0]["mean"][k]-per_chain[1]["mean"][k])>3*spread:
            flags.append(f"hot/cold mismatch in {name}")
    return {"L":n, "measurements":2*SAMPLES[label][n], "p_a":2*math.pi/n,
            "block32":trials["32"],"block16":trials["16"],"block64":trials["64"],
            "chain_plaquettes":[[s["mean"][0],s["se"][0]] for s in per_chain],
            "status":"PILOT_PLATEAU" if not flags else "UNRESOLVED","flags":flags}

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=SAMPLES)
    parser.add_argument("--pack-raw",action="store_true")
    args=parser.parse_args()
    if args.pack_raw:
        pack(args.stage)
    print(json.dumps([analyze(n,args.stage) for n in SAMPLES[args.stage]],indent=2,allow_nan=False))
