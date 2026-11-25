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

// Joint eigenspaces of commuting Pauli words. The product table carries the
// sign of each dependency; independent generators admit every sign pattern.
inline Q commuting_min(const std::vector<Term>& a,const std::vector<int>& g,Clock::time_point stop){
    if(g.empty()||g.size()>10)throw std::runtime_error("commuting block limit");
    std::string id(a[0].first.size(),'I');
    std::map<std::string,std::pair<unsigned,int>> table{{id,{0,1}}};
    unsigned dimension=1;
    std::vector<std::pair<unsigned,Q>> coeff;
    for(int j:g){
        tick(stop);
        auto& w=a[j].first;
        auto it=table.find(w);
        if(it==table.end()){
            auto old=table;
            for(const auto& [s,ms]:old){
                auto [prod,phase]=multiply(s,w);
                if(phase%2)throw std::runtime_error("commuting dependency phase");
                if(!table.emplace(prod,std::make_pair(ms.first|dimension,ms.second*(phase==0?1:-1))).second)
                    throw std::runtime_error("commuting dependency collision");
            }
            dimension*=2;it=table.find(w);
        }
        Q c=a[j].second*it->second.second;
        coeff.push_back({it->second.first,c});
    }
    Q best=0;
    for(unsigned x=0;x<dimension;++x){
        if((x&63u)==0)tick(stop);Q val=0;
        for(const auto& [mask,c]:coeff){if(std::popcount(x&mask)&1)val-=c;else val+=c;}
        if(x==0||val<best)best=val;
    }
    return best;
}
struct Partition {Q lower=0;std::string body;};
inline Partition evaluate(const std::vector<Term>& terms,const Groups& groups,const std::vector<char>& types,Q constant,Clock::time_point stop){
    Partition result;result.lower=constant;
    std::ostringstream o;o<<groups.size()<<"\n";
    for(size_t i=0;i<groups.size();++i){
        tick(stop);const auto& g=groups[i];char typ=types[i];o<<typ<<" "<<g.size();
        for(int j:g)o<<" "<<j;
        if(typ=='A'){Q b=norm_bound(terms,g);result.lower-=b;o<<" "<<b;}
        else if(typ=='D')result.lower+=diagonal_min(terms,g,stop);
        else result.lower+=commuting_min(terms,g,stop);
        o<<"\n";
    }
    result.body=o.str();return result;
}
inline int support_size(const std::string& w){return int(std::count_if(w.begin(),w.end(),[](char c){return c!='I';}));}
inline Partition explore(const std::vector<Term>& terms,Q constant,int policy,Clock::time_point stop){
    std::vector<int> order(terms.size());std::iota(order.begin(),order.end(),0);
    if(policy%3==1)std::reverse(order.begin(),order.end());
    if(policy%3==2)std::stable_sort(order.begin(),order.end(),[&](int i,int j){return absq(terms[i].second)>absq(terms[j].second);});
    Groups groups;std::vector<char> types;
    for(int j:order){
        tick(stop);const auto& w=terms[j].first;
        int best=-1;char best_type='A';long score=-1;
        for(int i=0;i<int(groups.size());++i){
            if((i&63)==0)tick(stop);
            auto& g=groups[i];bool a=true,c=g.size()<10;int overlap=0;
            for(int k:g){
                bool b=anti(w,terms[k].first);a=a&&b;c=c&&!b;
                for(size_t l=0;l<w.size();++l)if(w[l]!='I'&&terms[k].first[l]!='I')++overlap;
            }
            for(char typ: {'A','C'}){
                if((typ=='A'&&!a)||(typ=='C'&&!c)||(g.size()>1&&types[i]!=typ))continue;
                // Independent commuting terms can be joined: a later term
                // may close a signed product relation. Block size remains capped.
                long s=long(overlap)+long(g.size())*2;
                if((policy<3&&typ=='A')||(policy>=3&&typ=='C'))s+=10000;
                if(s>score){best=i;best_type=typ;score=s;}
            }
        }
        if(best<0){groups.push_back({j});types.push_back('A');}
        else{groups[best].push_back(j);types[best]=best_type;}
    }
    return evaluate(terms,groups,types,constant,stop);
}


// Learned templates are suggestions only. Every matched group is checked again
// by evaluate() and the independent source-bound certificate auditor.
inline std::set<std::string> load_rules(){
    std::set<std::string> result;
    const char* name=std::getenv("DRNAS_CORE_RULE_MEMORY");
    if(!name||!*name)return result;
    std::ifstream in(name);std::string s;
    if(!std::getline(in,s)||s!="drnas-rule-memory-v1")return result;
    for(int i=0;i<32&&std::getline(in,s);++i){
        if((s.size()==3&&s[0]=='C'&&s[1]>='3'&&s[1]<='8'&&(s[2]=='+'||s[2]=='-'))||(s.size()==2&&s[0]=='A'&&s[1]>='2'&&s[1]<='9')||s=="A10")result.insert(s);
    }
    if(const char* selected=std::getenv("DRNAS_CORE_RULE_SELECT")){
        std::string key(selected);if(!result.count(key))result.clear();else result={key};
    }
    return result;
}
inline Partition replay_rules(const std::vector<Term>& terms,Q constant,const std::set<std::string>& rules,
                              Clock::time_point stop,int& matches){
    Groups groups;std::vector<char> types;std::vector<bool> used(terms.size());
    std::map<std::string,int> index;
    for(int i=0;i<int(terms.size());++i)index.emplace(terms[i].first,i);
    // Longer learned identities: discover a commuting neighborhood and
    // find signed dependencies in its bounded subset lattice. The verifier
    // will reconstruct the actual commuting block, not trust the memory.
    bool long_rules=false;
    for(int len=5;len<=8;++len)
        long_rules=long_rules||rules.count("C"+std::to_string(len)+"+")||rules.count("C"+std::to_string(len)+"-");
    if(long_rules){
        unsigned scans=0,checks=0;
        const std::string id(terms.empty()?0:terms[0].first.size(),'I');
        for(int seed=0;seed<int(terms.size())&&scans<50000&&checks<50000;++seed){
            tick(stop);if(used[seed])continue;
            std::vector<int> g{seed};
            for(int j=seed+1;j<int(terms.size())&&g.size()<10&&checks<50000;++j){
                if((j&63)==0)tick(stop);++checks;if(used[j])continue;
                bool good=true;for(int k:g)if(anti(terms[k].first,terms[j].first)){good=false;break;}
                if(good)g.push_back(j);
            }
            if(g.size()<5)continue;
            const unsigned count=1u<<g.size();
            std::vector<std::pair<std::string,int>> products(count);
            products[0]={id,0};
            unsigned selected=0;
            for(unsigned mask=1;mask<count&&scans<50000;++mask){
                if((mask&63u)==0)tick(stop);++scans;
                unsigned bit=std::countr_zero(mask),prev=mask&(mask-1);
                auto [w,p]=multiply(products[prev].first,terms[g[bit]].first);
                p=(p+products[prev].second)%4;products[mask]={std::move(w),p};
                int len=std::popcount(mask);
                if(len<5||len>8||products[mask].first!=id||p%2)continue;
                if(!rules.count("C"+std::to_string(len)+(p==0?"+":"-")))continue;
                if(!selected||len>std::popcount(selected))selected=mask;
            }
            if(selected){
                std::vector<int> hit;
                for(unsigned i=0;i<g.size();++i)if(selected&(1u<<i)){hit.push_back(g[i]);used[g[i]]=true;}
                groups.push_back(std::move(hit));types.push_back('C');++matches;
            }
        }
    }
    // Composed relation: two signed commuting triples sharing a factor
    // imply a signed four-word identity. The shared factor need not be
    // present in a new input. Match equal pair products and check ALL pairs.
    if(rules.count("C4+")||rules.count("C4-")){
        struct Pair {int i,j,p;};
        std::map<std::string,std::vector<Pair>> products;
        unsigned pairs=0;
        for(int i=0;i<int(terms.size())&&pairs<50000;++i){
            tick(stop);
            for(int j=i+1;j<int(terms.size())&&pairs<50000;++j){
                if((j&63)==0)tick(stop);++pairs;
                if(used[i]||used[j]||anti(terms[i].first,terms[j].first))continue;
                auto [word,p]=multiply(terms[i].first,terms[j].first);
                auto& v=products[word];bool found=false;
                for(auto q:v){
                    if(used[q.i]||used[q.j]||q.i==i||q.i==j||q.j==i||q.j==j)continue;
                    if(!rules.count((p==q.p)?"C4+":"C4-"))continue;
                    if(anti(terms[i].first,terms[q.i].first)||anti(terms[i].first,terms[q.j].first)||
                       anti(terms[j].first,terms[q.i].first)||anti(terms[j].first,terms[q.j].first))continue;
                    groups.push_back({q.i,q.j,i,j});types.push_back('C');
                    used[q.i]=used[q.j]=used[i]=used[j]=true;++matches;found=true;break;
                }
                if(!found&&v.size()<16)v.push_back({i,j,p});
            }
        }
    }
    // Signed product relation P_i P_j = +/- P_k, independent of labels.
    if(rules.count("C3+")||rules.count("C3-")){
        for(int i=0;i<int(terms.size());++i){
            tick(stop);if(used[i])continue;
            for(int j=i+1;j<int(terms.size());++j){
                if((j&63)==0)tick(stop);if(used[j]||anti(terms[i].first,terms[j].first))continue;
                auto [w,p]=multiply(terms[i].first,terms[j].first);
                auto k=index.find(w);
                if(k==index.end()||k->second<=j||used[k->second]||!rules.count(p==0?"C3+":"C3-"))continue;
                groups.push_back({i,j,k->second});types.push_back('C');
                used[i]=used[j]=used[k->second]=true;++matches;break;
            }
        }
    }
    for(int size=10;size>=2;--size){
        if(!rules.count("A"+std::to_string(size)))continue;
        for(int i=0;i<int(terms.size());++i){
            tick(stop);if(used[i])continue;std::vector<int> g{i};
            for(int j=i+1;j<int(terms.size())&&int(g.size())<size;++j){
                if((j&63)==0)tick(stop);if(used[j])continue;
                bool good=true;for(int k:g)if(!anti(terms[j].first,terms[k].first)){good=false;break;}
                if(good)g.push_back(j);
            }
            if(int(g.size())==size){for(int j:g)used[j]=true;groups.push_back(g);types.push_back('A');++matches;}
        }
    }
    for(int i=0;i<int(terms.size());++i)if(!used[i]){groups.push_back({i});types.push_back('A');}
    return evaluate(terms,groups,types,constant,stop);
}

// A commuting Pauli Hamiltonian with constant sum |c| is a sum of
// positive projectors. Signed Gaussian elimination proves a common zero
// eigenspace exists (no -I in the generated group); a nontrivial generator
// proves an excited eigenspace exists. Every nonzero energy >= min 2|c|.
inline bool commuting_projector_gap(Sum a,int n,Q target,Clock::time_point stop,
                                    int& rank,Q& lower){
    if(target<=0)return false;
    std::string id(n,'I');Q constant=a[id];a.erase(id);
    if(a.empty())return false;
    Q total=0;lower=0;
    for(auto i=a.begin();i!=a.end();++i){
        tick(stop);Q weight=absq(i->second);total+=weight;
        if(lower==0||2*weight<lower)lower=2*weight;
        for(auto j=a.begin();j!=i;++j){tick(stop);if(anti(i->first,j->first))return false;}
    }
    if(constant!=total||lower<target)return false;
    std::map<int,std::pair<std::string,int>> basis;
    auto pivot=[&](const std::string& word){
        for(int i=0;i<n;++i){char c=word[i];
            if(c=='X'||c=='Y')return 2*i;
            if(c=='Z')return 2*i+1;
        }return -1;
    };
    for(const auto& [word,c]:a){
        tick(stop);std::string row=word;int sign=c<0?1:-1;
        while(true){
            int p=pivot(row);
            if(p<0){if(sign<0)return false;break;}
            auto it=basis.find(p);
            if(it==basis.end()){basis.emplace(p,std::make_pair(row,sign));break;}
            auto [prod,phase]=multiply(row,it->second.first);
            if(phase%2)return false;
            sign*=it->second.second*(phase==0?1:-1);row=std::move(prod);
        }
    }
    rank=int(basis.size());return rank>0&&rank<=n;
}

// Compare H against gamma times the Hamming-weight operator D.
// H|0...0>=0 is checked without constructing a state vector.
// If H-gamma D >= 0, the orthogonal complement has energy >= gamma.
inline bool product_zero(const Sum& a,int n,Clock::time_point stop){
    std::map<std::pair<std::string,int>,Q> amplitudes;
    for(const auto& [word,c]:a){
        tick(stop);std::string flips(n,'0');int phase=0;
        for(int i=0;i<n;++i){if(word[i]=='X'||word[i]=='Y')flips[i]='1';if(word[i]=='Y')++phase;}
        phase%=4;amplitudes[{flips,phase%2}]+=(phase<2?c:-c);
    }
    for(const auto& [key,c]:amplitudes)if(c!=0)return false;
    return true;
}
inline Partition product_gap_bound(Sum a,int n,Q gamma,Clock::time_point stop,int& attempts){
    std::string id(n,'I');a[id]-=gamma*n/2;
    for(int i=0;i<n;++i){std::string z=id;z[i]='Z';a[z]+=gamma/2;}
    Q constant=a[id];a.erase(id);
    std::vector<Term> terms;for(const auto& t:a)if(t.second!=0)terms.push_back(t);
    if(terms.empty()){++attempts;return Partition{constant,"0\n"};}
    int matches=0;++attempts;
    Partition best=replay_rules(terms,constant,{"C3+","C3-"},stop,matches);
    for(int policy=0;policy<6&&best.lower<0;++policy){
        tick(stop);++attempts;auto p=explore(terms,constant,policy,stop);
        if(p.lower>best.lower)best=std::move(p);
    }
    return best;
}

inline int run(const std::string& raw,const std::filesystem::path& out,double seconds){
    auto stop=Clock::now()+std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
    if(raw.size()>2000000)throw std::runtime_error("symbolic input limit");
    std::istringstream in(raw);std::string p,s,task,extra;int n,m,k=0;
    if(!(in>>p>>s>>task>>n>>m)||p!="p"||s!="sop"||n<1||n>256)throw std::runtime_error("symbolic header");
    Q target=0;if(task=="lower"||task=="lower-fixed"||task=="projector-gap"||task=="product-gap")target=core_operator::rational(in);
    else if(task=="commute"){if(!(in>>k))throw std::runtime_error("second term count");}
    else throw std::runtime_error("symbolic task");
    Sum a=read(in,n,m),b;if(task=="commute")b=read(in,n,k);if(in>>extra)throw std::runtime_error("trailing symbolic input");
    bool ok=false;std::string method="symbolic_limits";std::ostringstream proof;int attempts=0,memory_matches=0;bool memory_won=false;double memory_s=0;int memory_attempts=0;std::string best_bound="none";
    try{
        if(task=="commute"){ok=commutes(a,b,stop);method="sparse_commutator";}
        else if(task=="projector-gap"){int rank=0;Q lower=0;ok=commuting_projector_gap(a,n,target,stop,rank,lower);method="commuting_projector_gap";if(ok)proof<<rank<<" "<<lower<<"\n";}
        else if(task=="product-gap"){
            method="product_ground_comparison";
            if(target>0&&product_zero(a,n,stop)){
                auto p=product_gap_bound(a,n,target,stop,attempts);std::ostringstream value;value<<p.lower;best_bound=value.str();
                ok=p.lower>=0;if(ok)proof<<p.lower<<"\n"<<p.body;
            }
        }
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
            Groups groups=diag;groups.insert(groups.end(),anti_groups.begin(),anti_groups.end());
            std::vector<char> types(diag.size(),'D');types.insert(types.end(),anti_groups.size(),'A');
            Partition best;bool have=false;
            // Each candidate gets a bounded portion of remaining time. A failed
            // candidate cannot erase a previously completed proof.
            auto trial=[&](auto fn,Clock::time_point until){
                ++attempts;
                try{Partition p=fn(until);tick(until);if(!have||p.lower>best.lower){best=std::move(p);have=true;}}
                catch(const core_operator::Limit&){}
            };
            auto start_trials=Clock::now();
            auto safe_stop=start_trials+(stop-start_trials)*9/10;
            auto rules=task=="lower"?load_rules():std::set<std::string>{};
            if(!rules.empty()){
                auto until=start_trials+(safe_stop-start_trials)/5;
                auto replay_start=Clock::now();++memory_attempts;
                trial([&](auto end){return replay_rules(terms,constant,rules,end,memory_matches);},until);
                memory_s=std::chrono::duration<double>(Clock::now()-replay_start).count();
                memory_won=have&&memory_matches>0&&best.lower>=target;
            }
            auto baseline_stop=task=="lower-fixed"?safe_stop:start_trials+(safe_stop-start_trials)*2/5;
            if(!memory_won)trial([&](auto until){return evaluate(terms,groups,types,constant,until);},baseline_stop);
            bool improved=false;
            if(task=="lower"&&(!have||best.lower<target)){
                for(int policy=0;policy<6&&Clock::now()<safe_stop;++policy){
                    auto now=Clock::now();auto until=now+(safe_stop-now)/(6-policy);
                    bool had=have;Q before=best.lower;
                    trial([&](auto end){return explore(terms,constant,policy,end);},until);
                    if(have&&(!had||best.lower>before))improved=true;
                    if(have&&best.lower>=target)break;
                }
            }
            if(have){std::ostringstream b;b<<best.lower;best_bound=b.str();ok=best.lower>=target;
                if(ok)proof<<best.lower<<"\n"<<best.body;}
            method=memory_won?"learned_operator_rule":improved?"adaptive_operator_bounds":"local_operator_bounds";
        }
        tick(stop);
    }catch(const core_operator::Limit&){ok=false;method="symbolic_limits";}
    if(ok){std::ofstream f(out,std::ios::binary);f<<"drnas-sop-v1\n"<<core_operator::hash(raw)<<"\n"<<task<<"\n"<<proof.str();f.close();if(!f)throw std::runtime_error("symbolic write");}
    std::cout<<"c {\"domain\":\"symbolic_operator\",\"method\":\""<<method<<"\",\"certificate\":\""<<(ok?"SYMBOLIC_OPERATOR_EXACT":"none")<<"\",\"qubits\":"<<n<<",\"partitions_tried\":"<<attempts<<",\"memory_matches\":"<<memory_matches<<",\"memory_attempts\":"<<memory_attempts<<",\"memory_s\":"<<memory_s<<",\"memory_proved\":"<<(memory_won?"true":"false")<<",\"best_lower\":\""<<best_bound<<"\"}\n";
    return ok?31:0;
}
}
