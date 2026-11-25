#include "unified_reason.hpp"
#include <iostream>
using namespace toolbox;
void require(bool ok,const char* msg){if(!ok)throw std::runtime_error(msg);}
void add_relation(Clauses& cs,Clause vars,bool nonlinear,int rhs){
    for(unsigned m=0;m<(1u<<vars.size());++m){
        int x=m&1,y=(m>>1)&1,z=(m>>2)&1;
        bool good=nonlinear?(z==(x&y)):(__builtin_parity(m)==rhs);
        if(!good)cs.push_back(blocker(vars,m));
    }
}
int main(int argc,char**argv){
    if(argc!=2)return 2;
    for(int kind=0;kind<2;++kind){
        Clauses cs; add_relation(cs,{1,2,3},kind,0);add_relation(cs,{2,3,4},kind,1);
        auto original=cs;
        std::string stem=std::string(argv[1])+(kind?"/nonlinear":"/affine");
        {std::ofstream f(stem+".cnf");f<<"p cnf 4 "<<cs.size()<<"\n";
        for(const auto& c:cs){for(int l:c)f<<l<<" ";f<<"0\n";}}
        UnifiedStats st;UnifiedMemory mem;
        {Proof proof(stem+".drup");join_round(4,cs,proof,after(2),st,mem);}
        std::set<Clause> known(cs.begin(),cs.end());
        if(kind)require(known.count({1,-4}),"missing nonlinear boundary implication");
        if(!kind){
            require(known.count({1,4})&&known.count({-1,-4}),"affine parity boundary not derived");
            require(st.affine>0,"affine path not exercised");
        }else require(st.nonlinear>0,"nonlinear path not exercised");
        // Every newly shared clause must follow from the complete input, checked
        // by enumeration independently of the relation implementation.
        for(unsigned m=0;m<16;++m){
            Model model(5);for(int v=1;v<=4;++v)model[v]=(m>>(v-1))&1;
            if(satisfied(original,model))require(satisfied(cs,model),"unsound shared consequence");
        }
        std::cout<<"UNIFIED_KERNEL "<<kind<<" facts="<<st.relation_facts<<" proof="<<st.proof_lines<<"\n";
    }
}
