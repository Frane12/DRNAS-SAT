#pragma once
#include "discovery_reason.hpp"
#include <array>
#include <cstdlib>
namespace toolbox {
struct FactorStats {
    int rounds=0,bags=0,bag_max=0,boundaries=0,projections=0,prime_cubes=0,
        novel=0,wide=0,units=0,binaries=0,joins=0,global_blocked=0,stalls=0,
        proof_lines=0,mode=0,root_before=0,root_after=0;
    uint64_t rows=0,feasible=0;
    int trace_attempts=0,trace_failures=0,trace_deadlines=0;
};
struct FactorRow { unsigned pos,neg; };
struct FactorTable {
    Clause scope;
    std::vector<unsigned> allowed;
    bool complete=false;
};
#include "table_messages.hpp"
// Exact local Boolean factor: a join of all supplied clausal relations.
inline FactorTable factor_table(const Clause& scope,const Clauses& local,Time until){
    FactorTable t;t.scope=scope;
    if(scope.size()>16)return t;
    std::map<int,int> loc;for(int i=0;i<int(scope.size());++i)loc[scope[i]]=i;
    std::vector<FactorRow> rows;
    for(const auto& c:local){
        FactorRow r{0,0};
        for(int l:c){
            auto it=loc.find(std::abs(l));if(it==loc.end())throw std::logic_error("factor premise outside scope");
            if(l>0)r.pos|=1u<<it->second;else r.neg|=1u<<it->second;
        }
        rows.push_back(r);
    }
    for(unsigned m=0;m<(1u<<scope.size());++m){
        if((m&127u)==0&&Clock::now()>=until)return t;
        bool ok=true;for(auto r:rows)if(!(m&r.pos)&&!((~m)&r.neg)){ok=false;break;}
        if(ok)t.allowed.push_back(m);
    }
    t.complete=true;return t;
}
inline std::vector<unsigned char> factor_project(const FactorTable& t,const Clause& boundary){
    if(!t.complete||boundary.size()>8)throw std::logic_error("incomplete or oversized factor projection");
    Clause ix;
    for(int v:boundary){
        auto it=std::find(t.scope.begin(),t.scope.end(),v);
        if(it==t.scope.end())throw std::logic_error("boundary outside scope");
        ix.push_back(int(it-t.scope.begin()));
    }
    std::vector<unsigned char> seen(1u<<boundary.size(),0);
    for(unsigned m:t.allowed){
        unsigned b=0;for(size_t i=0;i<ix.size();++i)b|=((m>>ix[i])&1u)<<i;
        seen[b]=1;
    }
    return seen;
}
// Combine all adjacent absent rows into maximal forbidden subcubes.
// Each pair of children with opposite polarity resolves to its parent.
// The cube set is independent of CNF naming or variable polarity.
inline Clauses factor_prime_blockers(const Clause& vs,const std::vector<unsigned char>& seen,Time until){
    if(vs.size()>8||seen.size()!=(1u<<vs.size()))throw std::logic_error("bad factor shape");
    using Cube=std::pair<unsigned,unsigned>; // mask, assignment
    std::set<Cube> level;Clauses out;unsigned full=(1u<<vs.size())-1;
    for(unsigned a=0;a<seen.size();++a)if(!seen[a])level.emplace(full,a);
    while(!level.empty()){
        if(Clock::now()>=until)return {};
        std::set<Cube> next;
        for(auto [mask,a]:level){
            bool merged=false;
            for(size_t j=0;j<vs.size();++j)if(mask&(1u<<j)){
                unsigned b=1u<<j;
                if(level.count({mask,a^b})){
                    merged=true;next.emplace(mask^b,a&~b);
                }
            }
            if(!merged){
                Clause c;for(size_t j=0;j<vs.size();++j)if(mask&(1u<<j))c.push_back((a&(1u<<j))?-vs[j]:vs[j]);
                normalize(c);out.push_back(std::move(c));
            }
        }
        level.swap(next);
    }
    std::sort(out.begin(),out.end(),[](const Clause&a,const Clause&b){return a.size()!=b.size()?a.size()<b.size():a<b;});
    out.erase(std::unique(out.begin(),out.end()),out.end());return out;
}
inline bool factor_stage(const Input& f,Clauses& work,Model& fixed,Proof& proof,Time until,FactorStats& st,int mode,TableMessages* direct=nullptr){
    st.mode=mode;
    if(f.n<32||f.n>512||f.cs.size()>12000||work.empty()||Clock::now()>=until)return true;
    DiscoveryStats mem;
    Clauses active=load_blackboard(f,work,proof,std::min(until,after(.05)),mem);
    if(active.size()>12000||Clock::now()>=until)return true;
    std::set<Clause> known(active.begin(),active.end()),working(work.begin(),work.end()),source(f.cs.begin(),f.cs.end());
    AdaptivePropagator root(f.n,active);
    if(!root.consistent()){proof.add({});return false;}
    st.root_before=int(root.trail.size());st.root_after=st.root_before;
    std::set<Clause> visited;
    for(int epoch=0;epoch<3&&Clock::now()<until&&st.novel<220;++epoch){
        ++st.rounds;
        // Rebuild overlapping factor graph from original and new short facts.
        Input graph_input{f.n,active};BagDiscovery graph(graph_input);
        std::vector<std::vector<int>> occurrence(f.n+1);
        for(int i=0;i<int(active.size());++i)if(active[i].size()<=8)
            for(int l:active[i])occurrence[std::abs(l)].push_back(i);
        Clause seeds;
        for(int v=1;v<=f.n;++v)if(graph.degree[v]&&fixed[v]<0)seeds.push_back(v);
        std::sort(seeds.begin(),seeds.end(),[&](int a,int b){
            return std::make_pair(graph.degree[a],-a)>std::make_pair(graph.degree[b],-b);
        });
        if(seeds.empty())break;
        std::rotate(seeds.begin(),seeds.begin()+(size_t(epoch)*19)%seeds.size(),seeds.end());
        int start=st.novel,round_bags=0;
        for(int seed:seeds){
            if(Clock::now()>=until||round_bags>=16||st.novel>=220||st.proof_lines>=45000)break;
            int width=std::min(16,12+2*epoch);
            Clause bag=graph.build(seed,width,epoch);
            if(bag.size()<4||!visited.insert(bag).second)continue;
            std::vector<int> loc(f.n+1,-1);
            for(int i=0;i<int(bag.size());++i)loc[bag[i]]=i;
            std::set<int> ids;
            for(int v:bag)ids.insert(occurrence[v].begin(),occurrence[v].end());
            Clauses local;std::vector<int> inside(f.n+1),outside(f.n+1);
            for(int j:ids){
                const auto& c=active[j];bool fits=true;
                for(int l:c)if(loc[std::abs(l)]<0){fits=false;break;}
                if(fits){
                    local.push_back(c);
                    for(int l:c)++inside[std::abs(l)];
                    if(!source.count(c))++st.joins;
                }else for(int l:c)if(loc[std::abs(l)]>=0)++outside[std::abs(l)];
            }
            if(local.size()<3||local.size()>700)continue;
            ++round_bags;++st.bags;st.bag_max=std::max(st.bag_max,int(bag.size()));
            // Bounded exact truth-table join; no inference from incomplete tables.
            auto end=std::min(until,after(.045));
            auto table=factor_table(bag,local,end);
            if(!table.complete)continue;
            st.rows+=1u<<bag.size();st.feasible+=table.allowed.size();
            AdaptivePropagator local_prop(f.n,local);
            std::vector<int> premise_ids;
            Clauses source_local;
            FactorTable source_table;
            bool source_ready = false;
            auto record_table = [&](const Clause& claim) {
                if (!direct || direct->accepted >= 24 || Clock::now() >= until) return false;
                if (!source_ready) {
                    for (const auto& premise : local) {
                        auto found = direct->source_ids.find(premise);
                        if (found != direct->source_ids.end()) {
                            premise_ids.push_back(found->second);
                            source_local.push_back(premise);
                        }
                    }
                    if (source_local.size() != local.size() && !source_local.empty())
                        source_table = factor_table(bag, source_local, std::min(until, after(.045)));
                    source_ready = true;
                }
                // Global probes and derived local premises may have deleted rows.
                // Recheck the candidate against original clauses alone.
                const auto& witness = source_local.size() == local.size() ? table : source_table;
                return direct->record(claim, witness, premise_ids, until);
            };
            int before=st.novel;
            auto emit=[&](Clause c,AdaptivePropagator& prop,const Clause& support,Time limit){
                if(Clock::now()>=limit||st.novel>=220||st.proof_lines>=45000||subsumed_short(c,known))return false;
                Clause target_vars;for(int l:c)target_vars.push_back(std::abs(l));
                Clause hidden;
                std::set_difference(support.begin(),support.end(),target_vars.begin(),target_vars.end(),std::back_inserter(hidden));
                Clauses trace;
                bool stored = direct && direct->first && record_table(c);
                if (!stored) {
                    ++st.trace_attempts;
                    if (region_trace(prop,c,hidden,trace,limit) && st.proof_lines+int(trace.size())<=45000) {
                        for(const auto& q:trace){proof.add(q);++st.proof_lines;}
                    } else {
                        ++st.trace_failures;
                        if (Clock::now() >= limit) ++st.trace_deadlines;
                        if (!direct || direct->first || !record_table(c)) return false;
                        stored = true;
                    }
                }
                // The CORE integration installs source-certified premises before
                // replaying this stream. Standalone callers never enable direct mode.
                if (stored) proof.add(c);
                known.insert(c);active.push_back(c);++st.novel;
                st.wide+=c.size()>3;st.units+=c.size()==1;st.binaries+=c.size()==2;
                bool free=true;for(int l:c)if(fixed[std::abs(l)]>=0){free=false;break;}
                if(free&&working.insert(c).second)work.push_back(c);
                return true;
            };
            if(table.allowed.empty()){
                if(emit({},local_prop,bag,until))return false;
                continue;
            }
            // Two projections of the same joint factor: separator-facing and
            // interior-facing. A 4--8 variable boundary may expose a relation
            // which no individual variable probe can express.
            for(int shape=0;shape<2&&Clock::now()<until&&st.novel-before<24;++shape){
                Clause boundary=bag;
                std::sort(boundary.begin(),boundary.end(),[&](int a,int b){
                    auto score=[&](int v){return shape==0?8*outside[v]+inside[v]:8*inside[v]+outside[v];};
                    return std::make_pair(score(a),-a)>std::make_pair(score(b),-b);
                });
                boundary.resize(std::min<size_t>(8,boundary.size()));
                std::sort(boundary.begin(),boundary.end());
                ++st.boundaries;auto seen=factor_project(table,boundary);++st.projections;
                // Optional stronger representation: intersect the local factor
                // projection with globally RUP-forbidden boundary rows.
                // Such rows are proof checked immediately on use.
                if(mode==2){
                    AdaptivePropagator global(f.n,active);
                    for(unsigned m=0;m<seen.size()&&Clock::now()<until;++m)if(seen[m]){
                        Clause c=blocker(boundary,m);
                        if(!global.consistent(negate_clause(c))){seen[m]=0;++st.global_blocked;}
                    }
                }
                auto primes=factor_prime_blockers(boundary,seen,until);
                st.prime_cubes+=int(primes.size());
                for(auto c:primes){
                    if(st.novel-before>=24||Clock::now()>=until)break;
                    if(c.size()>6)continue;
                    // Local factor alone is a proof source. If intersected
                    // with global information, use all active clauses and
                    // the union of local and boundary hidden variables.
                    if(mode==2){
                        AdaptivePropagator global(f.n,active);
                        if(emit(c,global,bag,std::min(until,after(.018)))&&c.empty())return false;
                    }else if(emit(c,local_prop,bag,std::min(until,after(.018)))&&c.empty())return false;
                }
            }
            if(st.novel>before){
                AdaptivePropagator check(f.n,active);
                if(!check.consistent()){proof.add({});return false;}
                st.root_after=int(check.trail.size());
                // Rebuild factor graph and occurrence index after new facts.
                break;
            }
        }
        if(st.novel==start)++st.stalls;
        else visited.clear();
        if(st.stalls>=2)break;
    }
    return true;
}
} // namespace toolbox
