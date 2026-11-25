#pragma once
// Optional source-only certificates for the existing factor stage.
struct TableGroup {
    std::vector<int> premises; // 1-based index after removing tautological input clauses
    Clauses claims;
};
struct TableMessages {
    bool first = false;
    int accepted = 0;
    std::map<Clause,int> source_ids;
    std::vector<TableGroup> groups;

    void index(const Clauses& source) {
        for (size_t i = 0; i < source.size(); ++i)
            source_ids.emplace(source[i], int(i + 1));
    }
    bool record(const Clause& claim, const FactorTable& table,
                const std::vector<int>& ids, Time deadline) {
        if (!table.complete || ids.empty() || accepted >= 24) return false;
        unsigned pos = 0, neg = 0;
        for (int lit : claim) {
            auto it = std::find(table.scope.begin(), table.scope.end(), std::abs(lit));
            if (it == table.scope.end()) return false;
            unsigned bit = 1u << (it - table.scope.begin());
            (lit > 0 ? pos : neg) |= bit;
        }
        for (unsigned row : table.allowed)
            if (!(row & pos) && !((~row) & neg)) return false;
        if (Clock::now() >= deadline) return false;
        if (groups.empty() || groups.back().premises != ids)
            groups.push_back({ids, {}});
        groups.back().claims.push_back(claim);
        ++accepted;
        return true;
    }
};
