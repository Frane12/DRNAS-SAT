// YM27: exact rational continuation of the existence bounds at successive couplings.
// No approximate lattice vacuum coefficients are generated.
inline bool path_radius(const Q& p,const Q& eta,Q& radius,Clock::time_point stop){
    if(p<=0||eta<0)return false;
    if(eta==0){radius=0;return true;}
    Q b=Q(8)/3;
    if(p*p<=4*b*eta)return false;
    constexpr int D=100000000;
    int lo=0,hi=D;
    // Largest grid point strictly below the vertex p/(2b).
    while(lo<hi){tick(stop);int m=lo+(hi-lo+1)/2;if(2*b*Q(m)/D<p)lo=m;else hi=m-1;}
    int top=lo;
    auto good=[&](int m){Q r=Q(m)/D;return p*r-b*r*r>=eta;};
    if(!good(top))return false;
    lo=0;hi=top;
    while(lo<hi){tick(stop);int m=lo+(hi-lo)/2;if(good(m))hi=m;else lo=m+1;}
    radius=Q(lo)/D;return true;
}
inline int gauge_vacuum_path_run(const std::string& raw,std::istream& in,int d,const std::filesystem::path& out,Clock::time_point stop){
    Q alpha=rational(in),k=rational(in),target=rational(in);int maxsteps;std::string extra;
    if(d<2||d>4||alpha<=0||target<=0||!(in>>maxsteps)||maxsteps<1||maxsteps>64||(in>>extra))
        throw std::runtime_error("vacuum path parameters");
    Q q=2*(d-1),u=k/alpha;if(u<0)u=-u;
    Q goal=q*u,b=Q(8)/3,ell=Q(320)/3,c=(324/q+2368*(1-1/q))/9;
    Q x=std::min(goal,Q(1)/160),r=0,gap=0,inv=0;
    std::vector<std::pair<Q,Q>> path;
    bool ok=false;
    try{
        if(goal<1/ell&&path_radius(1-ell*x,c*x*x,r,stop)){
            path.emplace_back(x,r);
            while(x<goal&&int(path.size())<maxsteps){
                tick(stop);Q delta=goal-x;if(delta>Q(1)/10000)delta=Q(1)/10000;
                bool accepted=false;
                for(int h=0;h<25;++h){
                    Q next=x+delta,p=1-ell*next-2*b*r;
                    Q eta=c*(next*next-x*x)+ell*delta*r,s=0;
                    if(path_radius(p,eta,s,stop)){
                        x=next;r+=s;path.emplace_back(x,s);accepted=true;break;
                    }
                    delta/=2;
                }
                if(!accepted)break;
            }
            Q p=1-ell*x-2*b*r;
            gap=alpha*(Q(1)/2-Q(4)/3*(x+r));
            ok=x==goal&&p>0&&gap>=target;
            if(ok)inv=1/p;
        }
        tick(stop);
    }catch(const Limit&){ok=false;}
    if(ok){
        std::ofstream o(out,std::ios::binary);
        o<<"drnas-op-v1\n"<<hash(raw)<<"\ngauge-vacuum-path "<<path.size()<<" "<<gap<<" "<<inv<<"\n";
        for(const auto& [x,s]:path)o<<x<<" "<<s<<"\n";
        o.close();if(!o)throw std::runtime_error("vacuum path evidence");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"su2_validated_vacuum_continuation\",\"certificate\":\""<<(ok?"ANALYTIC_BOUND":"none")<<"\",\"path_nodes\":"<<path.size()<<"}\n";
    return ok?30:0;
}
