// YM21: explicit curvature gap of a gauge-invariant reference Hamiltonian.
// This task is NOT a uniform gap certificate for the original KS Hamiltonian.
inline int gauge_parent_volume_run(const std::string& raw,std::istream& in,int d,const std::filesystem::path& out,Clock::time_point stop){
    int L;if(d<2||d>3||!(in>>L)||L<2||L>64)throw std::runtime_error("parent grid");
    Q alpha=rational(in),k=rational(in),target=rational(in);std::string extra;
    if(alpha<=0||target<=0||(in>>extra))throw std::runtime_error("parent parameters");
    Q abs_k=k<0?-k:k,lambda=k/(3*alpha);
    int degree=2*(d-1);
    Q gap=alpha/2-Q(4)*degree*abs_k/3;
    Q incidence_square=0;
    // Count squared plaquette incidence over original links; for each
    // orientation the other d-1 coordinates determine incidence.
    for(int x=0;x<L;++x)for(int y=0;y<(d==3?L:1);++y){
        int m=(x>0)+(x<L-1);
        if(d==3)m+=(y>0)+(y<L-1);
        incidence_square+=m*m;
    }
    incidence_square*=d*(L-1);
    Q local=alpha*lambda*lambda*degree*degree;
    Q residual=alpha*lambda*lambda*incidence_square;
    bool ok=gap>=target;
    try{tick(stop);}catch(const Limit&){ok=false;}
    if(ok){
        std::ofstream o(out,std::ios::binary);
        o<<"drnas-op-v1\n"<<hash(raw)<<"\ngauge-parent-volume "<<lambda<<" "<<gap<<" "<<local<<" "<<residual<<" "<<gap-residual<<"\n";
        o.close();if(!o)throw std::runtime_error("parent certificate");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"su2_parent_bakry_emery\",\"certificate\":\""<<(ok?"OPERATOR_EXACT":"none")<<"\",\"reference_only_uniform\":true}\n";
    return ok?30:0;
}
