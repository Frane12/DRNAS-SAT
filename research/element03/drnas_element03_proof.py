"""Independent symbolic extension of the ELEMENT-03 profile ordering.
Polynomial density rho_p proportional to (1-x^2)^p, integer p>=0.
"""
import math,json
import sympy as s
x,t,u=s.symbols('x t u',real=True);j=s.symbols('j',integer=True,nonnegative=True)
c=lambda k:s.binomial(2*k,k)/4**k
ratio=s.simplify(s.combsimp(c(j+2)/c(j+1)))
assert s.simplify(ratio-(2*j+3)/(2*j+4))==0
assert c(0)==1 and c(1)==s.Rational(1,2)
checked=[]
for p in range(21):
    b=[s.Rational((-1)**k*math.comb(p,k),2*k+3) for k in range(p+1)]
    M=sum(v*t**(2*k+3) for k,v in enumerate(b))/sum(b)
    direct=s.expand(1+s.integrate(M/t**2,(t,x,1)))
    compact=sum(c(k)*u**k for k in range(p+2))
    assert s.expand(compact.subs(u,1-x*x)-direct)==0
    lap=s.expand(4*(1-u)*s.diff(compact,u,2)-6*s.diff(compact,u))
    assert s.expand(lap+(p+1)*(4*p+6)*c(p+1)*u**p)==0
    checked.append(p)
report={'coefficient':'binomial(2*k,k)/4**k','recurrence':str(ratio),'verified_exact_profiles':checked,'general_proof':'For u=1-x^2, radial Laplacian is 4(1-u)d2/du2-6d/du. Coefficient of u^j cancels by c_(j+2)/c_(j+1)=(2j+3)/(2j+4), leaving -(p+1)(4p+6)c_(p+1) u^p. Surface values and regularity imply unique solution. Adjacent difference c_(p+2) u^(p+2)>=0.','meaning':'Exact electrostatic identity, not proof of existence of a new nucleus or a universal critical charge.'}
print(json.dumps(report,indent=2))
