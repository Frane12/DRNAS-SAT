#pragma once
#include "vendor/unified/factor_reason.hpp"

namespace toolbox {
enum class LemmaPriority { unchanged, first, polarity };

struct PriorityResult {
    int candidates = 0;
    int ordinal = 0; // 1-based among eligible active table claims
    Clause chosen;
    double score = 0;
};

// The first source.cs.size() entries are the retained original clauses.
// Only change the order of the derived suffix presented to model discovery.
inline PriorityResult prioritize_lemma(const Input& source, Clauses& work,
                                       const TableMessages& messages, LemmaPriority policy) {
    PriorityResult result;
    if (policy == LemmaPriority::unchanged || !messages.accepted) return result;
    const auto begin = work.begin() + source.cs.size();
    std::set<Clause> candidates;
    for (const auto& group : messages.groups)
        candidates.insert(group.claims.begin(), group.claims.end());
    std::vector<size_t> slots;
    for (auto it = begin; it != work.end(); ++it)
        if (candidates.count(*it)) slots.push_back(size_t(it - work.begin()));
    result.candidates = int(slots.size());
    if (slots.empty()) return result;

    size_t best = 0;
    if (policy == LemmaPriority::polarity) {
        std::vector<unsigned> count(2 * source.n, 0);
        for (const auto& clause : source.cs)
            for (int lit : clause) ++count[index_of(lit)];
        for (size_t j = 0; j < slots.size(); ++j) {
            // Independence approximation under smoothed source-polarity frequencies.
            // This score schedules a proven clause; it is never evidence.
            double score = 1;
            for (int lit : work[slots[j]]) {
                double opposite = count[index_of(-lit)] + 1.0;
                score *= opposite / (opposite + count[index_of(lit)] + 1.0);
            }
            if (j == 0 || score > result.score) { best = j; result.score = score; }
        }
    }
    result.ordinal = int(best + 1);
    result.chosen = work[slots[best]];
    Clauses ordered;
    ordered.reserve(work.size());
    ordered.insert(ordered.end(),work.begin(),begin);
    ordered.push_back(result.chosen);
    for (auto it = begin; it != work.end(); ++it)
        if (!candidates.count(*it)) ordered.push_back(std::move(*it));
    for (size_t j = 0; j < slots.size(); ++j)
        if (j != best) ordered.push_back(std::move(work[slots[j]]));
    work.swap(ordered);
    return result;
}
}
