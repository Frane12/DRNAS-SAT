"""Finite-radius one-electron Dirac threshold, uniform spherical charge.
Energy E=-m_e c^2. Not an estimate of nuclear existence or lifetime.
Lengths in reduced electron Compton wavelengths. Requires scipy, mpmath.
"""
import json
import numpy as np
import mpmath as mp
from scipy.integrate import solve_ivp
from scipy.optimize import brentq
ALPHA=1/137.035999177
COMPTON_FM=386.15926764
mp.mp.dps=35

def determinant(Z,radius_fm,tol=1e-10):
 a=Z*ALPHA; R=radius_fm/COMPTON_FM
 def ode(x,y):
  G,F=y; v=-a*(3-x*x)/2
  return [G/x-v*F,-F/x+(2*R+v)*G]
 eps=1e-6
 sol=solve_ivp(ode,(eps,1),[eps,(2*R-1.5*a)*eps**2/3],rtol=tol,atol=tol*1e-2)
 if not sol.success: raise RuntimeError(sol.message)
 Gi,Fi=sol.y[:,-1]
 t=mp.sqrt(8*a*R); nu=2*mp.sqrt(1-a*a+0j)
 k=mp.besselk(nu,t); dk=-(mp.besselk(nu-1,t)+mp.besselk(nu+1,t))/2
 Go=float(mp.re(k)); Fo=float(mp.re((t*dk/2-k)/a))
 return (Gi*Fo-Fi*Go)/(np.hypot(Gi,Fi)*np.hypot(Go,Fo))

def root(R,tol):
 z=np.linspace(137.04,210,160); ds=[determinant(x,R,tol) for x in z]
 for i in range(len(z)-1):
  if ds[i]*ds[i+1]<0:
   return float(brentq(lambda x:determinant(x,R,tol),z[i],z[i+1],xtol=1e-10))
 raise RuntimeError('no crossing')
results=[]
for r in [4,6,8,10,12]:
 z=root(r,1e-9); z2=root(r,1e-11)
 results.append({'radius_fm':r,'critical_Z':z2,'tolerance_difference':abs(z-z2),'matching_residual':abs(determinant(z2,r,1e-11))})
print(json.dumps({'model':'one electron, uniform sphere, E=-mec^2, kappa=-1, first threshold root in 137.04..210','results':results,'limitations':'No electron screening, QED corrections, realistic nuclear charge profile or nuclear stability calculation.'},indent=2))
