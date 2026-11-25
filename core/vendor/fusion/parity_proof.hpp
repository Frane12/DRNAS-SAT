// Compile a contradiction between complete parity relations into plain DRUP.
// Each equation is XOR(scope) = rhs. No source label or encoding metadata is used.
struct ParityEquation { C scope; bool rhs; };

static C xor_scope(const C& a, const C& b) {
    C result;
    set_symmetric_difference(a.begin(), a.end(), b.begin(), b.end(), back_inserter(result));
    return result;
}

static bool parity_certificate(const map<C, set<unsigned>>& groups, int n, TP end,
                               vector<ParityEquation>& witness) {
    struct Row { ParityEquation eq; C origins; };
    vector<Row> basis(n + 1);
    vector<ParityEquation> source;
    for (const auto& [scope, patterns] : groups) {
        if (scope.size() > 5) continue;
        for (int rejected = 0; rejected <= 1; ++rejected) {
            if (expired(end) || source.size() >= 1024) return false;
            unsigned count = 0;
            for (unsigned mask : patterns)
                count += __builtin_parity(mask) == rejected;
            if (count != (1u << (scope.size() - 1))) continue;
            ParityEquation eq{scope, !rejected};
            C ids{static_cast<int>(source.size())};
            source.push_back(eq);
            while (!eq.scope.empty()) {
                Row& row = basis[eq.scope.front()];
                if (row.origins.empty()) {
                    row = {eq, ids};
                    break;
                }
                eq.scope = xor_scope(eq.scope, row.eq.scope);
                eq.rhs ^= row.eq.rhs;
                ids = xor_scope(ids, row.origins);
            }
            if (eq.scope.empty() && eq.rhs) {
                if (ids.size() > 192) return false;
                for (int id : ids) witness.push_back(source[id]);
                return true;
            }
        }
    }
    return false;
}

// Build shortest-union merges first. A merge that shares a variable can
// discharge that pivot by unit propagation after the other variables are fixed.
static bool compile_parity(const map<C,set<unsigned>>& groups, const F& original,
                           int n, TP end, F& result) {
    if (n > 1024) return false;
    vector<ParityEquation> rows;
    if (!parity_certificate(groups, n, end, rows)) return false;
    using Pair = tuple<size_t,size_t,int,int>;
    priority_queue<Pair,vector<Pair>,greater<Pair>> choices;
    vector<char> active(rows.size(), 1);
    auto offer = [&](int i, int j) {
        const C& a = rows[i].scope;
        const C& b = rows[j].scope;
        size_t common = 0;
        for (int v : a) common += binary_search(b.begin(), b.end(), v);
        const size_t total = a.size()+b.size()-common;
        if (common && total <= 12)
            choices.emplace(total,total-common,i,j);
    };
    for (int j=0; j<int(rows.size()); ++j)
        for (int i=0; i<j; ++i) offer(i,j);

    F db = original;
    AssumptionPropagator rup(db,n);
    constexpr size_t limit = 20000;
    while (!choices.empty() && !expired(end)) {
        auto [width, output_width, i, j] = choices.top();
        (void)width; (void)output_width;
        choices.pop();
        if (!active[i] || !active[j]) continue;
        active[i] = active[j] = false;
        const auto& a = rows[i]; const auto& b = rows[j];
        C shared;
        set_intersection(a.scope.begin(),a.scope.end(),b.scope.begin(),b.scope.end(),
                         back_inserter(shared));
        shared.pop_back(); // last common bit is the resolution pivot
        ParityEquation combined{xor_scope(a.scope,b.scope),a.rhs != b.rhs};
        for (unsigned mask=0; mask < (1u << combined.scope.size()); ++mask) {
            if (__builtin_parity(mask) == combined.rhs) continue;
            C base;
            for (size_t k=0; k<combined.scope.size(); ++k)
                base.push_back((mask&(1u<<k)) ? -combined.scope[k] : combined.scope[k]);
            // Full guards first. Opposite guards imply the next shorter clause.
            for (int len=int(shared.size()); len>=0; --len) {
                for (unsigned bits=0; bits<(1u<<len); ++bits) {
                    if (expired(end) || db.size()-original.size() >= limit) return false;
                    C clause=base;
                    for (int k=0; k<len; ++k)
                        clause.push_back((bits&(1u<<k)) ? -shared[k] : shared[k]);
                    C assumptions;
                    for (int lit : clause) assumptions.push_back(-lit);
                    if (rup.run(assumptions)) return false;
                    db.push_back(move(clause));
                    rup.index_next();
                }
            }
        }
        if (combined.scope.empty()) {
            if (combined.rhs && !db.back().size()) {
                result.assign(make_move_iterator(db.begin()+original.size()),
                              make_move_iterator(db.end()));
                return true;
            }
            continue;
        }
        int id=rows.size();
        rows.push_back(move(combined));
        active.push_back(true);
        for (int k=0; k<id; ++k) if (active[k]) offer(k,id);
    }
    return false;
}
