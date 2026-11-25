// Native, name-independent recognition of a finite-domain temporal chain.
// SAT only: partial transitions and resource limits never imply UNSAT.
struct TemporalResult { bool sat=false; int layers=0,states=0,edges=0; vector<int>a; };
static TemporalResult temporal_chain(const Input& d,TP until){
 TemporalResult r; const int n=d.n; set<C> clauses(d.c.begin(),d.c.end());
 vector<C> dom; vector<int> own(n+1,-1);
 for(auto &c:clauses) if(c.size()>=3&&c.size()<=16&&c.front()>0){
  bool ok=true; for(size_t i=0;i<c.size();i++)for(size_t j=i+1;j<c.size();j++)if(!clauses.count(norm({-c[i],-c[j]})))ok=false;
  if(!ok)continue;
  for(int v:c)if(own[v]>=0)return r;
  int z=dom.size();dom.push_back(c);for(int v:c)own[v]=z;
 }
 if(dom.size()<4)return r;
 vector<set<int>> graph(dom.size());
 for(auto &c:d.c){C g;for(int l:c)if(own[abs(l)]>=0)g.push_back(own[abs(l)]);g=norm(g);for(int a:g)for(int b:g)if(a!=b)graph[a].insert(b);}
 vector<C> components;vector<int> dc(dom.size(),-1),ac(n+1,-1);
 for(int i=0;i<(int)dom.size();i++)if(dc[i]<0){int k=components.size();C q{i};dc[i]=k;for(size_t j=0;j<q.size();j++)for(int v:graph[q[j]])if(dc[v]<0){dc[v]=k;q.push_back(v);}if(q.size()>4)return r;components.push_back(q);for(int z:q)for(int v:dom[z])ac[v]=k;}
 int T=components.size();if(T<2||T>128)return r;
 vector<set<int>> support(T);vector<F> local(T);F rest;
 for(auto &c:clauses){int k=-1;for(int l:c)if(ac[abs(l)]>=0){if(k>=0&&k!=ac[abs(l)])return r;k=ac[abs(l)];}if(k<0)rest.push_back(c);else{local[k].push_back(c);for(int l:c)if(ac[abs(l)]<0)support[k].insert(abs(l));}}
 vector<C> adj(T);vector<vector<int>> uses(n+1);for(int i=0;i<T;i++)for(int v:support[i])uses[v].push_back(i);
 for(auto &u:uses){if(u.size()>2)return r;if(u.size()==2){adj[u[0]].push_back(u[1]);adj[u[1]].push_back(u[0]);}}
 for(auto &q:adj)q=norm(q);
 C ends;for(int i=0;i<T;i++){if(adj[i].size()==1)ends.push_back(i);else if(adj[i].size()!=2)return r;}if(ends.size()!=2)return r;
 vector<int> fixed(n+1);for(auto &c:rest)if(c.size()==1){int v=abs(c[0]),s=sign(c[0]);if(fixed[v]&&fixed[v]!=s)return r;fixed[v]=s;}
 auto endvars=[&](int i){C q;for(int v:support[i])if(uses[v].size()==1)q.push_back(v);return q;};
 int start=-1;for(int i:ends){auto q=endvars(i);if(!q.empty()&&all_of(q.begin(),q.end(),[&](int v){return fixed[v]!=0;})){start=i;break;}}if(start<0)return r;
 C chain;int last=-1,cur=start;while(cur>=0){chain.push_back(cur);int z=-1;for(int j:adj[cur])if(j!=last)z=j;last=cur;cur=z;if((int)chain.size()>T)return r;}if((int)chain.size()!=T)return r;
 vector<C> state(T+1);state[0]=endvars(chain[0]);state[T]=endvars(chain.back());
 for(int i=1;i<T;i++)set_intersection(support[chain[i-1]].begin(),support[chain[i-1]].end(),support[chain[i]].begin(),support[chain[i]].end(),back_inserter(state[i]));
 vector<int> layer(n+1,-1),idx(n+1,-1);for(int i=0;i<=T;i++){if(state[i].empty()||state[i].size()>63)return r;for(int j=0;j<(int)state[i].size();j++){int v=state[i][j];if(layer[v]>=0)return r;layer[v]=i;idx[v]=j;}}
 for(int v=1;v<=n;v++)if(layer[v]<0&&ac[v]<0)return r;
 vector<F> invariants(T+1);for(auto&c:rest){if(c.empty())return r;int k=layer[abs(c[0])];if(k<0)return r;for(int l:c)if(layer[abs(l)]!=k)return r;invariants[k].push_back(c);}
 struct Mask{uint64_t pos=0,neg=0;};auto test=[](const Mask&m,uint64_t s){return (m.pos&s)||(m.neg&~s);};
 vector<vector<Mask>> inv(T+1);for(int i=0;i<=T;i++)for(auto&c:invariants[i]){Mask m;for(int l:c)(l>0?m.pos:m.neg)|=1ull<<idx[abs(l)];inv[i].push_back(m);}
 uint64_t initial=0;for(int v:state[0])if(fixed[v]>0)initial|=1ull<<idx[v];for(auto &m:inv[0])if(!test(m,initial))return r;
 struct Pred{uint64_t prev;C selected;};vector<map<uint64_t,Pred>> dp(T+1);dp[0][initial]={0,{}};r.layers=T;r.states=1;
 for(int t=0;t<T&&!expired(until);t++){
  int k=chain[t];C selected;vector<int> av(n+1);for(int g:components[k])for(int v:dom[g])av[v]=-1;
  struct PairMask{Mask p,q;};struct Action{C select;vector<PairMask> cond;};vector<Action> actions;
  auto enum_actions=[&](auto&& self,int j)->void{if(expired(until)||actions.size()>4096)return;if(j<(int)components[k].size()){int g=components[k][j];for(int v:dom[g]){av[v]=1;selected.push_back(v);self(self,j+1);selected.pop_back();av[v]=-1;}return;}
   Action a;a.select=selected;for(auto&c:local[k]){bool sat=false;PairMask m;for(int l:c){int v=abs(l);if(ac[v]>=0){if(av[v]==sign(l)){sat=true;break;}}else{int s=layer[v];if(s!=t&&s!=t+1)return;Mask& x=s==t?m.p:m.q;(l>0?x.pos:x.neg)|=1ull<<idx[v];}}if(sat)continue;if(!(m.p.pos|m.p.neg|m.q.pos|m.q.neg))return;a.cond.push_back(m);}actions.push_back(move(a));};
  enum_actions(enum_actions,0);if(expired(until)||actions.empty()||actions.size()>4096)return r;
  uint64_t full=(1ull<<state[t+1].size())-1;
  for(auto&[s,pred]:dp[t]){for(auto&a:actions){if(expired(until))return r;bool ok=true;vector<Mask> q;uint64_t yes=0,no=0;for(auto&m:a.cond){if(test(m.p,s))continue;if(!(m.q.pos|m.q.neg)){ok=false;break;}q.push_back(m.q);}if(!ok)continue;
   // Unit closure on the next state's bits, not global SAT search.
   for(auto&m:inv[t+1])q.push_back(m);
   bool changed=true;while(changed&&ok){changed=false;for(auto&m:q){if((m.pos&yes)||(m.neg&no))continue;uint64_t p=m.pos&~(yes|no),z=m.neg&~(yes|no),u=p|z;if(!u){ok=false;break;}if(!(u&(u-1))&&!(p&z)){if(p)yes|=p;else no|=z;changed=true;}}}
   if(!ok||(yes|no)!=full)continue;
   bool valid=true;for(auto&m:q)if(!test(m,yes)){valid=false;break;}if(!valid)continue;++r.edges;
   if(dp[t+1].emplace(yes,Pred{s,a.select}).second)++r.states;
   if(dp[t+1].size()>100000)return r;
  }}if(dp[t+1].empty())return r;
 }
 if(expired(until)||dp[T].empty())return r;
 r.a.assign(n+1,-1);uint64_t s=dp[T].begin()->first;
 for(int t=T;t>=0;t--){for(int v:state[t])if(s&(1ull<<idx[v]))r.a[v]=1;if(t){auto p=dp[t].at(s);for(int v:p.selected)r.a[v]=1;s=p.prev;}}
 r.sat=verify(d.c,r.a);return r;
}
// Exact bounded case decomposition for dense small cores. Leaf blockers are RUP;
// parents are the resolvents of the two complementary case blockers. No CDCL.
struct SplitResult{int status=0;long long nodes=0, common_units=0;vector<int>a;};
static SplitResult split_core(Prep& prep, TP deadline, long long node_limit, bool common = false, int max_variables = 200) {
    SplitResult result;
    F clauses = prep.residual();
    C variables;
    for (const C& clause : clauses)
        for (int literal : clause) variables.push_back(abs(literal));
    variables = norm(move(variables));
    if (variables.size() > size_t(max_variables)) return result;

    AssumptionPropagator closure(clauses, prep.in.n);
    C path;
    auto add_blocker = [&]() {
        C blocker;
        blocker.reserve(path.size());
        for (int lit : path) blocker.push_back(-lit);
        prep.add(norm(move(blocker)), -1, -1, 0);
        return -1;
    };

    auto walk = [&](auto&& self, bool consistent) -> int {
        if (expired(deadline) || ++result.nodes > node_limit) return 0;
        if (!consistent) return add_blocker();
        const vector<int>& assigned = closure.values();
        vector<double> weight(prep.in.n+1);
        bool solved = true;
        for (const C& clause : clauses) {
            bool satisfied = false;
            int free = 0;
            for (int literal : clause) {
                int val = assigned[abs(literal)];
                if (val == sign(literal)) { satisfied = true; break; }
                if (!val) ++free;
            }
            if (satisfied) continue;
            solved = false;
            const double increment = 1.0 / (double(free) * free);
            for (int literal : clause)
                if (!assigned[abs(literal)]) weight[abs(literal)] += increment;
        }
        if (solved) {
            result.a = assigned;
            for (int& value : result.a) if (!value) value = -1;
            return 1;
        }

        C candidates;
        for (int v : variables)
            if (!assigned[v] && weight[v]>0) candidates.push_back(v);
        if (candidates.empty()) return 0;
        sort(candidates.begin(), candidates.end(),
             [&](int a, int b) { return weight[a] > weight[b]; });
        const size_t checkpoint = closure.checkpoint();
        int first = candidates.front();
        double best = -1;
        const size_t limit = min(size_t(12), candidates.size());
        for (size_t i = 0; i < limit; ++i) {
            if (expired(deadline)) return 0;
            const int v = candidates[i];
            const bool left = closure.extend(v);
            const size_t gain_left = closure.checkpoint() - checkpoint;
            vector<int> left_values;
            if (common && left) left_values = closure.values();
            closure.rollback(checkpoint);
            const bool right = closure.extend(-v);
            const size_t gain_right = closure.checkpoint() - checkpoint;
            C shared;
            if (common && left && right) {
                // Parent assignments are identified after rollback below.
                for (int w : variables)
                    if (w != v && left_values[w] && left_values[w] == closure.values()[w])
                        shared.push_back(w * left_values[w]);
            }
            closure.rollback(checkpoint);
            if (!left || !right) {
                first = left ? -v : v;
                break;
            }
            if (common) {
                int installed = 0;
                for (int y : shared) {
                    if (closure.values()[abs(y)]) continue;
                    C guard;
                    for (int l : path) guard.push_back(-l);
                    C a = guard, b = guard, c = guard;
                    a.push_back(-v); a.push_back(y);
                    b.push_back(v); b.push_back(y);
                    c.push_back(y);
                    prep.add(norm(a), -1, -1, 0);
                    prep.add(norm(b), -1, -1, 0);
                    prep.add(norm(c), -1, -1, 0);
                    ++result.common_units;
                    if (!closure.extend(y)) return add_blocker();
                    if (++installed == 8) break;
                }
                if (installed) return self(self, true);
            }
            const double score = (1.0+gain_left)*(1.0+gain_right);
            if (score > best) {
                best = score;
                first = gain_left >= gain_right ? v : -v;
            }
        }

        for (int literal : {first, -first}) {
            path.push_back(literal);
            const bool ok = closure.extend(literal);
            const int status = self(self, ok);
            closure.rollback(checkpoint);
            path.pop_back();
            if (status >= 0) return status;
        }
        return add_blocker();
    };
    result.status = walk(walk, closure.run({}));
    return result;
}
