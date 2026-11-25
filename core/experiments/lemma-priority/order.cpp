// Test adapter for the production scheduling rule on frozen model-stage inputs.
#include <bits/stdc++.h>
#include "../../lemma_priority.hpp"
using namespace toolbox;
static std::string read(const char* path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("missing input");
    return {std::istreambuf_iterator<char>(in), {}};
}
static Clause read_clause(std::istringstream& in) {
    Clause clause; int lit;
    while (in >> lit && lit) clause.push_back(lit);
    if (!in || !normalize(clause)) throw std::runtime_error("invalid clause");
    return clause;
}
int main(int argc,char** argv) {
    if (argc != 6) return 2;
    Input source=parse(read(argv[1]));
    std::istringstream active(read(argv[2])), witness(read(argv[3]));
    Clauses work;
    std::string line;
    while (std::getline(active,line)) {std::istringstream row(line);work.push_back(read_clause(row));}
    TableMessages messages;
    messages.groups.emplace_back();
    while (std::getline(witness,line)) {
        if (line.rfind("t ",0)!=0) continue;
        std::istringstream row(line.substr(2));
        messages.groups.back().claims.push_back(read_clause(row));++messages.accepted;
    }
    if (work.size()<source.cs.size() || !std::equal(source.cs.begin(),source.cs.end(),work.begin()))
        throw std::runtime_error("source prefix mismatch");
    auto previous=work;
    std::string mode=argv[4];
    if (mode!="table-rank" && mode!="table-pick-first" && mode!="table-first") return 2;
    auto rule=mode=="table-rank" ? LemmaPriority::polarity :
              mode=="table-pick-first" ? LemmaPriority::first : LemmaPriority::unchanged;
    auto choice=prioritize_lemma(source,work,messages,rule);
    if (!std::equal(source.cs.begin(),source.cs.end(),work.begin())) return 3;
    auto sorted=work;
    std::sort(sorted.begin(),sorted.end());std::sort(previous.begin(),previous.end());
    if (sorted!=previous) return 3;
    std::ofstream out(argv[5]);
    for (const auto& c:work) {for(int l:c) out<<l<<' ';out<<"0\n";}
    out.close();
    std::cout<<choice.ordinal<<" "<<choice.candidates<<" "<<choice.score<<"\n";
    return out?0:2;
}
