// Repeated unit closure under independent assumptions on a fixed clause set.
// Each query resets its assignment. Watch positions can safely survive a reset:
// an unassigned variable cannot falsify either of the two watched literals.
class AssumptionPropagator {
    struct Watches { size_t left, right; };
    const F& formula;
    vector<Watches> positions;
    vector<vector<size_t>> lists;
    vector<int> assignment, trail, units;
    bool original_conflict = false;

    static size_t index(int lit) {
        return 2 * size_t(abs(lit)) + (lit < 0);
    }

    int value(int lit) const {
        return assignment[abs(lit)] * sign(lit);
    }

    bool assign(int lit) {
        int& entry = assignment[abs(lit)];
        if (entry) return entry == sign(lit);
        entry = sign(lit);
        trail.push_back(lit);
        return true;
    }

    bool process_false_literal(int falsified) {
        auto& affected = lists[index(falsified)];
        size_t cursor = 0;
        while (cursor < affected.size()) {
            const size_t id = affected[cursor];
            const C& clause = formula[id];
            auto& watch = positions[id];
            size_t& here = clause[watch.left] == falsified ? watch.left : watch.right;
            const size_t other = here == watch.left ? watch.right : watch.left;
            if (value(clause[other]) > 0) {
                ++cursor;
                continue;
            }

            size_t replacement = 0;
            while (replacement < clause.size() &&
                   (replacement == other || replacement == here ||
                    value(clause[replacement]) < 0)) {
                ++replacement;
            }
            if (replacement < clause.size()) {
                here = replacement;
                lists[index(clause[here])].push_back(id);
                affected[cursor] = affected.back();
                affected.pop_back();
            } else {
                if (!assign(clause[other])) return false;
                ++cursor;
            }
        }
        return true;
    }

public:
    AssumptionPropagator(const F& clauses, int variables)
        : formula(clauses), lists(2 * size_t(variables) + 2),
          assignment(size_t(variables) + 1) {
        positions.reserve(clauses.size());
        while (positions.size() < clauses.size()) index_next();
    }

    // The replay database only appends clauses. All watch references are IDs.
    // Each subsequent run resets every previous assignment before propagation.
    void index_next() {
        const size_t id = positions.size();
        const C& clause = formula.at(id);
        positions.push_back({0, 0});
        if (clause.empty()) original_conflict = true;
        else if (clause.size() == 1) units.push_back(clause[0]);
        else {
            positions[id] = {0, 1};
            lists[index(clause[0])].push_back(id);
            lists[index(clause[1])].push_back(id);
        }
    }

    // A checkpoint used by a branch is always at a propagation fixed point.
    // Watch positions may survive a rollback. The assignment trail may not.
    size_t checkpoint() const { return trail.size(); }
    const vector<int>& values() const { return assignment; }

    void rollback(size_t checkpoint) {
        while (trail.size() > checkpoint) {
            assignment[abs(trail.back())] = 0;
            trail.pop_back();
        }
    }

    bool extend(int literal) {
        size_t head = trail.size();
        if (!assign(literal)) return false;
        while (head < trail.size()) {
            if (!process_false_literal(-trail[head++])) return false;
        }
        return true;
    }

    bool run(const C& assumptions, vector<int>* propagated = nullptr) {
        for (int lit : trail) assignment[abs(lit)] = 0;
        trail.clear();
        if (original_conflict) return false;
        for (int lit : units) if (!assign(lit)) return false;
        for (int lit : assumptions) if (!assign(lit)) return false;
        for (size_t head = 0; head < trail.size(); ++head) {
            if (!process_false_literal(-trail[head])) return false;
        }
        if (propagated) *propagated = assignment;
        return true;
    }
};
