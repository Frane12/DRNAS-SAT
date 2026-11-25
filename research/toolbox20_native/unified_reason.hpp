#pragma once
#include "cases.hpp"
#include <map>
#include <tuple>

namespace toolbox {
struct UnifiedStats {
    int epochs=0, probes=0, probe_facts=0, pairs=0, affine=0, nonlinear=0,
        relation_facts=0, proof_lines=0, revisits=0;
};
using Mask=uint64_t;
struct Rel { Clause vars; Mask forbidden=0; };
using RKey=std::pair<Clause,Mask>;
struct UnifiedMemory {
    std::set<std::pair<RKey,RKey>> attempted;
    int probe_offset=0;
};
inline Mask bit(unsigned m) { return Mask(1)<<m; }
inline bool parity_relation(const Rel& r) {
    if(r.vars.empty()) return false;
    Mask even=0,odd=0;
    for(unsigned m=0;m<(1u<<r.vars.size());++m)
        (__builtin_parity(m)?odd:even)|=bit(m);
    return (r.forbidden==even || r.forbidden==odd);
}
inline Clause blocker(const Clause& vs,unsigned m) {
    Clause c; for(size_t i=0;i<vs.size();++i) c.push_back((m>>i&1)?-vs[i]:vs[i]);
    return c;
}
// Exact existential join: all internal assignments fail -> boundary clause.
// Leaves are weakened parent clauses; internal nodes are ordinary resolutions.
// The proof stream retains parents and temporary leaves even after projection.
inline void lift_blocker(Clause& c,const Clause& hidden,size_t i,Proof& proof,UnifiedStats& st) {
    if(i<hidden.size()){
        c.push_back(hidden[i]);lift_blocker(c,hidden,i+1,proof,st);
        c.back()=-hidden[i];lift_blocker(c,hidden,i+1,proof,st);
        c.pop_back();
    }
    proof.add(c);++st.proof_lines;
}
inline int join_round(int n,Clauses& cs,Proof& proof,Time until,UnifiedStats& st,UnifiedMemory& mem) {
    if(n>50000 || cs.size()>160000 || st.proof_lines>=120000 || mem.attempted.size()>=24000) return 0;
    std::map<Clause,Mask> groups;
    for(const auto& c:cs){
        if(Clock::now()>=until) return 0;
        if(c.empty()||c.size()>6) continue;
        Clause vs;unsigned m=0;
        for(size_t i=0;i<c.size();++i){vs.push_back(std::abs(c[i]));if(c[i]<0)m|=1u<<i;}
        groups[vs]|=bit(m);
    }
    std::vector<Rel> rel;
    for(const auto& kv:groups) if(kv.first.size()>=2)
        rel.push_back({kv.first,kv.second});
    std::vector<std::vector<int>> index(n+1);
    for(int i=0;i<int(rel.size());++i)for(int v:rel[i].vars)index[v].push_back(i);
    struct Pair {int a,b,kind,width,work;};
    std::vector<Pair> todo; int examined=0;
    for(int i=0;i<int(rel.size())&&examined<16000&&Clock::now()<until;++i){
        std::set<int> js;
        for(int v:rel[i].vars)if(index[v].size()<=96)
            for(int j:index[v])if(j<i)js.insert(j);
        for(int j:js){
            if(++examined>16000)break;
            const auto &a=rel[i],&b=rel[j];
            Clause u,h;
            std::set_union(a.vars.begin(),a.vars.end(),b.vars.begin(),b.vars.end(),std::back_inserter(u));
            std::set_intersection(a.vars.begin(),a.vars.end(),b.vars.begin(),b.vars.end(),std::back_inserter(h));
            int w=int(u.size()-h.size()); // union minus all shared variables
            if(h.empty()||u.size()>9||w>6)continue;
            bool aff=parity_relation(a)&&parity_relation(b);
            if(!aff && w>4 && h.size()<2)continue;
            auto key=std::make_pair(RKey{a.vars,a.forbidden},RKey{b.vars,b.forbidden});
            if(mem.attempted.count(key))continue;
            todo.push_back({i,j,aff?0:1,w,1<<u.size()});
        }
    }
    std::sort(todo.begin(),todo.end(),[](const Pair&a,const Pair&b){
        return std::tie(a.width,a.kind,a.work,a.a,a.b)<std::tie(b.width,b.kind,b.work,b.a,b.b);
    });
    std::set<Clause> known(cs.begin(),cs.end());
    int added=0, local=0;
    // Do not retain failed attempts beyond the exact relation versions.
    for(const auto& p:todo){
        if(Clock::now()>=until || local>=240 || added>=180 || st.proof_lines>=120000 || mem.attempted.size()>=24000)break;
        const auto &a=rel[p.a],&b=rel[p.b];
        Clause boundary,hidden;
        std::set_symmetric_difference(a.vars.begin(),a.vars.end(),b.vars.begin(),b.vars.end(),std::back_inserter(boundary));
        std::set_intersection(a.vars.begin(),a.vars.end(),b.vars.begin(),b.vars.end(),std::back_inserter(hidden));
        // Precompute each parent's mapping into boundary+hidden assignments.
        Clause order=boundary;order.insert(order.end(),hidden.begin(),hidden.end());
        auto mapping=[&](const Clause& vs){
            Clause r;for(int v:vs)r.push_back(int(std::find(order.begin(),order.end(),v)-order.begin()));return r;
        };
        auto ma=mapping(a.vars),mb=mapping(b.vars);
        auto project_mask=[](unsigned full,const Clause& m){
            unsigned r=0;for(size_t k=0;k<m.size();++k)r|=((full>>m[k])&1u)<<k;return r;
        };
        int before=added;bool complete=true;
        for(unsigned m=0;m<(1u<<boundary.size());++m){
            if(Clock::now()>=until || added>=180 || st.proof_lines+int((1u<<(hidden.size()+1))-1)>120000){complete=false;break;}
            bool possible=false;
            for(unsigned h=0;h<(1u<<hidden.size());++h){
                unsigned full=m|(h<<boundary.size());
                if(!(a.forbidden&bit(project_mask(full,ma)))&&!(b.forbidden&bit(project_mask(full,mb)))){possible=true;break;}
            }
            if(possible)continue;
            Clause c=blocker(boundary,m);
            if(known.count(c))continue;
            // A direct known subclause makes a longer blocker redundant.
            bool redundant=false;
            for(size_t k=0;k<c.size();++k){Clause shortc=c;shortc.erase(shortc.begin()+k);if(known.count(shortc)){redundant=true;break;}}
            if(redundant)continue;
            lift_blocker(c,hidden,0,proof,st);
            known.insert(c);cs.push_back(c);++added;++st.relation_facts;
            if(c.empty()){++st.pairs;if(p.kind==0)++st.affine;else ++st.nonlinear;return added;}
        }
        if(complete)mem.attempted.insert({RKey{a.vars,a.forbidden},RKey{b.vars,b.forbidden}});
        ++local;++st.pairs;
        if(added>before){if(p.kind==0)++st.affine;else ++st.nonlinear;}
    }
    return added;
}
// ATLAS40-inspired candidate subclause probes. These are RUP, not CDCL:
// no decision stack, conflict analysis, learned-clause search, or backtracking.
inline int probe_round(int n,Clauses& cs,Proof& proof,Time until,UnifiedStats& st,UnifiedMemory& mem) {
    if(n>50000||cs.size()>160000)return 0;
    std::set<Clause> known(cs.begin(),cs.end()), candidates;
    for(const auto& c:cs){
        if(Clock::now()>=until)return 0;
        if(c.size()<2||c.size()>4)continue;
        for(size_t k=0;k<c.size();++k){
            Clause r=c;r.erase(r.begin()+k);
            if(!known.count(r))candidates.insert(std::move(r));
        }
        if(candidates.size()>=18000)break;
    }
    Clauses todo(candidates.begin(),candidates.end()), facts;
    std::stable_sort(todo.begin(),todo.end(),[](const Clause&a,const Clause&b){return a.size()<b.size();});
    if(todo.empty())return 0;
    Propagator prop(n,cs);int checks=0;
    size_t offset=size_t(mem.probe_offset)%todo.size();
    for(size_t i=0;i<todo.size()&&checks<1200&&facts.size()<120&&Clock::now()<until;++i){
        const auto& c=todo[(offset+i)%todo.size()];
        bool ok=true;
        if(c.size()==1)ok=prop.consistent({-c[0]});
        if(c.size()==2)ok=prop.consistent({-c[0],-c[1]});
        if(c.size()==3)ok=prop.consistent({-c[0],-c[1],-c[2]});
        ++checks;++st.probes;
        if(!ok){proof.add(c);facts.push_back(c);++st.probe_facts;}
    }
    mem.probe_offset+=checks;
    cs.insert(cs.end(),facts.begin(),facts.end());
    return int(facts.size());
}
// A shared inference state. Every round gives all methods a bounded chance;
// a productive method receives the next epoch's first slot. If an entire
// epoch yields no new consequence, stop; projection can open a new epoch.
inline bool cooperate(int n,Clauses& cs,Model& fixed,Proof& proof,Time until,
                      CaseStats& cases,UnifiedStats& st,int max_epochs) {
    UnifiedMemory mem;
    std::array<int,4> order{0,1,2,3};
    for(int epoch=0;epoch<max_epochs&&Clock::now()<until;++epoch){
        ++st.epochs;
        std::array<int,4> gain{0,0,0,0};
        std::array<double,4> score{0,0,0,0};
        int total=0;
        for(int i=0;i<4&&Clock::now()<until;++i){
            int k=order[i];auto begin=Clock::now();
            double left=std::chrono::duration<double>(until-begin).count();
            auto stop=std::min(until,after(std::max(0.001,left/(4-i))));
            int d=0;
            if(k==0)d=join_round(n,cs,proof,stop,st,mem);
            if(k==1)d=probe_round(n,cs,proof,stop,st,mem);
            if(k==2)d=compose_round(n,cs,proof,stop,cases);
            if(k==3)d=guarded_round(n,cs,proof,stop,cases);
            gain[k]=d;total+=d;
            score[k]=d/std::max(.001,std::chrono::duration<double>(Clock::now()-begin).count());
            if(d && !reduce_root(n,cs,fixed,proof))return false;
            if(cs.empty())return true;
        }
        if(!total)break;
        std::stable_sort(order.begin(),order.end(),[&](int a,int b){return score[a]>score[b];});
    }
    return true;
}
} // namespace toolbox
