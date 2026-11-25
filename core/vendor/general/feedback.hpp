// Bounded ROBDD projection -> short clauses with local, transactional RUP proof.
// Called on the current residual, not the initial input. No global branching.
struct Feedback {
 Clock::time_point end; int n; long long clusters=0, candidates=0, messages=0, proof_count=0, work=0, parity_pairs=0;
 bool exhausted=false, selective=false, parity_context=false, remember=false; F dormant; set<C> prior_dormant; long long dormant_attempts=0; set<C> known;
 // Policy state is advisory only. Actual clauses and RUP proof stay in the
 // inherited shared ledger. Credit a removed superset at most once per round.
 const F* input=nullptr; vector<vector<size_t>> litocc; vector<int> counts;
 vector<uint8_t> covered; long long screened=0, rejected=0, proof_rejected=0, credited=0, predicted_lits=0, pair_reduction=0;
 struct Value { vector<size_t> remove; long long lits=0,pairs=0; bool eligible=false; };
 size_t li(int l) const {return (size_t)(n+l);}
 Value assess(const C&c){
  Value v;if(c.size()<=1){v.eligible=true;return v;}
  if(!input)return v;
  int rare=*min_element(c.begin(),c.end(),[&](int a,int b){return litocc[li(a)].size()<litocc[li(b)].size();});
  map<int,int> delta;
  for(size_t i:litocc[li(rare)]){tick();if(covered[i])continue;const C&d=(*input)[i];
   if(d.size()>c.size()&&proj::rel::sub(c,d)){v.remove.push_back(i);v.lits+=d.size();for(int l:d)--delta[l];}}
  for(int l:c)++delta[l];
  set<int> vars;for(auto [l,k]:delta){(void)k;vars.insert(abs(l));}
  for(int x:vars){long long p=counts[li(x)],q=counts[li(-x)];long long dp=delta[x],dq=delta[-x];v.pairs+=p*q-max(0LL,p+dp)*max(0LL,q+dq);}
  // Immediate exact subsumption, or a complete affine binary projection
  // (the two forbidden patterns form a parity relation). The score is not a proof.
  v.eligible=!v.remove.empty()||(c.size()==2&&parity_context);return v;
 }
 void credit(const C&c,const Value&v){
  for(size_t i:v.remove){if(covered[i])continue;covered[i]=1;for(int l:(*input)[i])--counts[li(l)];}
  for(int l:c){++counts[li(l)];}credited+=v.remove.size();predicted_lits+=v.lits-(long long)c.size();pair_reduction+=v.pairs;
 }
 F additions, emitted; set<C> visited;
 Feedback(int n_, Clock::time_point e,bool select=false):end(e),n(n_),selective(select){}
 void guard(){if(Clock::now()>=end||work>8000000||emitted.size()>12000||additions.size()>=120){exhausted=true;throw Limit{};}}
 void tick(){if((++work&127)==0)guard();}
 C vars(const C&c){C v;for(int l:c)v.push_back(abs(l));sort(v.begin(),v.end());v.erase(unique(v.begin(),v.end()),v.end());return v;}
 bool subset(const C&a,const C&b){return includes(b.begin(),b.end(),a.begin(),a.end());}
 C merged(const C&a,const C&b){C s;set_union(a.begin(),a.end(),b.begin(),b.end(),back_inserter(s));return s;}
 // Separate native propagation implementation for the local certificate emitter.
 bool conflict(const F&local,const C&cl,const C&scope){
  vector<int8_t>a(scope.size(),0);auto ix=[&](int l){return lower_bound(scope.begin(),scope.end(),abs(l))-scope.begin();};
  for(int l:cl)a[ix(l)]=l>0?-1:1;
  bool change=true;while(change){change=false;for(const auto&c:local){tick();bool sat=false;int u=0,k=0;for(int l:c){int v=a[ix(l)];if(v==(l>0?1:-1)){sat=true;break;}if(!v){u=l;k++;}}if(sat)continue;if(!k)return true;if(k==1){a[ix(u)]=u>0?1:-1;change=true;}}}return false;
 }
 // Local Shannon certificate expansion only: when the candidate is not RUP,
 // derive both extensions and resolve. Every leaf is checked by UP. No guess
 // is committed; an interrupted proof never changes the shared state.
 bool prove(const F&local,C clause,const C&scope,F&log,int&budget){
  guard();if(--budget<0)return false;proj::rel::normalize(clause);
  if(known.count(clause))return true;
  if(conflict(local,clause,scope)){log.push_back(move(clause));return true;}
  auto used=vars(clause);int v=0;for(int w:scope)if(!binary_search(used.begin(),used.end(),w)){v=w;break;}if(!v)return false;
  C a=clause,b=clause;a.push_back(v);b.push_back(-v);
  if(!prove(local,move(a),scope,log,budget)||!prove(local,move(b),scope,log,budget))return false;
  log.push_back(move(clause));return true;
 }
 // Retain certified rejected clauses in the proof-only ledger, not active CNF.
 void defer(const F&local,const C&c,const C&scope,F* ready=nullptr){
  if(!remember||c.size()<2||c.size()>3||dormant.size()>=24||prior_dormant.size()+dormant.size()>=96||dormant_attempts>=36)return;
  if(prior_dormant.count(c)||known.count(c))return;
  ++dormant_attempts;F log;int budget=31;
  if(ready){if(ready->size()>31)return;log=move(*ready);}
  else if(!prove(local,c,scope,log,budget))return;
  guard();for(auto&d:log)if(known.insert(d).second)emitted.push_back(move(d));
  dormant.push_back(c);
 }
 bool publish(const F&local,C c,const C&scope){
  proj::rel::normalize(c);if(known.count(c))return false;
  // Exclude consequences dominated by existing shorter clauses.
  if(c.size()>1)for(int l:c)if(known.count({l}))return false;
  if(c.size()==3)for(int i=0;i<3;i++){C p=c;p.erase(p.begin()+i);if(known.count(p))return false;}
  candidates++;Value value;
  if(selective){screened++;value=assess(c);if(!value.eligible){rejected++;defer(local,c,scope);return false;}}
  F log;int budget=255;if(!prove(local,c,scope,log,budget))return false;
  guard();
  if(selective&&c.size()>1){
   // Pay for proof size only after a complete, still-unpublished derivation.
   // Short parity messages retain a small allowance for cross-kernel use.
   long long benefit=2*(long long)value.remove.size()+max(0LL,value.lits-(long long)c.size())+min(64LL,max(0LL,value.pairs))/4;
   if(parity_context&&c.size()==2)benefit+=12;
   if((long long)log.size()>max(4LL,2*benefit)){proof_rejected++;defer(local,c,scope,&log);return false;}
   credit(c,value);
  }
  for(auto& d:log){if(known.insert(d).second)emitted.push_back(move(d));}additions.push_back(c);messages++;return true;
 }
 void cluster(const F&local,const C&scope){
  guard();if(local.size()<2||scope.empty()||scope.size()>10)return;
  sym::Solver b;b.n=n;b.end=end;b.maxnodes=16000;b.order=scope;b.rank.assign(n+1,-1);
  for(size_t i=0;i<scope.size();i++)b.rank[scope[i]]=i;
  int root=1;try{for(auto&c:local){b.guard();root=b.apply(root,b.clause(c),false);if(!root)break;}}catch(sym::Stop&){return;}
  clusters++;if(!root){publish(local,{},scope);return;}
  // Enumerate bounded ROBDD support, not assignments of the whole CNF.
  // For each 1/2/3-variable boundary, mark projected satisfying patterns.
  vector<unsigned> masks;vector<int>a(n+1);unsigned lim=1u<<scope.size();
  try{for(unsigned m=0;m<lim;m++){tick();for(size_t j=0;j<scope.size();j++)a[scope[j]]=m>>j&1;if(b.eval(root,a))masks.push_back(m);}}catch(sym::Stop&){return;}
  const int k=scope.size();auto projection=[&](const C&ix){unsigned present=0,full=(1u<<(1u<<ix.size()))-1;for(unsigned m:masks){tick();unsigned p=0;for(size_t j=0;j<ix.size();j++)p|=((m>>ix[j])&1)<<j;present|=1u<<p;if(present==full)break;}parity_context=ix.size()==2&&(present==6||present==9);if(parity_context)parity_pairs++;for(unsigned p=0;p<(1u<<ix.size());p++)if(!(present>>p&1)){C c;for(size_t j=0;j<ix.size();j++)c.push_back(p>>j&1?-scope[ix[j]]:scope[ix[j]]);publish(local,move(c),scope);}};
  for(int i=0;i<k;i++)projection({i});
  for(int i=0;i<k;i++)for(int j=i+1;j<k;j++)projection({i,j});
  // Ternary relations only for compact, highly constrained clusters, to keep
  // dense random instances from spending all their budget on weak messages.
  if(masks.size()*4<lim&&k<=8)for(int i=0;i<k;i++)for(int j=i+1;j<k;j++)for(int h=j+1;h<k;h++)projection({i,j,h});
 }
 void run(const F&res){
  known.insert(res.begin(),res.end());known.insert(prior_dormant.begin(),prior_dormant.end());if(res.size()>10000||n>1500)return;
  if(selective){input=&res;litocc.resize(2*n+1);counts.assign(2*n+1,0);covered.assign(res.size(),0);for(size_t i=0;i<res.size();i++){tick();for(int l:res[i]){litocc[li(l)].push_back(i);++counts[li(l)];}}}vector<C> scopes;vector<vector<int>> occ(n+1);scopes.reserve(res.size());
  for(size_t i=0;i<res.size();i++){tick();scopes.push_back(vars(res[i]));for(int v:scopes.back())occ[v].push_back(i);}
  vector<int> anchors;for(int v=1;v<=n;v++)if(!occ[v].empty())anchors.push_back(v);
  // Choose anchored scopes with more overlapping clauses per introduced variable.
  sort(anchors.begin(),anchors.end(),[&](int a,int b){return occ[a].size()!=occ[b].size()?occ[a].size()>occ[b].size():a<b;});
  for(int anchor:anchors){guard();if(clusters>=32)return;C scope={anchor};set<int> frontier(occ[anchor].begin(),occ[anchor].end());
   for(int step=0;step<9;step++){int best=-1;C next;tuple<int,int,int> key{INT_MAX,INT_MAX,INT_MAX};
    for(int id:frontier){tick();C s=merged(scope,scopes[id]);int extra=s.size()-scope.size();if(!extra||s.size()>10)continue;auto k=make_tuple(extra,-(int)scopes[id].size(),id);if(k<key){key=k;best=id;next=move(s);}}
    if(best<0)break;
    for(int v:next){if(!binary_search(scope.begin(),scope.end(),v))frontier.insert(occ[v].begin(),occ[v].end());}scope=move(next);
   }
   if(!visited.insert(scope).second)continue;
   F local;for(int id:frontier){tick();if(subset(scopes[id],scope))local.push_back(res[id]);}
   cluster(local,scope);if(!additions.empty()&&additions.back().empty())return;
  }
 }
};
