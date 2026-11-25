#include "compression_reason.hpp"
#include <iostream>
#include <random>
using namespace toolbox;
void require(bool b,const char* s){if(!b)throw std::runtime_error(s);}
void prepare(Input& f,const std::string& path){
    for(auto& c:f.cs)require(normalize(c),"tautology");
    std::ofstream o(path+".cnf");o<<"p cnf "<<f.n<<" "<<f.cs.size()<<"\n";
    for(const auto& c:f.cs){for(int l:c)o<<l<<" ";o<<"0\n";}
}
bool sat(int n,const Clauses& cs){
    for(unsigned m=0;m<(1u<<n);++m){Model x(n+1);for(int i=1;i<=n;++i)x[i]=(m>>(i-1))&1u;
        if(satisfied(cs,x))return true;}
    return false;
}
void consequence(const Input& f,const Clauses& cs){
    for(unsigned m=0;m<(1u<<f.n);++m){Model x(f.n+1);for(int i=1;i<=f.n;++i)x[i]=(m>>(i-1))&1u;
        if(satisfied(f.cs,x))require(satisfied(cs,x),"non-entailed clause");}
}
int main(int argc,char** argv){
    if(argc!=2)return 2;std::string b=argv[1];
    {
        Input f{4,{{1,2},{-1,-2},{-2,3},{2,-3},{2,4}}};
        std::string path=b+"/equiv";prepare(f,path);
        auto cs=f.cs;CompressionStats st;
        {Proof p(path+".drup");require(equivalence_compress(f.n,cs,p,after(2),st),"equiv false conflict");}
        require(st.equivalent>=2,"missing signed equivalences");
        std::set<Clause> known(cs.begin(),cs.end());require(known.count({-1,4}),"missing rewrite");
        require(sat(f.n,f.cs)==sat(f.n,cs),"rewrite not equisatisfiable");consequence(f,cs);
        std::cout<<"UNIFIED5_KERNEL equiv "<<st.equivalent<<" rewritten "<<st.rewritten<<"\n";
    }
    {
        Input f{3,{{1,2,3},{-1,2}}};std::string path=b+"/ssr";prepare(f,path);
        auto cs=f.cs;CompressionStats st;
        {Proof p(path+".drup");require(ssr_round(f.n,cs,p,after(2),st)>0,"missing SSR");}
        std::set<Clause> known(cs.begin(),cs.end());require(known.count({2,3}),"missing shortened clause");
        require(sat(f.n,f.cs)==sat(f.n,cs),"SSR not equisatisfiable");consequence(f,cs);
        std::cout<<"UNIFIED5_KERNEL ssr "<<st.ssr<<"\n";
    }
    {
        Input f{3,{}};for(unsigned m=0;m<8;++m)f.cs.push_back(blocker({1,2,3},m));
        std::string path=b+"/projection";prepare(f,path);auto cs=f.cs;CompressionStats st;
        {Proof p(path+".drup");require(!eliminate_fill(f.n,cs,p,after(2),st,2,8),"projection missed contradiction");}
        require(st.pivots>0,"projection not exercised");require(!sat(f.n,f.cs),"bad oracle");
        std::cout<<"UNIFIED5_KERNEL projection "<<st.pivots<<" resolvents "<<st.resolvents<<"\n";
    }
    {
        Input f{6,{{1,2},{3,4},{5,6},{-1,-3},{-1,-5},{-3,-5},{-2,-4},{-2,-6},{-4,-6}}};
        std::string path=b+"/capacity";prepare(f,path);
        Clauses demand{{1,2},{3,4},{5,6}};CapacityGraph g(f.n,f.cs);
        int cap=g.cover({1,2,3,4,5,6},0);require(cap==2,"incorrect clique cover");
        Clauses trace;require(capacity_trace(f.n,f.cs,demand,trace,after(2)),"capacity proof failed");
        require(!trace.empty()&&trace.back().empty(),"missing capacity contradiction");
        {Proof p(path+".drup");for(const auto& c:trace)p.add(c);}
        require(!sat(f.n,f.cs),"capacity oracle");
        std::cout<<"UNIFIED5_KERNEL capacity demand=3 capacity="<<cap<<" proof="<<trace.size()<<"\n";
    }
    std::mt19937 rng(510251);
    for(int i=0;i<64;++i){
        Input f{5+i%4,{}};int m=3*f.n+int(rng()%12);
        for(int j=0;j<m;++j){
            Clause vs;for(int v=1;v<=f.n;++v)vs.push_back(v);
            std::shuffle(vs.begin(),vs.end(),rng);vs.resize(2+rng()%2);
            for(int& v:vs)if(rng()&1u)v=-v;
            f.cs.push_back(vs);
        }
        std::string path=b+"/random-"+std::to_string(i);prepare(f,path);
        auto cs=f.cs;bool truth=sat(f.n,f.cs),ok=true;CompressionStats st;
        {Proof p(path+".drup");auto until=after(2);
            ok=compress_root(f.n,cs,p,st);
            if(ok)ok=equivalence_compress(f.n,cs,p,until,st);
            if(ok){ssr_round(f.n,cs,p,until,st);ok=compress_root(f.n,cs,p,st);}
            if(ok)ok=eliminate_fill(f.n,cs,p,until,st,3,16);
        }
        if(ok){require(sat(f.n,cs)==truth,"compression changed satisfiability");consequence(f,cs);}
        else require(!truth,"false refutation");
    }
    std::cout<<"UNIFIED5_RANDOM_EXHAUSTIVE 64\n";
}
