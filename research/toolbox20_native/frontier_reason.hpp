#pragma once
#include "composition_reason.hpp"
#include <cstdlib>
namespace toolbox {
struct FrontierStats {
    int rounds=0,contexts=0,probes=0,novel=0,units=0,binaries=0,
        root_before=0,root_after=0,stalls=0,policy=0,proof_lines=0;
};
inline int frontier_policy(){
    const char* s=std::getenv("DRNAS_U7_POLICY");
    return s&&s[0]>='0'&&s[0]<='2'?s[0]-'0':0;
}
// Bounded proof-frontier exploration. All emitted clauses retain the original
// proof parents. No global decision stack, backjumping or CDCL.
inline bool frontier_stage(const Input& f,Clauses& work,Model& fixed,Proof& proof,
                           Time until,FrontierStats& st){
    if(f.n<32||f.n>512||f.cs.size()>12000||work.empty())return true;
    st.policy=frontier_policy();
    DiscoveryStats mem;
    Clauses active=load_blackboard(f,work,proof,std::min(until,after(.07)),mem);
    if(active.size()>18000||Clock::now()>=until)return true;
    std::set<Clause> known(active.begin(),active.end()),orig(f.cs.begin(),f.cs.end()),
        working(work.begin(),work.end());
    std::vector<int> degree(f.n+1),residual(f.n+1),recent(f.n+1),pos(f.n+1),neg(f.n+1);
    for(const auto& c:f.cs)for(int l:c){++degree[std::abs(l)];}
    for(const auto& c:work)for(int l:c){
        int v=std::abs(l);++residual[v];++(l>0?pos[v]:neg[v]);
    }
    for(const auto& c:active)if(c.size()<=3&&!orig.count(c))
        for(int l:c)recent[std::abs(l)]+=4-int(c.size());
    auto prop=std::make_unique<AdaptivePropagator>(f.n,active);
    if(!prop->consistent()){proof.add({});return false;}
    st.root_before=int(prop->trail.size());
    auto add=[&](const Clause& c){
        if(!known.insert(c).second)return false;
        active.push_back(c);++st.novel;
        if(c.size()==1)++st.units;
        if(c.size()==2)++st.binaries;
        for(int l:c)recent[std::abs(l)]+=5-int(c.size());
        // Only import clauses over unfixed variables into the reduced work.
        // The proof blackboard retains everything, including guarded facts.
        bool free=true;
        for(int l:c)if(fixed[std::abs(l)]>=0){free=false;break;}
        if(free&&working.insert(c).second)work.push_back(c);
        return true;
    };
    std::set<Clause> visited;
    for(int epoch=0;epoch<5&&Clock::now()<until&&st.novel<180;++epoch){
        ++st.rounds;
        if(!prop->consistent()){proof.add({});return false;}
        Model root=prop->state;
        Clause rank;std::vector<int> score(f.n+1);
        int policy=(st.policy+st.stalls)%3;
        for(int v=1;v<=f.n;++v)if(root[v]<0&&residual[v]){
            rank.push_back(v);
            if(policy==0)score[v]=degree[v];
            else if(policy==1)score[v]=4*residual[v]+8*recent[v]+2*std::min(pos[v],neg[v]);
            else{
                if(Clock::now()>=until)break;
                bool p=prop->consistent({v});int a=int(prop->trail.size());
                bool q=prop->consistent({-v});int b=int(prop->trail.size());st.probes+=2;
                score[v]=(!p||!q)?100000+std::max(a,b):4*std::min(a,b)+std::max(a,b);
            }
        }
        std::sort(rank.begin(),rank.end(),[&](int a,int b){
            return std::make_pair(score[a],-a)>std::make_pair(score[b],-b);
        });
        if(rank.empty())break;
        if(rank.size()>64)rank.resize(64);
        // Open a different portion of the same source-derived frontier
        // after a no-progress round; reopen contexts when facts are added.
        if(epoch&&rank.size()>16)std::rotate(rank.begin()+8,rank.begin()+8+(size_t(epoch)*9)%(rank.size()-8),rank.end());
        int prior=st.novel;
        std::vector<Clause> todo{{}};
        for(int v:rank){todo.push_back({v});todo.push_back({-v});}
        // In later rounds connect highly ranked symbols appearing in
        // the same original or derived clause; never enumerate all assignments.
        if(epoch>=1){
            std::set<std::pair<int,int>> edges;
            std::set<int> head(rank.begin(),rank.begin()+std::min<size_t>(24,rank.size()));
            for(const auto& c:active)if(c.size()<=3)
                for(size_t i=0;i<c.size();++i)for(size_t j=i+1;j<c.size();++j){
                    int a=std::abs(c[i]),b=std::abs(c[j]);
                    if(a>b)std::swap(a,b);
                    if(a!=b&&head.count(a)&&head.count(b))edges.emplace(a,b);
                }
            std::vector<std::pair<int,int>> ordered(edges.begin(),edges.end());
            std::sort(ordered.begin(),ordered.end(),[&](auto a,auto b){
                return std::make_pair(score[a.first]+score[a.second],a)>
                       std::make_pair(score[b.first]+score[b.second],b);
            });
            int limit=0;
            // Place pair contexts before single contexts in later epochs.
            std::vector<Clause> pairs;
            for(auto [a,b]:ordered){
                if(limit++>=40)break;
                for(int x:{a,-a})for(int y:{b,-b})pairs.push_back({x,y});
            }
            todo.insert(todo.begin()+1,pairs.begin(),pairs.end());
        }
        int count=0;
        for(auto ctx:todo){
            if(Clock::now()>=until||st.novel>=180||count++>=120)break;
            normalize(ctx);
            if(!visited.insert(ctx).second)continue;
            if(!ctx.empty()&&subsumed_short(negate_clause(ctx),known))continue;
            ++st.contexts;
            DiscoveryStats local;
            // Short fixed-point deductions under a context. The context
            // is discharged by guarded RUP lines or by resolution.
            auto end=std::min(until,after(ctx.empty()?.025:.009));
            auto r=close_context(*prop,ctx,rank,end,local,ctx.empty()?220:100,32);
            st.probes+=int(local.local_trials);
            Clauses fresh;
            for(auto c:r.facts){
                if(!normalize(c)||subsumed_short(c,known))continue;
                if(c.size()>3)continue;
                fresh.push_back(std::move(c));
            }
            if(fresh.empty())continue;
            if(st.proof_lines+int(r.trace.size())>22000)break;
            for(const auto& c:r.trace){proof.add(c);++st.proof_lines;}
            for(const auto& c:fresh){
                if(c.empty())return false;
                add(c);
            }
            prop=std::make_unique<AdaptivePropagator>(f.n,active);
            if(!prop->consistent()){proof.add({});return false;}
            st.root_after=int(prop->trail.size());
            if(st.root_after>st.root_before&&st.units>0)break;
        }
        if(st.novel==prior)++st.stalls;
        else visited.clear();
        if(st.stalls>=3)break;
    }
    if(!prop->consistent()){proof.add({});return false;}
    st.root_after=int(prop->trail.size());
    return true;
}
} // namespace toolbox
