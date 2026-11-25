"""Bounded contextual rule utility; statistics are scheduling hints, never evidence."""
import json
import math
import os
import re
import tempfile
from pathlib import Path
import fcntl

VALID=re.compile(r'A(?:[2-9]|10)|C[3-8][+-]')
CONTEXT=re.compile(r'(diagonal|mixed|other):(small|medium|large)')
MAX_COUNT=1000000

def context(source):
    # Only a coarse, label-free signature; no saved problem or answer.
    with open(source,'rb') as f: raw=f.read(2000001)
    if len(raw)>2000000: return None
    try:
        w=raw.decode('ascii').split()
        if w[:3]!=['p','sop','lower']: return None
        n,m=int(w[3]),int(w[4])
        if not 1<=n<=256 or not 0<=m<=4096 or len(w)!=6+2*m: return None
        words=w[7::2]
        if any(len(s)!=n or set(s)-set('IXYZ') for s in words): return None
        active=[s for s in words if set(s)!={'I'}]
        kind='diagonal' if all(set(s)<=set('IZ') for s in active) else 'mixed'
        size='small' if m<=16 else 'medium' if m<=128 else 'large'
        return kind+':'+size
    except (ValueError,IndexError,UnicodeError): return None

def read_rules(path):
    p=Path(path)
    if not p.exists(): return []
    if p.stat().st_size>4096: raise ValueError('rule file too large')
    lines=p.read_text().splitlines()
    if not lines or lines[0]!='drnas-rule-memory-v1' or any(not VALID.fullmatch(x) for x in lines[1:]):
        raise ValueError('bad rule file')
    return sorted(set(lines[1:]))

def load(path):
    p=Path(path)
    if not p.exists(): return {}
    if p.stat().st_size>65536: raise ValueError('utility file too large')
    raw=json.loads(p.read_text())
    if not isinstance(raw,dict) or raw.get('version')!=1 or not isinstance(raw.get('contexts'),dict):
        raise ValueError('bad utility file')
    clean={}
    for ctx,entries in raw['contexts'].items():
        if not CONTEXT.fullmatch(ctx) or not isinstance(entries,dict): raise ValueError('bad context')
        clean[ctx]={}
        for rule,row in entries.items():
            if not VALID.fullmatch(rule) or not isinstance(row,dict): raise ValueError('bad rule')
            a,h,pv,c=(row.get(k) for k in ('attempts','matches','proved','cost_us'))
            if any(type(v) is not int or v<0 for v in (a,h,pv,c)) or not pv<=h<=a<=MAX_COUNT or c>10**18:
                raise ValueError('bad counters')
            clean[ctx][rule]=dict(attempts=a,matches=h,proved=pv,cost_us=c)
    return clean

def choose(rules,entries):
    if not rules:return None
    def stats(r):return entries.get(r,dict(attempts=0,matches=0,proved=0,cost_us=0))
    unseen=[r for r in rules if stats(r)['attempts']==0]
    if unseen:return sorted(unseen)[0]
    total=sum(stats(r)['attempts'] for r in rules)
    # Periodic exploration prevents a rule from being permanently discarded.
    if total%5==0:return min(rules,key=lambda r:(stats(r)['attempts'],r))
    def score(r):
        s=stats(r);a=s['attempts']
        quality=(s['proved']+1)/(a+2)
        # Cost penalty is bounded and uses measured replay time only.
        cost=1+min(10,s['cost_us']/max(1,a)/1000)
        return (quality/cost,(s['matches']+1)/(a+2),-a)
    return max(sorted(rules),key=score)

def observe(path,ctx,rule,matched,proved,cost_s):
    if not CONTEXT.fullmatch(ctx) or not VALID.fullmatch(rule):raise ValueError('invalid observation')
    if not math.isfinite(cost_s) or cost_s<0:raise ValueError('invalid cost')
    p=Path(path)
    with open(str(p)+'.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        data=load(p); row=data.setdefault(ctx,{}).setdefault(rule,dict(attempts=0,matches=0,proved=0,cost_us=0))
        if row['attempts']>=MAX_COUNT:
            for k in row:row[k]//=2
        row['attempts']+=1
        row['matches']+=int(bool(matched))
        row['proved']+=int(bool(matched and proved))
        row['cost_us']+=min(10**12,round(cost_s*1e6))
        with tempfile.NamedTemporaryFile(mode='w',dir=p.parent,delete=False) as f:
            json.dump(dict(version=1,contexts=data),f,sort_keys=True);f.write('\n');name=f.name
        try:os.replace(name,p)
        finally:
            if os.path.exists(name):os.unlink(name)
        return dict(row)
