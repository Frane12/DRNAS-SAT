#include "composition_reason.hpp"
#include <iostream>
#include <random>
using namespace toolbox;
void require(bool x,const char* msg){if(!x)throw std::runtime_error(msg);}
void source(const std::string& p,const Input& f){
    std::ofstream out(p);out<<"p cnf "<<f.n<<" "<<f.cs.size()<<"\n";
    for(const auto& c:f.cs){for(int l:c)out<<l<<" ";out<<"0\n";}
}
void verify_truth(const Input& f,const Clauses& proof,bool impossible,const Clause& context){
    for(unsigned m=0;m<(1u<<f.n);++m){
        Model x(f.n+1);for(int i=1;i<=f.n;++i)x[i]=(m>>(i-1))&1u;
        if(!satisfied(f.cs,x))continue;
        require(satisfied(proof,x),"non-entailed kernel fact");
        if(impossible){
            bool under=true;for(int l:context)if(value(x,l)!=1)under=false;
            require(!under,"false conditional contradiction");
        }
    }
}
void run(const std::string& base,const std::string& name,Input f,Clause context,
         bool must_close,bool shallow_must_fail){
    for(auto& c:f.cs)require(normalize(c),"tautology");
    source(base+"/"+name+".cnf",f);
    Clause rank;for(int v=1;v<=f.n;++v)rank.push_back(v);
    if(shallow_must_fail){
        AdaptivePropagator prop(f.n,f.cs);DiscoveryStats s;
        auto shallow=close_context(prop,context,rank,after(1),s,200,64);
        require(!shallow.impossible,"shallow control unexpectedly closes");
    }
    CompositionStats st;
    auto result=compose_context(f.n,f.cs,context,rank,after(2),st,128,0);
    if(must_close){require(result.impossible,"composition failed to close required context");require(st.child_contexts>0,"new child layer not used");}
    verify_truth(f,result.trace,result.impossible,context);
    {Proof proof(base+"/"+name+".drup");for(const auto& c:result.trace)proof.add(c);}
    if(must_close)require(!result.trace.empty()&&result.trace.back()==negate_clause(context),"missing final guard");
    std::cout<<"UNIFIED4_KERNEL "<<name<<" closed="<<result.impossible<<" children="<<st.child_contexts<<" lines="<<result.trace.size()<<"\n";
}
int main(int argc,char** argv){
    if(argc!=2)return 2;std::string base=argv[1];
    Input cube{3,{}};for(unsigned m=0;m<8;++m)cube.cs.push_back(blocker({1,2,3},m));
    run(base,"cube",cube,{},true,true);
    Input gated{4,{}};
    for(unsigned m=0;m<8;++m){Clause c=blocker({2,3,4},m);c.push_back(1);gated.cs.push_back(c);}
    run(base,"guarded",gated,{-1},true,true);
    cube.cs.pop_back();
    run(base,"sat-control",cube,{},false,false);
    std::mt19937 rng(741124);
    for(int i=0;i<64;++i){
        Input f{5+i%3,{}};int m=f.n*4+int(rng()%9);
        for(int j=0;j<m;++j){
            Clause vs;for(int v=1;v<=f.n;++v)vs.push_back(v);
            std::shuffle(vs.begin(),vs.end(),rng);vs.resize(3);
            for(int& v:vs)if(rng()&1u)v=-v;
            f.cs.push_back(vs);
        }
        Clause ctx;if(i%3==1)ctx={1};if(i%3==2)ctx={-1,2};
        run(base,"random-"+std::to_string(i),f,ctx,false,false);
    }
}
