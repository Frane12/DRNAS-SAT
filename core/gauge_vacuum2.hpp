// YM22: second-order local log-vacuum correction for open cubic SU(2).
// Only the corrected reference gap is certified; the original gap is not.
inline int gauge_vacuum2_run(const std::string& raw,std::istream& in,int d,const std::filesystem::path& out,Clock::time_point stop){
    Q alpha=rational(in),k=rational(in),target=rational(in);std::string extra;
    if(d<2||d>3||alpha<=0||target<=0||(in>>extra))throw std::runtime_error("vacuum2 parameters");
    Q t=k/(3*alpha),u=t<0?-t:t;
    Q q=2*(d-1),pairs=4*q*(q-1);
    Q gradient=q/2+Q(20)*pairs/39;
    Q hessian=2*q+Q(24)*pairs/13;
    Q gap=alpha*(Q(1)/2-4*q*u-2*hessian*u*u);
    Q remainder=alpha*(2*q*gradient*u*u*u+gradient*gradient*u*u*u*u);
    bool ok=gap>=target;
    try{tick(stop);}catch(const Limit&){ok=false;}
    if(ok){
        std::ofstream o(out,std::ios::binary);
        o<<"drnas-op-v1\n"<<hash(raw)<<"\ngauge-vacuum2 "<<t<<" "<<gradient<<" "<<hessian<<" "<<gap<<" "<<remainder<<"\n";
        o.close();if(!o)throw std::runtime_error("vacuum2 evidence");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"su2_second_order_log_vacuum\",\"certificate\":\""<<(ok?"OPERATOR_EXACT":"none")<<"\"}\n";
    return ok?30:0;
}
