#pragma once
#include "adaptive_reason.hpp"
#include <memory>
#include <functional>

namespace toolbox {
struct DiscoveryStats {
    int epochs=0,loaded=0,compacted=0,contexts=0,pair_contexts=0,closed=0;
    int conditional_facts=0,regional_facts=0,bags=0,bag_max=0,local_unsat=0;
    uint64_t local_trials=0,proof_lines=0,table_rows=0;
};
inline Clause negate_clause(const Clause& assumptions){
    Clause c;for(int l:assumptions)c.push_back(-l);normalize(c);return c;
}
inline bool subsumed_short(const Clause& c,const std::set<Clause>& known){
    if(known.count(c)||known.count(Clause{}))return true;
    for(int l:c)if(known.count(Clause{l}))return true;
    if(c.size()<=8){
        unsigned all=(1u<<c.size())-1;
        for(unsigned m=1;m<all;++m){
            if(__builtin_popcount(m)==1)continue;
            Clause r;for(size_t i=0;i<c.size();++i)if(m>>i&1u)r.push_back(c[i]);
            if(known.count(r))return true;
        }
    }
    return false;
}
// The solver's own DRUP stream is a proof-bound blackboard. Only short,
// normalized consequences are imported, never a result or reference model.
inline Clauses load_blackboard(const Input& f,const Clauses& residual,Proof& proof,
                               Time until,DiscoveryStats& st){
    proof.out.flush();std::ifstream in(proof.path);
    std::set<Clause> facts(f.cs.begin(),f.cs.end());
    for(const auto& c:residual)if(c.size()<=4)facts.insert(c);
    std::string line;int read=0;
    while(read<240000&&Clock::now()<until&&std::getline(in,line)){
        ++read;std::istringstream s(line);Clause c;int l;bool valid=true,ended=false;
        while(s>>l){
            if(l==0){ended=true;break;}
            if(l < -f.n || l > f.n || c.size()>=4){valid=false;break;}
            c.push_back(l);
        }
        if(valid&&ended&&normalize(c)&&facts.insert(c).second)++st.loaded;
    }
    return Clauses(facts.begin(),facts.end());
}
// Deletion is only from working memory. The independent proof stream retains
// every original and derived premise. Original constraints are retained or
// subsumed by an entailed stronger clause.
inline void compact_blackboard(const Input& f,Clauses& active,DiscoveryStats& st){
    std::set<Clause> originals(f.cs.begin(),f.cs.end());
    active.insert(active.end(),f.cs.begin(),f.cs.end());
    std::sort(active.begin(),active.end(),[](const Clause&a,const Clause&b){
        if(a.size()!=b.size())return a.size()<b.size();return a<b;
    });
    active.erase(std::unique(active.begin(),active.end()),active.end());
    std::set<Clause> kept;Clauses out;out.reserve(std::min<size_t>(active.size(),12000));
    size_t before=active.size();
    for(const auto& c:active){
        if(subsumed_short(c,kept))continue;
        if(!originals.count(c)&&(out.size()>=10000||(out.size()>=6500&&c.size()>=4)))continue;
        kept.insert(c);out.push_back(c);
    }
    st.compacted+=int(before-out.size());active=std::move(out);
}
struct ConditionalResult { bool impossible=false; Clauses trace,facts; };
// A fixed context is a mathematical assumption set, not a decision stack.
// Compute a conditional fixed point via single-symbol consistency and
// consensus of both polarities. Every emitted local fact is guarded by the
// whole context. Earlier guarded facts are unit-propagated under that context.
inline ConditionalResult close_context(AdaptivePropagator& prop,const Clause& context,
                                       const Clause& rank,Time until,DiscoveryStats& st,
                                       int max_trials,int max_facts){
    ConditionalResult out;
    Clause guard=negate_clause(context),forced=context;
    std::set<Clause> local;
    auto record=[&](Clause c){normalize(c);if(local.insert(c).second)out.trace.push_back(std::move(c));};
    auto guarded=[&](int l){Clause c=guard;c.push_back(l);normalize(c);return c;};
    auto impossible=[&](){
        record(guard);out.impossible=true;out.facts={guard};
    };
    int trials=0,derived=0;
    for(int sweep=0;sweep<10&&Clock::now()<until&&trials<max_trials&&derived<max_facts;++sweep){
        if(!prop.consistent(forced)){impossible();return out;}
        Model base=prop.state;bool changed=false;
        for(int v:rank){
            if(Clock::now()>=until||trials>=max_trials||derived>=max_facts)break;
            if(base[v]>=0)continue;
            Clause a=forced,b=forced;a.push_back(v);b.push_back(-v);
            bool pos=prop.consistent(a);Clause pos_trail=pos?prop.trail:Clause{};
            bool neg=prop.consistent(b);trials+=2;st.local_trials+=2;
            if(!pos||!neg){
                if(!pos)record(guarded(-v));
                if(!neg)record(guarded(v));
                if(!pos&&!neg){impossible();return out;}
                int l=pos?v:-v;
                Clause c=guarded(l);out.facts.push_back(c);forced.push_back(l);
                ++derived;changed=true;break;
            }
            // A consequence holding in both branches follows from the context.
            // Emit two RUP implications and resolve them; do not assume
            // a successful branch is a satisfying assignment.
            Clause common;
            for(int t:pos_trail)
                if(std::abs(t)!=v&&base[std::abs(t)]<0&&value(prop.state,t)==1)
                    common.push_back(t);
            if(common.empty())continue;
            for(int t:common){
                if(derived>=max_facts)break;
                Clause c=guarded(t);
                Clause cp=c,cn=c;cp.push_back(-v);cn.push_back(v);
                record(cp);record(cn);record(c);
                out.facts.push_back(c);forced.push_back(t);
                ++derived;changed=true;
            }
            if(changed)break;
        }
        if(!changed)break;
    }
    if(Clock::now()<until&&!prop.consistent(forced))impossible();
    return out;
}
inline Clause source_rank(const Input& f,const Clauses& cs,AdaptivePropagator& prop,Time until){
    std::vector<int> degree(f.n+1),impact(f.n+1);
    for(const auto& c:f.cs)for(int l:c)degree[std::abs(l)]+=c.size()<=3?3:1;
    for(const auto& c:cs)if(c.size()<=2)for(int l:c)degree[std::abs(l)]+=1;
    Clause vars;
    for(int v=1;v<=f.n;++v)if(degree[v])vars.push_back(v);
    for(int v:vars){
        if(Clock::now()>=until)break;
        for(int l:{v,-v})if(prop.consistent({l}))impact[v]+=int(prop.trail.size());
    }
    std::sort(vars.begin(),vars.end(),[&](int a,int b){
        return std::make_pair(4*impact[a]+degree[a],-a)>std::make_pair(4*impact[b]+degree[b],-b);
    });
    return vars;
}
// Pair contexts are selected from source adjacency and high-impact variables;
// the order changes as proved relations alter propagation. There is no full
// recursive assignment search and no conflict-driven decision process.
inline bool context_round(const Input& f,Clauses& active,Proof& proof,Time until,
                          DiscoveryStats& st,int width,int epoch){
    if(active.empty()||active.size()>18000||Clock::now()>=until)return false;
    std::set<Clause> known(active.begin(),active.end());
    auto prop=std::make_unique<AdaptivePropagator>(f.n,active);
    Clause rank=source_rank(f,active,*prop,until);
    if(rank.empty())return false;
    std::vector<Clause> todo;todo.push_back({});
    if(width==1){
        for(int v:rank){todo.push_back({v});todo.push_back({-v});}
    }else{
        std::set<std::pair<int,int>> edges;
        std::vector<int> priority(f.n+1,int(rank.size()));
        for(int i=0;i<int(rank.size());++i)priority[rank[i]]=i;
        for(const auto& c:f.cs)if(c.size()<=4)
            for(size_t i=0;i<c.size();++i)for(size_t j=i+1;j<c.size();++j){
                int a=std::abs(c[i]),b=std::abs(c[j]);if(a>b)std::swap(a,b);
                if(a!=b)edges.emplace(a,b);
            }
        size_t top=std::min(rank.size(),size_t(22+8*epoch));
        for(size_t i=0;i<top;++i)for(size_t j=i+1;j<top;++j){
            int a=rank[i],b=rank[j];if(a>b)std::swap(a,b);edges.emplace(a,b);
        }
        std::vector<std::pair<int,int>> pairs(edges.begin(),edges.end());
        std::sort(pairs.begin(),pairs.end(),[&](auto a,auto b){
            auto key=[&](auto p){return std::make_tuple(priority[p.first]+priority[p.second],
                                                       std::max(priority[p.first],priority[p.second]),p);};
            return key(a)<key(b);
        });
        if(pairs.size()>size_t(160+80*epoch)){
            size_t head=std::min<size_t>(80,pairs.size()/2),tail=pairs.size()-head;
            if(tail)std::rotate(pairs.begin()+head,pairs.begin()+head+(size_t(epoch)*71)%tail,pairs.end());
            pairs.resize(std::min(pairs.size(),size_t(160+80*epoch)));
        }
        for(auto [a,b]:pairs)for(int x:{a,-a})for(int y:{b,-b})todo.push_back({x,y});
    }
    int accepted=0;
    for(const auto& ctx:todo){
        if(Clock::now()>=until||st.proof_lines>=260000||accepted>=1000||active.size()>=18000)break;
        if(!ctx.empty()&&subsumed_short(negate_clause(ctx),known))continue;
        ++st.contexts;if(ctx.size()==2)++st.pair_contexts;
        // Allow more work under the empty/single context. A pair context
        // contributes only if it establishes an impossible boundary.
        int trials=std::min<int>(int(rank.size())*4+16,ctx.size()==2?360:900);
        auto result=close_context(*prop,ctx,rank,until,st,trials,ctx.size()==2?32:64);
        if(result.impossible)++st.closed;
        if(ctx.size()==2&&!result.impossible)continue;
        Clauses fresh;
        for(const auto& c:result.facts)
            if(!subsumed_short(c,known)&&std::find(fresh.begin(),fresh.end(),c)==fresh.end())fresh.push_back(c);
        if(fresh.empty())continue;
        if(st.proof_lines+result.trace.size()>260000)break;
        for(const auto& c:result.trace){proof.add(c);++st.proof_lines;}
        for(const auto& c:fresh){
            if(c.empty())return true;
            if(known.insert(c).second){active.push_back(c);++accepted;++st.conditional_facts;}
        }
        prop=std::make_unique<AdaptivePropagator>(f.n,active);
        if(!prop->consistent()){proof.add({});++st.proof_lines;return true;}
    }
    return false;
}
// Exact local truth-table projection. A failed boundary assignment is
// certified by a bounded case proof over the other variables of this bag.
// This enumerates only a selected small region, not the global CNF.
inline bool region_trace(AdaptivePropagator& prop,const Clause& target,const Clause& hidden,
                         Clauses& trace,Time until){
    Clause assumptions;for(int l:target)assumptions.push_back(-l);
    auto visit=[&](auto&& self,size_t i)->bool{
        if(Clock::now()>=until||trace.size()>=8192)return false;
        if(!prop.consistent(assumptions)){trace.push_back(negate_clause(assumptions));return true;}
        if(i==hidden.size())return false;
        assumptions.push_back(hidden[i]);
        if(!self(self,i+1)){assumptions.pop_back();return false;}
        assumptions.back()=-hidden[i];
        if(!self(self,i+1)){assumptions.pop_back();return false;}
        assumptions.pop_back();trace.push_back(negate_clause(assumptions));return true;
    };
    return visit(visit,0);
}
struct BagDiscovery {
    std::vector<std::vector<int>> weight;
    std::vector<int> degree;
    explicit BagDiscovery(const Input& f):weight(f.n+1,std::vector<int>(f.n+1)),degree(f.n+1){
        for(const auto& c:f.cs){
            if(c.size()>6)continue;
            for(size_t i=0;i<c.size();++i)for(size_t j=i+1;j<c.size();++j){
                int a=std::abs(c[i]),b=std::abs(c[j]);if(a==b)continue;
                ++weight[a][b];++weight[b][a];++degree[a];++degree[b];
            }
        }
    }
    Clause build(int seed,int width,int epoch)const{
        Clause bag{seed};std::vector<bool> in(degree.size());in[seed]=true;
        while(int(bag.size())<width){
            int best=0;long long score=-1;
            for(int v=1;v<int(degree.size());++v)if(!in[v]){
                int inside=0;for(int u:bag)inside+=weight[v][u];
                if(!inside)continue;
                long long s=1000LL*inside/(degree[v]+1)+40LL*inside;
                if(epoch%2==1)s=100LL*inside+500LL*inside/(degree[v]+1);
                if(s>score||(s==score&&v<best)){score=s;best=v;}
            }
            if(!best)break;
            in[best]=true;bag.push_back(best);
        }
        std::sort(bag.begin(),bag.end());return bag;
    }
};
inline bool regional_round(const Input& f,Clauses& active,Proof& proof,Time until,
                           DiscoveryStats& st,int epoch){
    if(f.n>512||active.size()>18000||Clock::now()>=until)return false;
    BagDiscovery graph(f);
    Clause seeds;for(int v=1;v<=f.n;++v)if(graph.degree[v])seeds.push_back(v);
    std::sort(seeds.begin(),seeds.end(),[&](int a,int b){
        return std::make_pair(graph.degree[a],-a)>std::make_pair(graph.degree[b],-b);
    });
    if(!seeds.empty())std::rotate(seeds.begin(),seeds.begin()+(size_t(epoch)*17)%seeds.size(),seeds.end());
    std::set<Clause> known(active.begin(),active.end()),tried;
    int max_bags=18+6*epoch,bags=0,newfacts=0,width=std::min(12,8+2*epoch);
    for(int seed:seeds){
        if(Clock::now()>=until||bags>=max_bags||newfacts>=600||st.proof_lines>=260000)break;
        Clause bag=graph.build(seed,width,epoch);
        if(bag.size()<2||!tried.insert(bag).second)continue;
        std::vector<int> loc(f.n+1,-1);
        for(int i=0;i<int(bag.size());++i)loc[bag[i]]=i;
        struct Local{unsigned pos,neg;};std::vector<Local> local;Clauses premises;
        for(const auto& c:active){
            if(c.size()>bag.size())continue;
            Local row{0,0};bool fits=true;
            for(int l:c){
                int j=loc[std::abs(l)];if(j<0){fits=false;break;}
                if(l>0)row.pos|=1u<<j;else row.neg|=1u<<j;
            }
            if(fits){local.push_back(row);premises.push_back(c);}
            if(local.size()>=600)break;
        }
        if(local.size()<2)continue;
        ++bags;++st.bags;st.bag_max=std::max(st.bag_max,int(bag.size()));
        std::vector<unsigned> allowed;bool complete=true;
        for(unsigned m=0;m<(1u<<bag.size());++m){
            if((m&63u)==0&&Clock::now()>=until){complete=false;break;}
            ++st.table_rows;
            bool ok=true;for(auto r:local)if(!(m&r.pos)&&!((~m)&r.neg)){ok=false;break;}
            if(ok)allowed.push_back(m);
        }
        if(!complete)break;
        AdaptivePropagator prop(f.n,premises);
        int localfacts=0;
        auto emit=[&](Clause target)->bool{
            if(Clock::now()>=until||localfacts>=30||st.proof_lines>=260000||subsumed_short(target,known))return false;
            Clause support;for(int l:target)support.push_back(std::abs(l));
            Clause hidden;std::set_difference(bag.begin(),bag.end(),support.begin(),support.end(),std::back_inserter(hidden));
            Clauses trace;
            if(!region_trace(prop,target,hidden,trace,until))return false;
            if(st.proof_lines+trace.size()>260000)return false;
            for(const auto& c:trace){proof.add(c);++st.proof_lines;}
            known.insert(target);active.push_back(std::move(target));++localfacts;++newfacts;++st.regional_facts;
            return true;
        };
        if(allowed.empty()){
            if(emit({})){++st.local_unsat;return true;}
            continue;
        }
        auto project=[&](Clause ix){
            if(Clock::now()>=until||localfacts>=30)return;
            unsigned seen=0,all=(1u<<(1u<<ix.size()))-1;
            for(unsigned m:allowed){
                unsigned p=0;for(size_t k=0;k<ix.size();++k)p|=((m>>ix[k])&1u)<<k;
                seen|=1u<<p;if(seen==all)return;
            }
            Clause support;for(int i:ix)support.push_back(bag[i]);
            for(unsigned m=0;m<(1u<<ix.size())&&localfacts<30;++m)
                if(!(seen&(1u<<m)))emit(blocker(support,m));
        };
        int k=int(bag.size());
        for(int i=0;i<k;++i)project({i});
        for(int i=0;i<k;++i)for(int j=i+1;j<k;++j)project({i,j});
        if(epoch>=1)
            for(int i=0;i<k&&localfacts<30;++i)
                for(int j=i+1;j<k&&localfacts<30;++j)
                    for(int l=j+1;l<k&&localfacts<30;++l)project({i,j,l});
        if(localfacts&&root_conflict(f.n,active,proof)){++st.proof_lines;return true;}
    }
    return false;
}
// Only the new tail is invoked after the complete UNIFIED2 route is exhausted.
// All new results must be witnessed by a standard clausal proof.
inline bool discovery_tail(const Input& f,const Clauses& residual,Proof& proof,Time deadline,
                           DiscoveryStats& st){
    if(f.n>512||f.cs.size()>12000||Clock::now()>=deadline)return false;
    Clauses active=load_blackboard(f,residual,proof,std::min(deadline,after(.35)),st);
    compact_blackboard(f,active,st);
    if(root_conflict(f.n,active,proof))return true;
    for(int epoch=0;epoch<5&&Clock::now()<deadline&&st.proof_lines<260000;++epoch){
        ++st.epochs;
        double remaining=std::chrono::duration<double>(deadline-Clock::now()).count();
        double slice=std::min(remaining,remaining/std::max(1,3-epoch));
        Time end=std::min(deadline,after(slice));
        // Revisit single-context closure after every new regional consequence.
        if(context_round(f,active,proof,std::min(end,after(slice*.38)),st,1,epoch))return true;
        compact_blackboard(f,active,st);
        if(regional_round(f,active,proof,std::min(end,after(slice*.25)),st,epoch))return true;
        compact_blackboard(f,active,st);
        if(context_round(f,active,proof,end,st,2,epoch))return true;
        compact_blackboard(f,active,st);
        if(root_conflict(f.n,active,proof))return true;
    }
    return false;
}
} // namespace toolbox
