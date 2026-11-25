// TOOLBOX23's protected-obligation repair, transcribed to C++.
// A repair may make at most eight explicit positive flip choices; unit
// consequences may flip more variables. Every accepted repair is checked
// against the original residual clauses. Failure has no UNSAT meaning.
struct RepairStats { long long states=0, attempts=0, accepted=0, flips=0; };
static RepairStats repair_stats;

static bool repair_model(const F& formula, int n, vector<int>& model, TP until) {
    if (model.size()!=size_t(n+1)) return false;
    auto false_ids = [&](const vector<int>& a) {
        C bad;
        for (int i=0;i<int(formula.size());++i) {
            bool sat=false;
            for (int l:formula[i]) if (a[abs(l)]==sign(l)) {sat=true;break;}
            if (!sat) bad.push_back(i);
        }
        return bad;
    };
    C bad=false_ids(model);
    while (!bad.empty() && !expired(until)) {
        bool improved=false;
        for (int target:bad) {
            if (expired(until)) break;
            F protected_clauses;
            for (int i=0;i<int(formula.size());++i) {
                if (i!=target && binary_search(bad.begin(),bad.end(),i)) continue;
                C c;
                for (int l:formula[i]) {
                    int v=abs(l);
                    c.push_back(model[v]==sign(l) ? -v : v);
                }
                protected_clauses.push_back(norm(move(c)));
            }
            AssumptionPropagator closure(protected_clauses,n);
            int states=0;
            set<vector<int>> visited;
            vector<int> candidate;
            ++repair_stats.attempts;
            auto walk = [&](auto&& self, int choices, bool ok)->bool {
                if (!ok || expired(until) || ++states>1500) return false;
                ++repair_stats.states;
                const auto& values=closure.values();
                if (!visited.insert(values).second) return false;
                C options;
                bool pending=false;
                for (const C& c:protected_clauses) {
                    // Unspecified flips are completed with zero.
                    bool satisfied=false;
                    C available;
                    for (int l:c) {
                        if ((l>0 && values[l]==1) || (l<0 && values[-l]!=1))
                            satisfied=true;
                        if (l>0 && values[l]==0) available.push_back(l);
                    }
                    if (satisfied) continue;
                    if (available.empty()) return false;
                    if (!pending || available.size()<options.size()) options=move(available);
                    pending=true;
                }
                if (!pending) {
                    candidate=model;
                    for(int v=1;v<=n;++v) if(values[v]==1) candidate[v]*=-1;
                    return true;
                }
                if (choices>=8) return false;
                const size_t saved=closure.checkpoint();
                // Deterministic obligation ordering; no solver oracle.
                for (int v:options) {
                    bool next=closure.extend(v);
                    if (self(self,choices+1,next)) return true;
                    closure.rollback(saved);
                    if (expired(until)||states>=1500) break;
                }
                return false;
            };
            if (!walk(walk,0,closure.run({}))) continue;
            C after=false_ids(candidate);
            if (after.size()>=bad.size() || binary_search(after.begin(),after.end(),target) ||
                !includes(bad.begin(),bad.end(),after.begin(),after.end()))
                throw runtime_error("repair violated protected clauses");
            for(int v=1;v<=n;++v) repair_stats.flips+=(candidate[v]!=model[v]);
            ++repair_stats.accepted;
            model=move(candidate); bad=move(after); improved=true;
            break;
        }
        if (!improved) break;
    }
    return bad.empty() && verify(formula,model);
}
