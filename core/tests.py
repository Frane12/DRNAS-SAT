"""Soundness against exhaustive truth tables, certificate tampering, parser failures."""
import itertools
import json
import pathlib
import random
import subprocess
import tempfile
from verify import verify, check_model, check_capacity

ROOT = pathlib.Path(__file__).resolve().parent


def write(path, n, cs):
    path.write_text(f'p cnf {n} {len(cs)}\n' + ''.join(' '.join(map(str, c)) + ' 0\n' for c in cs))


def truth(n, cs):
    return any(all(any(bool((mask >> (abs(x)-1)) & 1) == (x > 0) for x in c) for c in cs)
               for mask in range(1 << n))


def gf3(rng, groups=5):
    cs = []
    def v(g, d): return 3*g+d+1
    for g in range(groups):
        cs.append(tuple(v(g,d) for d in range(3)))
        cs.extend((-v(g,a),-v(g,b)) for a,b in itertools.combinations(range(3),2))
    planted = [rng.randrange(3) for _ in range(groups)]
    for g in range(groups-1):
        h,j=(g+1)%groups,(g+3)%groups
        coeff=rng.choice([1,2]);rhs=(planted[g]+coeff*planted[h]+planted[j])%3
        cs.extend((-v(g,a),-v(h,b),-v(j,d)) for a,b,d in itertools.product(range(3),repeat=3)
                  if (a+coeff*b+d)%3 != rhs)
    return hide(rng, 3*groups, cs)


def hide(rng,n,cs):
    perm=list(range(1,n+1));rng.shuffle(perm);perm=[v*rng.choice([-1,1]) for v in perm]
    out=[[perm[abs(l)-1]*(1 if l>0 else -1) for l in c] for c in cs]
    rng.shuffle(out)
    for c in out:rng.shuffle(c)
    return n,out


def word_formula(width,form):
    n=width;cs=[]
    def add_gate(op,a,b):
        nonlocal n
        assert a>0 and b>0 and a!=b
        n+=1;z=n
        if op==0:
            cs.extend(tuple(-v if bit else v for v,bit in zip([a,b,z],bits))
                      for bits in itertools.product([0,1],repeat=3) if bits[0]^bits[1]!=bits[2])
        elif op==1:cs.extend([(-a,-b,z),(a,-z),(b,-z)])
        else:cs.extend([(a,b,-z),(-a,z),(-b,z)])
        return z
    def shift(a,s,left):
        out=list(a)
        for i in range(width):
            j=i-s if left else i+s
            if 0<=j<width:out[i]=add_gate(0,a[i],a[j])
        return out
    x=list(range(1,width+1));y=shift(shift(x,2,True),3,False);out=[];carry=0
    for i in range(width):
        a,b=x[i],y[i];p=add_gate(0,a,b);out.append(add_gate(0,p,carry) if i else p)
        if i+1<width:
            gen=add_gate(1,a,b)
            carry=add_gate(2,gen,add_gate(1,p if form else add_gate(2,a,b),carry)) if i else gen
    mask=(1<<width)-1;k=173;v=(k^(k<<2))&mask;v^=v>>3;target=(k+v)&mask
    cs.extend((v if target>>i&1 else -v,) for i,v in enumerate(out))
    return n,cs


def main():
    rng=random.Random(11252026);cases=[]
    # Every subset of all eight full-width clauses on three variables.
    full=[tuple(v if bit else -v for v,bit in zip(range(1,4),bits))
          for bits in itertools.product([0,1],repeat=3)]
    for mask in range(256):cases.append((3,[c for i,c in enumerate(full) if mask>>i&1]))
    for i in range(160):
        n=1+i%9
        cs=[tuple(rng.choice([-1,1])*v for v in rng.sample(range(1,n+1),rng.randint(1,min(n,4))))
            for _ in range(rng.randint(0,6*n))]
        cases.append((n,cs))
    cases += [(0,[]),(0,[()]),(4,[(1,1),(-1,2),(3,-3),(-2,)]),
              (6,[(1,2),(-1,2),(3,4),(-3,4),(5,),(-5,)])]
    checked=0;terminal={};tamper=0
    with tempfile.TemporaryDirectory() as directory:
        d=pathlib.Path(directory);source=d/'in.cnf';cert=d/'out.cert'
        for i,(n,cs) in enumerate(cases):
            expected=10 if truth(n,cs) else 20
            for mode in (['default','memory','no-share'] if i%19==0 else ['default']):
                write(source,n,cs);cert.unlink(missing_ok=True)
                p=subprocess.run([ROOT/'bin/drnas-core',source,cert,'.6',mode],capture_output=True,text=True,timeout=.8)
                assert p.returncode==expected,(i,mode,p.returncode,expected,p.stdout,p.stderr)
                status,kind=verify(source,cert,p.returncode)
                terminal[kind]=terminal.get(kind,0)+1;checked+=1
                if i==255:
                    cert.write_text('1 0\n0\n')
                    try:verify(source,cert,10)
                    except ValueError:tamper+=1
                    else:raise AssertionError('invalid model accepted')
        for i in range(16):
            n,cs=gf3(rng);write(source,n,cs);cert.unlink(missing_ok=True)
            p=subprocess.run([ROOT/'bin/drnas-core',source,cert,'1'],capture_output=True,text=True,timeout=1.2)
            assert p.returncode==10,(p.stdout,p.stderr)
            verify(source,cert,10);assert 'GF3_domains' in p.stdout,p.stdout;checked+=1
        for form,width in enumerate([8,12]):
            n,cs=word_formula(width,form);write(source,n,cs);cert.unlink(missing_ok=True)
            p=subprocess.run([ROOT/'bin/drnas-core',source,cert,'5'],capture_output=True,text=True,timeout=5.2)
            assert p.returncode==10,(p.stdout,p.stderr)
            verify(source,cert,10);assert 'word_lift_circuit' in p.stdout,p.stdout;checked+=1
        # A real capacity certificate: four disjoint demands, three mutex slots.
        n=12;cs=[tuple(3*i+j+1 for j in range(3)) for i in range(4)]
        cs += [(-(3*a+j+1),-(3*b+j+1)) for j in range(3) for a,b in itertools.combinations(range(4),2)]
        lines=[' '.join(map(str,c))+' 0' for c in cs]
        check_capacity(n,cs,lines)
        for bad in [lines[:-1],lines+['1 2 3 4 0']]:
            try:check_capacity(n,cs,bad)
            except ValueError:tamper+=1
            else:raise AssertionError('bad capacity accepted')
        write(source,1,[(1,)])
        for text in ['0\n','2 0\n0\n','1 0\n','g11-symbolic-v1\nr\n0\no 1 0\n']:
            cert.write_text(text)
            try:verify(source,cert,20)
            except ValueError:tamper+=1
            else:raise AssertionError('bad proof accepted')
        write(source,2,[(1,2),(1,-2),(-1,2),(-1,-2)])
        cert.write_text('g11-symbolic-v1\nr\n1 2 0\n1 -2 0\n-1 2 0\n-1 -2 0\no 1 2 0\n')
        assert verify(source,cert,20)==('UNSAT','RUP+SYMBOLIC')
        for text in ['p cnf 1 2\n1 0\n','p cnf 1 1\n2 0\n','p cnf 1 1\n1 x 0\n','p cnf 1 1\n1\n']:
            source.write_text(text);cert.unlink(missing_ok=True)
            p=subprocess.run([ROOT/'bin/drnas-core',source,cert,'.2'],capture_output=True,timeout=.4)
            assert p.returncode==2 and not cert.exists();tamper+=1
        write(source,1,[(1,)])
        before=source.read_bytes()
        p=subprocess.run([ROOT/'bin/drnas-core',source,source,'.2'],capture_output=True,timeout=.4)
        assert p.returncode==2 and source.read_bytes()==before;tamper+=1
        factor_dir=d/'factors';factor_dir.mkdir()
        subprocess.run([ROOT/'bin/factor-test',factor_dir],check=True,capture_output=True,timeout=20)
        factor_cases=factor_lines=0
        for source in factor_dir.glob('*.cnf'):
            proof=source.with_suffix('.drup');lines=proof.read_text().splitlines()
            if lines:
                p=subprocess.run([ROOT/'bin/check-rup',source,proof,'--prefix',proof],capture_output=True,timeout=6)
                assert p.returncode==0,p.stderr
            factor_cases+=1;factor_lines+=len(lines)
        assert factor_cases==81
    print(json.dumps(dict(truth_table_formulas=len(cases),accepted_runs=checked,certificates=terminal,
                          gf3_signed_permutations=16,negative_tests=tamper,factor_cases=factor_cases,
                          factor_rup_lines=factor_lines,word_lift_forms=2)))


if __name__=='__main__':main()
