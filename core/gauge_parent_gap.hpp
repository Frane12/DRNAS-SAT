// Exact coefficient certificate for an interacting SU(2) parent Hamiltonian.
// Analytic premise: ground-state transform and Bakry-Emery inequality.
inline int gauge_parent_run(const std::string& raw,std::istream& in,int d,const std::filesystem::path& out,Clock::time_point stop){
    Q alpha=rational(in),k=rational(in),target=rational(in);std::string extra;
    if(d<2||d>4||alpha<=0||target<=0||(in>>extra))throw std::runtime_error("parent parameters");
    Q t=k/(3*alpha),abs_t=t;if(abs_t<0)abs_t=-abs_t;
    Q incidence=2*(d-1),hess=2*incidence*abs_t;
    Q rho=Q(1)/2-2*hess,gap=alpha*rho;
    Q residual=alpha*incidence*incidence*t*t;
    bool ok=gap>=target;
    try{tick(stop);}catch(const Limit&){ok=false;}
    if(ok){
        std::ofstream o(out,std::ios::binary);
        o<<"drnas-op-v1\n"<<hash(raw)<<"\ngauge-parent-gap "<<t<<" "<<rho<<" "<<gap<<" "<<residual<<"\n";o.close();
        if(!o)throw std::runtime_error("parent evidence");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"su2_parent_bakry_emery\",\"certificate\":\""<<(ok?"OPERATOR_EXACT":"none")<<"\",\"candidate_bound\":\""<<gap<<"\"}\n";
    return ok?30:0;
}
