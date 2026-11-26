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
    long long moves=0,work=0,block_trials=0,block_moves=0,block_states=0;
    int affine_factors=0,affine_trivial=0,max_block=0;
};
inline V symmetric(const V&a,const V&b){
    V out;out.reserve(a.size()+b.size());
    std::set_symmetric_difference(a.begin(),a.end(),b.begin(),b.end(),std::back_inserter(out));return out;
}
inline Result solve(const toolbox::Input& f,Time stop,bool weighted=false,bool blocks=false){
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
    // The residual factor graph is defined in free coordinates, not x.
    // A factor is removed from the *search graph* only when simultaneous
    // falsification of its literals is algebraically inconsistent.
    std::vector<V> scope,incidence;
    if(blocks){
        scope.resize(f.cs.size());incidence.resize(f.n+1);
        size_t links=0;
        for(int i=0;i<int(f.cs.size());++i){
            if((i&127)==0&&!live())return r;
            const auto& c=f.cs[i];bool trivial=false;
            if(c.size()<=8){
                std::map<int,Row> small;
                for(int l:c){
                    int v=std::abs(l);Row a{dep[v],int(l<0)^int(origin[v])};bool inserted=false;
                    while(!a.vars.empty()){
                        int p=a.vars.back();auto it=small.find(p);
                        if(it==small.end()){small.emplace(p,std::move(a));inserted=true;break;}
                        a.vars=symmetric(a.vars,it->second.vars);a.rhs^=it->second.rhs;
                    }
                    if(!inserted&&a.vars.empty()&&a.rhs){trivial=true;break;}
                }
            }
            if(trivial){++r.affine_trivial;continue;}
            V& vs=scope[i];for(int l:c)vs.insert(vs.end(),dep[std::abs(l)].begin(),dep[std::abs(l)].end());
            std::sort(vs.begin(),vs.end());vs.erase(std::unique(vs.begin(),vs.end()),vs.end());
            if(vs.empty())continue;
            links+=vs.size();if(links>6000000)return r;
            ++r.affine_factors;for(int z:vs)incidence[z].push_back(i);
        }
    }
    std::mt19937 rng(26112026);
    std::vector<int> count(f.cs.size()),where(f.cs.size(),-1),delta(f.cs.size()),stamp(f.cs.size());
    V bad,touched;int epoch=0;
    std::vector<int> weight(f.cs.size(),1);
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
        for(int i:touched)score+=weight[i]*(int(count[i]+delta[i]==0)-int(count[i]==0));
        if(commit){
            for(int v:direction[z])m[v]^=1;
            for(int i:touched){count[i]+=delta[i];if(count[i])remove_bad(i);else add_bad(i);}
        }
        return true;
    };
    // Exact conditional optimization on a bounded overlapping block of free
    // coordinates. Every affected nontrivial factor is included, even when
    // its support extends outside the block. Outside coordinates stay fixed.
    auto block_step=[&](int seed)->bool{
        if(!blocks||!live()||scope[seed].empty())return false;
        V block=scope[seed];
        auto low_cost=[&](int a,int b){return std::make_pair(incidence[a].size(),a)<std::make_pair(incidence[b].size(),b);};
        std::sort(block.begin(),block.end(),low_cost);if(block.size()>6)block.resize(6);
        V factors;
        auto collect=[&](){
            factors.clear();for(int z:block)factors.insert(factors.end(),incidence[z].begin(),incidence[z].end());
            std::sort(factors.begin(),factors.end());factors.erase(std::unique(factors.begin(),factors.end()),factors.end());
        };
        collect();while(factors.size()>192&&block.size()>1){block.pop_back();collect();}
        if(factors.size()>192)return false;
        // Expand by residual factor overlap, favoring nearby low-cost coordinates.
        std::map<int,int> overlap;
        for(int i:factors)for(int z:scope[i])if(std::find(block.begin(),block.end(),z)==block.end())++overlap[z];
        V near;for(auto [z,h]:overlap)near.push_back(z);
        std::sort(near.begin(),near.end(),[&](int a,int b){
            long long x=1LL*overlap[a]*(incidence[b].size()+1),y=1LL*overlap[b]*(incidence[a].size()+1);
            return x!=y?x>y:a<b;
        });
        for(int z:near){if(block.size()>=8||!live())break;
            if(incidence[z].size()>192)continue;
            block.push_back(z);collect();if(factors.size()>192){block.pop_back();collect();}
        }
        if(block.size()<2||!live())return false;
        struct Lit{unsigned mask;bool sat;};
        std::vector<std::vector<Lit>> local;local.reserve(factors.size());
        for(int i:factors){
            std::vector<Lit> ls;
            for(int l:f.cs[i]){
                int v=std::abs(l);unsigned mask=0;
                for(size_t j=0;j<block.size();++j)if(std::binary_search(dep[v].begin(),dep[v].end(),block[j]))mask|=1u<<j;
                ls.push_back({mask,toolbox::value(m,l)==1});
            }
            local.push_back(std::move(ls));
        }
        ++r.block_trials;r.max_block=std::max(r.max_block,int(block.size()));
        int before=0;for(int i:factors)if(!count[i])before+=weight[i];
        int best=before;unsigned choice=0;
        for(unsigned bits=1;bits<(1u<<block.size());++bits){
            if(!live())return false;++r.block_states;int cost=0;
            for(size_t i=0;i<local.size();++i){
                bool sat=false;for(auto l:local[i])if(l.sat^bool(__builtin_parity(bits&l.mask))){sat=true;break;}
                if(!sat)cost+=weight[factors[i]];if(cost>=best)break;
            }
            if(cost<best){best=cost;choice=bits;if(!best)break;}
        }
        if(!choice)return false;
        // Committing flips one at a time is safe: each is a nullspace direction.
        // If the deadline interrupts a block, no model is accepted here.
        for(size_t j=0;j<block.size();++j)if(choice&(1u<<j)){
            int ignored=0;if(!evaluate(block[j],true,ignored))return false;++r.moves;
        }
        ++r.block_moves;return true;
    };
    for(int restart=0;restart<64&&live();++restart){
        ++r.restarts;m=origin;
        std::fill(weight.begin(),weight.end(),1);
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
            if(weighted&&stale>0&&stale%48==0){
                for(int i:bad)weight[i]=std::min(32,weight[i]+1);
                if(stale%384==0)for(int& w:weight)w=1+(w-1)/2;
            }
            int seed=bad[rng()%bad.size()];
            if(blocks&&(step%32==0|| (stale>96&&step%8==0))&&block_step(seed))continue;
            const auto& c=f.cs[seed];
            V candidates;for(int l:c)for(int z:dep[std::abs(l)])candidates.push_back(z);
            if(candidates.empty())break;
            std::sort(candidates.begin(),candidates.end());candidates.erase(std::unique(candidates.begin(),candidates.end()),candidates.end());
            std::shuffle(candidates.begin(),candidates.end(),rng);
            if(candidates.size()>size_t(weighted?12:24))candidates.resize(weighted?12:24);
            int chosen=candidates[0],best=INT_MAX;
            if(rng()%100>=unsigned(weighted?(stale>192?35:12):20)){
                for(int z:candidates){int score=0;if(!evaluate(z,false,score))return r;
                    if(score<best){best=score;chosen=z;}}
            }
            int ignored=0;if(!evaluate(chosen,true,ignored))return r;++r.moves;
        }
    }
    return r;
}
} // namespace core_affine
