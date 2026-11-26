"""ELEMENT-03: charge geometry, symbolic certificates, held-out profile tests.
One-electron Dirac equation with prescribed spherical charge. No nuclear-stability prediction.
Run: OPENBLAS_NUM_THREADS=1 python drnas_element03.py > results.json
"""
import json,itertools,math,functools
import numpy as np
import sympy as sp
import mpmath as mp
from scipy.integrate import solve_ivp
from scipy.optimize import brentq
from concurrent.futures import ProcessPoolExecutor
ALPHA=1/137.035999177
COMPTON=386.15926764
mp.mp.dps=25
@functools.lru_cache(None)
def profile(p):
    if p==-1:return 1.,np.array([1.])
    b=np.array([(-1)**j*math.comb(p,j)/(2*j+3) for j in range(p+1)])
    b/=b.sum();d=b/(2*np.arange(p+1)+2)
    return math.sqrt(3/(2*p+5)),np.r_[1+d.sum(),-d]
def determinant(z,R,p,tol=2e-8,analytic_shell=True):
    a=z*ALPHA;R=R/COMPTON;_,co=profile(p)
    if p==-1 and analytic_shell and a>2*R:
        k=math.sqrt(a*(a-2*R));G=math.sin(k)/k;F=(math.cos(k)-G)/a
    else:
        def rhs(x,y):
            G,F=y;v=-a*np.polynomial.polynomial.polyval(x*x,co)
            return [G/x-v*F,-F/x+(2*R+v)*G]
        e=1e-6;s=solve_ivp(rhs,(e,1.),[e,(2*R-a*co[0])*e*e/3],rtol=tol,atol=tol*.01)
        if not s.success:raise RuntimeError(s.message)
        G,F=s.y[:,-1]
    t=mp.sqrt(8*a*R);nu=2*mp.sqrt(1-a*a+0j)
    K=mp.besselk(nu,t);dK=-(mp.besselk(nu-1,t)+mp.besselk(nu+1,t))/2
    Go=float(mp.re(K));Fo=float(mp.re((t*dK/2-K)/a))
    return (G*Fo-F*Go)/(math.hypot(G,F)*math.hypot(Go,Fo))
def solve(job):
    tag,p,r,kind=job;ratio,_=profile(p);R=r/ratio if kind=='rms' else r
    lo=1/ALPHA+1e-7;f=lambda z:determinant(z,R,p)
    def scan(step,ff):
        a=lo;fa=ff(a)
        while a<350:
            b=a+step;fb=ff(b)
            if fa*fb<0:return brentq(ff,a,b,xtol=1e-9)
            a=b;fa=fb
        raise RuntimeError((p,r,'no root'))
    step=.5 if r<.1 else 2.
    z=scan(step,f);g=lambda zz:determinant(zz,R,p,tol=2e-10,analytic_shell=False)
    z2=scan(step/2,g) if tag=='stress' else brentq(g,z-.05,z+.05,xtol=1e-10)
    return dict(tag=tag,p=p,r_input_fm=r,kind=kind,outer_radius_fm=R,rms_fm=R*ratio,z=z2,delta_audit=abs(z2-z),residual=abs(g(z2)))
def search(rows):
    def data(tag):
        d=[x for x in rows if x['tag']==tag];return np.array([x['rms_fm'] for x in d]),np.array([x['z'] for x in d])
    train=data('train');val=data('validation');test=data('holdout');stress=data('stress')
    transforms=['delta','inverse_sqrt_delta','inverse_nu','nu','identity']
    def transform(z,t):
        a=z*ALPHA
        return {'delta':lambda:a-1,'inverse_sqrt_delta':lambda:1/np.sqrt(a-1),'inverse_nu':lambda:1/np.sqrt(a*a-1),'nu':lambda:np.sqrt(a*a-1),'identity':lambda:a}[t]()
    def invert(y,t):
        if t=='delta':a=1+y
        elif t=='inverse_sqrt_delta':a=1+1/y**2
        elif t=='inverse_nu':a=np.sqrt(1+1/y**2)
        elif t=='nu':a=np.sqrt(1+y*y)
        else:a=y
        return a/ALPHA
    def feats(r):
        L=np.log(COMPTON/r);return np.column_stack([np.ones_like(L),L,1/L,L**2,1/L**2,np.log(L)])
    names=['1','L','1/L','L^2','1/L^2','log(L)']
    def metrics(z,zh):return {'rmse_Z':float(np.sqrt(np.mean((z-zh)**2))),'mae_Z':float(np.mean(abs(z-zh))),'max_abs_Z':float(np.max(abs(z-zh)))}
    models=[]
    for tr in transforms:
        for k in (1,2,3):
            for idx in itertools.combinations(range(6),k):
                X=feats(train[0])[:,idx];w=np.linalg.lstsq(X,transform(train[1],tr),rcond=None)[0]
                def pred(r):return invert(feats(r)[:,idx]@w,tr)
                rg=np.geomspace(.2,30,101);yy=feats(rg)[:,idx]@w
                if tr!='identity' and np.any(yy<=0):continue
                zg=pred(rg)
                if not np.all(np.isfinite(zg)) or np.any(zg<=1/ALPHA) or np.any(np.diff(zg)<0):continue
                m=metrics(val[1],pred(val[0]));models.append((m['rmse_Z']+.02*k,tr,idx,w,m))
    models.sort(key=lambda v:v[0]);score,tr,idx,w,vm=models[0]
    def evaluate(item):
        sc,t,j,c,v=item
        return {'transform':t,'terms':[names[i] for i in j],'coefficients':c.tolist(),'validation_score':sc,'validation':v,**{tag:metrics(d[1],invert(feats(d[0])[:,j]@c,t)) for tag,d in [('train',train),('holdout',test),('stress',stress)]}}
    best=evaluate(models[0]);best['holdout_rows']=[{'p':d['p'],'rms_fm':d['rms_fm'],'numerical_Z':d['z'],'predicted_Z':float(invert(feats(np.array([d['rms_fm']]))[:,idx]@w,tr)[0])} for d in rows if d['tag']=='holdout']
    def asym(r):return np.sqrt(1+(np.pi/np.log(COMPTON/r))**2)/ALPHA
    return {'generated':5*sum(math.comb(6,k) for k in (1,2,3)),'accepted':len(models),'selected':best,'top5':[evaluate(m) for m in models[:5]],'leading_log_comparator':{tag:metrics(d[1],asym(d[0])) for tag,d in [('train',train),('validation',val),('holdout',test),('stress',stress)]}}
def proof():
    x,t=sp.symbols('x t',real=True);P={-1:sp.Integer(1)}
    for p in range(5):
        b=[sp.Rational((-1)**j*math.comb(p,j),2*j+3) for j in range(p+1)];M=sum(v*t**(2*j+3) for j,v in enumerate(b))/sum(b)
        P[p]=sp.expand(1+sp.integrate(M/t**2,(t,x,1)))
    u=sp.symbols('u',nonnegative=True);cert=[]
    for p in range(-1,4):
        D=sp.expand(P[p+1]-P[p]);q=sp.Poly(D,x);pol=sp.expand(sum(c*(1-u)**(k[0]//2) for k,c in q.terms()))
        assert all(c>=0 for c in sp.Poly(pol,u).all_coeffs());assert sp.expand(pol.subs(u,1-x*x)-D)==0
        cert.append({'from_p':p,'to_p':p+1,'difference_in_u':str(pol)})
    return {'u':'1-x^2 in [0,1]','potentials':{str(p):str(v) for p,v in P.items()},'certificates':cert,'meaning':'At fixed outer radius and total charge each successive profile has a larger positive electrostatic potential magnitude at every interior point. Exact algebraic ordering, not a proof of nuclear existence.'}
def main():
    jobs=[]
    for p in [-1,0]:jobs.extend(('train',p,r,'rms') for r in [.5,1,2,4,8,16,24])
    jobs.extend(('validation',1,r,'rms') for r in [.75,3,5,10,20])
    for p in [2,4]:jobs.extend(('holdout',p,r,'rms') for r in [.25,1.5,7,14,30])
    for p in [-1,0,1,2,3,4]:
        jobs.append(('audit',p,8,'outer'));jobs.append(('audit',p,8,'rms'))
    for p in [-1,4]:jobs.extend(('stress',p,r,'rms') for r in [.001,.01,.1,40,60])
    with ProcessPoolExecutor(max_workers=6) as ex:rows=list(ex.map(solve,jobs))
    report={'model':'bare one-electron Dirac equation; prescribed spherical charge, no nuclear dynamics or QED screening','count':len(rows),'max_tol_difference':max(d['delta_audit'] for d in rows),'max_matching_residual':max(d['residual'] for d in rows),'search':search(rows),'proof':proof(),'rows':rows}
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
