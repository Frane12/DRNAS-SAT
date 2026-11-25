// FUSION1: structural portfolio on a shared deadline. No external solver calls.
struct FusionOptions { bool components=true, repair=true, common=false; int max_core=512; };
struct FusionStats {
    long long split_nodes=0, common_units=0, proof_steps=0;
    int component_groups=0, components_solved=0, gates=0, probes=0, bdd_nodes=0;
};
static FusionOptions options;
static FusionStats stats;
struct Answer {
    int status=0; // 1 SAT, -1 UNSAT, 0 unresolved
    string method="limits";
    vector<int> model;
    F proof, capacity_source;
};
struct Part {Input input; C original;};

static vector<Part> components(const Input& d) {
    vector<int> parent(d.n+1); iota(parent.begin(),parent.end(),0);
    auto root=[&](int v){while(parent[v]!=v){parent[v]=parent[parent[v]];v=parent[v];}return v;};
    for(const C& c:d.c) if(!taut(c) && !c.empty())
        for(int l:c) parent[root(abs(l))]=root(abs(c[0]));
    map<int,int> ids;
    vector<Part> parts;
    for(const C& c:d.c) if(!taut(c)) {
        int r=c.empty()?0:root(abs(c[0]));
        if(!ids.count(r)){ids[r]=parts.size();parts.push_back({});}
        parts[ids[r]].input.c.push_back(c);
    }
    for(Part& p:parts) {
        C vars;
        for(const C& c:p.input.c) for(int l:c) vars.push_back(abs(l));
        vars=norm(move(vars)); p.original={0};
        p.original.insert(p.original.end(),vars.begin(),vars.end());
        map<int,int> remap;
        for(int i=1;i<int(p.original.size());++i) remap[p.original[i]]=i;
        for(C& c:p.input.c){for(int& l:c) l=sign(l)*remap[abs(l)];c=norm(move(c));}
        p.input.n=vars.size();p.input.m=p.input.c.size();
    }
    stable_sort(parts.begin(),parts.end(),[](const Part&a,const Part&b){
        return a.input.n<b.input.n;
    });
    return parts;
}
static F remap_clauses(F cs,const C& original) {
    for(C& c:cs){for(int& l:c)l=sign(l)*original[abs(l)];c=norm(move(c));}
    return cs;
}
static F prep_proof(const Prep& p) {
    F out;out.reserve(p.proof.size());
    for(const Step& s:p.proof){out.push_back(s.c);if(s.c.empty())break;}
    if(out.empty()&&p.empty())out.push_back({});
    return out;
}
static TP slice(TP end,double fraction,double maximum=1e30) {
    double left=chrono::duration<double>(end-Clock::now()).count();
    return min(end,Clock::now()+chrono::duration_cast<Clock::duration>(
        chrono::duration<double>(max(0.0,min(maximum,left*fraction)))));
}
static Answer fusion_solve(const Input&,TP,bool,int);
static Answer solve_parts(const Input& d,vector<Part>& parts,TP end,bool capacity_ok,int depth) {
    Answer result; result.status=1; result.model.assign(d.n+1,-1);
    result.method="components"; ++stats.component_groups;
    for(size_t i=0;i<parts.size();++i) {
        Part& part=parts[i];
        TP budget=slice(end,1.0/double(parts.size()-i));
        Answer a=fusion_solve(part.input,budget,capacity_ok,depth+1);
        if(a.status==-1){
            a.proof=remap_clauses(move(a.proof),part.original);
            a.capacity_source=remap_clauses(move(a.capacity_source),part.original);
            a.method="component_"+a.method;return a;
        }
        if(a.status==0){result.status=0;continue;}
        ++stats.components_solved;
        for(int j=1;j<=part.input.n;++j)result.model[part.original[j]]=a.model[j];
    }
    if(result.status==1&&!verify(d.c,result.model))throw runtime_error("component model");
    return result;
}
static Answer fusion_solve(const Input& d,TP end,bool capacity_ok,int depth) {
    Answer out;
    if(expired(end))return out;
    for(const C& c:d.c) if(c.empty()){out.status=-1;out.method="empty_clause";out.proof={{}};return out;}
    if(options.components&&depth<8){
        auto parts=components(d);
        if(parts.size()>1)return solve_parts(d,parts,end,capacity_ok,depth);
    }
    if(d.c.empty()){out.status=1;out.method="empty_formula";out.model.assign(d.n+1,-1);return out;}
    auto temporal=temporal_chain(d,slice(end,.12,.15));
    if(temporal.sat){out.status=1;out.method="temporal_chain";out.model=move(temporal.a);return out;}
    if(capacity_ok){
        auto cap=capacity(d.c);
        if(cap.first>cap.second&&cap.second>0){
            out.status=-1;out.method="capacity_certificate";out.capacity_source=d.c;return out;
        }
    }
    if(gf2(d.c,d.n,out.model,slice(end,.12,.15),&out.proof)){
        out.status=1;out.method="GF2";return out;
    }
    if(!out.proof.empty()){out.status=-1;out.method="GF2_RUP";return out;}
    Prep p(d,slice(end,.20,.6));p.run(true);
    stats.gates+=p.gates;stats.probes+=p.probes;
    F residual=p.residual();
    auto accept_sat=[&](const string& method)->bool {
        if(!p.lift(out.model))return false;
        out.status=1;out.method=method;return true;
    };
    auto accept_unsat=[&](const string& method) {
        out.status=-1;out.method=method;out.proof=prep_proof(p);
    };
    if(p.empty()){accept_unsat("resolution");return out;}
    if(residual.empty()){
        out.model.assign(d.n+1,-1);accept_sat("elimination");return out;
    }
    if(options.components&&depth<8){
        Input reduced{d.n,int(residual.size()),residual};auto parts=components(reduced);
        if(parts.size()>1){
            Answer a=solve_parts(reduced,parts,end,false,depth);
            if(a.status==1){out.model=move(a.model);accept_sat("residual_components");return out;}
            if(a.status==-1){
                out=a;F prefix=prep_proof(p);prefix.insert(prefix.end(),out.proof.begin(),out.proof.end());
                out.proof=move(prefix);out.method="residual_"+a.method;return out;
            }
            return a;
        }
    }
    // Preprocessing can expose parity patterns absent from the raw encoding.
    F parity;
    if(gf2(residual,d.n,out.model,slice(end,.08,.10),&parity)&&accept_sat("residual_GF2"))return out;
    if(!parity.empty()){
        for(C& c:parity)p.add(move(c),-1,-1,0);
        accept_unsat("residual_GF2_RUP");return out;
    }
    set<int> vars;for(const C& c:residual)for(int l:c)vars.insert(abs(l));
    // A short constructive attempt avoids spending the whole budget proving
    // complementary cases on an easy satisfiable large component.
    if(vars.size()>90&&!expired(end)){
        bool sat=construct(residual,d.n,out.model,slice(end,.06,.04));
        if(!sat&&options.repair)sat=repair_model(residual,d.n,out.model,slice(end,.08,.06));
        if(sat&&accept_sat("constructive_repair"))return out;
    }
    if(!expired(end)){
        auto split=split_core(p,slice(end,.55),120000,options.common,options.max_core);
        stats.split_nodes+=split.nodes;stats.common_units+=split.common_units;
        if(split.status==1){out.model=move(split.a);if(accept_sat("case_decomposition"))return out;}
        if(split.status==-1){accept_unsat("case_RUP");return out;}
    }
    if(!expired(end)){
        bool sat=construct(residual,d.n,out.model,slice(end,.35,.25));
        if(!sat&&options.repair)sat=repair_model(residual,d.n,out.model,slice(end,.35,.20));
        if(sat&&accept_sat("constructive_repair"))return out;
    }
    // Preserve the exact BDD SAT constructor. An internal-only UNSAT replay is
    // not promoted to a certified result in this release.
    for(int mode=0;mode<2&&!expired(end);++mode){
        auto b=bdd(residual,d.n,mode,mode?slice(end,1):slice(end,.5),500000);
        stats.bdd_nodes=max(stats.bdd_nodes,b.nodes);
        if(b.status==1){out.model=move(b.a);if(accept_sat("BDD_model"))return out;}
    }
    out.proof.clear();return out;
}
static bool audit_rup(const Input& d,const F& proof,TP end) {
    if(proof.empty()||!proof.back().empty())return false;
    F all=d.c;all.reserve(all.size()+proof.size());AssumptionPropagator rup(all,d.n);
    for(const C& c:proof){
        if(expired(end))return false;
        C neg;for(int l:c)neg.push_back(-l);
        if(rup.run(neg))return false;
        all.push_back(c);rup.index_next();
    }
    return true;
}
static void write_clauses(const string& path,const F& cs) {
    ofstream f(path);
    for(const C& c:cs){for(int l:c)f<<l<<' ';f<<"0\n";}
    f.close();if(!f)throw runtime_error("certificate write failed");
}
int main(int argc,char** argv) {
    try {
        if(argc<2)throw runtime_error("usage: fusion input.cnf [seconds] [fuse|common|no-common|no-components|no-repair|no-wide] [output-prefix]");
        auto start=Clock::now();double seconds=argc>2?stod(argv[2]):5;
        if(!isfinite(seconds)||seconds<=0)throw runtime_error("positive finite seconds required");
        string mode=argc>3?argv[3]:"fuse",prefix=argc>4?argv[4]:"";
        if(mode=="common")options.common=true;
        else if(mode=="no-common")options.common=false;
        else if(mode=="no-components")options.components=false;
        else if(mode=="no-repair")options.repair=false;
        else if(mode=="no-wide")options.max_core=200;
        else if(mode!="fuse")throw runtime_error("unknown mode");
        Input d=readcnf(argv[1]);
        TP end=start+chrono::duration_cast<Clock::duration>(chrono::duration<double>(seconds));
        Answer a=fusion_solve(d,slice(end,.85),true,0);
        string status="UNKNOWN",certificate="none";
        if(a.status==1){
            if(!verify(d.c,a.model))throw runtime_error("final model invalid");
            status="SAT_VERIFIED";certificate="model";
            if(!prefix.empty()){
                ofstream f(prefix+".model");f<<"v ";for(int v=1;v<=d.n;++v)f<<(a.model[v]>0?v:-v)<<' ';f<<"0\n";
                f.close();if(!f)throw runtime_error("model write failed");
            }
        } else if(a.status==-1&&!a.capacity_source.empty()) {
            set<C> original(d.c.begin(),d.c.end());
            for(const C& c:a.capacity_source)if(!original.count(c))throw runtime_error("capacity provenance");
            auto cap=capacity(a.capacity_source);
            if(!(cap.first>cap.second&&cap.second>0))throw runtime_error("capacity certificate");
            status="UNSAT_CHECKED";certificate="capacity";
            if(!prefix.empty())write_clauses(prefix+".capacity",a.capacity_source);
        } else if(a.status==-1&&audit_rup(d,a.proof,end)) {
            status="UNSAT_CHECKED";certificate="DRUP";
            if(!prefix.empty())write_clauses(prefix+".drat",a.proof);
        } else if(a.status==-1) a.method="proof_audit_budget_or_failure";
        cout<<"{\"status\":\""<<status<<"\",\"method\":\""<<a.method
            <<"\",\"certificate\":\""<<certificate<<"\",\"vars\":"<<d.n<<",\"clauses\":"<<d.m
            <<",\"proof\":"<<a.proof.size()<<",\"split_nodes\":"<<stats.split_nodes
            <<",\"common_units\":"<<stats.common_units<<",\"component_groups\":"<<stats.component_groups
            <<",\"components_solved\":"<<stats.components_solved<<",\"gates\":"<<stats.gates
            <<",\"probes\":"<<stats.probes<<",\"bdd_nodes\":"<<stats.bdd_nodes
            <<",\"repair_states\":"<<repair_stats.states<<",\"repair_accepted\":"<<repair_stats.accepted
            <<",\"repair_flips\":"<<repair_stats.flips<<",\"ms\":"<<ms(start)<<"}\n";
        return 0;
    } catch(const exception& e){cerr<<e.what()<<'\n';return 2;}
}
