"""Public command: bounded native solve followed by independent evidence checking."""
import argparse
import json
import pathlib
import subprocess
import sys
import time
import os
import fcntl
import tempfile
import re
import rule_utility

ROOT = pathlib.Path(__file__).resolve().parent


def store_rules(path, rules):
    # Local opt-in memory; never trust it as evidence. Atomic update and lock
    # permit separate invocations to merge discoveries.
    path = pathlib.Path(path)
    valid = lambda x: re.fullmatch(r'A(?:[2-9]|10)|C[3-8][+-]', x) is not None
    new = {r for r in rules if isinstance(r,str) and valid(r)}
    if not new: return 0
    with open(str(path)+'.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        old=set()
        if path.exists():
            if path.stat().st_size>4096: raise ValueError('memory size')
            lines=path.read_text().splitlines()
            if not lines or lines[0]!='drnas-rule-memory-v1' or not all(valid(x) for x in lines[1:]):
                raise ValueError('invalid memory')
            old=set(lines[1:])
        with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False) as tmp:
            tmp.write('drnas-rule-memory-v1\n'+'\n'.join(sorted(old|new))+'\n')
            temp=tmp.name
        try: os.replace(temp,path)
        finally:
            if os.path.exists(temp): os.unlink(temp)
        return len(new-old)


def run(source, evidence, seconds=5, mode='default', audit_seconds=5, rule_memory=None, rule_feedback=False):
    started = time.monotonic()
    result = dict(status='UNKNOWN', mode=mode, budget_s=seconds)
    env=os.environ.copy()
    env.pop('DRNAS_CORE_RULE_MEMORY',None)
    env.pop('DRNAS_CORE_RULE_SELECT',None)
    selected=ctx=utility=None
    if rule_feedback and rule_memory is None:
        return dict(status='ERROR',error='rule feedback requires rule memory')
    if rule_memory is not None:
        memory=pathlib.Path(rule_memory).resolve()
        protected=[pathlib.Path(p).resolve() for p in (source,evidence)]
        if memory in protected or pathlib.Path(str(memory)+'.lock').resolve() in protected:
            return dict(status='ERROR',error='memory path conflicts with input/evidence')
        for p in protected:
            if memory.exists() and p.exists() and memory.samefile(p):
                return dict(status='ERROR',error='memory aliases input/evidence')
        env['DRNAS_CORE_RULE_MEMORY']=str(memory)
        if rule_feedback:
            utility=pathlib.Path(str(memory)+'.utility.json').resolve()
            lock=pathlib.Path(str(utility)+'.lock').resolve()
            for p in protected+[memory]:
                if p in (utility,lock) or any(q.exists() and p.exists() and q.samefile(p) for q in (utility,lock)):
                    return dict(status='ERROR',error='utility path conflicts with input/evidence/memory')
            try:
                ctx=rule_utility.context(source)
                if ctx:
                    selected=rule_utility.choose(rule_utility.read_rules(memory),rule_utility.load(utility).get(ctx,{}))
                    if selected: env['DRNAS_CORE_RULE_SELECT']=selected
                result['rule_feedback']=dict(context=ctx,selected=selected)
            except (OSError,ValueError) as error:
                result['rule_feedback_error']=str(error)
                # Invalid statistics do not affect certificate checking.
                selected=None
    def feedback():
        if not selected:return
        t=result.get('telemetry',{})
        if t.get('memory_attempts')!=1:return
        matched=t.get('memory_matches',0)>0
        proved=(result.get('status')=='PROVED' and t.get('memory_proved') is True)
        try:
            result['rule_feedback']['observation']=rule_utility.observe(utility,ctx,selected,matched,proved,float(t['memory_s']))
        except (OSError,ValueError,KeyError) as error:result['rule_feedback_error']=str(error)
    try:
        proc = subprocess.run([ROOT / 'bin/drnas-core', source, evidence, str(seconds), mode],
                              capture_output=True, text=True, timeout=seconds + .1, env=env)
    except subprocess.TimeoutExpired:
        result.update(status='TIMEOUT', solve_s=time.monotonic()-started)
        return result
    result['solve_s'] = time.monotonic() - started
    result['returncode'] = proc.returncode
    for line in proc.stdout.splitlines():
        if line.startswith('c {'):
            result['telemetry'] = json.loads(line[2:])
    if result['solve_s'] > seconds + .05:
        result['status'] = 'TIMEOUT'
        return result
    if proc.returncode not in (0, 10, 20, 30, 31):
        result.update(status='ERROR', error=proc.stderr.strip())
        return result
    if not proc.returncode:
        feedback()
        return result
    started = time.monotonic()
    try:
        command = ([sys.executable, ROOT / 'operator_verify.py', source, evidence]
                   if proc.returncode == 30 else
                   [sys.executable, ROOT / 'symbolic_verify.py', source, evidence]
                   if proc.returncode == 31 else
                   [sys.executable, ROOT / 'verify.py', source, evidence, str(proc.returncode), '--seconds', str(audit_seconds)])
        audit = subprocess.run(command,
                               capture_output=True, text=True, timeout=audit_seconds + .1)
        result.update(json.loads(audit.stdout))
    except subprocess.TimeoutExpired:
        result['status'] = 'AUDIT_LIMIT'
    except Exception as error:
        result.update(status='REJECTED', error=str(error))
    result['audit_s'] = time.monotonic() - started
    if rule_memory is not None and proc.returncode==31 and result.get('status')=='PROVED' and audit.returncode==0:
        try: result['rules_added']=store_rules(memory,result.get('learned_rules',[]))
        except (OSError,ValueError) as error: result['memory_error']=str(error)
    feedback()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('evidence', help='new evidence path; existing files are protected')
    parser.add_argument('--seconds', type=float, default=5)
    parser.add_argument('--mode', choices=['default', 'memory', 'no-share', 'freedom'], default='default')
    parser.add_argument('--audit-seconds', type=float, default=5)
    parser.add_argument('--rule-memory', help='optional persistent symbolic rule file')
    parser.add_argument('--rule-feedback', action='store_true', help='learn contextual rule scheduling utility')
    args = parser.parse_args()
    answer = run(args.input, args.evidence, args.seconds, args.mode, args.audit_seconds, args.rule_memory, args.rule_feedback)
    print(json.dumps(answer, ensure_ascii=False))
    sys.exit(0 if answer['status'] in ('SAT', 'UNSAT', 'PROVED', 'THEOREM_APPLIED', 'UNKNOWN', 'TIMEOUT', 'AUDIT_LIMIT') else 1)
