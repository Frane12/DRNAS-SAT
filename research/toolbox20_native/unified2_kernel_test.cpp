#include "adaptive_reason.hpp"
#include <iostream>
using namespace toolbox;
void require(bool x,const char* msg){if(!x)throw std::runtime_error(msg);}
void gate(Clauses& cs,Clause v,unsigned truth){
    for(unsigned m=0;m<8;++m)
        if(((m>>2)&1u)!=((truth>>(m&3u))&1u))cs.push_back(blocker(v,m));
}
void source(const std::string& p,int n,const Clauses& cs){
    std::ofstream f(p);f<<"p cnf "<<n<<" "<<cs.size()<<"\n";
    for(const auto& c:cs){for(int l:c)f<<l<<" ";f<<"0\n";}
}
int main(int argc,char** argv){
    if(argc!=2)return 2;std::string base=argv[1];
    {
        Clauses cs;
        gate(cs,{1,2,3},8);gate(cs,{1,2,4},8);
        // x5 = x3 XOR x1, x6 = x4 XOR x1. This needs equality
        // transfer between gates, not just matching literal IDs.
        gate(cs,{3,1,5},6);gate(cs,{4,1,6},6);
        for(auto& c:cs)normalize(c);
        source(base+"/gate.cnf",6,cs);
        auto original=cs;auto until=after(2);
        auto gates=discover_gates(original,until);AdaptiveStats st;
        {Proof proof(base+"/gate.drup");
        for(int r=0;r<8;++r)if(!gate_round(6,cs,gates,proof,until,st))break;}
        std::set<Clause> known(cs.begin(),cs.end());
        require(known.count({-3,4})&&known.count({3,-4}),"missing first congruence");
        require(known.count({-5,6})&&known.count({5,-6}),"missing transferred congruence");
        for(unsigned m=0;m<64;++m){Model x(7);for(int i=1;i<=6;++i)x[i]=(m>>(i-1))&1u;
            if(satisfied(original,x))require(satisfied(cs,x),"gate unsound");}
        std::cout<<"UNIFIED2_KERNEL gate facts="<<st.congruence<<" proof="<<st.gate_proof<<"\n";
    }
    {
        Clauses cs{{-1,-2,3},{-1,-2,-3},{1,4},{2,-4}};
        for(auto& c:cs)normalize(c);
        source(base+"/wide.cnf",4,cs);AdaptiveStats st;
        {Proof proof(base+"/wide.drup");wide_round(4,cs,proof,after(1),st,2,0);}
        std::set<Clause> known(cs.begin(),cs.end());
        require(known.count({-1,-2}),"missing non-source binary");
        std::cout<<"UNIFIED2_KERNEL wide facts="<<st.wide_facts<<"\n";
    }
    {
        Clauses cs{{1,2},{-1,3},{-2,3}};
        for(auto& c:cs)normalize(c);
        source(base+"/resolution.cnf",3,cs);AdaptiveStats st;
        {Proof proof(base+"/resolution.drup");resolution_sweep(3,cs,proof,after(1),st,3,100);}
        std::set<Clause> known(cs.begin(),cs.end());
        require(known.count({3}),"missing multi-step resolvent");
        std::cout<<"UNIFIED2_KERNEL resolution facts="<<st.resolution_facts<<"\n";
    }
}
