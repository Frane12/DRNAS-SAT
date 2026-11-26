// Direct boundary-bank controls: local solver is exhaustive, independent of CORE.
#include <bits/stdc++.h>
#include "vendor/unified/formula.hpp"
#include "boundary_join.hpp"
using namespace std;
using M=toolbox::Model;using V=vector<int>;using F=vector<V>;
static M exact(int n,const F& cs,toolbox::Time stop){
    if(n<0||n>20)return {};
    for(unsigned mask=0;mask<(1u<<n);++mask){
        if(toolbox::Clock::now()>=stop)return {};
        M m(n+1,0);for(int v=1;v<=n;++v)m[v]=(mask>>(v-1))&1u;
        if(toolbox::satisfied(cs,m))return m;
    }return {};
}
static core_boundary::Result run(const toolbox::Input& f){
    vector<V> vars;V group(f.n+1,0),local(f.n+1,0);
    for(int v=1;v<=f.n;++v){
        int g=(v-1)/2;if(g==int(vars.size()))vars.push_back({});
        group[v]=g;vars[g].push_back(v);local[v]=int(vars[g].size());
    }
    vector<V> internal(vars.size()),incident(vars.size());
    for(int i=0;i<int(f.cs.size());++i){
        set<int> gs;for(int l:f.cs[i])gs.insert(group[abs(l)]);
        for(int g:gs)incident[g].push_back(i);
        if(gs.size()==1)internal[*gs.begin()].push_back(i);
    }
    return core_boundary::solve(f,vars,group,local,internal,incident,toolbox::after(.10),exact);
}
int main(){
    // Individual coordinate changes worsen the boundary cost; both regions
    // have to switch together. Two copies of each implication use different
    // original variables whose equality is enforced inside the regions.
    toolbox::Input trap{4,{{-1,2},{1,-2},{-3,4},{3,-4},
                            {1,3},{-1,3},{-2,4},{1,-3},{2,-4}}};
    auto r=run(trap);
    if(r.model.empty()||!toolbox::satisfied(trap.cs,r.model)||r.merges<1||r.alternatives<2)return 1;
    trap.cs.push_back({-1,-3});
    if(!run(trap).model.empty())return 2;
    mt19937 rng(261120265);int accepted=0,feasible=0;
    for(int t=0;t<64;++t){
        toolbox::Input f{8,{}};
        for(int j=1;j<=8;j+=2){f.cs.push_back({-j,j+1});f.cs.push_back({j,-j-1});}
        for(int j=0;j<8;++j){
            int a=1+rng()%8,b=1+rng()%8;
            if(a==b)continue;
            f.cs.push_back({rng()%2?a:-a,rng()%2?b:-b});
        }
        bool sat=!exact(f.n,f.cs,toolbox::after(.1)).empty();feasible+=sat;
        auto a=run(f);
        if(!a.model.empty()){
            if(!sat||!toolbox::satisfied(f.cs,a.model))return 3;
            ++accepted;
        }
    }
    cout<<"BOUNDARY_BANK_TEST {\"cases\":66,\"random_feasible\":"<<feasible
        <<",\"random_models\":"<<accepted<<",\"merge_control\":true,\"false_models\":0}\n";
    return 0;
}
