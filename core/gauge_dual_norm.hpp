// YM28: contract in a weaker norm, propagate stronger regularity separately.
inline int gauge_dual_norm_run(const std::string& raw,std::istream& in,int d,const std::filesystem::path& out,Clock::time_point stop){
    Q alpha=rational(in),k=rational(in),target=rational(in);std::string extra;
    if(d<2||d>4||alpha<=0||target<=0||(in>>extra))throw std::runtime_error("dual norm parameters");
    Q q=2*(d-1),u=k/alpha;if(u<0)u=-u;
    Q x=q*u,b=Q(8)/3,l=Q(160)/3*x;
    Q c0=(81/q+640*(1-1/q))/9,c1=(324/q+2368*(1-1/q))/9;
    Q e0=c0*x*x,e1=c1*x*x,r0=0,r1=0,beta=0,gap=0,inv=0;
    bool ok=false;
    try{
        if(path_radius(1-l,e0,r0,stop)){
            beta=l+2*b*r0;
            if(beta<1){
                inv=1/(1-beta);
                r1=(e1+2*l*r0)*inv;
                gap=alpha*(Q(1)/2-Q(4)/3*(x+r1));
                ok=gap>=target;
            }
        }
        tick(stop);
    }catch(const Limit&){ok=false;}
    if(ok){
        std::ofstream o(out,std::ios::binary);
        o<<"drnas-op-v1\n"<<hash(raw)<<"\ngauge-dual-norm "<<x<<" "<<e0<<" "<<e1<<" "<<l<<" "<<r0<<" "<<r1<<" "<<beta<<" "<<inv<<" "<<gap<<"\n";
        o.close();if(!o)throw std::runtime_error("dual norm evidence");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"su2_dual_norm_bootstrap\",\"certificate\":\""<<(ok?"ANALYTIC_BOUND":"none")<<"\"}\n";
    return ok?30:0;
}
