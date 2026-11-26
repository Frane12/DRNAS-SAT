#pragma once
// Sparse GF(2) affine-space model construction. No UNSAT oracle.
namespace core_affine {
using V=std::vector<int>;
using Time=toolbox::Time;
struct Row{V vars;int rhs=0;};
struct Result{
    toolbox::Model model;
    int equations=0,rank=0,free=0,best=-1,restarts=0;
    size_t basis_entries=0,direction_entries=0;
    long long moves=0,work=0;
};
inline V symmetric(const V&a,const V&b){
    V out;out.reserve(a.size()+b.size());
    std::set_symmetric_difference(a.begin(),a.end(),b.begin(),b.end(),std::back_inserter(out));return out;
}
inline Result solve(const toolbox::Input& f,Time stop){
    Result r;auto live=[&](){return toolbox::Clock::now()<stop;};
    if(f.n<1||f.n>200000||f.cs.size()>1000000||!live())return r;
    // Complete forbidden half-cubes only: every recovered equation is implied by CNF.
    std::map<V,uint64_t> patterns;std::vector<Row> rows;
    size_t literals=0;
    for(size_t i=0;i<f.cs.size();++i){
        if((i&255)==0&&!live())return r;
        const auto& c=f.cs[i];literals+=c.size();
        if(literals>6000000)return r;
        if(c.empty())return r;
        if(c.size()==1){rows.push_back({{std::abs(c[0])},int(c[0]>0)});continue;}
        if(c.size()>6)continue;
        V v;for(int l:c)v.push_back(std::abs(l));std::sort(v.begin(),v.end());
        if(std::adjacent_find(v.begin(),v.end())!=v.end())continue;
        unsigned mask=0;for(int l:c)if(l<0)mask|=1u<<(std::lower_bound(v.begin(),v.end(),-l)-v.begin());
        patterns[v]|=uint64_t(1)<<mask;
        if(patterns.size()>400000)return r;
    }
    for(auto& [v,mask]:patterns){
        if(!live())return r;
        for(int p=0;p<2;++p){
            bool full=true;for(unsigned b=0;b<(1u<<v.size());++b)
                if((__builtin_popcount(b)&1)==p&&!(mask&(uint64_t(1)<<b))){full=false;break;}
            if(full){rows.push_back({v,1-p});++r.equations;}
        }
    }
    patterns.clear();
    if(!r.equations||rows.size()>400000)return r;
    // Highest-pivot sparse echelon form. Fill caps fail closed to UNKNOWN.
    std::vector<Row> basis(f.n+1);
    for(auto& row:rows){
        if(!live())return r;
        while(!row.vars.empty()){
            if(!live())return r;
            int v=row.vars.back();
            if(basis[v].vars.empty()){
                r.basis_entries+=row.vars.size();
                if(r.basis_entries>4000000)return r;
                basis[v]=std::move(row);++r.rank;break;
            }
            row.vars=symmetric(row.vars,basis[v].vars);row.rhs^=basis[v].rhs;
            if(row.vars.size()>4096)return r;
            if(row.vars.empty()&&row.rhs)return r; // existing certified methods may prove it
        }
    }
    // Express each original variable by sparse free-variable supports.
    std::vector<V> dep(f.n+1),direction(f.n+1);V free;
    toolbox::Model origin(f.n+1,0);
    for(int v=1;v<=f.n;++v){
        if((v&127)==0&&!live())return r;
        if(basis[v].vars.empty()){dep[v]={v};free.push_back(v);}
        else{
            origin[v]=basis[v].rhs;
            for(int u:basis[v].vars)if(u!=v){
                origin[v]^=origin[u];dep[v]=symmetric(dep[v],dep[u]);
                if(dep[v].size()>2048)return r;
            }
        }
        r.direction_entries+=dep[v].size();
        if(r.direction_entries>4000000)return r;
        for(int z:dep[v])direction[z].push_back(v);
    }
    r.free=int(free.size());
    if(toolbox::satisfied(f.cs,origin)){r.model=std::move(origin);r.best=0;return r;}
    if(free.empty()||!live())return r;
    // All directions preserve every recovered parity equation. Score original
    // clauses directly with incremental counts and multi-variable moves.
    std::vector<V> occ(f.n+1);
    for(int i=0;i<int(f.cs.size());++i){
        if((i&255)==0&&!live())return r;
        for(int l:f.cs[i])occ[std::abs(l)].push_back(l>0?i+1:-i-1);
    }
    std::mt19937 rng(26112026);
    std::vector<int> count(f.cs.size()),where(f.cs.size(),-1),delta(f.cs.size()),stamp(f.cs.size());
    V bad,touched;int epoch=0;
    toolbox::Model m=origin;
    auto add_bad=[&](int i){if(where[i]<0){where[i]=int(bad.size());bad.push_back(i);}};
    auto remove_bad=[&](int i){int j=where[i];if(j<0)return;int b=bad.back();bad[j]=b;where[b]=j;bad.pop_back();where[i]=-1;};
    auto evaluate=[&](int z,bool commit,int& score){
        if(!live())return false;
        if(++epoch==INT_MAX){std::fill(stamp.begin(),stamp.end(),0);epoch=1;}
        touched.clear();score=0;
        for(int v:direction[z])for(int l:occ[v]){
            if((++r.work&1023)==0&&!live())return false;
            int i=std::abs(l)-1;
            if(stamp[i]!=epoch){stamp[i]=epoch;delta[i]=0;touched.push_back(i);}
            delta[i]+=(m[v]==int(l>0))?-1:1;
        }
        for(int i:touched)score+=int(count[i]+delta[i]==0)-int(count[i]==0);
        if(commit){
            for(int v:direction[z])m[v]^=1;
            for(int i:touched){count[i]+=delta[i];if(count[i])remove_bad(i);else add_bad(i);}
        }
        return true;
    };
    for(int restart=0;restart<64&&live();++restart){
        ++r.restarts;m=origin;
        for(int z:free)if(rng()&1u)for(int v:direction[z])m[v]^=1;
        bad.clear();std::fill(where.begin(),where.end(),-1);
        for(int i=0;i<int(f.cs.size());++i){
            if((i&255)==0&&!live())return r;
            count[i]=0;for(int l:f.cs[i])count[i]+=toolbox::value(m,l)==1;
            if(!count[i])add_bad(i);
        }
        int stale=0,localbest=int(bad.size());
        for(int step=0;step<100000&&live();++step){
            if(r.best<0||int(bad.size())<r.best)r.best=int(bad.size());
            if(bad.empty()){if(toolbox::satisfied(f.cs,m))r.model=std::move(m);return r;}
            if(int(bad.size())<localbest){localbest=int(bad.size());stale=0;}else if(++stale>4000)break;
            const auto& c=f.cs[bad[rng()%bad.size()]];
            V candidates;for(int l:c)for(int z:dep[std::abs(l)])candidates.push_back(z);
            if(candidates.empty())break;
            std::sort(candidates.begin(),candidates.end());candidates.erase(std::unique(candidates.begin(),candidates.end()),candidates.end());
            std::shuffle(candidates.begin(),candidates.end(),rng);
            if(candidates.size()>24)candidates.resize(24);
            int chosen=candidates[0],best=INT_MAX;
            if(rng()%100>=20){
                for(int z:candidates){int score=0;if(!evaluate(z,false,score))return r;
                    if(score<best){best=score;chosen=z;}}
            }
            int ignored=0;if(!evaluate(chosen,true,ignored))return r;++r.moves;
        }
    }
    return r;
}
} // namespace core_affine
