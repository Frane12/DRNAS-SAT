#pragma once
#include "formula.hpp"
#include <array>

namespace toolbox {
struct CaseStats { int single=0, joint=0, covers=0, facts=0, composed=0, implications=0; };
// TOOLBOX18 short resolvents, indexed by opposite literals. Newly accepted
// clauses reenter the next round, including two-pivot compositions from TOOLBOX19.
inline int compose_round(int n,Clauses& cs,Proof& proof,Time until,CaseStats& stats) {
    std::vector<std::vector<int>> index(2*n);
    for (int i=0;i<int(cs.size());++i) if (cs[i].size()<=4)
        for (int l:cs[i]) index[index_of(l)].push_back(i);
    std::set<Clause> known(cs.begin(),cs.end()), found;
    int pairs=0;
    for (int v=1;v<=n && pairs<24000 && Clock::now()<until;++v) {
        for (int i:index[index_of(v)]) {
            for (int j:index[index_of(-v)]) {
                if (++pairs>24000) break;
                const auto& a=cs[i]; const auto& b=cs[j]; Clause r;
                for (int l:a) if (l!=v) r.push_back(l);
                for (int l:b) if (l!=-v) r.push_back(l);
                if (!normalize(r) || r.size()>3 || known.count(r)) continue;
                found.insert(std::move(r));
            }
            if (pairs>=24000) break;
        }
    }
    Clauses candidates(found.begin(),found.end());
    std::stable_sort(candidates.begin(),candidates.end(),[](const Clause& a,const Clause& b){return a.size()<b.size();});
    int added=0;
    for (const auto& c:candidates) {
        bool subsumed=false;
        for (size_t j=0;j<c.size() && !subsumed;++j) {
            Clause shorter=c; shorter.erase(shorter.begin()+j);
            subsumed=known.count(shorter) || known.count(Clause{c[j]});
        }
        if (subsumed) continue;
        cs.push_back(c); known.insert(c); proof.add(c); ++added; ++stats.composed;
        if (added==96 || c.empty()) break;
    }
    return added;
}
struct Cover { Clause residual; size_t source_width; };
inline bool cover_order(const Cover& a,const Cover& b) {
    if (a.residual.size()!=b.residual.size()) return a.residual.size()<b.residual.size();
    if (a.source_width!=b.source_width) return a.source_width>b.source_width;
    return a.residual<b.residual;
}
// The disjunction is shortened by UP under a. Under each remaining b, UP must
// imply t or refute the branch. The auxiliary DRUP clauses implement the case split.
inline int guarded_round(int n, Clauses& cs, Proof& proof, Time until, CaseStats& stats) {
    Propagator p(n,cs);
    std::vector<int> freq(2*n);
    std::vector<std::vector<int>> occurs(2*n);
    for (int i=0;i<int(cs.size());++i) for (int l:cs[i]) {
        ++freq[index_of(l)];
        if (cs[i].size()>=2 && cs[i].size()<=8) occurs[index_of(l)].push_back(i);
    }
    Clause guards;
    for (int v=1;v<=n;++v) for (int l:{v,-v})
        if (freq[index_of(-l)]) guards.push_back(l);
    std::stable_sort(guards.begin(),guards.end(),[&](int a,int b){return freq[index_of(-a)]>freq[index_of(-b)];});
    std::set<Clause> known(cs.begin(),cs.end());
    Clauses facts;
    auto fresh=[&](Clause c) {
        return normalize(c) && !known.count(c) &&
            std::none_of(c.begin(),c.end(),[&](int l){return known.count(Clause{l});});
    };
    auto record=[&](Clause c) {
        normalize(c); proof.add(c); known.insert(c); facts.push_back(std::move(c)); ++stats.facts;
    };
    int joint=0, singles=0, implications=0;
    std::vector<int> seen_clause(cs.size(),0); // deduplicate only clauses touched by a probe
    for (int a:guards) {
        if (joint>=600 || singles>=384 || facts.size()>=64 || Clock::now()>=until) break;
        ++stats.single; ++singles;
        if (!p.consistent({a})) { if (fresh({-a})) record({-a}); continue; }
        for (int t:p.trail) {
            if (implications>=24) break;
            if (t!=a && fresh({-a,t})) {record({-a,t}); ++implications; ++stats.implications;}
        }
        // A short cover which actually lost a false literal links this guard to its alternatives.
        std::vector<Cover> candidates;
        const int stamp=singles;
        for (int forced:p.trail) {
            for (int i:occurs[index_of(-forced)]) {
                if (seen_clause[i]==stamp) continue;
                seen_clause[i]=stamp; Clause open; bool sat=false;
                for (int l:cs[i]) {
                    if (value(p.state,l)==1) {sat=true;break;}
                    if (value(p.state,l)<0) open.push_back(l);
                }
                if (!sat && (open.size()==2 || open.size()==3)) candidates.push_back({std::move(open),cs[i].size()});
            }
        }
        std::sort(candidates.begin(),candidates.end(),cover_order);
        std::set<Clause> tried;
        Clause implied=p.trail;
        std::sort(implied.begin(),implied.end());
        for (const auto& cover:candidates) {
            const auto& bs=cover.residual;
            if (tried.size()>=4 || joint+int(bs.size())>600 || facts.size()>=64 || Clock::now()>=until) break;
            if (!tried.insert(bs).second) continue;
            ++stats.covers;
            std::vector<int> dead; Clause common; bool any_live=false;
            for (int b:bs) {
                ++stats.joint; ++joint;
                if (!p.consistent({a,b})) {dead.push_back(b);continue;}
                if (!any_live) {common=p.trail;any_live=true;}
                else std::erase_if(common,[&](int t){return value(p.state,t)!=1;});
            }
            if (!any_live) common={0};
            bool wrote_cover=false;
            for (int t:common) {
                if (facts.size()>=64) break;
                if (t && (std::binary_search(implied.begin(),implied.end(),t) ||
                          std::find(bs.begin(),bs.end(),t)!=bs.end())) continue;
                Clause result{-a}; if (t) result.push_back(t);
                if (!fresh(result)) continue;
                if (!wrote_cover) { Clause c=bs; c.push_back(-a); proof.add(c); wrote_cover=true; }
                for (int b:bs) {
                    Clause c{-a,-b};
                    if (std::find(dead.begin(),dead.end(),b)==dead.end()) c.push_back(t);
                    proof.add(c);
                }
                record(result);
            }
        }
    }
    cs.insert(cs.end(),facts.begin(),facts.end());
    return int(facts.size());
}
} // namespace toolbox
