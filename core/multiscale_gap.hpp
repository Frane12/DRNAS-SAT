// Exact successive Schur complements at a fixed spectral cut.
// Each proposed layer is diagonal in the current Schur matrix.
inline int multiscale_run(const std::string& raw,std::istream& in,int n,const std::filesystem::path& out,Clock::time_point stop){
    Q gamma=rational(in);int count;
    if(gamma<=0||!(in>>count)||count<2||count>n-1)throw std::runtime_error("multiscale layers");
    std::vector<std::vector<int>> layers;std::set<int> drop;
    for(int s=0;s<count;++s){int k;if(!(in>>k)||k<1||k>=n)throw std::runtime_error("layer size");
        std::vector<int> g;for(int i=0;i<k;++i){int j;if(!(in>>j)||j<0||j>=n||!drop.insert(j).second)throw std::runtime_error("layer index");g.push_back(j);}layers.push_back(g);}
    if(drop.size()>=size_t(n))throw std::runtime_error("empty remainder");
    M h=read_matrix(in,n);std::string extra;if(in>>extra)throw std::runtime_error("trailing multiscale input");
    Q lo=h[0][0],upper=h[0][0],cap=0;bool first=true;
    for(int i=0;i<n;++i){
        Q r=0;for(int j=0;j<n;++j)if(i!=j){Q x=h[i][j];if(x<0)x=-x;r+=x;}
        Q t=h[i][i]-r;if(t<lo)lo=t;if(h[i][i]<upper)upper=h[i][i];
    }
    for(int i:drop){
        Q r=0;for(int j:drop)if(i!=j){Q x=h[i][j];if(x<0)x=-x;r+=x;}
        Q t=h[i][i]-r;if(first||t<cap){cap=t;first=false;}
    }
    // All principal eliminated states are positive at cuts below cap.
    // Graph-fill planning is only a hint; recheck every exact pivot.
    auto counts=[&](const Q& t)->std::optional<std::pair<int,int>>{
        if(t>=cap)return {};
        M a=shift(h,t);std::set<int> active;for(int i=0;i<n;++i)active.insert(i);
        for(const auto& layer:layers){
            tick(stop);
            for(int i:layer){
                if(a[i][i]<=0)return {};
                for(int j:layer)if(i!=j&&a[i][j]!=0)return {};
            }
            for(int i:layer){
                Q pivot=a[i][i];active.erase(i);
                for(int j:active)for(int l:active)a[j][l]-=a[j][i]*a[i][l]/pivot;
            }
        }
        M small;for(int i:active){std::vector<Q> row;for(int j:active)row.push_back(a[i][j]);small.push_back(std::move(row));}
        return inertia(std::move(small),stop);
    };
    bool ok=false;Q lower=lo;
    try{
        if(upper<cap){
            Q ground_lo=lo,excited_hi=cap;
            for(int iter=0;iter<48;++iter){
                tick(stop);Q t=(ground_lo+upper)/2;auto a=counts(t);if(!a)break;
                if(a->first+a->second>=1)upper=t;else ground_lo=t;
                t=(lower+excited_hi)/2;auto b=counts(t);if(!b)break;
                if(b->first<=1)lower=t;else excited_hi=t;
                if(lower-upper>=gamma){ok=true;break;}
            }
        }tick(stop);
    }catch(const Limit&){ok=false;}
    if(ok){std::ofstream f(out,std::ios::binary);f<<"drnas-op-v1\n"<<hash(raw)<<"\nmultiscale-gap "<<upper<<" "<<gamma<<" "<<lower<<"\n";f.close();if(!f)throw std::runtime_error("multiscale evidence write");}
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"successive_exact_schur\",\"certificate\":\""<<(ok?"OPERATOR_EXACT":"none")<<"\",\"layers\":"<<count<<",\"eliminated\":"<<drop.size()<<",\"remaining\":"<<n-drop.size()<<"}\n";
    return ok?30:0;
}
