// YM24: arithmetic certificate of an explicit local Fourier norm contraction.
// Analytic premises are recorded in YM24_LOCAL_VACUUM.md, not formally proved here.
inline int gauge_local_vacuum_run(const std::string& raw,std::istream& in,int d,const std::filesystem::path& out,Clock::time_point stop){
    Q alpha=rational(in),k=rational(in),target=rational(in);int order;std::string extra;
    if(d<2||d>4||alpha<=0||target<=0||!(in>>order)||order<1||order>64||(in>>extra))
        throw std::runtime_error("local vacuum parameters");
    Q incidence=2*(d-1),lambda=k/alpha,u=lambda<0?-lambda:lambda;
    Q drive=48*incidence,b=Q(8)/3,R=Q(1)/8;
    Q threshold=(R-b*R*R)/drive;
    Q lip=2*b*R,rho=Q(1)/2-Q(4)/3*R,gap=alpha*rho;
    Q ratio=4*b*drive*u;
    bool ok=u<=threshold&&gap>=target;
    Q tail=0;
    try{
        if(ok){Q power=1;for(int i=0;i<order;++i){tick(stop);power*=ratio;}tail=drive*u*power/(1-ratio);}
        tick(stop);
    }catch(const Limit&){ok=false;}
    if(ok){
        std::ofstream o(out,std::ios::binary);
        o<<"drnas-op-v1\n"<<hash(raw)<<"\ngauge-local-vacuum "<<threshold<<" "<<R<<" "<<lip<<" "<<rho<<" "<<gap<<" "<<ratio<<" "<<tail<<"\n";
        o.close();if(!o)throw std::runtime_error("local vacuum evidence");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"local_fourier_vacuum_contraction\",\"certificate\":\""<<(ok?"ANALYTIC_BOUND":"none")<<"\"}\n";
    return ok?30:0;
}
