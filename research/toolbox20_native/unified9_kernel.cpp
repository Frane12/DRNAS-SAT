#include "meta_factor.hpp"
#include <iostream>
#include <random>
using namespace toolbox;
bool sat(const Clauses& cs,unsigned m){
    for(const auto& c:cs){bool ok=false;for(int l:c)if(bool(m&(1u<<(std::abs(l)-1)))==(l>0)){ok=true;break;}if(!ok)return false;}
    return true;
}
int main(int argc,char** argv){
    if(argc!=2)return 2;
    std::mt19937 rng(17418);
    int count=0,lines=0;
    for(int k=0;k<81;++k){
        Clause vars{1,2,3,4,5,6};
        Clauses cs;
        // Two independent or overlapping affine equations, both generated
        // as exact forbidden rows, then project their shared variables.
        Clause a{1,2,3,4},b{3,4,5,6};
        if(k>0){std::shuffle(vars.begin(),vars.end(),rng);a.assign(vars.begin(),vars.begin()+3);b.assign(vars.begin()+2,vars.end());}
        for(auto v:{a,b}){
            std::sort(v.begin(),v.end());int rhs=rng()%2;
            for(unsigned m=0;m<(1u<<v.size());++m)if(__builtin_parity(m)!=rhs)cs.push_back(blocker(v,m));
        }
        vars={1,2,3,4,5,6};Clause boundary;
        std::set<int> common;for(int v:a)if(std::find(b.begin(),b.end(),v)!=b.end())common.insert(v);
        for(int v:vars)if(!common.count(v))boundary.push_back(v);
        auto t=factor_table(vars,cs,after(2));
        auto seen=factor_project(t,boundary);
        if(!affine_table(seen))throw std::logic_error("affine classification failed");
        auto enc=parity_blockers(boundary,seen);
        for(unsigned m=0;m<seen.size();++m){
            unsigned bits=0;for(size_t j=0;j<boundary.size();++j)if(m&(1u<<j))bits|=1u<<(boundary[j]-1);
            bool expected=false;
            for(unsigned q=0;q<64;++q){bool fits=true;for(int v:boundary)if((q^bits)&(1u<<(v-1)))fits=false;
                if(fits&&sat(cs,q)){expected=true;break;}}
            if(expected!=bool(seen[m])||sat(enc,bits)!=expected)throw std::logic_error("projected affine encoding mismatch");
        }
        std::string stem=std::string(argv[1])+"/case-"+std::to_string(k);
        std::ofstream cnf(stem+".cnf");cnf<<"p cnf 6 "<<cs.size()<<"\n";
        for(auto c:cs){for(int l:c)cnf<<l<<" ";cnf<<"0\n";}cnf.close();
        Proof proof(stem+".drup");AdaptivePropagator prop(6,cs);
        for(auto c:enc){
            Clause supp;for(int l:c)supp.push_back(std::abs(l));
            Clause hidden;std::set_difference(vars.begin(),vars.end(),supp.begin(),supp.end(),std::back_inserter(hidden));
            Clauses trace;if(!region_trace(prop,c,hidden,trace,after(2)))throw std::logic_error("missing proof");
            for(auto q:trace){proof.add(q);++lines;}
        }
        ++count;
    }
    // Negative control: three of four assignments are not an affine space.
    if(affine_table({1,1,1,0}))throw std::logic_error("false affine");
    std::cout<<"U9_KERNEL "<<count<<" proof_lines="<<lines<<"\n";
}
