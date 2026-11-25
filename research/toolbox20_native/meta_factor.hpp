#pragma once
#include "factor_reason.hpp"
#include <cmath>
namespace toolbox {
struct MetaStats {
    int epochs=0,attempts=0,changes=0,cache=0,joins=0,join_facts=0,affine=0,
        affine_facts=0,local=0,global=0,stalls=0,proof=0,novel=0,short_facts=0,
        min_width=99,max_width=0,root_before=0,root_after=0;
};
struct CachedFactor {Clause scope;Clauses clauses;};
struct MetaPolicy {int width,boundary,method;}; // 0 local, 1 global, 2 join, 3 affine
inline bool affine_table(const std::vector<unsigned char>& seen){
    unsigned first=0,count=0;
    for(unsigned i=0;i<seen.size();++i)if(seen[i]){if(!count)first=i;++count;}
    if(!count||(count&(count-1)))return false;
    // Closure of translated set under xor is necessary and sufficient.
    for(unsigned i=0;i<seen.size();++i)if(seen[i])
        for(unsigned j=0;j<seen.size();++j)if(seen[j]&&!seen[i^j^first])return false;
    return true;
}
inline Clauses parity_blockers(const Clause& boundary,const std::vector<unsigned char>& seen){
    Clauses out;
    if(!affine_table(seen))return out;
    unsigned first=0;while(first<seen.size()&&!seen[first])++first;
    if(first==seen.size())return out;
    // Derive independent dual-space parity masks over GF(2).
    std::array<unsigned,8> basis{};
    for(unsigned mask=1;mask<seen.size();++mask){
        bool valid=true;int rhs=__builtin_parity(mask&first);
        for(unsigned i=0;i<seen.size();++i)if(seen[i]&&__builtin_parity(mask&i)!=rhs){valid=false;break;}
        if(!valid)continue;
        unsigned r=mask;
        for(int j=7;j>=0;--j)if(r&(1u<<j)){if(basis[j])r^=basis[j];else{basis[j]=r;break;}}
        if(!r)continue;
        Clause vars;for(size_t j=0;j<boundary.size();++j)if(mask&(1u<<j))vars.push_back(boundary[j]);
        for(unsigned m=0;m<(1u<<vars.size());++m)if(__builtin_parity(m)!=rhs)out.push_back(blocker(vars,m));
    }
    return out;
}
inline bool meta_stage(const Input& f,Clauses& work,Model& fixed,Proof& proof,Time until,MetaStats& st,bool adaptive){
    if(f.n<32||f.n>512||f.cs.size()>12000||work.empty()||Clock::now()>=until)return true;
    DiscoveryStats mem;
    Clauses active=load_blackboard(f,work,proof,std::min(until,after(.05)),mem);
    if(active.size()>12000||Clock::now()>=until)return true;
    std::set<Clause> known(active.begin(),active.end()),working(work.begin(),work.end());
    AdaptivePropagator initial(f.n,active);
    if(!initial.consistent()){proof.add({});return false;}
    st.root_before=st.root_after=int(initial.trail.size());
    std::vector<CachedFactor> cache;
    const std::array<MetaPolicy,5> policies{{{12,6,1},{16,8,1},{10,6,0},{14,8,2},{14,8,3}}};
    std::array<double,5> utility{};std::array<int,5> used{};
    std::set<std::tuple<int,Clause,int>> tried;
    std::set<std::pair<size_t,size_t>> joined;
    int version=0,last=-1;
    bool contradiction=false;
    auto commit=[&](const Clause& c,const Clauses& trace){
        if(st.proof+int(trace.size())>42000)return false;
        for(const auto& q:trace){proof.add(q);++st.proof;}
        if(known.insert(c).second){
            active.push_back(c);++st.novel;st.short_facts+=c.size()<=2;
            if(c.empty()){contradiction=true;return true;}
            bool free=true;for(int l:c)if(fixed[std::abs(l)]>=0){free=false;break;}
            if(free&&working.insert(c).second)work.push_back(c);
        }
        return true;
    };
    auto process=[&](const Clause& scope,const Clauses& premises,Clause boundary,int method,Time end){
        if(premises.empty()||scope.size()>16||Clock::now()>=end)return;
        auto table=factor_table(scope,premises,std::min(end,after(.035)));
        if(!table.complete)return;
        st.min_width=std::min(st.min_width,int(scope.size()));st.max_width=std::max(st.max_width,int(scope.size()));
        if(table.allowed.empty())boundary.clear();
        auto seen=factor_project(table,boundary);
        bool global=method==1||method==2||method==3;
        AdaptivePropagator prop(f.n,global?active:premises);
        if(global){
            for(unsigned m=0;m<seen.size()&&Clock::now()<end;++m)if(seen[m]){
                if(!prop.consistent(negate_clause(blocker(boundary,m))))seen[m]=0;
            }
        }
        if(Clock::now()>=end)return;
        if(method==3&&affine_table(seen))++st.affine;
        // An affine table has an exact parity encoding. Otherwise use
        // maximal forbidden cubes. In both cases prove each clause.
        Clauses blockers;
        if(method==3)blockers=parity_blockers(boundary,seen);
        bool algebraic=!blockers.empty();
        if(!algebraic)blockers=factor_prime_blockers(boundary,seen,end);
        if(blockers.empty())return;
        std::sort(blockers.begin(),blockers.end(),[](const Clause&a,const Clause&b){return a.size()!=b.size()?a.size()<b.size():a<b;});
        Clauses encoded;bool complete=true;int added=0;
        for(auto c:blockers){
            normalize(c);
            if(c.size()>6||Clock::now()>=end||st.novel>=240||added>=28){complete=false;break;}
            // A known exact clause needs no new proof; keep it as a cache premise.
            if(!known.count(c)){
                Clause vars;for(int l:c)vars.push_back(std::abs(l));
                Clause hidden;std::set_difference(scope.begin(),scope.end(),vars.begin(),vars.end(),std::back_inserter(hidden));
                Clauses trace;
                if(!region_trace(prop,c,hidden,trace,std::min(end,after(.012)))||!commit(c,trace)){complete=false;continue;}
                ++added;if(method==2)++st.join_facts;if(algebraic)++st.affine_facts;
                if(contradiction)return;
            }
            encoded.push_back(c);
        }
        // Retain only completely proved encodings. Partial encodings may
        // contribute individual sound facts but are not cached as exact factors.
        if(complete&&encoded.size()==blockers.size()&&cache.size()<36&&!boundary.empty()){
            bool duplicate=false;for(const auto& x:cache)if(x.scope==boundary&&x.clauses==encoded){duplicate=true;break;}
            if(!duplicate){cache.push_back({boundary,encoded});++st.cache;}
        }
    };
    for(int epoch=0;epoch<18&&Clock::now()<until&&st.novel<240&&st.proof<42000;++epoch){
        ++st.epochs;
        int p=1;
        if(adaptive){
            p=-1;for(int i=0;i<5;++i)if(!used[i]&&(policies[i].method!=2||cache.size()>=2)){p=i;break;}
            if(p<0){
                double best=-1e100;
                for(int i=0;i<5;++i){
                    if(policies[i].method==2&&cache.size()<2)continue;
                    double s=utility[i]+.45*std::sqrt(std::log(2.+epoch)/(1+used[i]));
                    if(s>best){best=s;p=i;}
                }
            }
        }
        if(p<0)break;
        if(last>=0&&last!=p)++st.changes;
        last=p;++used[p];++st.attempts;
        auto policy=policies[p];auto start=Clock::now();auto end=std::min(until,after(.047));
        int before=st.novel,short_before=st.short_facts,root_before=st.root_after;
        bool ran=false;
        if(policy.method==2){
            size_t best_a=0,best_b=0;int best=-1;Clause best_scope,best_shared;
            for(size_t i=0;i<cache.size();++i)for(size_t j=i+1;j<cache.size();++j){
                if(joined.count({i,j}))continue;
                Clause u,s;std::set_union(cache[i].scope.begin(),cache[i].scope.end(),cache[j].scope.begin(),cache[j].scope.end(),std::back_inserter(u));
                std::set_intersection(cache[i].scope.begin(),cache[i].scope.end(),cache[j].scope.begin(),cache[j].scope.end(),std::back_inserter(s));
                if(s.empty()||u.size()>16||u.size()<4)continue;
                int merit=8*int(s.size())-int(u.size());
                if(merit>best){best=merit;best_a=i;best_b=j;best_scope=u;best_shared=s;}
            }
            if(best>=0){
                joined.insert({best_a,best_b});++st.joins;ran=true;
                Clauses premises=cache[best_a].clauses;premises.insert(premises.end(),cache[best_b].clauses.begin(),cache[best_b].clauses.end());
                Clause boundary;std::set_difference(best_scope.begin(),best_scope.end(),best_shared.begin(),best_shared.end(),std::back_inserter(boundary));
                if(boundary.empty())boundary=best_scope;
                if(boundary.size()>size_t(policy.boundary))boundary.resize(policy.boundary);
                process(best_scope,premises,boundary,2,end);
            }
        }
        if(!ran){
            Input graph_input{f.n,active};BagDiscovery graph(graph_input);
            Clause seeds;for(int v=1;v<=f.n;++v)if(graph.degree[v]&&fixed[v]<0)seeds.push_back(v);
            std::sort(seeds.begin(),seeds.end(),[&](int a,int b){return std::make_pair(graph.degree[a],-a)>std::make_pair(graph.degree[b],-b);});
            if(!seeds.empty())std::rotate(seeds.begin(),seeds.begin()+(size_t(epoch)*7)%seeds.size(),seeds.end());
            for(int seed:seeds){
                if(Clock::now()>=end)break;
                Clause scope=graph.build(seed,policy.width,epoch);
                if(scope.size()<4||!tried.insert({p,scope,version}).second)continue;
                std::vector<int> loc(f.n+1),inside(f.n+1),outside(f.n+1);
                for(int v:scope)loc[v]=1;
                Clauses local;
                for(const auto& c:active){
                    bool fits=true;for(int l:c)if(!loc[std::abs(l)]){fits=false;break;}
                    if(fits){local.push_back(c);for(int l:c)++inside[std::abs(l)];}
                    else for(int l:c)if(loc[std::abs(l)])++outside[std::abs(l)];
                }
                if(local.size()<3||local.size()>700)continue;
                Clause boundary=scope;
                std::sort(boundary.begin(),boundary.end(),[&](int a,int b){
                    auto score=[&](int v){return (epoch%2)?8*inside[v]+outside[v]:8*outside[v]+inside[v];};
                    return std::make_pair(score(a),-a)>std::make_pair(score(b),-b);
                });
                boundary.resize(std::min<size_t>(boundary.size(),policy.boundary));std::sort(boundary.begin(),boundary.end());
                int method=policy.method==2?1:policy.method;
                if(method==0)++st.local;else ++st.global;
                process(scope,local,boundary,method,end);break;
            }
        }
        if(contradiction)return false;
        AdaptivePropagator check(f.n,active);
        if(!check.consistent()){proof.add({});return false;}
        st.root_after=int(check.trail.size());
        int gain=st.novel-before,short_gain=st.short_facts-short_before;
        int root_gain=std::max(0,st.root_after-root_before);
        double ms=1000*std::chrono::duration<double>(Clock::now()-start).count();
        double reward=(8.*root_gain+3.*short_gain+.15*gain)/std::max(1.,ms);
        utility[p]+=(reward-utility[p])/used[p];
        if(gain){++version;st.stalls=0;}else ++st.stalls;
        if(st.stalls>=6)break;
    }
    return true;
}
} // namespace toolbox
