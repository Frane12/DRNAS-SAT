// YM25: gauge-invariant norm and recentered contraction. Fixed-spacing only.
inline int gauge_vacuum_continue_run(const std::string& raw,std::istream& in,int d,const std::filesystem::path& out,Clock::time_point stop){
    Q alpha=rational(in),k=rational(in),target=rational(in);int n;std::string extra;
    if(d<2||d>4||alpha<=0||target<=0||!(in>>n)||n<1||n>64||(in>>extra))throw std::runtime_error("continuation parameters");
    Q q=2*(d-1),u=k/alpha;if(u<0)u=-u;
    Q b=Q(8)/3,a=32*q,c=(324*q+656*4*q*(q-1))/9;
    Q limit=1/(240*q),center=a*u,r=10*q*u,eta=c*u*u;
    Q image=eta+2*b*center*r+b*r*r,lip=2*b*(center+r);
    Q gap=alpha*(Q(1)/2-Q(4)/3*(center+r)),tail=0;
    bool ok=u<=limit&&image<=r&&lip<1&&gap>=target;
    try{
        if(ok){Q power=1;for(int i=0;i<n;++i){tick(stop);power*=lip;}tail=eta*power/(1-lip);}
        tick(stop);
    }catch(const Limit&){ok=false;}
    if(ok){
        std::ofstream o(out,std::ios::binary);
        o<<"drnas-op-v1\n"<<hash(raw)<<"\ngauge-vacuum-continue "<<limit<<" "<<center<<" "<<r<<" "<<eta<<" "<<image<<" "<<lip<<" "<<gap<<" "<<tail<<"\n";
        o.close();if(!o)throw std::runtime_error("continuation evidence");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"su2_recentered_contraction\",\"certificate\":\""<<(ok?"ANALYTIC_BOUND":"none")<<"\"}\n";
    return ok?30:0;
}
