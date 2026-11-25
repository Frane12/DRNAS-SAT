#include "factor_reason.hpp"
#include <iostream>
#include <random>
using namespace toolbox;
void require(bool b,const char* msg){if(!b)throw std::runtime_error(msg);}
bool sat_bits(const Clause& c,unsigned m){for(int l:c)if(bool(m&(1u<<(std::abs(l)-1)))==(l>0))return true;return false;}
int main(int argc,char** argv){
    if(argc!=2)return 2;
    std::string dir=argv[1];std::mt19937 rng(81241);
    int tests=0,wide=0,proof_lines=0;
    for(int k=0;k<81;++k){
        int n=k==0?7:5+k%4;Clause scope;for(int v=1;v<=n;++v)scope.push_back(v);
        Clauses cs;
        if(k==0){
            // Existentially eliminate one variable from two four-literal clauses.
            // Consequence has six literals, outside the old regional width cap.
            cs={{1,2,3,7},{4,5,6,-7}};
        }else{
            int m=4+int(rng()%25);
            for(int j=0;j<m;++j){
                Clause c=scope;std::shuffle(c.begin(),c.end(),rng);c.resize(2+rng()%2);
                for(int& l:c)if(rng()&1u)l=-l;normalize(c);cs.push_back(c);
            }
        }
        for(auto& c:cs)normalize(c);
        Clause boundary=scope;boundary.pop_back();if(k>0&&k%2)boundary.erase(boundary.begin());
        auto table=factor_table(scope,cs,after(2));require(table.complete,"table timed out");
        auto projected=factor_project(table,boundary);
        auto blockers=factor_prime_blockers(boundary,projected,after(2));
        for(unsigned m=0;m<projected.size();++m){
            bool expected=false;
            for(unsigned a=0;a<(1u<<n);++a){
                bool match=true;for(size_t j=0;j<boundary.size();++j)
                    if(((a>>(boundary[j]-1))&1u)!=((m>>j)&1u)){match=false;break;}
                if(match&&std::all_of(cs.begin(),cs.end(),[&](const Clause& c){return sat_bits(c,a);})){expected=true;break;}
            }
            unsigned actual=0;for(size_t j=0;j<boundary.size();++j)if(m&(1u<<j))actual|=1u<<(boundary[j]-1);
            bool reconstructed=std::all_of(blockers.begin(),blockers.end(),[&](const Clause& c){return sat_bits(c,actual);});
            require(bool(projected[m])==expected&&reconstructed==expected,"projection equivalence failed");
        }
        std::string stem=dir+"/case-"+std::to_string(k);
        std::ofstream cnf(stem+".cnf");cnf<<"p cnf "<<n<<" "<<cs.size()<<"\n";
        for(auto c:cs){for(int l:c)cnf<<l<<" ";cnf<<"0\n";}cnf.close();
        Proof proof(stem+".drup");AdaptivePropagator prop(n,cs);
        for(auto c:blockers){
            Clause vars;for(int l:c)vars.push_back(std::abs(l));
            Clause hidden;std::set_difference(scope.begin(),scope.end(),vars.begin(),vars.end(),std::back_inserter(hidden));
            Clauses trace;require(region_trace(prop,c,hidden,trace,after(2)),"proof unavailable");
            for(auto q:trace){proof.add(q);++proof_lines;}
            if(c.size()>3)++wide;
        }
        if(k==0)require(std::find(blockers.begin(),blockers.end(),Clause{1,2,3,4,5,6})!=blockers.end(),"missing six-variable consequence");
        ++tests;
    }
    std::cout<<"U8_KERNEL "<<tests<<" wide="<<wide<<" proof_lines="<<proof_lines<<"\n";
}
