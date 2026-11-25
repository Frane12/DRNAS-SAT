#include "discovery_reason.hpp"
#include <iostream>
using namespace toolbox;
void require(bool x,const char* msg){if(!x)throw std::runtime_error(msg);}
void source(const std::string& p,const Input& f){
    std::ofstream out(p);out<<"p cnf "<<f.n<<" "<<f.cs.size()<<"\n";
    for(const auto& c:f.cs){for(int l:c)out<<l<<" ";out<<"0\n";}
}
void canon(Input& f){for(auto& c:f.cs)require(normalize(c),"unexpected tautology");}
void consequence(const Input& f,const Clauses& cs){
    for(unsigned m=0;m<(1u<<f.n);++m){
        Model x(f.n+1);for(int i=1;i<=f.n;++i)x[i]=(m>>(i-1))&1u;
        if(satisfied(f.cs,x))require(satisfied(cs,x),"non-entailed kernel consequence");
    }
}
int main(int argc,char** argv){
    if(argc!=2)return 2;std::string base=argv[1];
    {
        Input f{5,{{1,2,3},{1,2,-3},{1,-2,4},{1,-2,-4},{-1,5}}};canon(f);
        source(base+"/context.cnf",f);
        AdaptivePropagator prop(f.n,f.cs);require(prop.consistent({-1}),"test must not be ordinary UP");
        DiscoveryStats st;auto r=close_context(prop,{-1},{2,3,4,5,1},after(2),st,100,32);
        require(r.impossible&&r.facts==Clauses{Clause{1}},"failed to discover guarded contradiction");
        {Proof proof(base+"/context.drup");for(const auto& c:r.trace)proof.add(c);}
        consequence(f,r.trace);
        std::cout<<"UNIFIED3_KERNEL context lines="<<r.trace.size()<<" trials="<<st.local_trials<<"\n";
    }
    {
        Input f{5,{{1,2,3,4},{1,2,3,-4},{1,2,-3,5},{1,2,-3,-5}}};canon(f);
        source(base+"/region.cnf",f);
        auto active=f.cs;DiscoveryStats st;
        {Proof proof(base+"/region.drup");
        require(!regional_round(f,active,proof,after(2),st,0),"regional SAT control refuted");}
        std::set<Clause> known(active.begin(),active.end());
        require(known.count({1,2}),"missing projected boundary");
        consequence(f,active);
        std::cout<<"UNIFIED3_KERNEL region facts="<<st.regional_facts<<" bags="<<st.bags<<"\n";
    }
    {
        Input f{3,{}};for(unsigned m=0;m<8;++m)f.cs.push_back(blocker({1,2,3},m));canon(f);
        source(base+"/region_unsat.cnf",f);
        auto active=f.cs;DiscoveryStats st;
        AdaptivePropagator prop(f.n,f.cs);require(prop.consistent(),"test must not have root UP conflict");
        {Proof proof(base+"/region_unsat.drup");
        require(regional_round(f,active,proof,after(2),st,0),"missing exact regional contradiction");}
        require(st.local_unsat==1,"regional UNSAT route not exercised");
        std::cout<<"UNIFIED3_KERNEL region_unsat lines="<<st.proof_lines<<"\n";
    }
    {
        Input f{3,{}};for(unsigned m=0;m<7;++m)f.cs.push_back(blocker({1,2,3},m));canon(f);
        source(base+"/negative.cnf",f);
        auto active=f.cs;DiscoveryStats st;
        {Proof proof(base+"/negative.drup");
        require(!context_round(f,active,proof,after(2),st,1,0),"false conditional UNSAT");
        compact_blackboard(f,active,st);
        require(!regional_round(f,active,proof,after(2),st,1),"false regional UNSAT");}
        consequence(f,active);
        std::cout<<"UNIFIED3_KERNEL negative facts="<<st.conditional_facts+st.regional_facts<<"\n";
    }
}
