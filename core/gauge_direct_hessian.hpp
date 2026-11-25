// YM29: direct Hessian estimate in the contraction norm, with joint spin-sector compression.
inline int gauge_direct_hessian_run(const std::string& raw,std::istream& in,int d,const std::filesystem::path& out,Clock::time_point stop){
    Q alpha=rational(in),k=rational(in),target=rational(in);std::string extra;
    if(d<2||d>4||alpha<=0||target<=0||(in>>extra))throw std::runtime_error("direct Hessian parameters");
    Q q=2*(d-1),u=k/alpha;if(u<0)u=-u;
    Q x=q*u,b=Q(8)/3,l=Q(160)/3*x;
    Q c=(81/q+576*(1-1/q))/9,eta=c*x*x,r=0,beta=0,gap=0,inv=0;
    bool ok=false;
    try{
        if(path_radius(1-l,eta,r,stop)){
            beta=l+2*b*r;
            if(beta<1){
                inv=1/(1-beta);
                gap=alpha*(Q(1)/2-Q(4)/3*x-2*r);
                ok=gap>=target;
            }
        }
        tick(stop);
    }catch(const Limit&){ok=false;}
    if(ok){
        std::ofstream o(out,std::ios::binary);
        o<<"drnas-op-v1\n"<<hash(raw)<<"\ngauge-direct-hessian "<<x<<" "<<eta<<" "<<l<<" "<<r<<" "<<beta<<" "<<inv<<" "<<gap<<"\n";
        o.close();if(!o)throw std::runtime_error("direct Hessian evidence");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"su2_direct_weak_norm_hessian\",\"certificate\":\""<<(ok?"ANALYTIC_BOUND":"none")<<"\"}\n";
    return ok?30:0;
}
