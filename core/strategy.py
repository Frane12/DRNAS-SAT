"""Opt-in cross-CNF scheduling memory. No clauses, models, or answers persisted."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import re
import tempfile
from run import run as native_run
from verify import parse_cnf

PROFILES=('narrow','wide','bridge')
CONTEXT=re.compile(r'(small|medium|large):(low|mid|high):(short|mixed|long)')
MAX=100000
KEYS=('attempts','solved','cost_us')

def context(source):
    p=Path(source)
    if p.stat().st_size>2000000: return None
    n,cs=parse_cnf(p)
    if n<1: return None
    size='small' if n<=32 else 'medium' if n<=256 else 'large'
    density='low' if len(cs)<2*n else 'mid' if len(cs)<5*n else 'high'
    literals=sum(len(set(c)) for c in cs)
    width='short' if literals<=2*len(cs) else 'mixed' if literals<=4*len(cs) else 'long'
    return ':'.join((size,density,width))

def load(path):
    p=Path(path)
    if not p.exists(): return {}
    if p.stat().st_size>65536: raise ValueError('strategy memory size')
    obj=json.loads(p.read_text())
    if not isinstance(obj,dict) or obj.get('version')!=1 or not isinstance(obj.get('contexts'),dict):
        raise ValueError('strategy memory format')
    data=obj['contexts']
    for ctx,rows in data.items():
        if not CONTEXT.fullmatch(ctx) or not isinstance(rows,dict): raise ValueError('context')
        for profile,row in rows.items():
            if profile not in PROFILES or not isinstance(row,dict) or set(row)!=set(KEYS):
                raise ValueError('profile')
            a,s,c=(row[k] for k in KEYS)
            if any(type(v) is not int or v<0 for v in (a,s,c)) or s>a or a>MAX or c>10**15:
                raise ValueError('counters')
    return data

def choose(rows,explore=True):
    def row(p):return rows.get(p,dict(attempts=0,solved=0,cost_us=0))
    if explore:
        unseen=[p for p in PROFILES if row(p)['attempts']==0]
        if unseen:return unseen[0]
        if sum(row(p)['attempts'] for p in PROFILES)%5==0:
            return min(PROFILES,key=lambda p:row(p)['attempts'])
    observed=[p for p in PROFILES if row(p)['attempts']]
    if not observed:return PROFILES[0]
    def score(p):
        r=row(p);a=r['attempts']
        return ((r['solved']+1)/(a+2),-r['cost_us']/a)
    return max(observed,key=score)

def observe(path,ctx,profile,solved,seconds):
    if not CONTEXT.fullmatch(ctx) or profile not in PROFILES:raise ValueError('observation')
    if not math.isfinite(seconds) or seconds<0:raise ValueError('cost')
    p=Path(path)
    with open(str(p)+'.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        data=load(p); row=data.setdefault(ctx,{}).setdefault(profile,dict(attempts=0,solved=0,cost_us=0))
        if row['attempts']>=MAX:
            for k in KEYS:row[k]//=2
        row['attempts']+=1
        row['solved']+=int(bool(solved))
        row['cost_us']+=min(10**9,round(seconds*1e6))
        with tempfile.NamedTemporaryFile(mode='w',dir=p.parent,delete=False) as f:
            json.dump(dict(version=1,contexts=data),f,sort_keys=True);f.write('\n');name=f.name
        try:os.replace(name,p)
        finally:
            if os.path.exists(name):os.unlink(name)
        return dict(row)

def run(source,evidence,seconds=5,audit_seconds=5,memory=None,readonly=False):
    if memory is None:
        return native_run(source,evidence,seconds,'freedom',audit_seconds)
    p=Path(memory).resolve()
    protected=[Path(source).resolve(),Path(evidence).resolve()]
    for candidate in (p,Path(str(p)+'.lock').resolve()):
        if any(candidate==q or (candidate.exists() and q.exists() and candidate.samefile(q)) for q in protected):
            return dict(status='ERROR',error='strategy memory aliases source/evidence')
    ctx=None;profile='narrow';error=None
    try:
        ctx=context(source)
        if ctx:profile=choose(load(p).get(ctx,{}),explore=not readonly)
    except (OSError,ValueError,TypeError) as exc:error=str(exc)
    result=native_run(source,evidence,seconds,'freedom',audit_seconds,strategy_profile=profile)
    result['strategy']=dict(context=ctx,profile=profile,readonly=readonly)
    if error is not None:result['strategy_error']=error
    status=result.get('status')
    telemetry=result.get('telemetry',{})
    if telemetry and telemetry.get('freedom_profile')!=profile:
        result['strategy_error']='native profile mismatch'
        return result
    # Credit is for the whole selected strategy, not a causal proof of the
    # individual profile's contribution. Rejected/error/audit-limit runs do not train.
    if ctx and error is None and not readonly and status in ('SAT','UNSAT','UNKNOWN','TIMEOUT'):
        try:
            result['strategy']['observation']=observe(p,ctx,profile,status in ('SAT','UNSAT'),result['solve_s'])
        except (OSError,ValueError,KeyError) as exc:result['strategy_error']=str(exc)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input');p.add_argument('evidence')
    p.add_argument('--seconds',type=float,default=5)
    p.add_argument('--audit-seconds',type=float,default=5)
    p.add_argument('--strategy-memory',required=True)
    p.add_argument('--readonly',action='store_true')
    a=p.parse_args()
    r=run(a.input,a.evidence,a.seconds,a.audit_seconds,a.strategy_memory,a.readonly)
    print(json.dumps(r))
    raise SystemExit(0 if r['status'] in ('SAT','UNSAT','UNKNOWN','TIMEOUT','AUDIT_LIMIT') else 1)
