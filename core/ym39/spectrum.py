"""Correlated finite-time stress tests on YM38. Weights refer to C(0)."""
import gzip
import json
from pathlib import Path

import numpy as np
from scipy.optimize import nnls
from scipy.stats import chi2, f as f_distribution, t as student

ROOT = Path(__file__).resolve().parent
MASSES = np.r_[np.arange(.8,4.01,.1),5,7,10,20]
FRACTIONS = (0.,.01,.05,.10,.25,1.)

def kernel(energy,T=16):
    e = np.atleast_1d(energy)[:,None]
    lag = np.arange(1,6)
    return ((np.exp(-e*lag)+np.exp(-e*(T-lag)))/(1+np.exp(-T*e))).T

def energy(p,mass,velocity=1.):
    return 2*np.arcsinh(np.hypot(velocity*np.sin(p/2),np.sinh(np.asarray(mass)/2)))

def dense_shape(momentum, time_extent, depth=16):
    # Each dyadic rational in (0,1) first appears with an odd numerator.
    result = np.zeros(5)
    for level in range(1, depth + 1):
        denominator = 2 ** level
        masses = np.arange(1, denominator, 2) / denominator
        component = kernel(energy(momentum, masses), time_extent).mean(axis=1)
        result += 2. ** -level * component
    # The remaining total weight is 2^(-depth). Reusing the last mean
    # changes any normalized lag by at most that value.
    return result + 2. ** -depth * component


def data(n,stage=None,block_size=64):
    if stage is None:
        stage = 'extra' if n == 4 else 'confirm'
    with gzip.open(ROOT.parent/'ym38'/f'{stage}_blocks.csv.gz','rt') as fp:
        rows=np.genfromtxt(fp,delimiter=',',names=True,dtype=None,encoding='utf8')
    chains=[]
    for start in ('cold','hot'):
        selected=rows[(rows['L']==n)&(rows['start']==start)]
        raw=np.column_stack([selected[f'c{i}'] for i in range(6)])
        chains.append(raw.reshape(-1,block_size//16,6).mean(axis=1))
    return np.array(chains)

def normalized(y):
    return y[...,1:]/y[...,:1]

def distance(obs,W,hard,soft,f):
    # Closest heavy mixture on the grid, with fixed soft fraction f.
    vertices = W@((1-f)*hard+f*soft[:,None])
    y=W@obs
    if f==1:
        err=vertices[:,0]-y
        d=float(err@err)
        return d,d,np.r_[1.,np.zeros(hard.shape[1]-1)]
    weights,_=nnls(np.vstack((vertices,np.full(vertices.shape[1],1.e5))),
                   np.r_[y,1.e5],maxiter=500)
    weights=weights/weights.sum()
    residual=y-vertices@weights
    norm=np.linalg.norm(residual)
    # Distance lower bound from a supporting hyperplane of the finite hull.
    lb=max(0.,float(residual@y-(residual@vertices).max())/norm) if norm>1e-14 else 0.
    return float(norm**2),lb**2,weights

def test(n):
    chains=data(n); blocks=np.concatenate(chains); k=len(blocks)
    mean=blocks.mean(axis=0); ratios=normalized(mean)
    loo=normalized((k*mean-blocks)/(k-1))
    cov=(k-1)*np.cov(loo,rowvar=False,ddof=0)
    se=np.sqrt(cov.diagonal())
    W=np.linalg.inv(np.linalg.cholesky(cov))
    p=2*np.pi/n
    hard=kernel(energy(p,MASSES))
    line=kernel(energy(p,0))[:,0]
    masses=1/np.arange(1,49)
    tower_weights=2.**-np.arange(1,49);tower_weights[-1]+=2.**-48
    shapes={'massless':line,'half_speed':kernel(energy(p,0,.5))[:,0],
            'accumulating_tower':kernel(energy(p,masses))@tower_weights,
            'dense_dyadic':dense_shape(p,16)}
    # Simultaneous, nominal 95% screen across 3 volumes and 5 lags.
    crit=float(chi2.ppf(1-.05/3,5))
    multiplier=student.ppf(1-.05/15,k-1)
    upper=(ratios+multiplier*se)/line
    out={'L':n,'blocks':k,'correlator_ratios':ratios.tolist(),'se':se.tolist(),
         'massless_fraction_positive_upper':float(min(1.,min(upper))),
         'limiting_lag':int(1+np.argmin(upper)),'ellipsoid_cut':crit,
         'finite_sample_reference_cut':float(5*(k-1)/(k-5)*f_distribution.ppf(1-.05/3,5,k-5)),
         'profiles':{}}
    checkblocks=np.concatenate(data(n,"pilot"))
    cm=checkblocks.mean(axis=0)
    ck=len(checkblocks)
    cloo=normalized((ck*cm-checkblocks)/(ck-1))
    cv=(ck-1)*np.cov(cloo,rowvar=False,ddof=0)
    out["holdout_blocks"]=ck
    sensitivities={}
    for bsize in (32,64,128):
        bs=np.concatenate(data(n,block_size=bsize))
        bm=bs.mean(axis=0); bk=len(bs)
        br=normalized(bm); bl=normalized((bk*bm-bs)/(bk-1))
        bse=bl.std(axis=0)*np.sqrt(bk-1)
        up=(br+student.ppf(1-.05/15,bk-1)*bse)/line
        sensitivities[str(bsize)]={"lags1_5":float(up.min()),"lags1_3":float(up[:3].min())}
    out["positive_bound_sensitivity"]=sensitivities
    for name,shape in shapes.items():
        profile={}
        for f in FRACTIONS:
            d,lb,w=distance(ratios,W,hard,shape,f)
            pred=(1-f)*(hard@w)+f*shape
            resid=normalized(cm)-pred
            holdout=float(resid@np.linalg.solve(cv,resid))
            profile[str(f)]={'pilot_D2_no_refit':holdout,'D2':d,'D2_lower':lb,
              'screen':'compatible' if d<=crit else 'excluded_on_grid' if lb>crit else 'undecided',
              'heavy_weights':[[float(m),float(a)] for m,a in zip(MASSES,w) if a>1e-6 and f<1.]}
        out['profiles'][name]=profile
    # Injection/recovery: add known massless signal to real resampled spectra.
    # Test whether the specified gapped nuisance grid can still explain them.
    rng=np.random.default_rng(390000+n)
    replicas=[]
    for _ in range(400):
        boot=np.array([chain[rng.integers(len(chain),size=len(chain))].mean(axis=0) for chain in chains])
        replicas.append(normalized(boot.mean(axis=0)))
    out['injection_gapped_grid_rejection']={}
    for f in FRACTIONS:
        excluded=sum(distance(v+f*(line-ratios),W,hard,line,0)[1]>crit for v in replicas)
        out['injection_gapped_grid_rejection'][str(f)]=excluded/len(replicas)
    return out

if __name__=='__main__':
    print(json.dumps([test(n) for n in (4,8,16)],indent=2,allow_nan=False))
