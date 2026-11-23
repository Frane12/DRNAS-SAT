#!/usr/bin/env python3
"""Auditable same-DIMACS pilot: Yosys CRC miter -> R28/Kissat/CaDiCaL/CMS.

Original upstream R28 source is compiled separately, unmodified.
R28 does NOT currently discharge a mixed XOR + mismatch-OR miter by itself;
the classification and any Kissat fallback are recorded explicitly.
"""
from __future__ import annotations
import argparse, hashlib, json, os, platform, re, shutil, subprocess, time
from pathlib import Path

def textsha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dimacs_meta(p):
    for line in p.open():
        if line.startswith('p cnf '):
            z=line.split()
            return {'vars':int(z[2]),'clauses':int(z[3])}
    raise ValueError('DIMACS header not found')

def one_command(cmd,cpu,timeout_s):
    command=['taskset','-c',str(cpu)]+[str(x) for x in cmd]
    t=time.perf_counter()
    try:
        p=subprocess.run(command,text=True,capture_output=True,timeout=timeout_s,check=False)
        out=p.stdout+'\n'+p.stderr
        return {'seconds':time.perf_counter()-t,'return_code':p.returncode,
                'timeout':False,'output':out[-150000:]}
    except subprocess.TimeoutExpired as e:
        return {'seconds':time.perf_counter()-t,'return_code':None,
                'timeout':True,'output':(e.stdout or b'').decode(errors='replace')[-150000:]
                if isinstance(e.stdout,bytes) else str(e.stdout or '')[-150000:]}

def sat_status(out,rc,timeout=False):
    if timeout:return 'TIMEOUT'
    m=re.findall(r'(?m)^s\s+(SATISFIABLE|UNSATISFIABLE|UNKNOWN)\b',out)
    if m:return {'SATISFIABLE':'SAT','UNSATISFIABLE':'UNSAT','UNKNOWN':'UNKNOWN'}[m[-1]]
    if rc==10:return 'SAT'
    if rc==20:return 'UNSAT'
    return 'ERROR'

def check_sat_model(cnf,stdout):
    pairs=[]
    for line in stdout.splitlines():
        if line.startswith('v '):
            pairs.extend(int(q) for q in line[2:].split() if q!='0')
    if not pairs:return None
    assignment={abs(x):x>0 for x in pairs}
    num=0
    for line in cnf.open():
        if line[0:1] in ('c','p','%') or not line.strip():continue
        literals=[int(t) for t in line.split() if t!='0']
        if any(abs(x) not in assignment for x in literals):return False
        if not any(assignment[abs(x)]==(x>0) for x in literals):return False
        num+=1
    return num>0

def pilot(a):
    out=a.out
    out.mkdir(parents=True,exist_ok=True)
    cpu=sorted(os.sched_getaffinity(0))[0]
    rtl=json.loads(a.manifest.read_text())
    versions={}
    for cmd in ('yosys','kissat','cadical','cryptominisat5'):
        versions[cmd]=shutil.which(cmd)
    versions['r28']=str(a.r28) if a.r28.exists() else None
    versions['r28_mix2']=str(a.mix2) if a.mix2.exists() else None
    result={'kind':'real Yosys exported CRC32 equivalence miter',
            'os':platform.platform(),'cpu_first_allowed':cpu,
            'time_cap_s':a.time_cap,'versions':versions,'cases':[]}
    for case in rtl:
        name=case['case']
        cnf=out/(name+'.cnf')
        ys=f'read_verilog {case["rtl"]}; hierarchy -check -top miter; proc; flatten; opt; sat -timeout 1 -set mismatch 1 -dump_cnf {cnf}'
        synth=one_command(['yosys','-p',ys],cpu,120)
        (out/f'{name}.yosys.log').write_text(synth['output'])
        record={'case':name,'fault':case['fault'],'nbytes':case['nbytes'],
                'yosys':{'seconds':synth['seconds'],'return_code':synth['return_code'],
                          'timeout':synth['timeout']}}
        if not cnf.exists() or cnf.stat().st_size==0:
            record['error']='Yosys did not export nonempty CNF'
            result['cases'].append(record)
            (out/'results.json').write_text(json.dumps(result,indent=2))
            continue
        record['dimacs']={**dimacs_meta(cnf),'sha256':textsha(cnf),'size_bytes':cnf.stat().st_size}
        classify=one_command([a.r28,cnf,a.kissat,'--classify-only'],cpu,15)
        route=re.search(r'(?m)^c R28_ROUTE\s+(.+)$',classify['output'])
        record['r28_classify']={'route':route.group(1) if route else None,
                                 'seconds':classify['seconds'],'return_code':classify['return_code']}
        candidates=[('R28-MIX2',[a.mix2,cnf]),('R28+Kissat',[a.r28,cnf,a.kissat]),('Kissat',[a.kissat,cnf])]
        if shutil.which('cadical'):
            candidates.append(('CaDiCaL',['cadical',cnf]))
        if shutil.which('cryptominisat5'):
            candidates.append(('CryptoMiniSat',['cryptominisat5',cnf]))
        record['solvers']={}
        for solver,command in candidates:
            trial=one_command(command,cpu,a.time_cap)
            status=sat_status(trial['output'],trial['return_code'],trial['timeout'])
            check=check_sat_model(cnf,trial['output']) if status=='SAT' else None
            record['solvers'][solver]={'status':status,'seconds':round(trial['seconds'],6),
                'return_code':trial['return_code'],'sat_witness_checked':check,
                'timed_out':trial['timeout']}
            if solver == 'R28-MIX2' and status == 'UNSAT':
                # Compare the *original source CNF* with an independently implemented
                # project-level checker. DO NOT describe this as DRAT/LRAT/VeriPB.
                verify=one_command(['python3',a.checker,cnf,'--expected','UNSAT'],cpu,120)
                (out/f'{name}.mix2-source-check.json').write_text(verify['output'])
                ok=(verify['return_code']==0 and not verify['timeout'])
                record['solvers'][solver]['source_project_checked']=ok
                record['solvers'][solver]['independent_standard_certificate']=False
                if not ok:
                    raise RuntimeError('Source-checker failed on '+name)
            (out/f'{name}.{solver.replace("+","_")}.log').write_text(trial['output'])
            print(name,solver,status,round(trial['seconds'],4),'s',flush=True)
        result['cases'].append(record)
        (out/'results.json').write_text(json.dumps(result,indent=2))
    report=[
        '# DRNAS R28-MIX2 – practical CRC-32 Yosys CNF experiment',
        '',
        'Uses independently generated RTL and **Yosys -dump_cnf** (not manually built XOR CNF).',
        'The upstream R28 C++ is built unmodified from the pinned historic source.',
        'R28-MIX2 is a separate experimental native C++ engine (gate-structure extension).',
        'UNSAT from MIX2 must pass an independent project-level CNF source checker; it is not a DRAT/LRAT/VeriPB proof.',
        'All timings are one-run pilot wall-times pinned to the same logical CPU. ',
        '**R28+Kissat means R28 can invoke Kissat as fallback.**',
        '',
        '| CNF | Vars | Clauses | Original R28 route | MIX2 (+ project check) | R28+Kissat | Kissat | CaDiCaL | CryptoMiniSat |',
        '|---|---:|---:|---|---|---|---|---|---|'
    ]
    def fmt(one):
        if not one:return 'n/a'
        return f"{one['status']} {one['seconds']:.3f}s"
    for r in result['cases']:
        if 'dimacs' not in r:
            report.append('| '+r['case']+' | Yosys CNF not exported | | | | | | | | |')
            continue
        ss=r['solvers']
        route=r['r28_classify']['route'] or 'not classified'
        report.append('| '+r['case']+' | '+str(r['dimacs']['vars'])+' | '
          +str(r['dimacs']['clauses'])+' | '+route.replace('|','/')+' | '
          +fmt(ss.get('R28-MIX2'))+(' [source-checked]' if ss.get('R28-MIX2',{}).get('source_project_checked') else '')+' | '+fmt(ss.get('R28+Kissat'))+' | '+fmt(ss.get('Kissat'))+' | '
          +fmt(ss.get('CaDiCaL'))+' | '+fmt(ss.get('CryptoMiniSat'))+' |')
    report.extend(['','Each DIMACS SHA-256 is preserved in results.json.',
        'The MIX2 source checker is independent but project-specific; no standard UNSAT certificate is generated by this pilot.',
        'Any timeout is censored and is not a measured completed-run ratio.',
        'A pure-XOR success on prior synthetic CRC CNFs must not be conflated with this Yosys-CNF benchmark.'])
    (out/'REPORT.md').write_text('\n'.join(report)+'\n')
    print('RESULTS',out/'results.json',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--r28',type=Path,required=True)
    ap.add_argument('--mix2',type=Path,required=True)
    ap.add_argument('--checker',type=Path,required=True)
    ap.add_argument('--kissat',type=Path,required=True)
    ap.add_argument('--time-cap',type=int,default=12)
    pilot(ap.parse_args())
