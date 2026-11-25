#pragma once
#include <boost/multiprecision/cpp_int.hpp>
namespace core_operator {
using Q=boost::multiprecision::cpp_rational;
using Z=boost::multiprecision::cpp_int;
using M=std::vector<std::vector<Q>>;
using Clock=std::chrono::steady_clock;
struct Limit {};
inline void tick(Clock::time_point stop){if(Clock::now()>=stop)throw Limit{};}
inline Z integer(const std::string& s){
    if(s.empty()||s.size()>17)throw std::runtime_error("operator integer limit");
    bool neg=s[0]=='-';size_t i=neg?1:0;if(i==s.size())throw std::runtime_error("integer");
    Z z=0;for(;i<s.size();++i){if(s[i]<'0'||s[i]>'9')throw std::runtime_error("integer");z=z*10+(s[i]-'0');}
    if(neg)z=-z;return z;
}
inline Q rational(std::istream& in){
    std::string s;if(!(in>>s))throw std::runtime_error("missing rational");
    auto p=s.find('/');if(p==std::string::npos)return Q(integer(s));
    Z d=integer(s.substr(p+1));if(d<=0)throw std::runtime_error("denominator");
    return Q(integer(s.substr(0,p)))/Q(d);
}
inline M read_matrix(std::istream& in,int n){
    M a(n,std::vector<Q>(n));for(auto& row:a)for(auto& x:row)x=rational(in);
    for(int i=0;i<n;++i)for(int j=0;j<i;++j)if(a[i][j]!=a[j][i])throw std::runtime_error("not real symmetric");
    return a;
}
inline M product(const M& a,const M& b,Clock::time_point stop){
    int n=int(a.size());M c(n,std::vector<Q>(n));
    for(int i=0;i<n;++i){tick(stop);for(int k=0;k<n;++k)if(a[i][k]!=0)
        for(int j=0;j<n;++j)c[i][j]+=a[i][k]*b[k][j];}
    return c;
}
inline M shift(M a,const Q& e){for(size_t i=0;i<a.size();++i)a[i][i]-=e;return a;}
// Exact congruence elimination. A zero diagonal in a PSD matrix requires a zero row.
// Returns -1 if not PSD, otherwise its rank.
inline int psd(M a,Clock::time_point stop){
    int n=int(a.size()),rank=0;
    for(int k=0;k<n;++k){tick(stop);int p=-1;
        for(int i=k;i<n;++i){if(a[i][i]<0)return -1;if(a[i][i]>0&&p<0)p=i;}
        if(p<0){for(int i=k;i<n;++i)for(int j=k;j<n;++j)if(a[i][j]!=0)return -1;return rank;}
        if(p!=k){std::swap(a[p],a[k]);for(auto& row:a)std::swap(row[p],row[k]);}
        Q pivot=a[k][k];++rank;
        for(int i=k+1;i<n;++i)for(int j=i;j<n;++j){
            a[i][j]-=a[i][k]*a[k][j]/pivot;a[j][i]=a[i][j];}
    }return rank;
}
inline bool gap(const M& h,const Q& e,const Q& g,Clock::time_point stop){
    M a=shift(h,e);int r=psd(a,stop);
    if(r<=0||r==int(a.size()))return false; // nonempty ground and excited subspaces
    M b=product(a,a,stop);for(size_t i=0;i<a.size();++i)for(size_t j=0;j<a.size();++j)b[i][j]-=g*a[i][j];
    return psd(std::move(b),stop)>=0;
}

// Exact inertia by rational congruence. A zero diagonal with a nonzero
// off-diagonal is converted to a nonzero pivot by e_i <- e_i + e_j.
inline std::pair<int,int> inertia(M a,Clock::time_point stop){
    int n=int(a.size()),negative=0,zero=0;
    for(int k=0;k<n;++k){
        tick(stop);int p=-1;
        for(int i=k;i<n;++i)if(a[i][i]!=0){p=i;break;}
        if(p<0){
            int u=-1,v=-1;
            for(int i=k;i<n&&u<0;++i)for(int j=i+1;j<n;++j)if(a[i][j]!=0){u=i;v=j;break;}
            if(u<0){zero=n-k;break;}
            Q diagonal=a[u][u]+2*a[u][v]+a[v][v];
            for(int j=k;j<n;++j)if(j!=u){Q x=a[u][j]+a[v][j];a[u][j]=a[j][u]=x;}
            a[u][u]=diagonal;p=u;
        }
        if(p!=k){std::swap(a[p],a[k]);for(auto& row:a)std::swap(row[p],row[k]);}
        Q pivot=a[k][k];if(pivot<0)++negative;
        for(int i=k+1;i<n;++i)for(int j=i;j<n;++j){
            a[i][j]-=a[i][k]*a[k][j]/pivot;a[j][i]=a[i][j];
        }
    }
    return {negative,zero};
}
inline bool interval_gap(const M& a,const Q& gamma,Clock::time_point stop,Q& upper,Q& lower){
    int n=int(a.size());if(n<2)return false;
    Q lo=a[0][0],hi=lo;
    for(int i=0;i<n;++i){Q radius=0;for(int j=0;j<n;++j)if(i!=j){Q x=a[i][j];if(x<0)x=-x;radius+=x;}
        Q l=a[i][i]-radius,h=a[i][i]+radius;if(l<lo)lo=l;if(h>hi)hi=h;}
    Q ground_lo=lo,excited_hi=hi;upper=hi;lower=lo;
    // The second eigenvalue is counted with multiplicity: only a simple
    // ground state is certified by this task. No floating-point guess.
    for(int iter=0;iter<48;++iter){
        tick(stop);
        Q mid=(ground_lo+upper)/2;
        auto [neg,z]=inertia(shift(a,mid),stop);
        if(neg+z>=1)upper=mid;else ground_lo=mid;
        mid=(lower+excited_hi)/2;
        auto [neg2,z2]=inertia(shift(a,mid),stop);
        if(neg2<=1)lower=mid;else excited_hi=mid;
        if(lower-upper>=gamma)return true;
        if(excited_hi-ground_lo<gamma)return false;
    }
    return false;
}


// Infinite rotor-index model on N_0^d, d=1 or 2. Diagonal sum j(j+2),
// axial hopping -k and (d=2) joint (1,1) hopping -c. All omitted states
// are bounded below by N(N+2)-2(d|k|+|c|).
struct RotorHead {M a,gram;Q tail,lo;};
inline RotorHead rotor_head(int d,int n,Q k,Q c,Clock::time_point stop){
    int size=d==1?n:n*n;M a(size,std::vector<Q>(size)),gram=a;
    std::map<std::pair<int,int>,std::vector<Q>> boundary;
    std::vector<std::tuple<int,int,Q>> steps{{1,0,k}};
    if(d==2){steps.emplace_back(0,1,k);steps.emplace_back(1,1,c);}
    for(int i=0;i<size;++i){
        tick(stop);int x=d==1?i:i/n,y=d==1?0:i%n;
        a[i][i]=x*(x+2)+y*(y+2);
        for(const auto& [dx,dy,w]:steps)if(w!=0)for(int sign:{-1,1}){
            int u=x+sign*dx,v=y+sign*dy;if(u<0||v<0)continue;
            if(u<n&&v<n){int j=d==1?u:u*n+v;a[i][j]-=w;}
            else{auto& row=boundary[{u,v}];if(row.empty())row.resize(size);row[i]-=w;}
        }
    }
    for(const auto& [point,row]:boundary)for(int i=0;i<size;++i)if(row[i]!=0)
        for(int j=0;j<size;++j)if(row[j]!=0)gram[i][j]+=row[i]*row[j];
    if(k<0)k=-k;if(c<0)c=-c;Q norm=2*(d*k+c);
    return {std::move(a),std::move(gram),Q(n*(n+2))-norm,-norm};
}
inline bool rotor_gap(int d,int n,Q k,Q c,const Q& gamma,Clock::time_point stop,Q& upper,Q& lower){
    auto h=rotor_head(d,n,k,c,stop);Q ground_lo=h.lo;upper=0;
    // The index-zero basis vector gives E0<=0; refine by head inertia.
    lower=h.lo;Q high=h.tail-Q(1)/16;
    if(high<lower)return false;
    for(int iter=0;iter<40;++iter){
        tick(stop);Q mid=(ground_lo+upper)/2;
        auto [ng,z]=inertia(shift(h.a,mid),stop);
        if(ng+z>=1)upper=mid;else ground_lo=mid;
        mid=(lower+high)/2;
        M b=shift(h.a,mid);Q den=h.tail-mid;
        for(size_t i=0;i<b.size();++i)for(size_t j=0;j<b.size();++j)b[i][j]-=h.gram[i][j]/den;
        if(inertia(std::move(b),stop).first<=1)lower=mid;else high=mid;
        if(lower-upper>=gamma)return true;
    }
    return false;
}

inline std::string hash(const std::string& raw){
    unsigned char bytes[EVP_MAX_MD_SIZE];unsigned count=0;
    if(!EVP_Digest(raw.data(),raw.size(),bytes,&count,EVP_sha256(),nullptr)||count!=32)throw std::runtime_error("SHA256");
    std::ostringstream o;o<<std::hex<<std::setfill('0');for(unsigned i=0;i<count;++i)o<<std::setw(2)<<unsigned(bytes[i]);return o.str();
}
#include "gauge_gap.hpp"
#include "gauge_stability.hpp"
#include "decimation_gap.hpp"
#include "multiscale_gap.hpp"
// Physical one-cycle SU(2) Hamiltonian in the character basis chi_{j/2}.
// Exact tridiagonal Sturm counts; the entire infinite tail is bounded.
inline int ks_sturm(int n,const Q& e,const Q& k,const Q& cut,const Q& correction,Clock::time_point stop){
    Q prev=1,last=1;int signs=0,prior=1;
    for(int j=0;j<n;++j){
        tick(stop);Q d=e*j*(j+2)-cut;if(j==n-1)d-=correction;
        Q next=d*last;if(j)next-=k*k*prev;
        int sign=next>0?1:next<0?-1:0;
        if(sign){if(sign!=prior)++signs;prior=sign;}
        prev=last;last=next;
    }
    return signs; // number strictly below cut, including terminal-zero handling
}
inline int ks_loop_run(const std::string& raw,std::istream& in,int len,const std::filesystem::path& out,Clock::time_point stop){
    int cutoff;if(len<3||len>24||!(in>>cutoff)||cutoff<2||cutoff>128)throw std::runtime_error("ks loop dimensions");
    Q a=rational(in),g2=rational(in),target=rational(in);std::string extra;
    if(a<=0||g2<=0||target<=0||(in>>extra))throw std::runtime_error("ks loop parameters");
    Q e=Q(len)*g2/(8*a),k=2/(a*g2),tail=e*cutoff*(cutoff+2)-2*k;
    Q bottom=-2*k,upper=0,low=bottom,high=tail;
    bool ok=false;
    try{
        if(high>low){
            Q ground_lo=bottom;
            for(int i=0;i<80;++i){
                tick(stop);Q mid=(ground_lo+upper)/2;
                if(ks_sturm(cutoff,e,k,mid,0,stop)>=1)upper=mid;else ground_lo=mid;
                mid=(low+high)/2;
                if(ks_sturm(cutoff,e,k,mid,k*k/(tail-mid),stop)<=1)low=mid;else high=mid;
                if(low-upper>=target){ok=true;break;}
            }
        }
        tick(stop);
    }catch(const Limit&){ok=false;}
    if(ok){
        std::ofstream f(out,std::ios::binary);
        f<<"drnas-op-v1\n"<<hash(raw)<<"\nks-loop-gap "<<upper<<" "<<low<<"\n";f.close();
        if(!f)throw std::runtime_error("ks loop evidence");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"ks_loop_sturm_schur\",\"certificate\":\""<<(ok?"OPERATOR_EXACT":"none")<<"\"}\n";
    return ok?30:0;
}

// Two cycles sharing one edge. Delete its positive Casimir for a lower
// comparison, retain it in a central product Rayleigh trial for the upper.
inline Q angular_hop2(int j,int l,const Q& k){
    return k*k*Q((j-l+1)*(j+l+2))/((j+1)*(j+2));
}
inline int angular_sturm(int n,int l,const Q& e,const Q& k,const Q& cut,bool tail,Clock::time_point stop){
    Q prev=1,last=1;int count=0,prior=1;
    Q tau=e*n*(n+2)-2*k;
    for(int j=l;j<n;++j){
        tick(stop);Q d=e*j*(j+2)-cut;
        if(tail&&j==n-1)d-=angular_hop2(j,l,k)/(tau-cut);
        Q next=d*last;if(j>l)next-=angular_hop2(j-1,l,k)*prev;
        int sign=next>0?1:next<0?-1:0;
        if(sign){if(sign!=prior)++count;prior=sign;}
        prev=last;last=next;
    }
    return count;
}
inline int ks_pair_run(const std::string& raw,std::istream& in,int len,const std::filesystem::path& out,Clock::time_point stop){
    int n;if(len<3||len>24||!(in>>n)||n<3||n>128)throw std::runtime_error("pair dimensions");
    Q a=rational(in),g2=rational(in),target=rational(in);std::string extra;
    if(a<=0||g2<=0||target<=0||(in>>extra))throw std::runtime_error("pair parameters");
    Q e=Q(len-1)*g2/(8*a),f=Q(len)*g2/(8*a),k=2/(a*g2);
    Q bottom=-2*k,tau=e*n*(n+2)-2*k,u=0,ulo=bottom;
    Q l0=bottom,l1=bottom,la=bottom,h0=tau,h1=tau,ha=tau;
    bool ok=false;Q lower=0;
    try{
        for(int it=0;it<32;++it){
            tick(stop);
            Q mid=(ulo+u)/2;
            if(angular_sturm(n,0,f,k,mid,false,stop)>=1)u=mid;else ulo=mid;
            auto refine=[&](Q& lo,Q& hi,int l,int count){
                Q m=(lo+hi)/2;
                if(angular_sturm(n,l,e,k,m,true,stop)<=count)lo=m;else hi=m;
            };
            refine(l0,h0,0,0);refine(l1,h1,0,1);refine(la,ha,1,0);
            Q radial=l0+l1,angular=2*la;lower=radial<angular?radial:angular;
            if(lower-2*u>=target){ok=true;break;}
        }
        tick(stop);
    }catch(const Limit&){ok=false;}
    if(ok){
        std::ofstream o(out,std::ios::binary);
        o<<"drnas-op-v1\n"<<hash(raw)<<"\nks-pair-gap "<<u<<" "<<l0<<" "<<l1<<" "<<la<<"\n";o.close();
        if(!o)throw std::runtime_error("pair evidence");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"ks_shared_edge_angular_comparison\",\"certificate\":\""<<(ok?"OPERATOR_EXACT":"none")<<"\"}\n";
    return ok?30:0;
}

inline int run(const std::string& raw,const std::filesystem::path& out,double seconds){
    auto stop=Clock::now()+std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
    if(raw.size()>65536)throw std::runtime_error("operator input limit");
    std::istringstream in(raw);std::string p,op,kind,extra;int n;
    if(!(in>>p>>op>>kind>>n)||p!="p"||op!="op"||n<1||(kind=="gauge-gap"?n>256:n>24))throw std::runtime_error("operator header");
    if(kind=="ks-pair-gap")return ks_pair_run(raw,in,n,out,stop);
    if(kind=="ks-loop-gap")return ks_loop_run(raw,in,n,out,stop);
    if(kind=="gauge-gap")return gauge_run(raw,in,n,out,stop);
    if(kind=="gauge-stability")return gauge_stability_run(raw,in,n,out,stop);
    if(kind=="decimation-gap")return decimation_run(raw,in,n,out,stop);
    if(kind=="multiscale-gap")return multiscale_run(raw,in,n,out,stop);
    Q e=0,g=0;
    if(kind=="rotor-gap"){
        // Here n is the rotor count, not the matrix dimension.
        int cutoff; if(n>2||!(in>>cutoff)||cutoff<2||cutoff>4)throw std::runtime_error("rotor dimensions");
        Q gamma=rational(in),k=rational(in),c=rational(in),upper=0,lower=0;
        if(gamma<=0||(n==1&&c!=0)||(in>>extra))throw std::runtime_error("rotor parameters");
        bool ok=false;try{ok=rotor_gap(n,cutoff,k,c,gamma,stop,upper,lower);tick(stop);}catch(const Limit&){ok=false;}
        if(ok){std::ofstream f(out,std::ios::binary);f<<"drnas-op-v1\n"<<hash(raw)<<"\nrotor-gap "<<upper<<" "<<gamma<<" "<<lower<<"\n";f.close();if(!f)throw std::runtime_error("rotor evidence write");}
        std::cout<<"c {\"domain\":\"operator\",\"method\":\"infinite_rotor_schur\",\"certificate\":\""<<(ok?"OPERATOR_EXACT":"none")<<"\"}\n";return ok?30:0;
    }
    if(kind=="gap")e=rational(in);
    if(kind=="gap"||kind=="auto-gap"||kind=="interval-gap"){g=rational(in);if(g<=0)throw std::runtime_error("gap must be positive");}
    else if(kind!="psd"&&kind!="pd"&&kind!="commute")throw std::runtime_error("operator task");
    M a=read_matrix(in,n),b;
    if(kind=="commute")b=read_matrix(in,n);
    if(in>>extra)throw std::runtime_error("operator trailing data");
    bool ok=false;Q excited_lower=0;std::string method="operator_limits";
    try{
        if(kind=="psd"||kind=="pd"){int r=psd(a,stop);ok=kind=="psd"?r>=0:r==n;method="exact_congruence";}
        else if(kind=="commute"){ok=product(a,b,stop)==product(b,a,stop);method="exact_commutator";}
        else if(kind=="gap"){ok=gap(a,e,g,stop);method="spectral_polynomial";}
        else if(kind=="interval-gap"){ok=interval_gap(a,g,stop,e,excited_lower);method="rational_spectral_bracketing";}
        else{
            std::set<Q> candidates{Q(0)};Q lower=a[0][0];
            for(int i=0;i<n;++i){Q radius=0,sum=0;for(int j=0;j<n;++j){sum+=a[i][j];if(i!=j){Q v=a[i][j];if(v<0)v=-v;radius+=v;}}
                Q lo=a[i][i]-radius;if(i==0||lo<lower)lower=lo;candidates.insert(a[i][i]);candidates.insert(sum);}
            candidates.insert(lower);for(int i=-16;i<=16;++i)candidates.insert(Q(i));
            for(const Q& q:candidates){tick(stop);if(gap(a,q,g,stop)){e=q;ok=true;break;}}
            method="discover_rational_ground";
        }
        tick(stop);
    }catch(const Limit&){ok=false;method="operator_limits";}
    if(ok){
        std::ofstream f(out,std::ios::binary);f<<"drnas-op-v1\n"<<hash(raw)<<"\n"<<kind<<" "<<e<<" "<<g;if(kind=="interval-gap")f<<" "<<excited_lower;f<<"\n";f.close();
        if(!f)throw std::runtime_error("operator evidence write");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\""<<method<<"\",\"certificate\":\""<<(ok?"OPERATOR_EXACT":"none")<<"\"}\n";
    return ok?30:0;
}
}
