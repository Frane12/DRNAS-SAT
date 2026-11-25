// DRNAS CORE: one process, shared certified clauses, one monotonic solve budget.
#include <bits/stdc++.h>
#include <filesystem>
#include <unistd.h>
#include <openssl/evp.h>
#include "operator.hpp"
#include "symbolic_operator.hpp"
#include "vendor/unified/discovery_reason.hpp"
#include "vendor/unified/affine_domains.hpp"
#include "vendor/unified/factor_reason.hpp"
#include "vendor/unified/projection.hpp"
#include "vendor/structural/src/pcmax_capacity.hpp"
#include "vendor/structural/src/pcmax_clause_hall.hpp"
#include "vendor/structural/src/hall3_guard.hpp"
#include "vendor/structural/src/math4_xor_unit.hpp"
namespace fusion_kernel {
#include "vendor/fusion/native.cpp"
}
namespace general_kernel {
#include "vendor/general/general14.cpp"
}
using namespace std;
namespace fs = std::filesystem;
using C=vector<int>; using F=vector<C>; using Clock=chrono::steady_clock;
using Time=Clock::time_point;
static string read_file(const fs::path& p) {
    ifstream in(p,ios::binary); if(!in)throw runtime_error("cannot read "+p.string());
    string s((istreambuf_iterator<char>(in)),{});
    if(in.bad())throw runtime_error("read failed"); return s;
}
static void write_file(const fs::path& p,const string& s) {
    ofstream out(p,ios::binary);out<<s;out.close();
    if(!out)throw runtime_error("cannot write "+p.string());
}
static string clauses_text(const F& cs) {
    ostringstream o;for(const C& c:cs){for(int l:c)o<<l<<' ';o<<"0\n";}return o.str();
}
static F parse_proof(const string& text,int n) {
    F out;istringstream in(text);string line;
    while(getline(in,line)){
        istringstream s(line);long long l;C c;bool zero=false;
        while(s>>l){if(!l){zero=true;string extra;if(s>>extra)throw runtime_error("proof trailing data");break;}
            if(l>n||l< -n)throw runtime_error("proof literal");c.push_back(int(l));}
        if(!zero)throw runtime_error("incomplete proof");out.push_back(move(c));
    }return out;
}
struct Scratch {
    fs::path dir;
    Scratch(){string t=(fs::temp_directory_path()/"drnas-core-XXXXXX").string();vector<char>b(t.begin(),t.end());b.push_back(0);
        char* p=mkdtemp(b.data());if(!p)throw runtime_error("temporary directory");dir=p;}
    ~Scratch(){error_code ec;fs::remove_all(dir,ec);}
};
struct Core {
    toolbox::Input original;
    F all,ledger,proof_db; set<C> known,active_known;
    Time start=Clock::now(),deadline;
    double seconds;bool memory=false,no_share=false;
    Scratch tmp;
    string method="limits",format="none",artifact;
    long long shared=0,rejected_by_budget=0,fb_messages=0,mem_saved=0,mem_activated=0;
    int projected_variables=0;uint64_t repair_flips=0;
    toolbox::AlgebraStats algebra;
    toolbox::UnifiedStats unified;
    toolbox::CaseStats cases;
    toolbox::AdaptiveStats adaptive;
    toolbox::DiscoveryStats discovery;
    toolbox::FactorStats factors;
    explicit Core(double s):seconds(s){deadline=start+chrono::duration_cast<Clock::duration>(chrono::duration<double>(s));}
    double left()const{return max(0.0,chrono::duration<double>(deadline-Clock::now()).count());}
    Time budget(double fraction,double cap=1e30)const{return min(deadline,toolbox::after(min(cap,left()*fraction)));}
    bool model(toolbox::Model m,const string& name){
        if(m.size()!=size_t(original.n+1)||!toolbox::satisfied(original.cs,m))return false;
        ostringstream o;o<<"v ";for(int i=1;i<=original.n;++i)o<<(m[i]==1?i:-i)<<' ';o<<"0\n";
        artifact=o.str();format="MODEL";method=name;return true;
    }
    // The only cross-kernel messages are independently RUP-checked additions.
    // Keep source clauses: eliminated-variable state never crosses this boundary.
    bool absorb(const F& additions,const F& messages,Time until){
        fusion_kernel::AssumptionPropagator checker(proof_db,original.n);
        for(C c:additions){
            if(Clock::now()>=until||ledger.size()>=120000){++rejected_by_budget;break;}
            c=fusion_kernel::norm(move(c));
            if(!known.count(c)){
                C neg;for(int l:c)neg.push_back(-l);
                if(checker.run(neg))throw runtime_error("invalid inter-kernel RUP message");
                ledger.push_back(c);proof_db.push_back(c);known.insert(c);checker.index_next();
            }
            if(c.empty()){if(ledger.empty()||!ledger.back().empty())ledger.push_back({});
                artifact=clauses_text(ledger);format="DRUP";method="shared_closure";return true;}
        }
        // Proof helpers stay in the ledger. Only explicitly exported consequences
        // become active: injecting the whole proof trace swamps later kernels.
        for(C c:messages){
            if(all.size()>=160000||Clock::now()>=until)break;
            c=fusion_kernel::norm(move(c));
            if(known.count(c)&&active_known.insert(c).second){all.push_back(move(c));++shared;}
        }
        return false;
    }
    int relations(){
        if(no_share||original.n>50000||all.size()>160000||left()<.003)return 0;
        auto path=tmp.dir/"relations.rup";toolbox::Proof p(path.string());
        auto active=original.cs;toolbox::Model fixed(original.n+1,-1);
        bool consistent=toolbox::reduce_root(original.n,active,fixed,p);
        if(consistent)consistent=toolbox::cooperate(original.n,active,fixed,p,budget(.18,.7),cases,unified,4);
        if(consistent&&!active.empty()&&left()>.04){
            consistent=toolbox::factor_stage(original,active,fixed,p,budget(.12,.35),factors,2);
            if(consistent)consistent=toolbox::reduce_root(original.n,active,fixed,p);
        }
        p.out.flush();
        if(absorb(parse_proof(read_file(path),original.n),active,budget(.08,.2)))return 20;
        if(consistent)for(int bit:{0,1}){toolbox::Model m(original.n+1,int8_t(bit));
            for(int i=1;i<=original.n;++i)if(fixed[i]>=0)m[i]=fixed[i];
            if(model(m,"shared_closure_model"))return 10;}
        return 0;
    }
    int fusion(){
        fusion_kernel::Input f{original.n,int(all.size()),all};
        for(C& c:f.c)c=fusion_kernel::norm(move(c));
        auto a=fusion_kernel::fusion_solve(f,budget(.52),true,0);
        if(a.status==1){toolbox::Model m(original.n+1);for(int v=1;v<=original.n;++v)m[v]=a.model[v]>0;
            if(!model(m,"fusion_"+a.method))throw runtime_error("fusion model rejected");return 10;}
        if(a.status==-1){
            if(!a.capacity_source.empty()){
                // Capacity evidence is accepted only when it cites original clauses.
                set<C> source;for(C c:original.cs)source.insert(fusion_kernel::norm(move(c)));
                for(C c:a.capacity_source)if(!source.count(fusion_kernel::norm(move(c))))return 0;
                artifact="drnas-capacity-v1\n"+clauses_text(a.capacity_source);format="CAPACITY";method="fusion_capacity";return 20;
            }
            F proof=ledger;proof.insert(proof.end(),a.proof.begin(),a.proof.end());
            if(proof.empty()||!proof.back().empty())throw runtime_error("missing fusion terminal proof");
            artifact=clauses_text(proof);format="DRUP";method="fusion_"+a.method;return 20;
        }return 0;
    }
    int discover(){
        if(no_share||original.n>1500||all.size()>10000||left()<.06)return 0;
        auto path=tmp.dir/"discovery.rup";toolbox::Proof p(path.string());
        // The discovery loader sees the common ledger, not a new empty memory.
        for(const C& c:ledger)p.add(c);p.out.flush();
        toolbox::Input f{original.n,all};for(C& c:f.cs)toolbox::normalize(c);
        toolbox::Model answer;
        auto stop=budget(.50,.6);
        auto work=f.cs;toolbox::Model fixed(original.n+1,-1);
        bool consistent=toolbox::reduce_root(f.n,work,fixed,p);
        if(consistent){
            auto part=[&](double fraction){return min(stop,toolbox::after(max(0.0,chrono::duration<double>(stop-Clock::now()).count()*fraction)));};
            toolbox::Projection projection(f.n,work);
            consistent=projection.run(p,part(.25));projected_variables=projection.projected;
            work=projection.residual();
            if(consistent&&projection.projected>0&&!work.empty())
                consistent=toolbox::cooperate(f.n,work,fixed,p,part(.20),cases,unified,2);
            if(consistent){
                toolbox::Model m(f.n+1,0);vector<int> balance(f.n+1);
                for(const C& c:work)for(int l:c)balance[abs(l)]+=l>0?1:-1;
                for(int v=1;v<=f.n;++v)m[v]=fixed[v]>=0?fixed[v]:balance[v]>0;
                bool good=toolbox::satisfied(work,m)||toolbox::repair(f.n,work,m,part(.35),repair_flips);
                if(good){
                    for(int v=1;v<=f.n;++v)if(fixed[v]>=0)m[v]=fixed[v];
                    projection.reconstruct(m);
                    for(int v=1;v<=f.n;++v)if(fixed[v]>=0)m[v]=fixed[v];
                    if(model(m,"unified_projection_model"))return 10;
                }
            }
        }
        auto r=consistent?toolbox::adaptive_tail(f,work,p,stop,true,answer,adaptive):toolbox::TailResult::unsat;
        if(r==toolbox::TailResult::sat&&model(answer,"adaptive_model"))return 10;
        if(r!=toolbox::TailResult::unsat&&Clock::now()<stop)
            toolbox::discovery_tail(f,f.cs,p,stop,discovery);
        p.out.flush();
        F proof=parse_proof(read_file(path),original.n),messages;
        for(const C& c:proof)if(c.size()<=3&&messages.size()<1024)messages.push_back(c);
        if(absorb(proof,messages,budget(.1,.1)))return 20;
        return 0;
    }
    int general(){
        if(original.n>10000||all.size()>100000||left()<.003)return 0;
        auto source=tmp.dir/"shared.cnf",cert=tmp.dir/"general.cert";
        write_file(source,"p cnf "+to_string(original.n)+" "+to_string(all.size())+"\n"+clauses_text(all));
        general_kernel::Runner r;r.output=cert.string();r.mode=memory?"memory":"contract";
        int rc=0;
        try{rc=r.run(source.string(),max(1,int(left()*950)));}
        catch(general_kernel::Limit&){}
        catch(general_kernel::proj::rel::Stop&){}
        catch(general_kernel::table::Stop&){}
        fb_messages=r.fb_messages;mem_saved=r.memory_messages.size();mem_activated=r.memory_activated.size();
        if(rc==10){auto a=r.model_file(cert.string());toolbox::Model m(original.n+1);
            for(int v=1;v<=original.n;++v)m[v]=a[v];
            if(!model(m,"general_"+r.stage))throw runtime_error("general model rejected");return 10;}
        if(rc==20){
            auto suffix=read_file(cert);string header="g11-symbolic-v1\n";
            if(suffix.rfind(header,0)==0){artifact=header+clauses_text(ledger)+suffix.substr(header.size());format="RUP+SYMBOLIC";}
            else{artifact=clauses_text(ledger)+suffix;format="DRUP";}
            method="general_"+r.stage;return 20;
        }return 0;
    }
    int solve(const string& input){
        string raw=read_file(input);original=toolbox::parse(raw);
        if(original.n>2000000||original.cs.size()>10000000)throw runtime_error("input resource limit");
        all=original.cs;for(C& c:all)c=fusion_kernel::norm(move(c));known.insert(all.begin(),all.end());
        proof_db=all;active_known=known;
        for(int bit:{0,1})if(model(toolbox::Model(original.n+1,int8_t(bit)),"constant_model"))return 10;
        unsigned char bytes[EVP_MAX_MD_SIZE];unsigned count=0;
        if(!EVP_Digest(raw.data(),raw.size(),bytes,&count,EVP_sha256(),nullptr)||count!=32)throw runtime_error("SHA256");
        ostringstream hash;hash<<hex<<setfill('0');for(unsigned i=0;i<count;++i)hash<<setw(2)<<unsigned(bytes[i]);
        toolbox::Model seed;
        auto gf2=pcmax::math4::xor_unit(original.cs,original.n,hash.str(),min({left(),.25,seconds*.08}),&seed);
        if(gf2.verified){artifact=gf2.certificate_json+"\n";format="GF2";method="structural_GF2";return 20;}
        if(!seed.empty()&&model(seed,"structural_GF2_model"))return 10;
        if(count_if(original.cs.begin(),original.cs.end(),[](const C& c){return c.size()==2;})>=2){
            pcmax::Options opts;opts.seconds=min({left(),.1,seconds*.05});
            auto hall=pcmax::analyze_clause_hall(original.cs,original.n,hash.str(),opts);
            if(hall.verified){artifact=hall.certificate_json+"\n";format="HALL";method="structural_Hall";return 20;}
        }
        toolbox::Model m;
        if(toolbox::finite3_model(original,m,budget(.20,2.5),algebra)&&model(m,"GF3_domains"))return 10;
        toolbox::Propagator root_closure(original.n,original.cs);
        if(!root_closure.consistent()){artifact="0\n";format="DRUP";method="root_conflict";return 20;}
        toolbox::Model root=root_closure.state;
        if(toolbox::circuit_affine_model(original,root,m,budget(.68),algebra)&&
           model(m,algebra.word.recovered&&algebra.word.candidates?"word_lift_circuit":"affine_circuit"))return 10;
        int rc=relations();if(rc)return rc;
        rc=fusion();if(rc)return rc;
        rc=discover();if(rc)return rc;
        return general();
    }
    void report(int rc)const{
        cout<<"c {\"version\":\"0.1.2\",\"method\":\""<<method<<"\",\"certificate\":\""<<format
            <<"\",\"shared_clauses\":"<<shared<<",\"share_budget_stops\":"<<rejected_by_budget
            <<",\"relation_pairs\":"<<unified.pairs<<",\"feedback_messages\":"<<fb_messages
            <<",\"proof_helpers\":"<<ledger.size()<<",\"active_clauses\":"<<all.size()
            <<",\"unified_projected\":"<<projected_variables<<",\"unified_repair_flips\":"<<repair_flips
            <<",\"factor_messages\":"<<factors.novel<<",\"factor_projections\":"<<factors.projections
            <<",\"memory_saved\":"<<mem_saved<<",\"memory_activated\":"<<mem_activated
            <<",\"components\":"<<fusion_kernel::stats.component_groups<<",\"split_nodes\":"<<fusion_kernel::stats.split_nodes
            <<",\"gf3_domains\":"<<algebra.domains<<",\"affine_gates\":"<<algebra.gates
            <<",\"word_recovered\":"<<algebra.word.recovered<<",\"word_candidates\":"<<algebra.word.candidates
            <<",\"elapsed_s\":"<<chrono::duration<double>(Clock::now()-start).count()<<"}\n";
        cout<<"s "<<(rc==10?"SATISFIABLE":rc==20?"UNSATISFIABLE":"UNKNOWN")<<'\n';
    }
};
int main(int argc,char** argv){
    try{
        if(argc<3||argc>5)throw runtime_error("usage: drnas-core INPUT.cnf|INPUT.op|INPUT.sop EVIDENCE [seconds [default|memory|no-share]]");
        double seconds=5;if(argc>=4){size_t used;seconds=stod(argv[3],&used);if(used!=strlen(argv[3]))throw runtime_error("invalid budget");}
        if(!isfinite(seconds)||seconds<=0||seconds>86400)throw runtime_error("invalid budget");
        string mode=argc==5?argv[4]:"default";
        if(mode!="default"&&mode!="memory"&&mode!="no-share")throw runtime_error("invalid mode");
        fs::path out=argv[2];
        if(fs::exists(out)&&fs::equivalent(argv[1],out))throw runtime_error("evidence must differ from input");
        if(fs::exists(out))throw runtime_error("evidence already exists; choose a new path");
        { std::ifstream probe(argv[1],std::ios::binary);std::string p,kind; if(probe>>p>>kind && p=="p" && (kind=="op"||kind=="sop")){if(mode!="default")throw runtime_error("operator requires default mode");return kind=="op"?core_operator::run(read_file(argv[1]),out,seconds):core_symbolic::run(read_file(argv[1]),out,seconds);} }
        Core core(seconds);core.memory=mode=="memory";core.no_share=mode=="no-share";
        int rc=core.solve(argv[1]);
        if(core.left()==0){rc=0;core.artifact.clear();core.format="none";core.method="solve_budget";}
        if(rc)write_file(out,core.artifact);
        core.report(rc);return rc;
    }catch(const exception& e){cerr<<"error: "<<e.what()<<'\n';return 2;}
}
