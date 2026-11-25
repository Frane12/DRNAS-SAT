// YM26: explicit Neumann inverse for the linearization at F1.
inline int gauge_vacuum_inverse_run(const std::string& raw,std::istream& in,int d,const std::filesystem::path& out,Clock::time_point stop){
    Q alpha=rational(in),k=rational(in),target=rational(in);int n;std::string extra;
    if(d<2||d>4||alpha<=0||target<=0||!(in>>n)||n<1||n>64||(in>>extra))
        throw std::runtime_error("inverse parameters");
    Q q=2*(d-1),u=k/alpha;if(u<0)u=-u;
    Q x=q*u,limit=1/(160*q),b=Q(8)/3,l=Q(320)/3*x;
    Q r=9*x,eta=(324*q+2624*q*(q-1))*u*u/9;
    Q gap=alpha*(Q(1)/2-Q(4)/3*(x+r));
    Q m=0,image=0,lip=0,tail=0;
    bool ok=u<=limit&&l<1&&gap>=target;
    try{
        if(ok){
            m=1/(1-l);image=m*(eta+b*r*r);lip=2*m*b*r;
            ok=image<=r&&lip<1;
            if(ok){Q p=1;for(int i=0;i<n;++i){tick(stop);p*=lip;}tail=m*eta*p/(1-lip);}
        }
        tick(stop);
    }catch(const Limit&){ok=false;}
    if(ok){
        std::ofstream o(out,std::ios::binary);
        o<<"drnas-op-v1\n"<<hash(raw)<<"\ngauge-vacuum-inverse "<<limit<<" "<<l<<" "<<m<<" "<<r<<" "<<eta<<" "<<image<<" "<<lip<<" "<<gap<<" "<<tail<<"\n";
        o.close();if(!o)throw std::runtime_error("inverse evidence");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"su2_plaquette_neumann_inverse\",\"certificate\":\""<<(ok?"ANALYTIC_BOUND":"none")<<"\"}\n";
    return ok?30:0;
}
