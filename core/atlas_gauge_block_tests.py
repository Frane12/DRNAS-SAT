"""YM17: independent path audit, actual pinned ATLAS, native CORE gap."""
from pathlib import Path
from tempfile import TemporaryDirectory
from fractions import Fraction as Q
import json,sys
from atlas_gauge_block import solve
from gauge_block_verify import verify_block

def subdivide(edges,loops,n,k):
    paths={};new=[]
    for a,b in edges:
        p=[a]+list(range(n,n+k-1))+[b];n+=k-1
        paths[a,b]=p;paths[b,a]=p[::-1];new.extend(zip(p,p[1:]))
    expanded=[]
    for coupling,v in loops:
        path=[]
        for a,b in zip(v,v[1:]+v[:1]):path+=paths[a,b][:-1]
        expanded.append((coupling,path))
    return n,new,expanded

def main(atlas):
    # Two plaquettes sharing an edge. Subdivision changes the model
    # unless electric weights are added during blocking.
    e=[(0,1),(1,2),(2,3),(3,0),(1,4),(4,5),(5,2)]
    p=[(Q(1,4),[0,1,2,3]),(Q(1,4),[1,4,5,2])]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for k in (2,3,4):
            n,edges,loops=subdivide(e,p,6,k)
            r=solve(n,edges,loops,Q(1),Q(1),atlas,root/str(k))
            assert r['status']=='PROVED',r
            b=r['blocking'];assert b['weighted_girth']==4*k and b['remaining_edges']<b['original_edges'],r
            assert all(x['model_verified'] for x in r['atlas_plans'])
            cert=root/str(k)/'block.json';src=root/str(k)/'graph.json'
            old=cert.read_text();z=json.loads(old);z['edges'][0][2]+=1;cert.write_text(json.dumps(z))
            try:verify_block(src,cert)
            except ValueError:pass
            else:raise AssertionError('tampered weight accepted')
            cert.write_text(old)
            print('YM17_ROW '+json.dumps(dict(id=k,**r)),flush=True)
        n,edges,loops=subdivide(e,p,6,2)
        r=solve(n,edges,loops,Q(1),Q(100),atlas,root/'negative')
        assert r['status']=='UNKNOWN' and r['blocking']['status']=='BLOCK_EQUIVALENCE_CHECKED',r
        print('YM17_SUMMARY '+json.dumps(dict(cases=4,positive=3,negative=1,continuum=False)),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
