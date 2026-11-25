#pragma once
// Source-only finite-field reconstruction and affine circuit restriction.
// SAT only: every proposed model must satisfy the full input, independently checked by bench.py.
// No family names, saved models, expected answers, CDCL, or external solving oracle.
#include "formula.hpp"
#include <array>
#include <bit>
#include <map>
#include <numeric>

namespace toolbox {
struct AlgebraStats {
    int domains=0, relations=0, rank3=0, gates=0, inputs=0, free=0, affine_rounds=0;
    uint64_t blocks=0;
};
inline int mod3(int x){x%=3;return x<0?x+3:x;}
inline bool finite3_model(const Input& f,Model& model,Time deadline,AlgebraStats& st){
    if(f.n<3||f.n%3||f.n>12000||f.cs.size()>200000||Clock::now()>=deadline)return false;
    std::set<Clause> binaries;
    for(const auto& c:f.cs)if(c.size()==2)binaries.insert(c);
    std::vector<int> owner(f.n+1,-1), digit(f.n+1,-1), indicator(f.n+1,0);
    std::vector<Clause> groups;
    for(const auto& c:f.cs){
        if(Clock::now()>=deadline)return false;
        if(c.size()!=3)continue;
        bool ok=true;
        for(int l:c)if(owner[std::abs(l)]>=0)ok=false;
        for(int i=0;i<3&&ok;++i)for(int j=i+1;j<3;++j){
            Clause b={-c[i],-c[j]};normalize(b);
            if(!binaries.count(b))ok=false;
        }
        if(!ok)continue;
        int g=int(groups.size());groups.push_back(c);
        for(int i=0;i<3;++i){int v=std::abs(c[i]);owner[v]=g;digit[v]=i;indicator[v]=c[i];}
    }
    st.domains=int(groups.size());
    // Require a complete disjoint domain reconstruction; no numeric-layout assumption.
    if(groups.size()*3!=size_t(f.n)||groups.size()>2000)return false;
    std::map<std::vector<int>,std::vector<uint8_t>> forbidden;
    for(const auto& c:f.cs){
        if(Clock::now()>=deadline)return false;
        if(c.size()<2||c.size()>6)continue;
        std::vector<std::pair<int,int>> t;
        bool ok=true;
        for(int l:c){int v=std::abs(l);if(indicator[v]!=-l){ok=false;break;}t.push_back({owner[v],digit[v]});}
        if(!ok)continue;
        std::sort(t.begin(),t.end());
        std::vector<int> key;int mask=0,p=1;
        for(auto [g,d]:t){if(!key.empty()&&key.back()==g){ok=false;break;}key.push_back(g);mask+=p*d;p*=3;}
        if(!ok)continue;
        auto& table=forbidden[key];if(table.empty())table.resize(p);
        table[mask]=1;
    }
    int n=int(groups.size());
    std::vector<std::vector<uint8_t>> basis(n);
    for(const auto& [key,tab]:forbidden){
        if(Clock::now()>=deadline)return false;
        int k=int(key.size()), allowed=int(tab.size())-std::accumulate(tab.begin(),tab.end(),0);
        if(allowed!=int(tab.size()/3))continue;
        std::vector<int> coeff(k,1);int rhs=-1;bool found=false;
        // A full-support affine hyperplane, normalized to first coefficient 1.
        for(int code=0;code<(1<<(k-1))&&!found;++code){
            for(int i=1;i<k;++i)coeff[i]=1+((code>>(i-1))&1);
            rhs=-1;bool eq=true;
            for(int t=0;t<int(tab.size());++t)if(!tab[t]){
                int tmp=t,val=0;
                for(int i=0;i<k;++i){val+=coeff[i]*(tmp%3);tmp/=3;}
                val%=3;
                if(rhs<0)rhs=val;else if(rhs!=val){eq=false;break;}
            }
            found=eq;
        }
        if(!found||rhs<0)continue;
        ++st.relations;
        std::vector<uint8_t> row(n+1,0);
        for(int i=0;i<k;++i)row[key[i]]=uint8_t(coeff[i]);
        row[n]=uint8_t(rhs);
        bool installed=false;
        for(int i=0;i<n;++i){
            if(!row[i])continue;
            if(basis[i].empty()){
                int inv=row[i]; // 1^-1=1; 2^-1=2 in GF(3)
                for(int j=i;j<=n;++j)row[j]=uint8_t((row[j]*inv)%3);
                basis[i]=std::move(row);++st.rank3;installed=true;break;
            }
            int a=row[i];
            for(int j=i;j<=n;++j)row[j]=uint8_t(mod3(int(row[j])-a*int(basis[i][j])));
        }
        if(!installed&&row[n])return false; // no UNSAT certificate emitted
    }
    if(st.relations==0)return false;
    // Free variables may have any value; try a few deterministic choices.
    uint64_t rng=0x9e3779b97f4a7c15ULL;
    for(int attempt=0;attempt<16&&Clock::now()<deadline;++attempt){
        std::vector<int> x(n,0);
        for(int i=n-1;i>=0;--i){
            if(basis[i].empty()){
                if(attempt){rng^=rng<<13;rng^=rng>>7;rng^=rng<<17;x[i]=int(rng%3);}
            }else{
                int sum=0;for(int j=i+1;j<n;++j)sum+=basis[i][j]*x[j];
                x[i]=mod3(int(basis[i][n])-sum);
            }
        }
        Model m(f.n+1,0);
        for(int i=0;i<n;++i)for(int j=0;j<3;++j){
            int l=groups[i][j];m[std::abs(l)]=int8_t((j==x[i])==(l>0));
        }
        if(satisfied(f.cs,m)){model=std::move(m);return true;}
    }
    return false;
}

struct CircuitGate {int z=0,a=0,b=0;bool xor_gate=false,inv=false;};
inline uint64_t compose_affine(uint64_t e,const std::vector<uint64_t>& sub){
    constexpr uint64_t K=1ULL<<32;
    uint64_t ans=e&K, mask=e&(K-1);
    while(mask){unsigned i=std::countr_zero(mask);ans^=sub[i];mask&=mask-1;}
    return ans;
}
// An exact, source-backed acyclic two-input gate grammar. Currently uses
// topological output numbering, not the problem name; all clauses must match.
inline bool circuit_affine_model(const Input& f,const Model& root,Model& model,Time deadline,AlgebraStats& st){
    constexpr uint64_t K=1ULL<<32, BAD=~0ULL;
    if(f.n<3||f.n>12000||f.cs.size()>50000||Clock::now()>=deadline)return false;
    std::set<Clause> source,covered;
    std::map<Clause,std::vector<Clause>> triples;
    for(const auto& c:f.cs){
        if(c.empty()||c.size()>3)return false;
        source.insert(c);
        if(c.size()==1)covered.insert(c);
        if(c.size()==3){
            Clause key;for(int l:c)key.push_back(std::abs(l));
            std::sort(key.begin(),key.end());triples[key].push_back(c);
        }
    }
    std::vector<CircuitGate> gs;
    std::vector<uint8_t> defined(f.n+1,0);
    for(const auto& [key,table0]:triples){
        if(Clock::now()>=deadline)return false;
        std::set<Clause> table(table0.begin(),table0.end());
        int a=key[0],b=key[1],z=key[2];
        if(defined[z])return false;
        CircuitGate gate{z,a,b,false,false};
        if(table.size()==4){
            int parity=-1;
            for(const auto& c:table){
                int p=0;for(int l:c)p^=l<0;
                if(parity<0)parity=p;else if(p!=parity)return false;
            }
            gate.xor_gate=true;gate.inv=(1-parity)!=0;
        }else if(table.size()==1){
            auto c=*table.begin(); // normalized by variable
            Clause ca={-c[0],-c[2]}, cb={-c[1],-c[2]};
            normalize(ca);normalize(cb);
            if(!source.count(ca)||!source.count(cb))return false;
            covered.insert(ca);covered.insert(cb);
            gate.a=c[0];gate.b=c[1];gate.inv=c[2]<0;
        }else return false;
        for(const auto& c:table)covered.insert(c);
        defined[z]=1;gs.push_back(gate);
    }
    if(covered!=source||gs.empty())return false;
    std::sort(gs.begin(),gs.end(),[](const auto& a,const auto& b){return a.z<b.z;});
    std::vector<int> primary;
    for(int v=1;v<=f.n;++v)if(!defined[v])primary.push_back(v);
    st.gates=int(gs.size());st.inputs=int(primary.size());st.free=st.inputs;
    if(primary.empty()||primary.size()>32)return false;
    int d=int(primary.size());
    std::vector<uint64_t> expr(d);
    for(int i=0;i<d;++i)expr[i]=1ULL<<i;
    // Re-express the circuit in the affine subspace imposed by its fixed outputs.
    // Repeating this can turn previously nonlinear gates into affine gates.
    for(int round=0;round<33&&Clock::now()<deadline;++round){
        std::vector<uint64_t> aff(f.n+1,BAD),basis(d,0);
        for(int i=0;i<st.inputs;++i)aff[primary[i]]=expr[i];
        auto lit=[&](int l){auto x=aff[std::abs(l)];return x==BAD?BAD:x^(l<0?K:0);};
        for(const auto& g:gs){
            auto a=lit(g.a),b=lit(g.b);uint64_t out=BAD;
            if(g.xor_gate){
                if(a!=BAD&&b!=BAD)out=a^b^(g.inv?K:0);
            }else{
                // OR with constant/same/complementary operands, then signed NOR.
                if(a==K||b==K)out=K;
                else if(a==0)out=b;
                else if(b==0)out=a;
                else if(a!=BAD&&b!=BAD){
                    if(a==b)out=a;else if((a^b)==K)out=K;
                }
                if(out!=BAD)out^=g.inv?0:K;
            }
            aff[g.z]=out;
        }
        int rank=0;
        for(int v=1;v<=f.n;++v)if(root[v]>=0&&aff[v]!=BAD){
            uint64_t row=aff[v]^(root[v]?K:0);bool inserted=false;
            while(row&(K-1)){
                unsigned p=std::countr_zero(row&(K-1));
                if(!basis[p]){basis[p]=row;++rank;inserted=true;break;}
                row^=basis[p];
            }
            if(!inserted&&(row&K))return false; // SAT-only module
        }
        if(!rank)break;
        ++st.affine_rounds;
        std::vector<uint64_t> sub(d,0);
        int nf=0;
        for(int i=0;i<d;++i)if(!basis[i])sub[i]=1ULL<<nf++;
        for(int i=d-1;i>=0;--i)if(basis[i])sub[i]=compose_affine(basis[i]^(1ULL<<i),sub);
        for(auto& e:expr)e=compose_affine(e,sub);
        d=nf;st.free=d;
    }
    // Bounded bit-parallel search on the remaining independent coordinates.
    // This is explicitly enumeration, not a polynomial decision algorithm.
    constexpr std::array<uint64_t,6> pat={0xaaaaaaaaaaaaaaaaULL,0xccccccccccccccccULL,0xf0f0f0f0f0f0f0f0ULL,0xff00ff00ff00ff00ULL,0xffff0000ffff0000ULL,0xffffffff00000000ULL};
    uint64_t count=1ULL<<d,blocks=(count+63)/64;
    uint64_t lane_mask=count<64?((1ULL<<count)-1):~0ULL;
    std::vector<uint64_t> x(f.n+1,0), coords(d,0);
    for(uint64_t block=0;block<blocks;++block){
        if((block&31)==0&&Clock::now()>=deadline)return false;
        for(int i=0;i<d;++i)coords[i]=i<6?pat[i]:0ULL-((block>>(i-6))&1ULL);
        for(int i=0;i<st.inputs;++i){
            uint64_t e=expr[i],v=e&K?~0ULL:0;
            e&=K-1;
            while(e){unsigned p=std::countr_zero(e);v^=coords[p];e&=e-1;}
            x[primary[i]]=v;
        }
        for(const auto& g:gs){
            uint64_t a=x[std::abs(g.a)],b=x[std::abs(g.b)];
            if(g.a<0)a=~a;
            if(g.b<0)b=~b;
            x[g.z]=g.xor_gate?(a^b^(g.inv?~0ULL:0)):(g.inv?(a|b):~(a|b));
        }
        uint64_t valid=lane_mask;
        // Root closure includes every source unit. Checking all fixed values is safe.
        for(int v=1;v<=f.n&&valid;++v)if(root[v]>=0)valid&=root[v]?x[v]:~x[v];
        ++st.blocks;
        if(valid){
            unsigned lane=std::countr_zero(valid);Model m(f.n+1,0);
            for(int v=1;v<=f.n;++v)m[v]=(x[v]>>lane)&1ULL;
            if(satisfied(f.cs,m)){model=std::move(m);return true;}
        }
    }
    return false;
}
} // namespace toolbox
