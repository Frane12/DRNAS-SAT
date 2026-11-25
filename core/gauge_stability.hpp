// Qualitative application of Yarotsky's product-vacuum stability theorem.
// No numerical coupling threshold or gap is claimed by this certificate.
inline int gauge_stability_run(const std::string& raw,std::istream& in,int d,const std::filesystem::path& out,Clock::time_point stop){
    Q alpha=rational(in);std::string extra;
    if(d<2||d>4||alpha<=0||(in>>extra))throw std::runtime_error("gauge-stability parameters");
    Q scale=3*alpha/(4*(d+1));
    Q beta_factor=Q(d*(d-1))/scale;
    try{tick(stop);}catch(const Limit&){return 0;}
    std::ofstream f(out,std::ios::binary);
    f<<"drnas-op-v1\n"<<hash(raw)<<"\ngauge-stability "<<d+1<<" "<<scale<<" "<<beta_factor<<"\n";
    f.close();if(!f)throw std::runtime_error("stability evidence write");
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"yarotsky_su2_periodic_stability\",\"certificate\":\"THEOREM_APPLICATION\"}\n";
    return 30;
}
