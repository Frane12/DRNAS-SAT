// Direct kernel checks, independent exhaustive truth on small CNFs.
#include <bits/stdc++.h>
#include "vendor/unified/formula.hpp"
#include "affine_sparse.hpp"
using namespace std;
int main(){
    mt19937 gen(261120264);
    int solved=0;long long blocks=0,moves=0,states=0;
    for(int t=0;t<64;++t){
        const int n=12;toolbox::Input f{n,{}};
        // Three complete XOR triples, with alternating RHS.
        for(int j=0;j<3;++j)for(unsigned b=0;b<8;++b)
            if((__builtin_parity(b))!=(j%2)){
                vector<int> c;
                for(int k=0;k<3;++k){int v=3*j+k+1;c.push_back((b&(1u<<k))?-v:v);}
                f.cs.push_back(c);
            }
        for(int i=0;i<22;++i){
            set<int> vars;while(vars.size()<3)vars.insert(1+gen()%n);
            vector<int> c;for(int v:vars)c.push_back(gen()&1u?v:-v);f.cs.push_back(c);
        }
        // Some explicitly contradictory cases. A failed constructor is
        // inconclusive; it must never return an invalid SAT model.
        if(t%8==0){f.cs.push_back({10});f.cs.push_back({-10});}
        bool expected=false;
        for(unsigned b=0;b<(1u<<n)&&!expected;++b){
            toolbox::Model m(n+1,0);for(int v=1;v<=n;++v)m[v]=(b>>(v-1))&1u;
            expected=toolbox::satisfied(f.cs,m);
        }
        auto r=core_affine::solve(f,toolbox::after(.08),true,true);
        if(!r.model.empty()){
            if(!expected||!toolbox::satisfied(f.cs,r.model))return 1;
            ++solved;
        }
        if(r.affine_factors&&r.affine_trivial<12)return 2;
        blocks+=r.block_trials;moves+=r.block_moves;states+=r.block_states;
    }
    cout<<"AFFINE_BLOCK_TEST {\"cases\":64,\"sat_models\":"<<solved<<",\"block_trials\":"<<blocks
        <<",\"block_moves\":"<<moves<<",\"block_states\":"<<states<<"}\n";
    return solved>0&&blocks>0&&moves>0?0:3;
}
