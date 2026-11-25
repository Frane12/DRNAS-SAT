#pragma once
// Sparse Pauli sums. No Hilbert-space matrix is allocated.
namespace core_symbolic {
using core_operator::Q;using core_operator::Clock;using core_operator::tick;
using Term=std::pair<std::string,Q>;
using Sum=std::map<std::string,Q>;
using Groups=std::vector<std::vector<int>>;
inline bool anti(const std::string& a,const std::string& b){
    bool x=false;for(size_t i=0;i<a.size();++i)x^=a[i]!='I'&&b[i]!='I'&&a[i]!=b[i];return x;
}
inline Sum read(std::istream& in,int n,int m){
    if(m<0||m>4096)throw std::runtime_error("symbolic term limit");
    Sum a;for(int i=0;i<m;++i){Q q=core_operator::rational(in);std::string s;
        if(!(in>>s)||int(s.size())!=n||s.find_first_not_of("IXYZ")!=std::string::npos)throw std::runtime_error("Pauli word");
        a[s]+=q;}
    for(auto i=a.begin();i!=a.end();)if(i->second==0)i=a.erase(i);else ++i;
    return a;
}
inline std::pair<std::string,int> multiply(const std::string& a,const std::string& b){
    std::string c=a;int phase=0;
    const std::string xyz="XYZ";
    for(size_t i=0;i<a.size();++i){
        if(a[i]=='I')c[i]=b[i];else if(b[i]=='I'){}else if(a[i]==b[i])c[i]='I';
        else{int u=int(xyz.find(a[i])),v=int(xyz.find(b[i]));c[i]=xyz[3-u-v];phase+=(v==(u+1)%3)?1:3;}
    }return {c,phase%4};
}
inline bool commutes(const Sum& a,const Sum& b,Clock::time_point stop){
    Sum result;
    for(const auto& [s,x]:a){tick(stop);for(const auto& [t,y]:b)if(anti(s,t)){
        auto [w,p]=multiply(s,t);if(p==1)result[w]+=x*y;else if(p==3)result[w]-=x*y;else throw std::runtime_error("phase");}}
    for(const auto& [s,x]:result)if(x!=0)return false;return true;
}
inline Q absq(Q x){if(x<0)x=-x;return x;}
inline Q norm_bound(const std::vector<Term>& a,const std::vector<int>& g){
    Q square=0,hi=0;for(int j:g){Q x=a[j].second;square+=x*x;hi+=absq(x);}
    if(g.size()==1)return hi;
    Q lo=0;for(int i=0;i<32;++i){Q mid=(lo+hi)/2;if(mid*mid>=square)hi=mid;else lo=mid;}return hi;
}
inline Q diagonal_min(const std::vector<Term>& a,const std::vector<int>& g,Clock::time_point stop){
    std::vector<int> support;for(size_t i=0;i<a[0].first.size();++i)
        for(int j:g)if(a[j].first[i]!='I'){support.push_back(int(i));break;}
    if(support.size()>16)throw std::runtime_error("diagonal block limit");
    std::vector<unsigned> masks;for(int j:g){unsigned mask=0;for(size_t i=0;i<support.size();++i){
        char c=a[j].first[support[i]];if(c=='Z')mask|=1u<<i;else if(c!='I')throw std::runtime_error("not diagonal");}masks.push_back(mask);}
    Q best=0;for(unsigned v=0;v<(1u<<support.size());++v){if((v&63u)==0)tick(stop);Q val=0;
        for(size_t k=0;k<g.size();++k){Q x=a[g[k]].second;if(std::popcount(v&masks[k])&1)val-=x;else val+=x;}
        if(v==0||val<best)best=val;}
    return best;
}
inline int run(const std::string& raw,const std::filesystem::path& out,double seconds){
    auto stop=Clock::now()+std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
    if(raw.size()>2000000)throw std::runtime_error("symbolic input limit");
    std::istringstream in(raw);std::string p,s,task,extra;int n,m,k=0;
    if(!(in>>p>>s>>task>>n>>m)||p!="p"||s!="sop"||n<1||n>256)throw std::runtime_error("symbolic header");
    Q target=0;if(task=="lower")target=core_operator::rational(in);
    else if(task=="commute"){if(!(in>>k))throw std::runtime_error("second term count");}
    else throw std::runtime_error("symbolic task");
    Sum a=read(in,n,m),b;if(task=="commute")b=read(in,n,k);if(in>>extra)throw std::runtime_error("trailing symbolic input");
    bool ok=false;std::string method="symbolic_limits";std::ostringstream proof;
    try{
        if(task=="commute"){ok=commutes(a,b,stop);method="sparse_commutator";}
        else{
            std::string id(n,'I');Q constant=0;auto it=a.find(id);if(it!=a.end()){constant=it->second;a.erase(it);}
            std::vector<Term> terms(a.begin(),a.end());
            // Greedy exact local diagonal blocks: grouping is valid even if blocks overlap.
            Groups diag,anti_groups;std::vector<std::set<int>> supports;
            for(int j=0;j<int(terms.size());++j){tick(stop);auto& w=terms[j].first;
                std::set<int> supp;bool zonly=true;for(int i=0;i<n;++i){if(w[i]!='I')supp.insert(i);if(w[i]=='X'||w[i]=='Y')zonly=false;}
                if(zonly&&supp.size()<=16){
                    int selected=-1,overlap=0;for(int g=0;g<int(diag.size());++g){
                        int common=0;for(int i:supp)common+=supports[g].count(i);
                        if(common>overlap&&supports[g].size()+supp.size()-common<=16){selected=g;overlap=common;}}
                    if(selected<0){diag.push_back({j});supports.push_back(supp);}
                    else{diag[selected].push_back(j);supports[selected].insert(supp.begin(),supp.end());}
                }else{
                    bool placed=false;for(auto& g:anti_groups){bool good=true;for(int i:g)if(!anti(w,terms[i].first)){good=false;break;}
                        if(good){g.push_back(j);placed=true;break;}}
                    if(!placed)anti_groups.push_back({j});
                }
            }
            Q lower=constant;std::ostringstream groups;groups<<diag.size()+anti_groups.size()<<"\n";
            for(auto& g:diag){lower+=diagonal_min(terms,g,stop);groups<<"D "<<g.size();for(int j:g)groups<<" "<<j;groups<<"\n";}
            for(auto& g:anti_groups){Q bound=norm_bound(terms,g);lower-=bound;groups<<"A "<<g.size();for(int j:g)groups<<" "<<j;groups<<" "<<bound<<"\n";}
            ok=lower>=target;proof<<lower<<"\n"<<groups.str();method="local_operator_bounds";
        }
        tick(stop);
    }catch(const core_operator::Limit&){ok=false;method="symbolic_limits";}
    if(ok){std::ofstream f(out,std::ios::binary);f<<"drnas-sop-v1\n"<<core_operator::hash(raw)<<"\n"<<task<<"\n"<<proof.str();f.close();if(!f)throw std::runtime_error("symbolic write");}
    std::cout<<"c {\"domain\":\"symbolic_operator\",\"method\":\""<<method<<"\",\"certificate\":\""<<(ok?"SYMBOLIC_OPERATOR_EXACT":"none")<<"\",\"qubits\":"<<n<<"}\n";
    return ok?31:0;
}
}
