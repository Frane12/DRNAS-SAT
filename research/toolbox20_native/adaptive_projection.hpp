#pragma once
#include "formula.hpp"
#include <map>
#include <queue>
#include <tuple>

namespace toolbox {
// A Davis-Putnam projection is committed atomically, only if every non-tautological
// resolvent fits. Parents stay in the proof database and in the reconstruction frame.
struct ProjectionPolicy { int pairs=256, growth=32, width=16; size_t total=24000; };
class AdaptiveProjection {
    ProjectionPolicy policy;
    struct Frame { int variable; std::vector<int> parents; };
    using Priority = std::tuple<int64_t,int,int>; // pair count, occurrence count, variable
    Clauses db;
    std::map<Clause,int> active;
    std::vector<bool> live;
    std::vector<std::vector<int>> index;
    std::vector<int> count;
    std::priority_queue<Priority,std::vector<Priority>,std::greater<Priority>> queue;
    std::vector<Frame> frames;
    Priority priority(int v) const {
        int p=count[index_of(v)], q=count[index_of(-v)];
        return {int64_t(p)*q,p+q,v};
    }
    void reschedule(int v) {
        auto key=priority(v);
        if (std::get<0>(key)<=policy.pairs && std::get<1>(key)>0) queue.push(key);
    }
    void insert(const Clause& c) {
        int id=int(db.size()); active.emplace(c,id); db.push_back(c); live.push_back(true);
        for (int l:c) { index[index_of(l)].push_back(id); ++count[index_of(l)]; }
    }
    std::vector<int> parents(int lit) const {
        std::vector<int> ids;
        for (int id:index[index_of(lit)]) if (live[id]) ids.push_back(id);
        return ids;
    }
public:
    int projected=0, generated=0;
    bool blocked=false;
    AdaptiveProjection(int n,const Clauses& cs,ProjectionPolicy limits):policy(limits),index(2*n),count(2*n) {
        for (const auto& c:cs) if (!active.count(c)) insert(c);
        for (int v=1; v<=n; ++v) reschedule(v);
    }
    bool run(Proof& proof,Time until) {
        const size_t initial=db.size();
        while (!queue.empty() && Clock::now()<until && db.size()<initial+policy.total) {
            auto key=queue.top(); queue.pop(); int v=std::get<2>(key);
            if (key!=priority(v)) continue;
            // Repeated heap entries for this pivot from older neighbor updates.
            while (!queue.empty() && queue.top()==key) queue.pop();
            auto pos=parents(v), neg=parents(-v);
            std::set<Clause> added;
            bool eligible=true; int checks=0;
            for (int p:pos) {
                for (int q:neg) {
                    if ((++checks&127)==0 && Clock::now()>=until) {eligible=false;break;}
                    Clause r;
                    for (int l:db[p]) if (l!=v) r.push_back(l);
                    for (int l:db[q]) if (l!=-v) r.push_back(l);
                    if (!normalize(r) || active.count(r)) continue;
                    if (r.empty()) { proof.add({}); return false; }
                    if (r.size()>size_t(policy.width)) {eligible=false;break;}
                    added.insert(std::move(r));
                    if (added.size()>pos.size()+neg.size()+size_t(policy.growth)) {eligible=false;break;}
                }
                if (!eligible) break;
            }
            if (!eligible || db.size()+added.size()>initial+policy.total) continue;
            pos.insert(pos.end(),neg.begin(),neg.end()); std::set<int> touched;
            for (int id:pos) {
                live[id]=false; active.erase(db[id]);
                for (int l:db[id]) {--count[index_of(l)];touched.insert(std::abs(l));}
            }
            for (const auto& r:added) {
                insert(r); proof.add(r); ++generated;
                for (int l:r) touched.insert(std::abs(l));
            }
            frames.push_back({v,std::move(pos)}); ++projected;
            for (int w:touched) if (w!=v) reschedule(w);
        }
        blocked=!active.empty(); return true;
    }
    Clauses residual() const {
        Clauses out; out.reserve(active.size());
        for (size_t i=0;i<db.size();++i) if (live[i]) out.push_back(db[i]);
        return out;
    }
    void reconstruct(Model& m) const {
        for (auto it=frames.rbegin();it!=frames.rend();++it) {
            int need=-1;
            for (int id:it->parents) {
                bool sat=false; int sign=-1;
                for (int l:db[id]) {
                    if (std::abs(l)==it->variable) sign=l>0;
                    else if (value(m,l)==1) {sat=true;break;}
                }
                if (sat) continue;
                if (sign<0 || (need!=-1 && sign!=need)) throw std::logic_error("inconsistent projection witness");
                need=sign;
            }
            if (need>=0) m[it->variable]=int8_t(need);
        }
    }
};
} // namespace toolbox
