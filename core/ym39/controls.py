"""Recompute every reported screen; exercise distinguishable counterexamples."""
import json
import numpy as np
import basis
import fresh
import spectrum

def discrete_examples():
    # Every finite approximation has finitely many positive, separated levels.
    results = []
    for count in (4, 16, 64, 256):
        relative_levels = np.arange(1, count + 1) / count
        row = {'count': count}
        for threshold in (0, 1):
            energies = np.r_[0, threshold + relative_levels]
            shifted = energies + 17
            assert np.array_equal(energies - energies[0], shifted - shifted[0])
            row[f'first_above_{threshold}'] = float(energies[1])
        results.append(row)
    return results


def tests():
    line=spectrum.kernel(.3)[:,0]
    hard=spectrum.kernel([1.,1.5,2.])
    obs=.04*line+.96*hard[:,0]
    d,lb,_=spectrum.distance(obs,1000*np.eye(5),hard,line,.04)
    assert d<1e-9 and lb<=d+1e-12
    d,lb,_=spectrum.distance(line,1000*np.eye(5),hard,line,0)
    assert d>=lb-1e-6 and lb>1000
    for delta in (.1,.3,1.):
        assert np.all(spectrum.kernel(delta)>=spectrum.kernel(delta+.1))
    profile=[spectrum.test(n) for n in (4,8,16)]
    assert all(x['profiles']['massless']['0.0']['screen']=='compatible' and
               x['profiles']['massless']['0.01']['screen']=='compatible' for x in profile)
    new={str(b):{str(n):fresh.analyze(b,n) for n in (8,16)} for b in (235,245)}
    new['extension']={'16':fresh.analyze('extend',16)}
    rest_models={}
    for b,n in ((235,8),(235,16),(245,8),(245,16),('extend',16)):
        blocks=fresh.ensemble(b,n,64).reshape(-1,64);k=len(blocks);mean=blocks.mean(axis=0)
        part={}
        for ch in (2,3):
            def normed(x):
                c=fresh.corr(x,ch)
                return c[...,1:6]/c[...,:1]
            obs=normed(mean)
            loo=normed((k*mean-blocks)/(k-1))
            cov=(k-1)*np.cov(loo,rowvar=False,ddof=0)
            W=np.linalg.inv(np.linalg.cholesky(cov))
            hard=spectrum.kernel(spectrum.MASSES,24)
            ix=np.arange(1,49)
            weight=2.**-ix
            weight[-1]+=2.**-48
            tower=spectrum.kernel(1/ix,24)@weight
            modes={}
            for mode,shape in [('energy_0.1',spectrum.kernel(.1,24)[:,0]),('tower',tower),
                               ('dense_dyadic',spectrum.dense_shape(0,24))]:
                modes[mode]={str(f):spectrum.distance(obs,W,hard,shape,f)[0]
                             for f in (0.,.01,.05,.10,.25)}
            part[fresh.NAMES[ch]]=modes
        rest_models[f"{b}_{n}"]=part
    combo=basis.run()
    return dict(discrete_examples=discrete_examples(),spectral=profile,new_ensembles=new,variational=combo,rest_profiles_D2=rest_models)

def verify_recorded(result):
    """Verify reported fit decisions and energies across numerical backends."""
    reference = json.loads((fresh.ROOT / 'results.json').read_text())
    for actual, expected in zip(result['spectral'], reference['spectral'], strict=True):
        assert actual['L'] == expected['L']
        np.testing.assert_allclose(actual['massless_fraction_positive_upper'],
                                   expected['massless_fraction_positive_upper'])
        for label, fits in expected['profiles'].items():
            for fraction, fit in fits.items():
                current = actual['profiles'][label][fraction]
                assert current['screen'] == fit['screen']
                np.testing.assert_allclose(current['D2'], fit['D2'], rtol=2e-4, atol=2e-5)
    for beta, sizes in result['new_ensembles'].items():
        for size, channels in sizes.items():
            for ch, actual in channels.items():
                expected = reference['new_ensembles'][beta][size][ch]
                assert actual['status'] == expected['status']
                if actual['status'] == 'PROVISIONAL':
                    np.testing.assert_allclose(actual['block64']['energy'], expected['block64']['energy'])
    for key, blocks in result['variational'].items():
        for size, folds in blocks.items():
            for actual, expected in zip(folds, reference['variational'][key][str(size)], strict=True):
                assert actual['screen'] == expected['screen']
                if actual['screen']:
                    np.testing.assert_allclose(actual['heldout_energy'], expected['heldout_energy'])


if __name__=='__main__':
    import sys
    result=tests()
    if '--json' in sys.argv:
        print(json.dumps(result,indent=2,allow_nan=False))
    else:
        verify_recorded(result)
        for entry in result['spectral']:
            print('YM39 SPECTRUM', entry['L'],entry['massless_fraction_positive_upper'])
        for b,t in result['new_ensembles'].items():
            for n,probes in t.items():
                print('YM39 PROBES', b,n, [k for k,v in probes.items() if v['status']=='PROVISIONAL'])
        for k,v in result['variational'].items():print('YM39 BASIS',k,v[32])
        print('YM39 stress controls passed')
