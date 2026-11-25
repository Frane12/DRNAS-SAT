#pragma once
#include "discovery_reason.hpp"

namespace toolbox {
struct CompositionStats {
    int epochs=0,outer_contexts=0,child_contexts=0,child_closed=0,consensus=0,
        parent_facts=0,global_facts=0,memory_loaded=0,compacted=0,rankings=0;
    uint64_t trials=0,proof_lines=0;
};
struct ChildKnowledge {
    ConditionalResult result;
    Clause implied;
};
// Recover explicit guarded implications from the inner closure. The context
// fixes its own variables; those literals are not candidate conclusions.
inline Clause conditional_literals(const ConditionalResult& r,const Clause& ctx){
    Clause guard=negate_clause(ctx),out;
    for(const auto& c:r.facts){
        if(c.size()!=guard.size()+1)continue;
        bool has=true;
        for(int l:guard)if(std::find(c.begin(),c.end(),l)==c.end()){has=false;break;}
        if(!has)continue;
        for(int l:c)if(std::find(guard.begin(),guard.end(),l)==guard.end())out.push_back(l);
    }
    std::sort(out.begin(),out.end());out.erase(std::unique(out.begin(),out.end()),out.end());
    return out;
}
// Rank by consequences that are available *in this context*, rather than
// relying solely on the global incidence order. No decisions are retained.
inline Clause contextual_rank(AdaptivePropagator& prop,const Clause& context,
                              const Clause& initial,Time until,CompositionStats& st,int rotation){
    if(!prop.consistent(context))return {};
    Model fixed=prop.state;
    std::vector<std::pair<int,int>> score;
    for(int v:initial){
        if(Clock::now()>=until)break;
        if(fixed[v]>=0)continue;
        Clause a=context,b=context;a.push_back(v);b.push_back(-v);
        bool pa=prop.consistent(a);int x=int(prop.trail.size());
        bool pb=prop.consistent(b);int y=int(prop.trail.size());
        st.trials+=2;
        int s=(!pa||!pb)?100000+std::max(x,y):4*std::min(x,y)+std::max(x,y);
        score.emplace_back(-s,v);
    }
    std::sort(score.begin(),score.end());Clause rank;
    for(auto [s,v]:score)rank.push_back(v);
    if(rotation&&rank.size()>20){
        size_t tail=rank.size()-16;
        std::rotate(rank.begin()+16,rank.begin()+16+(size_t(rotation)*11)%tail,rank.end());
    }
    ++st.rankings;return rank;
}
// A second inference layer composes complete, bounded local derivations.
// It is NOT a recursive global search: outer contexts have at most two
// symbols; one child split and the existing fixed-point inference are the
// only extra nesting. Each selected child proof is committed in order.
inline ConditionalResult compose_context(int n,const Clauses& active,const Clause& context,
                                         const Clause& initial,Time until,CompositionStats& st,
                                         int pivot_cap,int epoch){
    ConditionalResult out;
    Clause guard=negate_clause(context);
    std::set<Clause> known(active.begin(),active.end());
    Clauses work=active;
    auto prop=std::make_unique<AdaptivePropagator>(n,work);
    DiscoveryStats inner;
    auto add_trace=[&](const Clauses& trace){
        out.trace.insert(out.trace.end(),trace.begin(),trace.end());
    };
    auto add_fact=[&](Clause c){
        normalize(c);
        if(known.insert(c).second){out.facts.push_back(c);work.push_back(c);++st.parent_facts;return true;}
        return false;
    };
    auto close=[&](){
        out.trace.push_back(guard);out.facts={guard};out.impossible=true;
    };
    auto guarded=[&](int l){Clause c=guard;c.push_back(l);normalize(c);return c;};
    auto run_inner=[&](const Clause& ctx,const Clause& rank,int trials){
        uint64_t before=inner.local_trials;
        auto r=close_context(*prop,ctx,rank,until,inner,trials,96);
        st.trials+=inner.local_trials-before;
        return r;
    };
    auto rebuild=[&](){prop=std::make_unique<AdaptivePropagator>(n,work);};
    int used=0;
    for(int sweep=0;sweep<6&&used<pivot_cap&&Clock::now()<until;++sweep){
        if(!prop->consistent(context)){close();return out;}
        Clause rank=contextual_rank(*prop,context,initial,until,st,epoch+sweep);
        if(Clock::now()>=until||rank.empty())break;
        int trials=std::min(1200,std::max(120,int(initial.size())*(epoch>=2?8:5)));
        auto base=run_inner(context,rank,trials);
        if(base.impossible){add_trace(base.trace);close();return out;}
        bool changed=false;
        for(const auto& c:base.facts)if(add_fact(c))changed=true;
        if(changed){
            add_trace(base.trace);rebuild();
            if(!prop->consistent(context)){close();return out;}
        }
        Model fixed=prop->state;
        for(int v:rank){
            if(Clock::now()>=until||used>=pivot_cap||out.trace.size()>=28000)break;
            if(fixed[v]>=0)continue;
            ++used;
            Clause ca=context,cb=context;ca.push_back(v);cb.push_back(-v);
            ChildKnowledge a,b;
            auto evaluate=[&](ChildKnowledge& q,const Clause& c){
                ++st.child_contexts;
                // Rotate the inner order around the pivot to avoid always
                // spending the trial budget on the same low-impact prefix.
                Clause inner_rank=rank;
                auto it=std::find(inner_rank.begin(),inner_rank.end(),v);
                if(it!=inner_rank.end())std::rotate(inner_rank.begin(),it,inner_rank.end());
                q.result=run_inner(c,inner_rank,trials);
                if(q.result.impossible)++st.child_closed;
                else q.implied=conditional_literals(q.result,c);
            };
            evaluate(a,ca);
            if(Clock::now()>=until&&!a.result.impossible)break;
            if(a.result.impossible){
                add_trace(a.result.trace);changed=add_fact(negate_clause(ca));
                if(changed){rebuild();break;}
                continue;
            }
            evaluate(b,cb);
            if(b.result.impossible){
                add_trace(b.result.trace);changed=add_fact(negate_clause(cb));
                if(changed){rebuild();break;}
                continue;
            }
            Clause common;
            std::set_intersection(a.implied.begin(),a.implied.end(),b.implied.begin(),b.implied.end(),std::back_inserter(common));
            Clauses conclusions;
            for(int l:common){
                if(std::abs(l)==v||fixed[std::abs(l)]>=0)continue;
                Clause c=guarded(l);
                if(!subsumed_short(c,known))conclusions.push_back(std::move(c));
                if(conclusions.size()>=24)break;
            }
            if(conclusions.empty())continue;
            // Child traces establish G OR -v OR l and G OR v OR l.
            // Their resolvent G OR l is RUP with both traces present.
            add_trace(a.result.trace);add_trace(b.result.trace);
            for(const auto& c:conclusions)if(add_fact(c)){out.trace.push_back(c);++st.consensus;changed=true;}
            if(changed){rebuild();break;}
        }
        if(!changed)break;
    }
    if(Clock::now()<until&&!prop->consistent(context))close();
    return out;
}
// The new stage reads only the original CNF and its own already emitted
// proof. The blackboard is compacted without removing any proof parents.
inline bool composition_tail(const Input& f,const Clauses& residual,Proof& proof,Time deadline,
                             CompositionStats& st){
    if(f.n>512||f.cs.size()>12000||Clock::now()>=deadline)return false;
    DiscoveryStats memory;
    auto active=load_blackboard(f,residual,proof,std::min(deadline,after(.35)),memory);
    st.memory_loaded=memory.loaded;
    compact_blackboard(f,active,memory);
    if(root_conflict(f.n,active,proof))return true;
    // Versioned context agenda: reconsider a context only when the
    // shared database has changed, or a new width/rank policy opens.
    std::map<Clause,int> visited;
    int version=0;
    for(int epoch=0;epoch<6&&Clock::now()<deadline&&st.proof_lines<220000;++epoch){
        ++st.epochs;
        auto prop=std::make_unique<AdaptivePropagator>(f.n,active);
        Clause rank=source_rank(f,active,*prop,std::min(deadline,after(.08)));
        if(rank.empty())break;
        std::set<Clause> known(active.begin(),active.end());
        std::vector<Clause> agenda{{}};
        size_t top=std::min(rank.size(),size_t(36+12*epoch));
        if(epoch&&rank.size()>top){
            size_t head=top/2,tail=rank.size()-head;
            std::rotate(rank.begin()+head,rank.begin()+head+(size_t(epoch)*19)%tail,rank.end());
        }
        for(size_t i=0;i<top;++i)for(int sign:{1,-1})agenda.push_back({sign*rank[i]});
        if(epoch>=2){
            // Connected pairs, selected from original-clause adjacency.
            std::set<std::pair<int,int>> edges;
            std::vector<int> priority(f.n+1,int(rank.size()));
            for(int i=0;i<int(rank.size());++i)priority[rank[i]]=i;
            for(const auto& c:f.cs)if(c.size()<=4)
                for(size_t i=0;i<c.size();++i)for(size_t j=i+1;j<c.size();++j){
                    int a=std::abs(c[i]),b=std::abs(c[j]);if(a>b)std::swap(a,b);
                    if(a!=b&&(priority[a]<int(top)||priority[b]<int(top)))edges.emplace(a,b);
                }
            std::vector<std::pair<int,int>> pairs(edges.begin(),edges.end());
            std::sort(pairs.begin(),pairs.end(),[&](auto a,auto b){
                return std::make_tuple(priority[a.first]+priority[a.second],a)<
                       std::make_tuple(priority[b.first]+priority[b.second],b);
            });
            if(pairs.size()>size_t(50+20*epoch))pairs.resize(50+20*epoch);
            for(auto [a,b]:pairs)for(int x:{a,-a})for(int y:{b,-b})agenda.push_back({x,y});
        }
        int accepted=0;
        for(const auto& ctx:agenda){
            if(Clock::now()>=deadline||accepted>=600||active.size()>18000||st.proof_lines>=220000)break;
            Clause key=ctx;normalize(key);
            if(!ctx.empty()&&subsumed_short(negate_clause(ctx),known))continue;
            int stamp=epoch*100000+version;
            if(auto it=visited.find(key);it!=visited.end()&&it->second==stamp)continue;
            visited[key]=stamp;++st.outer_contexts;
            // Reserve time for changing contexts instead of one costly branch.
            double budget=ctx.empty()?0.9:ctx.size()==1?0.20:0.09;
            if(epoch>=3)budget*=1.5;
            Time end=std::min(deadline,after(budget));
            int pivots=ctx.empty()?128:ctx.size()==1?48+8*epoch:22+6*epoch;
            auto r=compose_context(f.n,active,ctx,rank,end,st,pivots,epoch);
            if(ctx.size()==2&&!r.impossible)continue;
            Clauses fresh;
            for(const auto& c:r.facts)if(!subsumed_short(c,known)&&std::find(fresh.begin(),fresh.end(),c)==fresh.end())fresh.push_back(c);
            if(fresh.empty())continue;
            if(st.proof_lines+r.trace.size()>220000)break;
            for(const auto& c:r.trace){proof.add(c);++st.proof_lines;}
            for(const auto& c:fresh){
                if(c.empty())return true;
                if(known.insert(c).second){active.push_back(c);++accepted;++st.global_facts;}
            }
            ++version;
            if(root_conflict(f.n,active,proof))return true;
            // New root units get priority via the next root closure.
            if(std::any_of(fresh.begin(),fresh.end(),[](const Clause& c){return c.size()==1;}))break;
        }
        compact_blackboard(f,active,memory);st.compacted=memory.compacted;
        if(root_conflict(f.n,active,proof))return true;
    }
    return false;
}
} // namespace toolbox
