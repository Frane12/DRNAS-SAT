"""DRNAS ELEMENT-02: standalone research continuation of ELEMENT-01.
Requires numpy, RDKit, sympy. Frozen Z splits; no holdout tuning.
RDKit tabulated isotope masses, not individually AME provenance-verified.
Shell basis centers generated without a list of magic numbers.
"""
import json, hashlib
import numpy as np
import sympy as sp
from rdkit import Chem,rdBase
pt=Chem.GetPeriodicTable(); u=931.49410242; mn=1.00866491595; h=pt.GetMassForIsotope(1,1)
rows=[]
for z in range(8,119):
 for a in range(z,4*z+10):
  m=pt.GetMassForIsotope(z,a)
  if m>0: rows.append((z,a-z,a,(z*h+(a-z)*mn-m)*u))
data=np.array(rows); z,n,a,y=data.T
train=z<=70; val=(z>70)&(z<=88); test=z>88
def base(z,n):
 a=z+n; p=(np.cos(np.pi*z)+np.cos(np.pi*n))/2
 return np.column_stack([a,-a**(2/3),-z*(z-1)/a**(1/3),-(n-z)**2/a,p/a**.5])
B=base(z,n)
features=[(q,c,w) for q in ('Z','N') for c in range(8,161,2) for w in (2.,4.,8.)]
def shell(z,n,key):
 q,c,w=key; x=z if q=='Z' else n
 return np.exp(-.5*((x-c)/w)**2)
F=np.column_stack([shell(z,n,k) for k in features]); nt=train.sum()
support=np.sum(F[train]>.2,axis=0)>=8
Ftr=F[train]; Fv=F[val]; ytr=y[train]; yv=y[val]
def rmse(x): return float(np.sqrt(np.mean(x*x)))
def fit(M):return np.linalg.lstsq(M[train],ytr,rcond=None)[0]
def metric(pred,mask):
 d=pred[mask]-y[mask]
 return {'n':int(mask.sum()),'rmse_MeV':rmse(d),'mae_MeV':float(np.mean(abs(d))),'rmse_per_nucleon_MeV':rmse(d/a[mask])}
bw=fit(B); bp=B@bw
chosen=[]; path=[]; evaluated=0; models=[]
for step in range(13):
 M=np.column_stack([B,F[:,chosen]])
 w=fit(M); pr=M@w; score=rmse(pr[val]-yv)+.025*step
 models.append((score,list(chosen),w.copy())); path.append({'step':step,'train':rmse(pr[train]-ytr),'validation':rmse(pr[val]-yv),'score':score,'last':features[chosen[-1]] if chosen else None})
 if step==12:break
 Q,_=np.linalg.qr(M[train],mode='reduced'); P=Q.T@Ftr; R=Ftr-Q@P; denom=np.sum(R*R,axis=0)
 beta=(R.T@(ytr-pr[train]))/np.maximum(denom,1e-25)
 coef=np.linalg.lstsq(M[train],Ftr,rcond=None)[0]
 V=Fv-M[val]@coef
 err=pr[val]-yv; errors=np.sqrt(np.mean((err[:,None]+V*beta)**2,axis=0))
 ok=support & (denom>1e-7) & (np.abs(beta)<30)
 ok[chosen]=False; evaluated+=int(ok.sum())
 errors[~ok]=np.inf
 if not np.any(ok):break
 chosen.append(int(np.argmin(errors)))
score,idx,w=min(models,key=lambda r:r[0]); M=np.column_stack([B,F[:,idx]]); pred=M@w
old=a*(6.37249803403575+19.120326183855482*z/a+36.47007082985067*z*(z-1)/a**(4/3)-37.125910246735124*z*z/a**(4/3))
alpha=1/137.035999177; Z=sp.symbols('Z', positive=True); al=sp.symbols('alpha',positive=True); m,c=sp.symbols('m c',positive=True)
E=m*c*c*sp.sqrt(1-(Z*al)**2)
d2=sp.simplify(sp.diff(E,Z,2)); expected=-m*c*c*al**2/(1-(Z*al)**2)**sp.Rational(3,2)
assert sp.simplify(d2-expected)==0
atomic=[]
for zz in [1,82,118,119,120,126,130,136,137,138,150,170,200,500,1000]:
 x=zz*alpha; r=1-x*x
 atomic.append({'Z':zz,'Zalpha':x,'E_over_mec2':float(np.sqrt(r)) if r>=0 else None,'status':'real_point_model' if r>0 else 'point_model_outside_domain'})
report={'data':{'rdkit':rdBase.rdkitVersion,'rows':len(rows),'sha256':hashlib.sha256(data.tobytes()).hexdigest(),'split':{'train':'Z 8-70','validation':'Z 71-88','holdout':'Z 89-118'},'warning':'Mass entries are tabulations, not individually checked for measured vs extrapolated provenance. Atomic electron binding not corrected.'},'search':{'basis_size':len(features),'evaluated':evaluated,'path':path,'selected_shell_terms':[{'axis':features[i][0],'center':features[i][1],'width':features[i][2],'weight_MeV':float(v)} for i,v in zip(idx,w[5:])],'base_coefficients':w[:5].tolist(),'baseline_coefficients':bw.tolist()},'metrics':{},'atomic':{'alpha':alpha,'critical_continuous_Z':1/alpha,'first_integer_outside_domain':138,'symbolic_second_derivative':str(d2),'symbolic_check':True,'rows':atomic},'scope':'Standalone continuation of ELEMENT-01, no CORE/YM execution. No nuclear existence or lifetime prediction.'}
for name,mask in [('train',train),('validation',val),('holdout',test),('superheavy_tabulated',z>=104)]:
 report['metrics'][name]={k:metric(v,mask) for k,v in [('element01',old),('liquid_drop',bp),('element02',pred)]}
print(json.dumps(report,indent=2))
