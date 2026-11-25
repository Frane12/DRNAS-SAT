#include "unified_reason.hpp"
#include "adaptive_reason.hpp"
#include "discovery_reason.hpp"
#include "composition_reason.hpp"
#include "frontier_reason.hpp"
#include <memory>
#include "projection.hpp"
#include "repair.hpp"
#include "../../src/pcmax_capacity.hpp"
#include "../../src/pcmax_clause_hall.hpp"
#include "../../src/hall3_guard.hpp"
#include "../../src/math4_xor_unit.hpp"
#include <openssl/evp.h>
#include <filesystem>
#include <iomanip>
#include <iostream>

namespace {
using namespace toolbox;
std::string sha256(const std::string& raw) {
    unsigned char bytes[EVP_MAX_MD_SIZE]; unsigned size=0;
    if (!EVP_Digest(raw.data(),raw.size(),bytes,&size,EVP_sha256(),nullptr) || size!=32)
        throw std::runtime_error("SHA256 failed");
    std::ostringstream h; h<<std::hex<<std::setfill('0');
    for (unsigned i=0;i<size;++i) h<<std::setw(2)<<unsigned(bytes[i]);
    return h.str();
}
struct Stats {
    CaseStats cases;
    UnifiedStats unified;
    AdaptiveStats adaptive;
    DiscoveryStats discovery;
    CompositionStats composition;
    FrontierStats frontier;
    int eliminated=0, resolvents=0, residual=0;
    uint64_t flips=0;
    void print(const char* phase) const {
        std::cout<<"c phase "<<phase<<" single "<<cases.single<<" joint "<<cases.joint
                 <<" covers "<<cases.covers<<" facts "<<cases.facts<<" composed "<<cases.composed
                 <<" implications "<<cases.implications<<" epochs "<<unified.epochs
                 <<" joins "<<unified.pairs<<" affine "<<unified.affine<<" nonlinear "<<unified.nonlinear
                 <<" relation_facts "<<unified.relation_facts<<" probes "<<unified.probes
                 <<" probe_facts "<<unified.probe_facts<<" revisits "<<unified.revisits<<" eliminated "<<eliminated
                 <<" resolvents "<<resolvents<<" residual "<<residual<<" flips "<<flips
                 <<" adaptive_epochs "<<adaptive.epochs<<" gates "<<adaptive.gates<<" congruence "<<adaptive.congruence
                 <<" gate_proof "<<adaptive.gate_proof<<" pair_checks "<<adaptive.pair_checks<<" triple_checks "<<adaptive.triple_checks
                 <<" wide_facts "<<adaptive.wide_facts<<" resolution_facts "<<adaptive.resolution_facts
                 <<" resolution_pairs "<<adaptive.resolution_pairs<<" extra_pivots "<<adaptive.extra_pivots
                 <<" extra_resolvents "<<adaptive.extra_resolvents<<" feedback "<<adaptive.feedback<<" attempts "<<adaptive.attempts
                 <<" discovery_epochs "<<discovery.epochs<<" memory_loaded "<<discovery.loaded<<" compacted "<<discovery.compacted
                 <<" contexts "<<discovery.contexts<<" pair_contexts "<<discovery.pair_contexts<<" closed_contexts "<<discovery.closed
                 <<" conditional_facts "<<discovery.conditional_facts<<" regional_facts "<<discovery.regional_facts
                 <<" bags "<<discovery.bags<<" bag_max "<<discovery.bag_max<<" local_unsat "<<discovery.local_unsat
                 <<" local_trials "<<discovery.local_trials<<" discovery_proof "<<discovery.proof_lines<<" table_rows "<<discovery.table_rows
                 <<" composition_epochs "<<composition.epochs<<" outer_contexts "<<composition.outer_contexts
                 <<" child_contexts "<<composition.child_contexts<<" child_closed "<<composition.child_closed
                 <<" consensus "<<composition.consensus<<" parent_facts "<<composition.parent_facts
                 <<" global_facts "<<composition.global_facts<<" composition_loaded "<<composition.memory_loaded
                 <<" composition_compacted "<<composition.compacted<<" rankings "<<composition.rankings
                 <<" frontier_policy "<<frontier.policy<<" frontier_rounds "<<frontier.rounds
                 <<" frontier_contexts "<<frontier.contexts<<" frontier_probes "<<frontier.probes
                 <<" frontier_novel "<<frontier.novel<<" frontier_units "<<frontier.units
                 <<" frontier_binaries "<<frontier.binaries<<" frontier_root_before "<<frontier.root_before
                 <<" frontier_root_after "<<frontier.root_after<<" frontier_stalls "<<frontier.stalls
                 <<" frontier_proof "<<frontier.proof_lines
                 <<" composition_trials "<<composition.trials<<" composition_proof "<<composition.proof_lines<<"\n";
    }
};
int emit_sat(const Input& input,const Model& m,const char* phase,const Stats& stats) {
    if (!satisfied(input.cs,m)) throw std::logic_error("model fails original CNF");
    stats.print(phase); std::cout<<"s SATISFIABLE\n";
    for (int v=1;v<=input.n;++v) {
        if ((v-1)%20==0) std::cout<<"v ";
        std::cout<<(m[v]==1?v:-v)<<" ";
        if (v%20==0 && v!=input.n) std::cout<<"\n";
    }
    if (!input.n) std::cout<<"v ";
    std::cout<<"0\n"; return 10;
}
int emit_unsat(Proof& proof,const char* phase,const Stats& stats) {
    proof.out.flush(); stats.print(phase); std::cout<<"s UNSATISFIABLE\n"; return 20;
}
int solve(const std::string& path,const std::string& artifact,double seconds,bool construct) {
    const Time start=Clock::now(), deadline=after(seconds*.96);
    std::ifstream file(path,std::ios::binary);
    if (!file) throw std::runtime_error("cannot open input");
    std::string raw((std::istreambuf_iterator<char>(file)),{});
    if (file.bad()) throw std::runtime_error("input read failure");
    auto f=parse(raw);
    if (std::filesystem::exists(artifact) && std::filesystem::equivalent(path,artifact))
        throw std::runtime_error("input and proof must be different files");
    auto digest=sha256(raw); Proof proof(artifact); Stats stats;
    auto cs=f.cs; Model fixed(f.n+1,-1), seed;
    auto patch_fixed=[&](Model& m){ for (int v=1;v<=f.n;++v) if (fixed[v]>=0) m[v]=fixed[v]; };
    if (!reduce_root(f.n,cs,fixed,proof)) return emit_unsat(proof,"root-rup",stats);
    for (int bit:{0,1}) {
        Model m(f.n+1,int8_t(bit)); patch_fixed(m);
        if (satisfied(cs,m)) return emit_sat(f,m,"root-model",stats);
    }
    auto left=[&](){return std::max(0.0,std::chrono::duration<double>(deadline-Clock::now()).count());};
    auto affine=pcmax::math4::xor_unit(f.cs,f.n,digest,std::min({left(),.25,seconds*.10}),&seed);
    if (affine.verified) {
        proof.structural(affine.certificate_json); return emit_unsat(proof,"gf2-certificate",stats);
    }
    if (!seed.empty() && satisfied(f.cs,seed)) return emit_sat(f,seed,"gf2-model",stats);
    const auto binary=std::count_if(cs.begin(),cs.end(),[](const Clause& c){return c.size()==2;});
    if (binary>=2) {
        pcmax::Options options; options.seconds=std::min({left(),.10,seconds*.05});
        auto hall=pcmax::analyze_clause_hall(f.cs,f.n,digest,options);
        if (hall.verified) {
            proof.structural(hall.certificate_json); return emit_unsat(proof,"hall-certificate",stats);
        }
    }
    const bool compact=f.n<=192 && cs.size()<=2200;
    const bool cooperative=f.n<=50000 && cs.size()<=160000;
    if(cooperative){
        auto stage=std::min(deadline,after(std::min(3.0,seconds*.38)));
        if(!cooperate(f.n,cs,fixed,proof,stage,stats.cases,stats.unified,compact?8:4))
            return emit_unsat(proof,"unified-closure-rup",stats);
        Model m=seed.empty()?Model(f.n+1,0):seed;patch_fixed(m);
        if(satisfied(cs,m))return emit_sat(f,m,"unified-closure-model",stats);
    }else{
        // Preserve bounded baseline path when the shared-state memory policy
        // rules out relation tables. Hall and GF2 above remain unchanged.
        auto stage=std::min(deadline,after(std::min(.60,seconds*.30)));
        for(int round=0;round<2 && Clock::now()<stage;++round){
            int changes=guarded_round(f.n,cs,proof,stage,stats.cases);
            if(!changes)break;
            if(!reduce_root(f.n,cs,fixed,proof))return emit_unsat(proof,"cases-rup",stats);
        }
    }
    // An unresolved shared closure triggers a bounded native recovery phase.
    // Skip on tiny inputs or when the remaining budget is insufficient.
    if(left()>seconds*.35 && f.n>=32 && f.n<=512 && cs.size()>=size_t(f.n)){
        auto end=std::min(deadline,after(std::min(.85,seconds*.17)));
        if(!frontier_stage(f,cs,fixed,proof,end,stats.frontier))
            return emit_unsat(proof,"frontier-rup",stats);
        if(!reduce_root(f.n,cs,fixed,proof))return emit_unsat(proof,"frontier-root-rup",stats);
    }
    Projection p(f.n,cs);
    bool consistent=p.run(proof,std::min(deadline,after(std::min(1.5,seconds*.22))));
    stats.eliminated=p.projected;stats.resolvents=p.generated;
    if(!consistent)return emit_unsat(proof,"projection-rup",stats);
    auto residual=p.residual();
    // Projection exposes new relations. Feed them back into exactly the same
    // inference engine, then reconstruct both projection frames in reverse.
    std::unique_ptr<Projection> second;
    if(cooperative && p.projected>0 && !residual.empty() && left()>seconds*.27){
        ++stats.unified.revisits;
        auto stage=std::min(deadline,after(std::min(1.5,seconds*.15)));
        if(!cooperate(f.n,residual,fixed,proof,stage,stats.cases,stats.unified,3))
            return emit_unsat(proof,"projected-closure-rup",stats);
        if(!residual.empty() && left()>seconds*.25){
            second=std::make_unique<Projection>(f.n,residual);
            if(!second->run(proof,std::min(deadline,after(std::min(.75,seconds*.10)))))
                return emit_unsat(proof,"second-projection-rup",stats);
            stats.eliminated+=second->projected;stats.resolvents+=second->generated;
            residual=second->residual();
        }
    }
    stats.residual=int(residual.size());
    Model m=seed.empty()?Model(f.n+1,0):seed;
    if(seed.empty()){
        std::vector<int> balance(f.n+1);
        for(const auto& c:residual)for(int l:c)balance[std::abs(l)]+=l>0?1:-1;
        for(int v=1;v<=f.n;++v)m[v]=balance[v]>0;
    }
    patch_fixed(m);
    bool good=satisfied(residual,m);
    const char* phase="projection-model";
    if(!good && construct){phase="residual-repair";good=repair(f.n,residual,m,deadline,stats.flips);}
    if(good){
        patch_fixed(m);
        if(second)second->reconstruct(m);
        p.reconstruct(m);
        patch_fixed(m);
        return emit_sat(f,m,phase,stats);
    }
    if(left()>.05){
        Model answer;
        auto result=adaptive_tail(f,residual,proof,deadline,construct,answer,stats.adaptive);
        if(result==TailResult::unsat)return emit_unsat(proof,"adaptive-proof",stats);
        if(result==TailResult::sat)return emit_sat(f,answer,"adaptive-model",stats);
    }
    if(left()>.05&&discovery_tail(f,residual,proof,deadline,stats.discovery))
        return emit_unsat(proof,"discovered-contradiction",stats);
    if(left()>.05&&composition_tail(f,residual,proof,deadline,stats.composition))
        return emit_unsat(proof,"composed-contradiction",stats);
    stats.print("residual-open");
    std::cout<<"c elapsed "<<std::chrono::duration<double>(Clock::now()-start).count()<<"\ns UNKNOWN\n";
    return 0;
}
} // namespace
int main(int argc,char** argv) {
    try {
        if (argc<3 || argc>5 || (argc==5 && std::string(argv[4])!="--no-repair"))
            throw std::runtime_error("usage: drnas-unified7 input.cnf evidence [seconds [--no-repair]]");
        std::string limit=argc>=4?argv[3]:"5"; size_t used=0;
        double seconds=std::stod(limit,&used);
        if (used!=limit.size() || !std::isfinite(seconds) || seconds<=0 || seconds>86400)
            throw std::runtime_error("invalid time budget");
        return solve(argv[1],argv[2],seconds,argc!=5);
    } catch (const std::exception& e) { std::cerr<<"error: "<<e.what()<<"\n";return 2; }
}
