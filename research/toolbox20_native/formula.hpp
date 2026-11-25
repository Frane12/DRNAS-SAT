#pragma once
#include <algorithm>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <limits>
#include <set>
#include <span>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace toolbox {
using Clause = std::vector<int>;
using Clauses = std::vector<Clause>;
using Model = std::vector<int8_t>; // -1 unknown, 0 false, 1 true
using Clock = std::chrono::steady_clock;
using Time = Clock::time_point;
inline Time after(double seconds) {
    return Clock::now() + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
}
inline int index_of(int lit) { return 2 * (std::abs(lit) - 1) + (lit < 0); }
inline int value(const Model& m, int lit) {
    int x = m[std::abs(lit)];
    return x < 0 ? -1 : (lit > 0 ? x : 1-x);
}
inline bool satisfied(const Clauses& cs, const Model& m) {
    return std::all_of(cs.begin(), cs.end(), [&](const Clause& c) {
        return std::any_of(c.begin(), c.end(), [&](int l){ return value(m,l)==1; });
    });
}
// Sort by variable so duplicate literals and complementary pairs are adjacent.
inline bool normalize(Clause& c) {
    std::sort(c.begin(), c.end(), [](int a,int b) {
        return std::abs(a)!=std::abs(b) ? std::abs(a)<std::abs(b) : a<b;
    });
    c.erase(std::unique(c.begin(), c.end()), c.end());
    return std::adjacent_find(c.begin(), c.end(), [](int a,int b){return a == -b;}) == c.end();
}
struct Input { int n; Clauses cs; };
inline Input parse(const std::string& raw) {
    std::istringstream file(raw);
    Input f{0,{}}; bool header=false;
    int64_t declared=0, seen=0; Clause pending;
    std::string line;
    while (std::getline(file,line)) {
        auto start=line.find_first_not_of(" \t\r");
        if (start==std::string::npos || line[start]=='c') continue;
        if (line[start]=='%') break;
        if (line[start]=='p') {
            std::istringstream h(line.substr(start)); std::string p,format,extra;
            if (header || !(h>>p>>format>>f.n>>declared) || h>>extra || p!="p" ||
                format!="cnf" || f.n<0 || f.n>std::numeric_limits<int>::max()/2 || declared<0)
                throw std::runtime_error("invalid DIMACS header");
            header=true; continue;
        }
        if (!header) throw std::runtime_error("missing DIMACS header");
        const char* cur=line.data()+start; const char* end=line.data()+line.size();
        while (cur<end) {
            if (*cur==' ' || *cur=='\t' || *cur=='\r') { ++cur; continue; }
            int lit=0; auto parsed=std::from_chars(cur,end,lit);
            if (parsed.ec!=std::errc{} || (parsed.ptr<end && *parsed.ptr!=' ' && *parsed.ptr!='\t' && *parsed.ptr!='\r') ||
                lit < -f.n || lit > f.n) throw std::runtime_error("invalid DIMACS literal");
            cur=parsed.ptr;
            if (lit) pending.push_back(lit);
            else {
                if (++seen>declared) throw std::runtime_error("extra DIMACS clause");
                if (normalize(pending)) f.cs.push_back(pending);
                pending.clear();
            }
        }
    }
    if (!header || !pending.empty() || seen!=declared) throw std::runtime_error("incomplete DIMACS input");
    return f;
}
struct Proof {
    std::string path;
    std::ofstream out;
    explicit Proof(const std::string& target):path(target) {
        out.exceptions(std::ios::badbit | std::ios::failbit); out.open(path);
    }
    void add(const Clause& clause) {
        for (int l:clause) out<<l<<' ';
        out<<"0\n";
    }
    void structural(const std::string& json) {
        out.close(); out.open(path,std::ios::trunc); out<<json<<'\n';
    }
};
// Watches can move across probes. Each call undoes just the old trail.
class Propagator {
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
    Propagator(int n,const Clauses& clauses):cs(clauses),watches(2*n),state(n+1,-1) {
        for (int i=0; i<int(cs.size()); ++i) {
            const auto& c=cs[i];
            if (c.empty()) empty=true;
            else if (c.size()==1) units.push_back(c[0]);
            else { watches[index_of(c[0])].push_back(i); watches[index_of(c[1])].push_back(i); }
        }
    }
    bool consistent(std::initializer_list<int> assumptions={}) {
        return consistent(std::span<const int>(assumptions.begin(),assumptions.size()));
    }
    bool consistent(std::span<const int> assumptions) {
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
inline bool reduce_root(int n, Clauses& cs, Model& fixed, Proof& proof) {
    Propagator p(n,cs);
    if (!p.consistent()) { proof.add({}); return false; }
    if (p.trail.empty()) return true;
    for (int l:p.trail) { fixed[std::abs(l)]=l>0; proof.add({l}); }
    Clauses residual;
    for (const auto& c:cs) {
        if (std::any_of(c.begin(),c.end(),[&](int l){return value(fixed,l)==1;})) continue;
        Clause r;
        for (int l:c) if (value(fixed,l)<0) r.push_back(l);
        if (r.size()!=c.size()) proof.add(r);
        residual.push_back(std::move(r));
    }
    cs=std::move(residual);
    return true;
}
} // namespace toolbox
