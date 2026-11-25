#pragma once
#include "unified_reason.hpp"
#include "adaptive_projection.hpp"
#include "repair.hpp"
#include <queue>
#include <numeric>

namespace toolbox {
struct AdaptiveStats {
    int epochs=0,gates=0,congruence=0,gate_proof=0,
        pair_checks=0,triple_checks=0,wide_facts=0,
        resolution_facts=0,resolution_pairs=0,extra_pivots=0,extra_resolvents=0,
        feedback=0,attempts=0;
};
class AdaptivePropagator {
    Clauses cs;
    std::vector<std::vector<int>> watches;
    Clause units;
    bool empty=false;
    bool put(int l) {
        int old=value(state,l);
        if (old>=0) return old==1;
        state[std::abs(l)]=l>0; trail.push_back(l); return true;
    }
public:
    Model state;
    Clause trail;
    AdaptivePropagator(int n,const Clauses& clauses):cs(clauses),watches(2*n),state(n+1,-1) {
        for (int i=0; i<int(cs.size()); ++i) {
            const auto& c=cs[i];
            if (c.empty()) empty=true;
            else if (c.size()==1) units.push_back(c[0]);
            else { watches[index_of(c[0])].push_back(i); watches[index_of(c[1])].push_back(i); }
        }
    }
    bool consistent(const Clause& assumptions={}) {
        for (int l:trail) state[std::abs(l)]=-1;
        trail.clear();
        if (empty) return false;
        for (int l:units) if (!put(l)) return false;
        for (int l:assumptions) if (!put(l)) return false;
        for (size_t head=0;head<trail.size();++head) {
            int falsified=-trail[head]; auto& watching=watches[index_of(falsified)];
            for (size_t i=0;i<watching.size();) {
                int id=watching[i]; auto& c=cs[id];
                if (c[0]==falsified) std::swap(c[0],c[1]);
                if (value(state,c[0])==1) { ++i; continue; }
                size_t k=2;
                while (k<c.size() && value(state,c[k])==0) ++k;
                if (k<c.size()) {
                    std::swap(c[1],c[k]); watches[index_of(c[1])].push_back(id);
                    watching[i]=watching.back(); watching.pop_back();
                } else { if (!put(c[0])) return false; ++i; }
            }
        }
        return true;
    }
};

struct SignedUF {
    std::vector<int> parent,phase;
    explicit SignedUF(int n):parent(n+1),phase(n+1){std::iota(parent.begin(),parent.end(),0);}
    std::pair<int,int> find(int v){
        int r=v,d=0;while(parent[r]!=r){d^=phase[r];r=parent[r];}
        int t=v,p=0;while(parent[t]!=t){int u=parent[t],old=phase[t];parent[t]=r;phase[t]=d^p;p^=old;t=u;}
        return {r,d};
    }
    bool unite(int a,int b,int d){
        auto [x,p]=find(a);auto [y,q]=find(b);
        if(x==y)return (p^q)==d;
        if(x>y){parent[x]=y;phase[x]=p^q^d;}
        else{parent[y]=x;phase[y]=p^q^d;}
        return true;
    }
};
struct Gate {int out;Clause in;unsigned truth;};
// Source-derived local truth tables, with no assumption about variable numbering
// or gate names. Only total, deterministic two-input functions are admitted.
inline std::vector<Gate> discover_gates(const Clauses& source,Time until){
    std::map<Clause,unsigned> masks;
    for(const auto& c:source){
        if(Clock::now()>=until)return {};
        if(c.size()!=2&&c.size()!=3)continue;
        Clause v;unsigned m=0;
        for(size_t i=0;i<c.size();++i){v.push_back(std::abs(c[i]));if(c[i]<0)m|=1u<<i;}
        masks[v]|=1u<<m;
    }
    std::vector<Gate> gates;
    for(const auto& [v,bad]:masks){
        if(Clock::now()>=until||gates.size()>=12000)break;
        if(v.size()!=3)continue;
        unsigned allowed=0;
        for(unsigned m=0;m<8;++m){
            if(bad&(1u<<m))continue;
            bool ok=true;
            for(int i=0;i<3;++i)for(int j=i+1;j<3;++j){
                auto it=masks.find(Clause{v[i],v[j]});
                unsigned a=((m>>i)&1u)|(((m>>j)&1u)<<1);
                if(it!=masks.end()&&(it->second&(1u<<a)))ok=false;
            }
            if(ok)allowed|=1u<<m;
        }
        for(int o=0;o<3;++o){
            int a=(o==0?1:0),b=(o==2?1:2);
            unsigned truth=0;bool total=true;
            for(unsigned m=0;m<4;++m){
                unsigned base=((m&1u)<<a)|(((m>>1)&1u)<<b);
                bool lo=allowed&(1u<<base),hi=allowed&(1u<<(base|(1u<<o)));
                if(lo==hi){total=false;break;}
                if(hi)truth|=1u<<m;
            }
            if(total)gates.push_back({v[o],{v[a],v[b]},truth});
        }
    }
    return gates;
}
// Local case proof: all leaves must independently pass unit propagation.
// Their parents are then RUP by resolving the two child blockers.
inline bool case_proof(AdaptivePropagator& prop,Clause target,Clause hidden,Clauses& lines,Time until){
    if(!normalize(target))return false;
    hidden.erase(std::remove_if(hidden.begin(),hidden.end(),[&](int v){
        return std::any_of(target.begin(),target.end(),[&](int l){return std::abs(l)==v;});
    }),hidden.end());
    auto rec=[&](auto&& self,Clause c,size_t i)->bool{
        if(Clock::now()>=until)return false;
        if(i==hidden.size()){
            Clause assumptions;for(int l:c)assumptions.push_back(-l);
            if(prop.consistent(assumptions))return false;
        }else{
            Clause a=c,b=c;a.push_back(hidden[i]);b.push_back(-hidden[i]);
            if(!self(self,std::move(a),i+1)||!self(self,std::move(b),i+1))return false;
        }
        normalize(c);lines.push_back(std::move(c));return true;
    };
    return rec(rec,std::move(target),0);
}
inline int gate_round(int n,Clauses& active,const std::vector<Gate>& gates,Proof& proof,Time until,AdaptiveStats& st){
    if(gates.empty()||active.size()>24000)return 0;
    SignedUF uf(n);
    std::set<Clause> known(active.begin(),active.end());
    for(const auto& c:active){
        if(Clock::now()>=until)return 0;
        if(c.size()!=2)continue;
        Clause rev{-c[0],-c[1]};normalize(rev);
        if(known.count(rev)){
            int d=1^(c[0]<0)^(c[1]<0);
            if(!uf.unite(std::abs(c[0]),std::abs(c[1]),d))return 0; // wide probes will check it
        }
    }
    AdaptivePropagator prop(n,active);Clauses facts;
    using Key=std::pair<Clause,unsigned>;
    std::map<Key,std::pair<int,int>> canonical;
    auto add=[&](Clause c,const Clause& hidden){
        if(!normalize(c)||known.count(c)||facts.size()>=1000)return;
        Clauses lines;
        if(!case_proof(prop,c,hidden,lines,until))return;
        for(const auto& q:lines){proof.add(q);++st.gate_proof;}
        known.insert(c);facts.push_back(std::move(c));++st.congruence;
    };
    auto equivalent=[&](int y,int z,int d,const Clause& hidden){
        if(y==z){if(d)add({},hidden);return;}
        auto [ry,py]=uf.find(y);auto [rz,pz]=uf.find(z);
        if(ry==rz&&(py^pz)==d)return;
        if(d){add({y,z},hidden);add({-y,-z},hidden);}
        else{add({-y,z},hidden);add({y,-z},hidden);}
    };
    for(const auto& g:gates){
        if(Clock::now()>=until||facts.size()>=1000)break;
        auto [a,p]=uf.find(g.in[0]);auto [b,q]=uf.find(g.in[1]);
        Clause support{a,b};std::sort(support.begin(),support.end());
        support.erase(std::unique(support.begin(),support.end()),support.end());
        unsigned truth=0,all=(1u<<(1u<<support.size()))-1;
        for(unsigned m=0;m<(1u<<support.size());++m){
            unsigned aa=((m>>(a==support.front()?0:1))&1u)^unsigned(p);
            unsigned bb=((m>>(b==support.front()?0:1))&1u)^unsigned(q);
            if(g.truth&(1u<<(aa|(bb<<1))))truth|=1u<<m;
        }
        if(!truth||truth==all){add({truth?g.out:-g.out},support);continue;}
        if(support.size()==1){
            equivalent(g.out,support.front(),truth&1u,support);continue;
        }
        // Also recognize a binary table that in fact depends on one input only.
        if(truth==10||truth==5){equivalent(g.out,support[0],truth==5,support);continue;}
        if(truth==12||truth==3){equivalent(g.out,support[1],truth==3,support);continue;}
        unsigned canon=std::min(truth,all^truth);int invert=truth!=canon;
        auto [it,fresh]=canonical.emplace(Key{support,canon},std::make_pair(g.out,invert));
        if(!fresh)equivalent(g.out,it->second.first,invert^it->second.second,support);
    }
    active.insert(active.end(),facts.begin(),facts.end());
    return int(facts.size());
}
inline bool root_conflict(int n,const Clauses& cs,Proof& proof){
    AdaptivePropagator p(n,cs);
    if(p.consistent())return false;
    proof.add({});return true;
}
// Bounded relation exploration: every accepted clause is a direct RUP
// consequence under a fixed two-/three-symbol tuple. No recursive search,
// decision stack, conflict analysis, or backjumping.
inline int wide_round(int n,Clauses& cs,Proof& proof,Time until,AdaptiveStats& st,int width,int epoch){
    if(n>2000||cs.size()>24000)return 0;
    AdaptivePropagator prop(n,cs);
    std::set<Clause> known(cs.begin(),cs.end());Clauses facts;
    std::vector<int> degree(n+1),impact(n+1);
    for(const auto& c:cs)for(int l:c)degree[std::abs(l)]+=c.size()<=3?3:1;
    Clause rank;for(int v=1;v<=n;++v)if(degree[v])rank.push_back(v);
    auto add=[&](Clause c){
        normalize(c);if(known.insert(c).second){proof.add(c);facts.push_back(c);++st.wide_facts;}
    };
    for(int v:rank){
        if(Clock::now()>=until)break;
        for(int l:{v,-v}){
            if(!prop.consistent({l}))add({-l});
            else impact[v]+=int(prop.trail.size());
        }
    }
    if(!facts.empty()){cs.insert(cs.end(),facts.begin(),facts.end());return int(facts.size());}
    std::sort(rank.begin(),rank.end(),[&](int a,int b){
        return std::make_pair(impact[a]*4+degree[a],-a)>std::make_pair(impact[b]*4+degree[b],-b);
    });
    const size_t limit=width==2?size_t(128+32*std::min(epoch,3)):size_t(28+4*std::min(epoch,3));
    if(rank.size()>limit){
        // Retain a stable high-impact core, rotate the rest across epochs.
        size_t head=limit/2,remaining=rank.size()-head;
        if(remaining)std::rotate(rank.begin()+head,rank.begin()+head+(size_t(epoch)*head)%remaining,rank.end());
        rank.resize(limit);
    }
    int checks=0,cap=width==2?60000:70000;
    auto test=[&](Clause assumptions){
        if(checks>=cap||facts.size()>=1500||Clock::now()>=until)return;
        Clause c;for(int l:assumptions)c.push_back(-l);normalize(c);
        if(known.count(c))return;
        for(size_t k=0;k<c.size();++k){Clause sub=c;sub.erase(sub.begin()+k);if(known.count(sub))return;}
        ++checks;if(width==2)++st.pair_checks;else ++st.triple_checks;
        if(!prop.consistent(assumptions))add(std::move(c));
    };
    auto stop=[&](){return checks>=cap||facts.size()>=1500||Clock::now()>=until;};
    for(size_t i=0;i<rank.size()&&!stop();++i)
        for(size_t j=i+1;j<rank.size()&&!stop();++j){
            if(width==2){
                for(int a:{rank[i],-rank[i]})for(int b:{rank[j],-rank[j]})test({a,b});
            }else for(size_t k=j+1;k<rank.size()&&!stop();++k)
                for(int a:{rank[i],-rank[i]})for(int b:{rank[j],-rank[j]})for(int c:{rank[k],-rank[k]})test({a,b,c});
        }
    cs.insert(cs.end(),facts.begin(),facts.end());return int(facts.size());
}
inline int resolution_sweep(int n,Clauses& cs,Proof& proof,Time until,AdaptiveStats& st,int width,int fact_cap){
    if(n>2000||cs.size()>24000)return 0;
    std::set<Clause> known;
    Clauses db;
    for(const auto& c:cs)if(known.insert(c).second)db.push_back(c);
    using Item=std::pair<size_t,int>;
    std::priority_queue<Item,std::vector<Item>,std::greater<Item>> queue;
    std::vector<std::vector<int>> index(2*n);
    for(int i=0;i<int(db.size());++i)if(db[i].size()<=size_t(width+1))queue.push({db[i].size(),i});
    int pairs=0,added=0;
    auto stop=[&](){return pairs>=350000||added>=fact_cap||Clock::now()>=until;};
    while(!queue.empty()&&!stop()){
        int i=queue.top().second;queue.pop();Clause a=db[i];
        if(a.empty())return added;
        for(int l:a){
            for(int j:index[index_of(-l)]){
                if(stop())break;
                ++pairs;++st.resolution_pairs;
                Clause r;
                for(int x:a)if(x!=l)r.push_back(x);
                for(int x:db[j])if(x!=-l)r.push_back(x);
                if(!normalize(r)||r.size()>size_t(width)||known.count(r))continue;
                bool redundant=false;
                for(size_t k=0;k<r.size();++k){
                    if(known.count(Clause{r[k]})){redundant=true;break;}
                    Clause sub=r;sub.erase(sub.begin()+k);
                    if(known.count(sub)){redundant=true;break;}
                }
                if(redundant)continue;
                proof.add(r);known.insert(r);cs.push_back(r);++added;++st.resolution_facts;
                if(r.empty())return added;
                queue.push({r.size(),int(db.size())});db.push_back(std::move(r));
            }
            if(stop())break;
        }
        for(int l:a)index[index_of(l)].push_back(i);
    }
    return added;
}
enum class TailResult { open,sat,unsat };
// Preserve the completed UNIFIED1 route. If it leaves a residual, restart
// reasoning on the original constraints plus already proved residual clauses.
// All new knowledge is a consequence of the original formula.
inline TailResult adaptive_tail(const Input& f,const Clauses& residual,Proof& proof,Time deadline,
                               bool construct,Model& answer,AdaptiveStats& st){
    if(f.n>2000||f.cs.size()>18000||residual.size()>18000||Clock::now()>=deadline)return TailResult::open;
    Clauses active=f.cs;std::set<Clause> known(active.begin(),active.end());
    for(const auto& c:residual)if(known.insert(c).second)active.push_back(c);
    if(active.size()>24000)return TailResult::open;
    auto gates=discover_gates(f.cs,std::min(deadline,after(.20)));st.gates=int(gates.size());
    std::array<int,4> order=gates.size()>=4?std::array<int,4>{0,1,3,2}:std::array<int,4>{1,2,3,0};
    std::array<double,4> utility{0,0,0,0};
    for(int epoch=0;epoch<4&&Clock::now()<deadline&&active.size()<=24000;++epoch){
        ++st.epochs;int total=0;
        for(int j=0;j<4&&Clock::now()<deadline&&active.size()<=24000;++j){
            int method=order[j];++st.attempts;
            auto begin=Clock::now();
            double left=std::chrono::duration<double>(deadline-begin).count();
            auto until=std::min(deadline,after(std::max(.001,left/(4-j))));
            int gain=0;
            if(method==0){
                for(int round=0;round<24&&Clock::now()<until;++round){
                    int d=gate_round(f.n,active,gates,proof,until,st);gain+=d;
                    if(root_conflict(f.n,active,proof))return TailResult::unsat;
                    if(!d)break;
                }
            }else if(method==1){
                gain=wide_round(f.n,active,proof,until,st,epoch==0?2:3,epoch);
            }else if(method==2){
                gain=resolution_sweep(f.n,active,proof,until,st,3+std::min(epoch,2),1600+600*epoch);
            }else{
                // Widen the *exact* elimination budget, not the SAT search.
                // Start from original+proved facts; all reconstruction frames
                // are private to this attempt. Import short entailed residues.
                Clauses work=active;Model fixed(f.n+1,-1);
                if(!reduce_root(f.n,work,fixed,proof))return TailResult::unsat;
                ProjectionPolicy policy{256<<epoch,32<<epoch,16+4*epoch,size_t(12000+8000*epoch)};
                AdaptiveProjection p(f.n,work,policy);
                if(!p.run(proof,until))return TailResult::unsat;
                st.extra_pivots+=p.projected;st.extra_resolvents+=p.generated;
                auto rest=p.residual();
                Model m(f.n+1,0);for(int v=1;v<=f.n;++v)if(fixed[v]>=0)m[v]=fixed[v];
                uint64_t flips=0;
                bool good=satisfied(rest,m);
                if(!good&&construct&&Clock::now()<until)
                    good=repair(f.n,rest,m,std::min(until,after(.05)),flips);
                if(good){
                    for(int v=1;v<=f.n;++v)if(fixed[v]>=0)m[v]=fixed[v];
                    p.reconstruct(m);
                    for(int v=1;v<=f.n;++v)if(fixed[v]>=0)m[v]=fixed[v];
                    if(satisfied(f.cs,m)){answer=std::move(m);return TailResult::sat;}
                }
                known=std::set<Clause>(active.begin(),active.end());
                // Do not drop any original constraints; importing a clause
                // proved by elimination is safe even for another projection.
                for(const auto& c:rest){
                    if(c.size()>size_t(3+std::min(epoch,1))||gain>=1200||active.size()>=24000)continue;
                    if(known.insert(c).second){active.push_back(c);++gain;++st.feedback;}
                }
            }
            total+=gain;
            utility[method]=gain/std::max(.001,std::chrono::duration<double>(Clock::now()-begin).count());
            if(root_conflict(f.n,active,proof))return TailResult::unsat;
        }
        // Even a zero-gain epoch can open a new width or projection policy.
        // Once the finite escalation ladder is exhausted, report UNKNOWN.
        std::stable_sort(order.begin(),order.end(),[&](int a,int b){return utility[a]>utility[b];});
        if(!total&&epoch==3)break;
    }
    return TailResult::open;
}
} // namespace toolbox
