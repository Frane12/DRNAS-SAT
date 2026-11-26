"""YM40: train-only variational optimization, independent validation, no spectral injection."""
import argparse,json
import numpy as np
from scipy.stats import t as student
K,D=8,6
def unpack(row):
    mean=row[...,1:1+K]
    return row[...,1+K:].reshape(*row.shape[:-1],D,K,K)-mean[...,None,:,None]*mean[...,None,None,:]
def choose(c,lag=0,cut=1e-3):
    a=(c[lag]+c[lag].T)/2
    b=(c[lag+1]+c[lag+1].T)/2
    vals,u=np.linalg.eigh(a)
    if vals[-1]<=0: raise ValueError("no positive metric")
    keep=vals>cut*vals[-1]
    w=u[:,keep]/np.sqrt(vals[keep])
    ev,z=np.linalg.eigh(w.T@b@w)
    v=w@z[:,-1]
    return v/np.linalg.norm(v),int(keep.sum()),float(ev[-1])
def energy(c,j,T):
    a,b=c[...,j],c[...,j+1]
    ok=(a>b)&(b>0)
    r=np.divide(a,b,out=np.ones_like(a),where=b!=0)
    lo=np.zeros_like(r);hi=lo+8
    for _ in range(50):
        mid=(lo+hi)/2
        small=np.cosh((T/2-j)*mid)/np.cosh((T/2-j-1)*mid)<r
        lo=np.where(small,mid,lo);hi=np.where(small,hi,mid)
    return np.where(ok,(lo+hi)/2,np.nan)
def assess(rows,v,T):
    n=len(rows); avg=rows.mean(axis=0);loo=(n*avg-rows)/(n-1)
    c=np.einsum('i,tij,j->t',v,unpack(avg),v)
    cl=np.einsum('i,btij,j->bt',v,unpack(loo),v)
    se=cl.std(axis=0)*np.sqrt(n-1)
    est=np.array([energy(c,j,T) for j in range(3)])
    jack=np.stack([energy(cl,j,T) for j in range(3)],axis=1)
    err=jack.std(axis=0)*np.sqrt(n-1)
    delta=(jack[:,1]-jack[:,2]).std()*np.sqrt(n-1)
    snr=np.divide(c[1:4],se[1:4],out=np.full(3,np.nan),where=se[1:4]>0)
    ok=bool(np.all(snr>=3) and np.all(np.isfinite(err)) and abs(est[1]-est[2])<=2*delta)
    def clean(a):return [float(x) if np.isfinite(x) else None for x in a]
    upper=est[0]+student.ppf(.995,n-1)*err[0]
    return dict(blocks=n,correlations=clean(c),snr=clean(snr),effective_energies=clean(est),
                conditional_se=clean(err),screen=ok,
                early_upper_nominal=float(upper) if np.isfinite(upper) else None)
def test():
    t=np.arange(D)
    heavy=np.array([1.,1.,0,0,0,0,0,0]);soft=np.array([.01,.15,0,0,0,0,0,0])
    shape=lambda m:np.exp(-m*t)+np.exp(-m*(24-t))
    c=shape(1.2)[:,None,None]*np.outer(heavy,heavy)+shape(.06)[:,None,None]*np.outer(soft,soft)
    v,rank,_=choose(c,cut=1e-4)
    assert rank==2 and abs(v@heavy)<1e-8
    assert abs(energy(np.einsum('i,tij,j->t',v,c,v),0,24)-.06)<1e-8
    # A common vacuum offset must not enter connected covariance.
    m=np.arange(K,dtype=float)+1
    row=np.r_[.5,m,(c+np.outer(m,m)).ravel()]
    assert np.max(abs(unpack(row)-c))<1e-12
    print("YM40 exact two-state and vacuum-subtraction controls PASS",flush=True)
def read(path,b):
    r=np.loadtxt(path,delimiter=',',ndmin=2)
    assert r.shape[1]==1+K+D*K*K and np.isfinite(r).all()
    assert len(r)%(b//16)==0
    return r.reshape(-1,b//16,r.shape[1]).mean(axis=1)
def run(cold,hot,L,T,beta):
    results={}
    for block in (32,64):
        rows=[read(p,block) for p in (cold,hot)]
        for lag,cut in ((0,1e-3),(0,1e-2),(1,1e-3)):
            key=f"b{block}_t{lag}_cut{cut}"
            fold=[]
            for i in (0,1):
                train,val=rows[i],rows[1-i]
                try:
                    v,rank,eig=choose(unpack(train.mean(axis=0)),lag,cut)
                    r=assess(val,v,T)
                    r.update(train=['cold','hot'][i],rank=rank,train_eigenvalue=eig,coefficients=v.tolist())
                except (ValueError,np.linalg.LinAlgError) as e:
                    r=dict(screen=False,error=str(e))
                fold.append(r)
            results[key]=fold
            print("YM40_ROW "+json.dumps(dict(L=L,T=T,beta=beta,setting=key,folds=fold),allow_nan=False),flush=True)
        for i,r in enumerate(rows):
            v=np.eye(K)[2]
            print("YM40_BASE "+json.dumps(dict(L=L,T=T,beta=beta,block=block,chain=i,**assess(r,v,T)),allow_nan=False),flush=True)
    primary=[r for key in ("b32_t0_cut0.001","b64_t0_cut0.001") for r in results[key]]
    good=all(r["screen"] for r in primary)
    upper=[r.get("early_upper_nominal") for r in primary]
    soft=good and all(u is not None and u<.2 for u in upper)
    print("YM40_SUMMARY "+json.dumps(dict(L=L,T=T,beta=beta,screen=good,soft_candidate=soft,early_uppers=upper),allow_nan=False),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("cold",nargs="?");p.add_argument("hot",nargs="?")
    p.add_argument("--L",type=int);p.add_argument("--T",type=int,default=24);p.add_argument("--beta",type=float,default=2.35)
    a=p.parse_args();test()
    if a.cold:run(a.cold,a.hot,a.L,a.T,a.beta)
