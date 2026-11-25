#include "cases.hpp"
#include "projection.hpp"
#include "repair.hpp"
#include "affine_domains.hpp"
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
    AlgebraStats algebra;
    int eliminated=0, resolvents=0, residual=0;
    uint64_t flips=0;
    void print(const char* phase) const {
        std::cout<<"c phase "<<phase<<" single "<<cases.single<<" joint "<<cases.joint
                 <<" covers "<<cases.covers<<" facts "<<cases.facts<<" composed "<<cases.composed
                 <<" implications "<<cases.implications<<" eliminated "<<eliminated
                 <<" resolvents "<<resolvents<<" residual "<<residual<<" flips "<<flips
                 <<" gf3_domains "<<algebra.domains<<" gf3_relations "<<algebra.relations
                 <<" gf3_rank "<<algebra.rank3<<" circuit_gates "<<algebra.gates
                 <<" circuit_inputs "<<algebra.inputs<<" circuit_free "<<algebra.free
                 <<" affine_rounds "<<algebra.affine_rounds<<" circuit_blocks "<<algebra.blocks
                 <<" word_recovered "<<algebra.word.recovered<<" word_pool "<<algebra.word.pool
                 <<" word_nodes "<<algebra.word.nodes<<" word_shifts "<<algebra.word.shifts
                 <<" word_xors "<<algebra.word.xors<<" word_adds "<<algebra.word.adds
                 <<" word_bits "<<algebra.word.bits<<" word_candidates "<<algebra.word.candidates<<"\n";
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
    Model algebra_model;
    if (finite3_model(f,algebra_model,std::min(deadline,after(std::min(2.5,seconds*.20))),stats.algebra))
        return emit_sat(f,algebra_model,"finite3-model",stats);
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
    if (construct && circuit_affine_model(f,fixed,algebra_model,std::min(deadline,after(std::min(left(),seconds*.68))),stats.algebra))
        return emit_sat(f,algebra_model,stats.algebra.word.recovered&&stats.algebra.word.candidates?"word-lift-circuit-model":"affine-circuit-model",stats);
    const bool compact=f.n<=192 && cs.size()<=2200;
    auto case_end=std::min(deadline,after(std::min(.60,seconds*.30)));
    for (int round=0;round<(compact?10:2) && Clock::now()<case_end;++round) {
        int changes=compact?compose_round(f.n,cs,proof,case_end,stats.cases):0;
        if (changes && !reduce_root(f.n,cs,fixed,proof)) return emit_unsat(proof,"composition-rup",stats);
        changes+=guarded_round(f.n,cs,proof,case_end,stats.cases);
        if (!changes) break;
        if (!reduce_root(f.n,cs,fixed,proof)) return emit_unsat(proof,"cases-rup",stats);
        Model m=seed.empty()?Model(f.n+1,0):seed; patch_fixed(m);
        if (satisfied(cs,m)) return emit_sat(f,m,"cases-model",stats);
    }
    Projection p(f.n,cs);
    bool consistent=p.run(proof,std::min(deadline,after(std::min(.75,seconds*.28))));
    stats.eliminated=p.projected; stats.resolvents=p.generated;
    if (!consistent) return emit_unsat(proof,"projection-rup",stats);
    auto residual=p.residual(); stats.residual=int(residual.size());
    Model m=seed.empty()?Model(f.n+1,0):seed;
    if (seed.empty()) {
        std::vector<int> balance(f.n+1);
        for (const auto& c:residual) for (int l:c) balance[std::abs(l)]+=l>0?1:-1;
        for (int v=1;v<=f.n;++v) m[v]=balance[v]>0;
    }
    bool good=satisfied(residual,m);
    const char* phase="projection-model";
    if (!good && construct) { phase="residual-repair"; good=repair(f.n,residual,m,deadline,stats.flips); }
    if (good) {
        p.reconstruct(m); patch_fixed(m); return emit_sat(f,m,phase,stats);
    }
    stats.print("residual-open");
    std::cout<<"c elapsed "<<std::chrono::duration<double>(Clock::now()-start).count()<<"\ns UNKNOWN\n";
    return 0;
}
} // namespace
int main(int argc,char** argv) {
    try {
        if (argc<3 || argc>5 || (argc==5 && std::string(argv[4])!="--no-repair"))
            throw std::runtime_error("usage: drnas-toolbox20 input.cnf evidence [seconds [--no-repair]]");
        std::string limit=argc>=4?argv[3]:"5"; size_t used=0;
        double seconds=std::stod(limit,&used);
        if (used!=limit.size() || !std::isfinite(seconds) || seconds<=0 || seconds>86400)
            throw std::runtime_error("invalid time budget");
        return solve(argv[1],argv[2],seconds,argc!=5);
    } catch (const std::exception& e) { std::cerr<<"error: "<<e.what()<<"\n";return 2; }
}
