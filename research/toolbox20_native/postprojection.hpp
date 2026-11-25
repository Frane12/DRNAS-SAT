#pragma once
#include "formula.hpp"
#include <array>

namespace toolbox {
struct PostStats {
    int singles=0, units=0, tree_probes=0, nodes=0;
    double milliseconds=0;
};

// Only implications common to both polarities, or failed assumptions, become
// residual units. All clauses emitted here are RUP in the existing proof.
inline bool probe_units(int n, Clauses& residual, Proof& proof, Time until, PostStats& stats) {
    std::vector<std::array<int64_t,2>> frequency(n+1);
    for (const auto& c:residual) for (int l:c)
        frequency[std::abs(l)][l<0] += c.size()<=2 ? 8 : c.size()==3 ? 3 : 1;
    Clause order;
    for (int v=1;v<=n;++v) if (frequency[v][0] && frequency[v][1]) order.push_back(v);
    auto score=[&](int v){return std::min(frequency[v][0],frequency[v][1]);};
    std::stable_sort(order.begin(),order.end(),[&](int a,int b){return score(a)>score(b);});
    Model known(n+1,-1);
    auto record=[&](int l){
        if (value(known,l)==1) return true;
        residual.push_back({l});
        proof.add({l});
        ++stats.units;
        if (value(known,l)==0) return false;
        known[std::abs(l)]=l>0;
        return true;
    };
    for (int round=0;round<4 && Clock::now()<until;++round) {
        Propagator p(n,residual);
        if (!p.consistent()) return true;
        for (int l:p.trail) known[std::abs(l)]=l>0;
        const int before=stats.units;
        for (int v:order) {
            if (known[v]>=0) continue;
            if (stats.singles+2>256 || stats.units>=64 || Clock::now()>=until) break;
            stats.singles+=2;
            bool positive=p.consistent({v});
            Clause first=p.trail;
            bool negative=p.consistent({-v});
            if (!positive && !record(-v)) return true;
            if (!negative && !record(v)) return true;
            if (positive && negative) for (int l:first) {
                if (value(known,l)==1 || value(p.state,l)!=1) continue;
                proof.add({-v,l});
                proof.add({v,l});
                if (!record(l)) return true;
                if (stats.units>=64) break;
            }
            if (stats.units-before>=8) break;
        }
        if (stats.units==before) break;
    }
    return false;
}

class ResidualTree {
    Propagator prop;
    const Clauses& clauses;
    int n;
    Proof& proof;
    Time until;
    PostStats& stats;
    bool allowed() const { return stats.tree_probes<512 && Clock::now()<until; }
    bool consistent(const Clause& path) {
        ++stats.tree_probes;
        return prop.consistent(std::span<const int>(path));
    }
    void block(const Clause& path) {
        Clause lemma;
        for (int l:path) lemma.push_back(-l);
        proof.add(lemma);
    }
    Clause candidates() const {
        std::vector<std::array<int64_t,2>> frequency(n+1);
        Clause active;
        for (const auto& c:clauses) {
            int open=0;
            bool sat=false;
            for (int l:c) {
                int val=value(prop.state,l);
                if (val==1) {sat=true;break;}
                if (val<0 && ++open>6) break;
            }
            if (sat || open>6) continue;
            for (int l:c) if (value(prop.state,l)<0) {
                auto& pair=frequency[std::abs(l)];
                if (!pair[0] && !pair[1]) active.push_back(std::abs(l));
                pair[l<0]+=1<<(6-open);
            }
        }
        auto score=[&](int v){return (1.0+frequency[v][0])*(1.0+frequency[v][1]);};
        auto end=active.begin()+std::min<size_t>(4,active.size());
        std::partial_sort(active.begin(),end,active.end(),[&](int a,int b){
            return score(a)!=score(b) ? score(a)>score(b) : a<b;
        });
        active.erase(end,active.end());
        return active;
    }
public:
    ResidualTree(int vars,const Clauses& cs,Proof& pr,Time limit,PostStats& s):
        prop(vars,cs),clauses(cs),n(vars),proof(pr),until(limit),stats(s) {}
    // Only two refuted children can refute a parent. Unfinished paths return open.
    bool refute(Clause& path) {
        if (!allowed()) return false;
        ++stats.nodes;
        if (!consistent(path)) {block(path);return true;}
        if (path.size()>=6) return false;
        int best=0;
        uint64_t best_gain=0;
        for (int v:candidates()) {
            int dead=0, live_sign=0;
            uint64_t gain=1;
            for (int l:{v,-v}) {
                if (!allowed()) return false;
                path.push_back(l);
                if (consistent(path)) {live_sign=l;gain*=prop.trail.size();}
                else {++dead;block(path);}
                path.pop_back();
            }
            if (dead==2) {block(path);return true;}
            if (dead==1) {
                path.push_back(live_sign);
                bool closed=refute(path);
                path.pop_back();
                if (closed) block(path);
                return closed;
            }
            if (!best || gain>best_gain) {best=v;best_gain=gain;}
        }
        if (!best) return false;
        for (int l:{best,-best}) {
            path.push_back(l);
            bool closed=refute(path);
            path.pop_back();
            if (!closed) return false;
        }
        block(path);
        return true;
    }
};

inline bool postprojection(int n,Clauses& residual,Proof& proof,Time deadline,PostStats& stats) {
    auto start=Clock::now();
    if (start>=deadline) return false;
    const auto original_size=residual.size();
    bool closed=probe_units(n,residual,proof,std::min(deadline,after(.020)),stats);
    if (closed) proof.add({});
    else if (Clock::now()<deadline) {
        auto until=std::min(deadline,after(.025));
        ResidualTree tree(n,residual,proof,until,stats);
        Clause path;
        closed=tree.refute(path);
    }
    residual.resize(original_size);
    stats.milliseconds=std::chrono::duration<double,std::milli>(Clock::now()-start).count();
    return closed;
}
} // namespace toolbox
