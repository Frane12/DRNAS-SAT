#pragma once
// Source-backed word algebra lifting from the already reconstructed gate graph.
// No file names, expected answers, known shift constants or saved models.
// A recovered word equation proposes SAT witnesses only, checked on every original clause.
#include "formula.hpp"
#include <array>
#include <bit>
#include <map>
#include <numeric>
#include <tuple>
namespace toolbox {
struct WordLiftStats {
    int recovered=0, pool=0, nodes=0, shifts=0, xors=0, adds=0, bits=0;
    uint64_t candidates=0;
};
using WordBits=std::vector<int>;
struct WordNode {WordBits bits;int op=0,a=-1,b=-1,shift=0;}; // 0 input,1 leftxor,2 rightxor,3 xor,4 add
inline int word_max(const WordBits& w){int m=0;for(int l:w)m=std::max(m,std::abs(l));return m;}
inline bool word_distinct(const WordBits& w){
    std::set<int> s;for(int l:w)if(!l||!s.insert(std::abs(l)).second)return false;return true;
}
struct WordGateIndex {
    using Key=std::tuple<int,int,int>;
    std::map<Key,std::vector<int>> lut;
    template<class Gates> explicit WordGateIndex(const Gates& gs){
        for(const auto& g:gs){
            int a=std::min(std::abs(g.a),std::abs(g.b)),b=std::max(std::abs(g.a),std::abs(g.b)),mask=0;
            for(int i=0;i<4;++i){
                auto value=[&](int l){int x=(i>>(std::abs(l)==a?0:1))&1;return x^(l<0);};
                int x=value(g.a),y=value(g.b);
                int z=g.xor_gate?(x^y^int(g.inv)):((x|y)^int(!g.inv));
                mask|=z<<i;
            }
            lut[{a,b,mask}].push_back(g.z);
            lut[{a,b,mask^15}].push_back(-g.z);
        }
        for(auto& [k,vs]:lut)std::sort(vs.begin(),vs.end(),[](int x,int y){return std::abs(x)<std::abs(y);});
    }
    // op: 0 xor, 1 and, 2 or. Return signed output literal, zero if not present.
    int get(int op,int a,int b,int floor)const{
        if(!a||!b)return 0;
        if(a==b)return op==0?0:a;
        if(a==-b)return 0;
        int u=std::min(std::abs(a),std::abs(b)),v=std::max(std::abs(a),std::abs(b)),mask=0;
        for(int i=0;i<4;++i){
            auto val=[&](int l){return ((i>>(std::abs(l)==u?0:1))&1)^(l<0);};
            int x=val(a),y=val(b);
            mask|=(op==0?(x^y):op==1?(x&y):(x|y))<<i;
        }
        auto it=lut.find({u,v,mask});if(it==lut.end())return 0;
        const auto& list=it->second;
        auto p=std::upper_bound(list.begin(),list.end(),floor,[](int n,int l){return n<std::abs(l);});
        return p==list.end()?0:*p;
    }
    int maj(int a,int b,int c,int floor)const{
        if(!a||!b||!c)return 0;
        if(a==b||a==c)return a;if(b==c)return b;
        if(a==-b)return c;if(a==-c)return b;if(b==-c)return a;
        std::array<int,3> q={a,b,c};
        // c*(a|b)+(a*b); also the XOR-propagate and dual forms.
        for(int p=0;p<3;++p){
            int x=q[p],y=q[(p+1)%3],z=q[(p+2)%3];
            int xy=get(1,x,y,floor);
            for(int p_op:{0,2}){
                int prop=get(p_op,x,y,floor),pc=get(1,prop,z,floor);
                if(int r=get(2,xy,pc,floor))return r;
                // Disjoint products can also be combined by XOR.
                if(p_op==0)if(int r=get(0,xy,pc,floor))return r;
            }
            int xo=get(2,x,y,floor),zc=get(2,get(1,x,y,floor),z,floor);
            if(int r=get(1,xo,zc,floor))return r;
            int xz=get(1,x,z,floor),yz=get(1,y,z,floor);
            if(int r=get(2,get(2,xy,xz,floor),yz,floor))return r;
            int oz=get(2,x,z,floor),oy=get(2,y,z,floor);
            if(int r=get(1,get(1,xo,oz,floor),oy,floor))return r;
        }
        return 0;
    }
    WordBits shift(const WordBits& a,int s,bool left)const{
        int n=int(a.size()),floor=word_max(a);WordBits out(n);
        for(int i=0;i<n;++i){
            int j=left?i-s:i+s;
            out[i]=(j<0||j>=n)?a[i]:get(0,a[i],a[j],floor);
            if(!out[i])return {};
        }
        if(word_max(out)<=floor||!word_distinct(out))return {};
        return out;
    }
    WordBits combine(const WordBits& a,const WordBits& b,bool add)const{
        int n=int(a.size()),floor=std::max(word_max(a),word_max(b)),carry=0;
        WordBits out(n);
        for(int i=0;i<n;++i){
            int x=a[i],y=b[i],t=get(0,x,y,floor);
            if(!add||i==0){
                if(!t)return {};
                out[i]=t;
                if(add&&n>1){carry=get(1,x,y,floor);if(!carry)return {};}
            }else{
                int s=get(0,t,carry,floor);
                if(!s)s=get(0,get(0,x,carry,floor),y,floor);
                if(!s)s=get(0,get(0,y,carry,floor),x,floor);
                if(!s)return {};
                out[i]=s;
                if(i+1<n){carry=maj(x,y,carry,floor);if(!carry)return {};}
            }
        }
        if(word_max(out)<=floor||!word_distinct(out))return {};
        return out;
    }
};
struct WordPlan {std::vector<WordNode> nodes;int target=-1;uint32_t rhs=0;};
inline WordPlan recover_word_plan(const WordGateIndex& index,WordBits primary,const Model& units,Time deadline,WordLiftStats& st){
    WordPlan p;auto& ns=p.nodes;
    const int w=int(primary.size()),limit=1024;
    std::map<WordBits,int> seen;
    ns.push_back({primary,0,-1,-1,0});seen[primary]=0;
    auto test=[&](const WordBits& x,uint32_t& rhs){
        rhs=0;for(int i=0;i<w;++i){int l=x[i];if(units[std::abs(l)]<0)return false;
            rhs|=uint32_t(units[std::abs(l)]^(l<0))<<i;}return true;
    };
    auto insert=[&](WordBits b,int op,int a,int c,int s){
        if(b.empty()||seen.count(b)||ns.size()>=size_t(limit))return;
        int id=int(ns.size());seen[b]=id;ns.push_back({std::move(b),op,a,c,s});
        uint32_t rhs=0;if(p.target<0&&test(ns.back().bits,rhs)){p.target=id;p.rhs=rhs;}
    };
    // Infer shifts from complete groups of bit-level XOR identities, not constants.
    for(int i=0;i<int(ns.size())&&ns.size()<256&&p.target<0&&Clock::now()<deadline;++i){
        auto a=ns[i].bits;
        for(int s=1;s<w&&Clock::now()<deadline;++s)for(bool left:{true,false})
            insert(index.shift(a,s,left),left?1:2,i,-1,s);
    }
    int linear=int(ns.size());st.pool=std::max(st.pool,linear);
    // Fold with any recovered word. A macro is admitted only if every bit and
    // every nonterminal carry is backed by a gate in the source graph.
    for(int i=0;i<int(ns.size())&&p.target<0&&ns.size()<size_t(limit)&&Clock::now()<deadline;++i){
        auto a=ns[i].bits;
        for(int j=0;j<linear&&p.target<0&&Clock::now()<deadline;++j){
            if(i==j)continue;
            auto b=ns[j].bits;
            insert(index.combine(a,b,false),3,i,j,0);
            insert(index.combine(a,b,true),4,i,j,0);
        }
    }
    st.nodes=std::max(st.nodes,int(ns.size()));
    return p;
}
template<class Gates>
inline bool word_lift_model(const Input& f,const Gates& gs,const std::vector<int>& primary,
    const std::vector<uint64_t>& affine,int d,Model& model,Time deadline,WordLiftStats& st){
    const int w=int(primary.size());
    if(w<3||w>32||d<0||d>w||Clock::now()>=deadline)return false;
    Model units(f.n+1,-1);int count_units=0;
    for(const auto& c:f.cs)if(c.size()==1){
        int l=c[0],v=std::abs(l);
        if(units[v]>=0&&units[v]!=(l>0))return false;
        if(units[v]<0)++count_units;
        units[v]=l>0;
    }
    if(count_units<w)return false;
    WordGateIndex ix(gs);
    WordPlan p=recover_word_plan(ix,primary,units,std::min(deadline,after(.35)),st);
    if(p.target<0){
        WordBits reverse=primary;std::reverse(reverse.begin(),reverse.end());
        p=recover_word_plan(ix,reverse,units,std::min(deadline,after(.35)),st);
    }
    if(p.target<0)return false;
    st.recovered=1;st.bits=w;
    // Keep only ancestors of the fixed-output equation.
    std::vector<uint8_t> live(p.nodes.size(),0);
    live[p.target]=1;
    for(int i=p.target;i>0;--i)if(live[i]){
        const auto& q=p.nodes[i];live[q.a]=1;if(q.b>=0)live[q.b]=1;
    }
    std::vector<int> remap(p.nodes.size(),-1);std::vector<WordNode> plan;
    for(int i=0;i<=p.target;++i)if(live[i]){
        auto q=p.nodes[i];if(q.a>=0)q.a=remap[q.a];if(q.b>=0)q.b=remap[q.b];
        remap[i]=int(plan.size());plan.push_back(q);
        st.shifts+=q.op==1||q.op==2;st.xors+=q.op==3;st.adds+=q.op==4;
    }
    constexpr uint64_t K=1ULL<<32;
    std::array<uint32_t,32> cols{};uint32_t offset=0;
    const auto& bit_order=plan.front().bits;
    for(int i=0;i<w;++i){
        auto it=std::find(primary.begin(),primary.end(),bit_order[i]);
        if(it==primary.end())return false;
        uint64_t e=affine[it-primary.begin()];
        if(e&K)offset|=uint32_t(1)<<i;
        for(int j=0;j<d;++j)if((e>>j)&1ULL)cols[j]|=uint32_t(1)<<i;
    }
    std::array<std::array<uint32_t,256>,4> lut{};
    for(int k=0;k<4;++k)for(int u=1;u<256;++u){
        int b=std::countr_zero(unsigned(u));
        lut[k][u]=lut[k][u&(u-1)]^cols[8*k+b];
    }
    // Native packed evaluation of an exact word equation; this remains bounded
    // enumeration of residual coordinates, not a polynomial SAT method.
    constexpr size_t B=512;
    std::vector<std::array<uint32_t,B>> a(plan.size());
    uint32_t mask=w==32?~0u:((uint32_t(1)<<w)-1);
    uint64_t count=1ULL<<d;
    bool identity=offset==0&&d==w;
    for(int i=0;i<d&&identity;++i)identity=cols[i]==(uint32_t(1)<<i);
    for(uint64_t base=0;base<count;base+=B){
        if(Clock::now()>=deadline)return false;
        size_t len=size_t(std::min<uint64_t>(B,count-base));
        if(identity){for(size_t j=0;j<len;++j)a[0][j]=uint32_t(base+j);}
        else for(size_t j=0;j<len;++j){
            uint32_t u=uint32_t(base+j);
            a[0][j]=offset^lut[0][u&255]^lut[1][(u>>8)&255]^lut[2][(u>>16)&255]^lut[3][u>>24];
        }
        for(size_t k=1;k<plan.size();++k){
            const auto& q=plan[k];auto* out=a[k].data();const auto* x=a[q.a].data();
            if(q.op==1)for(size_t j=0;j<len;++j)out[j]=(x[j]^(x[j]<<q.shift))&mask;
            else if(q.op==2)for(size_t j=0;j<len;++j)out[j]=x[j]^(x[j]>>q.shift);
            else{
                const auto* y=a[q.b].data();
                if(q.op==3)for(size_t j=0;j<len;++j)out[j]=x[j]^y[j];
                else for(size_t j=0;j<len;++j)out[j]=(x[j]+y[j])&mask;
            }
        }
        st.candidates+=len;
        for(size_t j=0;j<len;++j)if(a.back()[j]==p.rhs){
            Model m(f.n+1,0);uint32_t key=a.front()[j];
            for(int i=0;i<w;++i)m[bit_order[i]]=(key>>i)&1u;
            for(const auto& g:gs){
                int x=(m[std::abs(g.a)]!=0)^(g.a<0),y=(m[std::abs(g.b)]!=0)^(g.b<0);
                m[g.z]=g.xor_gate?(x^y^int(g.inv)):((x|y)^int(!g.inv));
            }
            if(satisfied(f.cs,m)){model=std::move(m);return true;}
        }
    }
    return false;
}
} // namespace toolbox
