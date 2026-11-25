// Exact spectral decimation of a diagonal positive high-energy block.
inline int decimation_run(const std::string& raw,std::istream& in,int n,const std::filesystem::path& out,Clock::time_point stop){
    Q gamma=rational(in);int k;
    if(gamma<=0||!(in>>k)||k<1||k>=n)throw std::runtime_error("decimation dimensions");
    std::set<int> drop;
    for(int i=0;i<k;++i){int j;if(!(in>>j)||j<0||j>=n||!drop.insert(j).second)throw std::runtime_error("decimation indices");}
    M h=read_matrix(in,n);std::string extra;if(in>>extra)throw std::runtime_error("decimation trailing input");
    std::vector<int> keep;for(int i=0;i<n;++i)if(!drop.count(i))keep.push_back(i);
    for(int i:drop)for(int j:drop)if(i!=j&&h[i][j]!=0)throw std::runtime_error("decimation block not diagonal");
    Q cap=h[*drop.begin()][*drop.begin()],lo=h[0][0],upper=h[keep[0]][keep[0]];
    for(int i:drop)if(h[i][i]<cap)cap=h[i][i];
    for(int i:keep)if(h[i][i]<upper)upper=h[i][i];
    for(int i=0;i<n;++i){Q r=0;for(int j=0;j<n;++j)if(i!=j){Q v=h[i][j];if(v<0)v=-v;r+=v;}Q t=h[i][i]-r;if(t<lo)lo=t;}
    auto counts=[&](const Q& t){
        if(t>=cap)throw std::runtime_error("nonpositive eliminated block");
        M a(keep.size(),std::vector<Q>(keep.size()));
        for(size_t i=0;i<keep.size();++i){tick(stop);for(size_t j=0;j<keep.size();++j){
            a[i][j]=h[keep[i]][keep[j]];if(i==j)a[i][j]-=t;
            for(int e:drop)a[i][j]-=h[keep[i]][e]*h[e][keep[j]]/(h[e][e]-t);
        }}
        return inertia(std::move(a),stop);
    };
    bool ok=false;Q lower=lo;
    try{
        if(upper<cap){
            Q ground_lo=lo,excited_hi=cap;
            for(int iter=0;iter<48;++iter){
                tick(stop);
                Q t=(ground_lo+upper)/2;auto [a,b]=counts(t);
                if(a+b>=1)upper=t;else ground_lo=t;
                t=(lower+excited_hi)/2;auto [c,d]=counts(t);
                if(c<=1)lower=t;else excited_hi=t;
                if(lower-upper>=gamma){ok=true;break;}
            }
        }
        tick(stop);
    }catch(const Limit&){ok=false;}
    if(ok){std::ofstream f(out,std::ios::binary);f<<"drnas-op-v1\n"<<hash(raw)<<"\ndecimation-gap "<<upper<<" "<<gamma<<" "<<lower<<"\n";f.close();if(!f)throw std::runtime_error("decimation evidence write");}
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"positive_block_schur_decimation\",\"certificate\":\""<<(ok?"OPERATOR_EXACT":"none")<<"\",\"eliminated\":"<<k<<",\"remaining\":"<<keep.size()<<"}\n";
    return ok?30:0;
}
