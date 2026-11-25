#pragma once
#include "formula.hpp"
#include <random>
namespace toolbox {
// Flip one variable from a violated residual clause. Keep satisfying-literal counts
// and a swap/pop list of bad clauses, so each flip touches only occurrences of v.
inline bool repair(int n,const Clauses& cs,Model& m,Time until,uint64_t& steps) {
    if (cs.empty()) return true;
    std::vector<std::vector<int>> occ(2*n);
    for (int i=0;i<int(cs.size());++i) {
        if (cs[i].empty()) return false;
        for (int l:cs[i]) occ[index_of(l)].push_back(i);
    }
    std::mt19937 rng(20310719);
    auto pick=[&](size_t size) {return std::uniform_int_distribution<size_t>(0,size-1)(rng);};
    std::vector<int> counts(cs.size()), slot(cs.size()), bad;
    auto set_bad=[&](int i){slot[i]=int(bad.size());bad.push_back(i);};
    auto clear_bad=[&](int i){int last=bad.back();bad[slot[i]]=last;slot[last]=slot[i];bad.pop_back();};
    const int64_t moves=std::min<int64_t>(250000,std::max<int64_t>(3000,120LL*n));
    for (int restart=0;restart<36 && Clock::now()<until;++restart) {
        if (restart) for (int v=1;v<=n;++v) m[v]=rng()&1u;
        std::fill(counts.begin(),counts.end(),0); bad.clear();
        for (int i=0;i<int(cs.size());++i) {
            for (int l:cs[i]) counts[i]+=value(m,l)==1;
            if (!counts[i]) set_bad(i);
        }
        for (int64_t step=0;step<moves;++step) {
            if (bad.empty()) return true;
            if ((step&127)==0 && Clock::now()>=until) return false;
            const auto& c=cs[bad[pick(bad.size())]];
            int chosen=0, best=std::numeric_limits<int>::max(); size_t ties=0;
            if ((rng()%100)<12) chosen=c[pick(c.size())];
            else for (int l:c) {
                int loss=0;
                for (int i:occ[index_of(-l)]) if (counts[i]==1 && ++loss>best) break;
                if (loss<best) { best=loss; ties=1; chosen=l; }
                else if (loss==best && pick(++ties)==0) chosen=l;
            }
            m[std::abs(chosen)]=chosen>0;
            for (int i:occ[index_of(chosen)]) if (counts[i]++==0) clear_bad(i);
            for (int i:occ[index_of(-chosen)]) if (--counts[i]==0) set_bad(i);
            ++steps;
        }
        if (bad.empty()) return true;
    }
    return false;
}
} // namespace toolbox
