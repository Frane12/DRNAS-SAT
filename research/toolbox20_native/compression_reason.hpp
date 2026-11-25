#pragma once
#include "discovery_reason.hpp"
#include <functional>
#include <numeric>

namespace toolbox {
struct CompressionStats {
    int epochs=0,loaded=0,removed=0,equivalent=0,rewritten=0,ssr=0,
        pivots=0,resolvents=0,peak=0,best_vars=0,capacity_checks=0,capacity_deficit=0,
        demand=0,capacity=0;
    uint64_t ssr_checks=0,plans=0,pair_checks=0,proof_lines=0;
};
inline bool subset_fast(const Clause& a,const Clause& b){
    if(a.size()>b.size())return false;
    for(int l:a)if(std::find(b.begin(),b.end(),l)==b.end())return false;
    return true;
}
inline bool short_subsumed(const Clause& c,const std::set<Clause>& known){
    if(known.count(c)||known.count(Clause{}))return true;
    for(int l:c)if(known.count(Clause{l}))return true;
    for(size_t i=0;i<c.size();++i)for(size_t j=i+1;j<c.size();++j)
        if(known.count(Clause{c[i],c[j]}))return true;
    if(c.size()>=4&&c.size()<=12)
        for(size_t i=0;i<c.size();++i){
            Clause d=c;d.erase(d.begin()+i);if(known.count(d))return true;
        }
    if(c.size()<=6)return subsumed_short(c,known);
    return false;
}
inline void compact_exact(Clauses& cs,CompressionStats& st){
    std::sort(cs.begin(),cs.end(),[](const Clause&a,const Clause&b){
        if(a.size()!=b.size())return a.size()<b.size();return a<b;
    });
    std::set<Clause> kept;Clauses out;out.reserve(cs.size());
    for(const auto& c:cs)if(!short_subsumed(c,kept)){kept.insert(c);out.push_back(c);}
    st.removed+=int(cs.size()-out.size());cs=std::move(out);
    st.peak=std::max(st.peak,int(cs.size()));
}
inline bool compress_root(int n,Clauses& cs,Proof& proof,CompressionStats& st){
    Model fixed(n+1,-1);
    if(!reduce_root(n,cs,fixed,proof))return false;
    // Retain root units in the working state for the remaining transforms.
    for(int v=1;v<=n;++v)if(fixed[v]>=0)cs.push_back({fixed[v]?v:-v});
    compact_exact(cs,st);return true;
}
// Binary implication SCCs identify signed equivalences, not guessed
// correlations. Every representative mapping has explicit RUP implications.
inline bool equivalence_compress(int n,Clauses& cs,Proof& proof,Time until,CompressionStats& st){
    std::vector<std::vector<int>> graph(2*n),rev(2*n);
    auto edge=[&](int a,int b){int u=index_of(a),v=index_of(b);graph[u].push_back(v);rev[v].push_back(u);};
    for(const auto& c:cs)if(c.size()==2){edge(-c[0],c[1]);edge(-c[1],c[0]);}
    std::vector<bool> seen(2*n);std::vector<int> order,comp(2*n,-1);
    std::function<void(int)> dfs=[&](int u){seen[u]=true;for(int v:graph[u])if(!seen[v])dfs(v);order.push_back(u);};
    for(int i=0;i<2*n;++i)if(!seen[i])dfs(i);
    std::function<void(int,int)> assign=[&](int u,int c){comp[u]=c;for(int v:rev[u])if(comp[v]<0)assign(v,c);};
    int k=0;for(auto it=order.rbegin();it!=order.rend();++it)if(comp[*it]<0)assign(*it,k++);
    auto literal=[](int i){return (i&1)?-(i/2+1):(i/2+1);};
    std::vector<int> rep(k,0);
    for(int i=0;i<2*n;++i){
        int l=literal(i),&r=rep[comp[i]];
        if(!r||std::abs(l)<std::abs(r))r=l;
    }
    for(int v=1;v<=n;++v)if(comp[index_of(v)]==comp[index_of(-v)]){
        proof.add({v});proof.add({-v});proof.add({});st.proof_lines+=3;return false;
    }
    std::vector<int> subst(n+1);
    std::set<Clause> known(cs.begin(),cs.end());
    auto record=[&](Clause c){
        if(normalize(c)&&known.insert(c).second){proof.add(c);++st.proof_lines;}
    };
    bool changed=false;
    for(int v=1;v<=n;++v){
        subst[v]=rep[comp[index_of(v)]];
        if(subst[v]==v)continue;
        if(Clock::now()>=until)return true; // no rewrite until all equivalences certified
        int r=subst[v];record({-v,r});record({v,-r});
        ++st.equivalent;changed=true;
    }
    if(!changed)return true;
    Clauses out;out.reserve(cs.size());
    for(const auto& c:cs){
        Clause d;for(int l:c)d.push_back(l>0?subst[l]:-subst[-l]);
        if(!normalize(d)){++st.removed;continue;}
        if(d!=c){record(d);++st.rewritten;}
        out.push_back(std::move(d));
    }
    cs=std::move(out);compact_exact(cs,st);return true;
}
// Self-subsuming resolution: replace C=l OR R by R when another
// clause -l OR S exists with S subset R. Both original parents remain
// in the proof stream. This is equivalence-preserving compression.
inline int ssr_round(int n,Clauses& cs,Proof& proof,Time until,CompressionStats& st){
    const Clauses snapshot=cs;
    std::vector<std::vector<int>> idx(2*n);
    for(int i=0;i<int(snapshot.size());++i)if(snapshot[i].size()<=6)
        for(int l:snapshot[i])idx[index_of(l)].push_back(i);
    std::set<Clause> known(cs.begin(),cs.end());uint64_t checks=0;int changed=0;
    for(auto& c:cs){
        if(Clock::now()>=until||checks>=350000)break;
        if(c.size()>18)continue;
        for(size_t i=0;i<c.size();){
            if(Clock::now()>=until||checks>=350000)break;
            int l=c[i];Clause r=c;r.erase(r.begin()+i);bool found=false;
            for(int id:idx[index_of(-l)]){
                if(++checks>350000)break;
                const auto& d=snapshot[id];if(d.size()>c.size())continue;
                bool fits=true;
                for(int x:d)if(x!=-l&&std::find(r.begin(),r.end(),x)==r.end()){fits=false;break;}
                if(fits){found=true;break;}
            }
            if(found){
                if(known.insert(r).second){proof.add(r);++st.proof_lines;}
                c=std::move(r);++st.ssr;++changed;
                if(c.empty()){st.ssr_checks+=checks;return changed;}
            }else ++i;
        }
    }
    st.ssr_checks+=checks;compact_exact(cs,st);return changed;
}
struct FillPlan {
    int pivot=0,parents=0,maxwidth=0;
    int64_t literal_delta=0;Clauses added;
    bool valid=false,contradiction=false;
};
// Calculate actual fill after tautology removal and subsumption by clauses
// that do not contain the pivot. Reject the whole plan if any necessary
// resolvent exceeds a bound. Thus a committed pivot is exact.
inline FillPlan plan_pivot(int v,const Clauses& cs,const std::set<Clause>& known,
                           const std::vector<int>& pos,const std::vector<int>& neg,
                           int width,int growth,int pair_cap,Time until,CompressionStats& st){
    FillPlan p;p.pivot=v;p.parents=int(pos.size()+neg.size());
    if(int64_t(pos.size())*neg.size()>pair_cap)return p;
    ++st.plans;
    int64_t parent_lits=0;for(int i:pos)parent_lits+=cs[i].size();for(int i:neg)parent_lits+=cs[i].size();
    std::set<Clause> proposed;
    for(int i:pos)for(int j:neg){
        ++st.pair_checks;
        if(Clock::now()>=until)return p;
        Clause r;
        for(int l:cs[i])if(l!=v)r.push_back(l);
        for(int l:cs[j])if(l!=-v)r.push_back(l);
        if(!normalize(r)||short_subsumed(r,known))continue;
        if(r.empty()){p.valid=true;p.contradiction=true;return p;}
        if(r.size()>size_t(width))return p;
        proposed.insert(std::move(r));
        if(proposed.size()>size_t(p.parents+growth*2+32))return p;
    }
    Clauses sorted(proposed.begin(),proposed.end());
    std::sort(sorted.begin(),sorted.end(),[](const Clause&a,const Clause&b){if(a.size()!=b.size())return a.size()<b.size();return a<b;});
    std::set<Clause> chosen;int64_t added_lits=0;
    for(const auto& r:sorted){
        if(short_subsumed(r,chosen))continue;
        chosen.insert(r);p.added.push_back(r);added_lits+=r.size();
        p.maxwidth=std::max(p.maxwidth,int(r.size()));
        if(p.added.size()>size_t(p.parents+growth))return p;
    }
    p.literal_delta=added_lits-parent_lits;p.valid=true;return p;
}
inline bool eliminate_fill(int n,Clauses& cs,Proof& proof,Time until,
                           CompressionStats& st,int epoch,int max_pivots){
    int width=std::min(18,6+epoch*2),growth=std::min(160,8+epoch*epoch*6);
    int pair_cap=std::min(10000,240+epoch*epoch*280);
    for(int step=0;step<max_pivots&&Clock::now()<until&&cs.size()<=18000;++step){
        if(root_conflict(n,cs,proof))return false;
        std::vector<std::vector<int>> idx(2*n);
        for(int i=0;i<int(cs.size());++i)for(int l:cs[i])idx[index_of(l)].push_back(i);
        std::vector<std::tuple<int64_t,int,int>> rank;
        for(int v=1;v<=n;++v){
            int a=idx[index_of(v)].size(),b=idx[index_of(-v)].size();
            if(a+b&&int64_t(a)*b<=pair_cap)rank.emplace_back(int64_t(a)*b,a+b,v);
        }
        std::sort(rank.begin(),rank.end());
        if(rank.empty())break;
        std::set<Clause> known(cs.begin(),cs.end());FillPlan best;
        auto key=[](const FillPlan& p){
            return std::make_tuple(int64_t(p.added.size())-p.parents,p.literal_delta,p.maxwidth,p.pivot);
        };
        int considered=0;
        for(auto [pairs,occ,v]:rank){
            if(Clock::now()>=until||considered++>=24)break;
            auto p=plan_pivot(v,cs,known,idx[index_of(v)],idx[index_of(-v)],width,growth,pair_cap,until,st);
            if(p.contradiction){proof.add({});++st.proof_lines;return false;}
            if(p.valid&&(!best.valid||key(p)<key(best)))best=std::move(p);
        }
        if(!best.valid||cs.size()+best.added.size()>19000)break;
        Clauses out;out.reserve(cs.size()+best.added.size());
        for(auto& c:cs)if(std::find(c.begin(),c.end(),best.pivot)==c.end()&&
                          std::find(c.begin(),c.end(),-best.pivot)==c.end())out.push_back(std::move(c));
        for(auto& c:best.added){proof.add(c);++st.proof_lines;++st.resolvents;out.push_back(std::move(c));}
        cs=std::move(out);++st.pivots;
        compact_exact(cs,st);
        if(!compress_root(n,cs,proof,st))return false;
    }
    return true;
}
// A capacity inequality from the current proved clauses. Disjoint literal
// demand groups each require >=1 true literal. Partition their union into
// pairwise-mutex cliques, each permitting <=1 true literal. If D>K the
// contradiction is a counting invariant, independent of variable names.
struct CapacityGraph {
    std::vector<std::vector<bool>> mutex;
    std::vector<int> degree;
    explicit CapacityGraph(int n,const Clauses& cs):mutex(2*n,std::vector<bool>(2*n)),degree(2*n){
        auto add=[&](int a,int b){int i=index_of(a),j=index_of(b);if(i!=j&&!mutex[i][j]){mutex[i][j]=mutex[j][i]=true;++degree[i];++degree[j];}};
        for(int v=1;v<=n;++v)add(v,-v);
        for(const auto& c:cs)if(c.size()==2)add(-c[0],-c[1]);
    }
    int cover(Clause lits,int policy)const{
        std::vector<int> weight(degree.size());
        for(int a:lits){int x=0;for(int l:lits)x+=mutex[index_of(a)][index_of(l)];
            if(policy==1)x+=degree[index_of(a)];weight[index_of(a)]=x;}
        std::sort(lits.begin(),lits.end(),[&](int a,int b){
            return std::make_pair(weight[index_of(a)],a)>std::make_pair(weight[index_of(b)],b);
        });
        std::vector<Clause> cliques;
        for(int l:lits){
            int best=-1;
            for(int i=0;i<int(cliques.size());++i){
                bool ok=true;for(int q:cliques[i])if(!mutex[index_of(l)][index_of(q)]){ok=false;break;}
                if(ok&&(best<0||cliques[i].size()>cliques[best].size()))best=i;
            }
            if(best<0)cliques.push_back({l});else cliques[best].push_back(l);
        }
        return int(cliques.size());
    }
};
// Standard RUP certificate of a *previously detected* small capacity
// deficit. The local expansion ranges over demand groups only; not a
// general CNF assignment search. No clause is committed on failure.
inline bool capacity_trace(int n,const Clauses& cs,const Clauses& groups,
                           Clauses& trace,Time until){
    AdaptivePropagator prop(n,cs);Clause chosen;
    auto go=[&](auto&& self,size_t i)->bool{
        if(Clock::now()>=until||trace.size()>=40000)return false;
        Clause guard=chosen;for(int& l:guard)l=-l;
        if(!normalize(guard))return true; // contradictory assumptions
        if(!prop.consistent(chosen)){trace.push_back(guard);return true;}
        if(i==groups.size())return false;
        for(int l:groups[i]){
            chosen.push_back(l);
            bool ok=self(self,i+1);chosen.pop_back();
            if(!ok)return false;
        }
        trace.push_back(std::move(guard));return true;
    };
    return go(go,0);
}
inline bool capacity_round(int n,const Clauses& cs,Proof& proof,Time until,CompressionStats& st){
    if(n>512||cs.size()>18000)return false;
    CapacityGraph graph(n,cs);Clauses candidates;
    for(const auto& c:cs)if(c.size()>=2&&c.size()<=5)candidates.push_back(c);
    auto score=[&](const Clause& c){int d=0;for(int l:c)d+=graph.degree[index_of(l)];return d/int(c.size());};
    std::sort(candidates.begin(),candidates.end(),[&](const Clause&a,const Clause&b){
        return std::make_tuple(a.size(),-score(a),a)<std::make_tuple(b.size(),-score(b),b);
    });
    if(candidates.size()>600)candidates.resize(600);
    for(size_t seed=0;seed<std::min<size_t>(candidates.size(),45)&&Clock::now()<until;++seed){
        Clauses groups{candidates[seed]};Clause unionl=candidates[seed];std::set<int> used(unionl.begin(),unionl.end());
        size_t combinations=unionl.size();
        for(int step=0;step<8&&Clock::now()<until;++step){
            int best=-1,bestscore=-1;
            for(int i=0;i<int(candidates.size());++i){
                const auto& c=candidates[i];bool disjoint=true;int cross=0;
                if(combinations*c.size()>18000)continue;
                for(int l:c){
                    if(used.count(l)){disjoint=false;break;}
                    for(int q:unionl)cross+=graph.mutex[index_of(l)][index_of(q)];
                }
                if(disjoint&&cross>0){
                    int s=100*cross/int(c.size())+score(c);
                    if(s>bestscore){best=i;bestscore=s;}
                }
            }
            if(best<0)break;
            const auto& c=candidates[best];groups.push_back(c);
            unionl.insert(unionl.end(),c.begin(),c.end());used.insert(c.begin(),c.end());combinations*=c.size();
            ++st.capacity_checks;
            int capacity=std::min(graph.cover(unionl,0),graph.cover(unionl,1));
            if(capacity>=int(groups.size()))continue;
            ++st.capacity_deficit;st.demand=int(groups.size());st.capacity=capacity;
            Clauses trace;
            if(!capacity_trace(n,cs,groups,trace,until))return false;
            for(const auto& q:trace){proof.add(q);++st.proof_lines;}
            return true;
        }
    }
    return false;
}
inline int remaining_vars(int n,const Clauses& cs){
    std::vector<bool> seen(n+1);for(const auto& c:cs)for(int l:c)seen[std::abs(l)]=true;
    return int(std::count(seen.begin(),seen.end(),true));
}
// Two proof-bound viewpoints: a lightly augmented original formula and
// the projected residual with short certified facts. The former can avoid
// the large fill caused by retaining thousands of wide consequences.
inline bool compression_tail(const Input& f,const Clauses& residual,Proof& proof,Time deadline,
                             CompressionStats& st){
    if(f.n>512||f.cs.size()>12000||Clock::now()>=deadline)return false;
    DiscoveryStats mem;
    Clauses all=load_blackboard(f,residual,proof,std::min(deadline,after(.30)),mem);
    st.loaded=mem.loaded;st.best_vars=f.n;
    // Only short consequences in the first view; longer original clauses
    // remain. Every dropped extra clause is entailed by the original.
    for(int view=0;view<2&&Clock::now()<deadline;++view){
        Clauses active=f.cs;
        std::set<Clause> known(active.begin(),active.end());
        std::stable_sort(all.begin(),all.end(),[](const Clause&a,const Clause&b){return a.size()<b.size();});
        int cap=view==0?2:3;
        for(const auto& c:all)if(c.size()<=size_t(cap)&&known.insert(c).second&&active.size()<9000)active.push_back(c);
        compact_exact(active,st);
        for(int epoch=0;epoch<5&&Clock::now()<deadline&&active.size()<18000;++epoch){
            ++st.epochs;
            double left=std::chrono::duration<double>(deadline-Clock::now()).count();
            Time end=std::min(deadline,after(std::min(1.25,left/std::max(1,3-epoch))));
            if(!compress_root(f.n,active,proof,st))return true;
            if(!equivalence_compress(f.n,active,proof,end,st))return true;
            if(!compress_root(f.n,active,proof,st))return true;
            for(int r=0;r<2&&Clock::now()<end;++r){
                if(!ssr_round(f.n,active,proof,end,st))break;
                if(!compress_root(f.n,active,proof,st))return true;
            }
            if(active.empty())break;
            if(capacity_round(f.n,active,proof,std::min(end,after(.08)),st))return true;
            if(!eliminate_fill(f.n,active,proof,end,st,epoch,32))return true;
            st.best_vars=std::min(st.best_vars,remaining_vars(f.n,active));
            if(root_conflict(f.n,active,proof))return true;
            if(active.empty())break;
        }
    }
    return false;
}
} // namespace toolbox
