#include <bits/stdc++.h>
namespace proj {
#include "base/g11_projection.hpp"
}
namespace table {
#include "g11_table.hpp"
}
namespace sym {
#include "base/symbolic_local.hpp"
}
using namespace std; using C=vector<int>; using F=vector<C>; using Clock=chrono::steady_clock;
using Factor=table::Factor;
struct Limit{};
struct Bridge: sym::Solver {
 int encode(const Factor& f,const vector<pair<int,int>>& p,int i,int mask){
  tick();if(i==(int)p.size())return f.t[mask];auto [r,k]=p[i];
  int lo=encode(f,p,i+1,mask),hi=encode(f,p,i+1,mask|(1<<k));return mk(r,lo,hi);
 }
 int run(const vector<Factor>* factors,const F& clauses){
  cs=clauses;if(factors){cs.clear();for(const auto& f:*factors)cs.push_back(f.v);}ordering(true);
  vector<vector<int>> buckets(n);joined.assign(n,1);
  auto add=[&](int f){if(f>1)buckets[nodes[f].v].push_back(f);return f!=0;};
  if(factors){for(auto& f:*factors){guard();vector<pair<int,int>> p;for(int j=0;j<(int)f.v.size();j++)p.emplace_back(rank[f.v[j]],j);sort(p.begin(),p.end());if(!add(encode(f,p,0,0)))return 20;}}
  else for(auto& c:clauses)if(!add(clause(c)))return 20;
  for(int v=0;v<n;v++){guard();memo.clear();auto& b=buckets[v];if(b.empty())continue;sort(b.begin(),b.end());b.erase(unique_(b.begin(),b.end()),b.end());
   while(b.size()>1){vector<int> next;for(size_t i=0;i<b.size();i+=2){int f=i+1<b.size()?apply(b[i],b[i+1],false):b[i];joins++;if(f==0)return 20;if(f!=1)next.push_back(f);}if(next.empty())next.push_back(1);b=move(next);}
   int f=b[0];joined[v]=f;int q=f;if(f>1&&nodes[f].v==v){auto p=nodes[f];q=apply(p.l,p.h,true);}if(q==0)return 20;if(q>1){if(nodes[q].v<=v)throw runtime_error("order invariant");buckets[nodes[q].v].push_back(q);}
  }
  vector<int>a(n+1);for(int v=n-1;v>=0;v--){a[order[v]]=0;if(!eval(joined[v],a)){a[order[v]]=1;if(!eval(joined[v],a))throw runtime_error("symbolic lift");}}solution=move(a);return 10;
 }
 template<class It> It unique_(It a,It b){return std::unique(a,b);}
};
#include "feedback.hpp"
struct Runner {
 Clock::time_point start=Clock::now(),end; int n=0;F source;bool share=true;string mode="on";F feedback_messages,memory_messages,memory_activated;map<C,int> pending; long long memory_expired=0,memory_reassess=0,memory_activated_value=0,memory_activated_stall=0,memory_attempts=0;long long fb_rounds=0,fb_clusters=0,fb_candidates=0,fb_messages=0,fb_proof=0,fb_pairs=0,fb_affine_rows=0,fb_affine_clauses=0,fb_projection_steps=0,fb_subsumed=0,fb_units=0;
 long long fb_screened=0,fb_rejected=0,fb_proof_rejected=0,fb_credited=0,fb_predicted_lits=0,fb_pair_reduction=0;
 long long g7steps=0,g7clauses=0,tableSteps=0,factors=0,factorEntries=0,fromG7=0,fromTable=0,proofLines=0,nodes=0;string stage="none",g7reason="none",tablereason="none",bddreason="none";
 // Never reintroduce an eliminated variable. The original proof ledger
 // retains dormant clauses, while the active CNF does not.
 F reactivate(const F&res,int round,bool stalled,Clock::time_point until){
  F out;if(pending.empty()||Clock::now()>=until)return out;
  vector<bool> eliminated(n+1,false);for(const auto&b:proj::rel::stack)eliminated[b.v]=true;
  Feedback assess(n,until,true);assess.input=&res;assess.litocc.resize(2*n+1);assess.counts.assign(2*n+1,0);assess.covered.assign(res.size(),0);
  for(size_t i=0;i<res.size();i++)for(int l:res[i]){assess.litocc[assess.li(l)].push_back(i);assess.counts[assess.li(l)]++;}
  vector<pair<long long,C>> useful,bridge;vector<C> expire;
  try{for(const auto&[c,born]:pending){assess.guard();if(round<=born)continue;
   bool dead=false;for(int l:c)if(eliminated[abs(l)]||(!assess.counts[assess.li(l)]&&!assess.counts[assess.li(-l)])){dead=true;break;}
   if(dead||proj::rel::active.count(c)){expire.push_back(c);continue;}
   for(int l:c)if(proj::rel::active.count({l})){dead=true;break;}
   if(dead){expire.push_back(c);continue;}memory_reassess++;
   auto v=assess.assess(c);if(v.eligible){useful.push_back({2*(long long)v.remove.size()+v.lits+max(0LL,v.pairs)/4,c});}
   else if(stalled){long long opposite=0;for(int l:c)opposite+=assess.counts[assess.li(-l)];bridge.push_back({opposite,c});}
  }}catch(Limit&){}
  for(auto&c:expire){pending.erase(c);memory_expired++;}
  auto take=[&](auto&list,int cap,bool immediate){sort(list.begin(),list.end(),[](const auto&a,const auto&b){return a.first!=b.first?a.first>b.first:a.second<b.second;});for(auto&[score,c]:list){(void)score;if(cap--<=0||Clock::now()>=until)break;out.push_back(c);if(immediate)memory_activated_value++;else memory_activated_stall++;}};
  take(useful,12,true);if(stalled)take(bridge,8,false);return out;
 }
 string output; void guard(){if(Clock::now()>=end)throw Limit{};}
 bool good(const vector<int>&a,const F& cs){for(auto&c:cs){bool sat=false;for(int l:c)if(a[abs(l)]==(l>0)){sat=true;break;}if(!sat)return false;}return true;}
 vector<int> model_file(const string&p){ifstream in(p);string v;in>>v;if(v!="v")throw runtime_error("model header");vector<int>a(n+1);int l;while(in>>l&&l){if(abs(l)>n)throw runtime_error("model var");a[abs(l)]=l>0;}return a;}
 void emit_model(vector<int>a,bool carryG7,table::Engine* t){
  if(t){for(auto it=t->trail.rbegin();it!=t->trail.rend();++it){guard();a[it->pivot]=0;if(!it->joined.t[t->index(it->joined.v,a)]){a[it->pivot]=1;if(!it->joined.t[t->index(it->joined.v,a)])throw runtime_error("table lift invariant");}}}
  if(carryG7){for(auto it=proj::rel::stack.rbegin();it!=proj::rel::stack.rend();++it){guard();int needed=-1;for(auto&c:it->clauses){bool sat=false;int sign=-1;for(int l:c){if(abs(l)==it->v)sign=l>0;else if(a[abs(l)]==(l>0)){sat=true;break;}}if(!sat){if(sign<0||(needed>=0&&needed!=sign))throw runtime_error("projection lift invariant");needed=sign;}}a[it->v]=max(0,needed);}}
  if(!good(a,source)){throw runtime_error("original model invariant");}guard();ofstream o(output);o<<"v ";for(int v=1;v<=n;v++)o<<(a[v]?v:-v)<<' ';o<<"0\n";if(!o)throw runtime_error("model write");}
 void append_file(ofstream& o,const string&p){ifstream in(p);if(!in)throw runtime_error("prefix read");string line;while(getline(in,line)){if((++proofLines&255)==0)guard();if(proofLines>250000)throw Limit{};o<<line<<'\n';}}
 void emit_clause(ofstream&o,const C&c){if((++proofLines&255)==0)guard();if(proofLines>250000)throw Limit{};for(int l:c)o<<l<<' ';o<<"0\n";}
 void emit_prefix(ofstream&o,bool carryG7,const string&tp){if(carryG7)for(auto&c:proj::rel::proof)emit_clause(o,c);if(!tp.empty())append_file(o,tp);}
 void terminal_rup(bool carryG7,const string&tp){ofstream o(output);emit_prefix(o,carryG7,tp);if(!o)throw runtime_error("proof write");guard();}
 F encode_residual(const vector<Factor>&fs){F r;size_t lits=0;for(auto&f:fs){guard();for(size_t i=0;i<f.t.size();i++)if(!f.t[i]){C c;for(size_t j=0;j<f.v.size();j++)c.push_back((i>>j&1)?-f.v[j]:f.v[j]);lits+=c.size();if(r.size()>=100000||lits>1000000)throw Limit{};r.push_back(move(c));}}return r;}
 void symbolic_proof(bool carryG7,table::Engine* t,const F&res,const vector<int>&order,const string&tmp){
  // The residual is a conjunction of source-implied clauses; a separate
  // auditor validates every RUP step and checks UNSAT by exact BDD replay.
  string tp;if(t){t->end=end;t->proof(tmp);tp=tmp;}
  ofstream o(output);o<<"g11-symbolic-v1\n";emit_prefix(o,carryG7,tp);o<<"r\n";for(auto&c:res)emit_clause(o,c);o<<"o ";for(int v:order)o<<v<<' ';o<<"0\n";if(!o)throw runtime_error("cert write");guard();}
 int run(const string&input,int ms){end=start+chrono::milliseconds(ms);string tmp=output+".tmp";struct Cleanup{string p;~Cleanup(){std::remove(p.c_str());}} cleanup{tmp};
  // Parse source once. The projection kernel consumes the same in-memory clauses.
  proj::rel::end=start+chrono::milliseconds(max(1,ms*30/100));
  if(!proj::rel::read(input)){throw runtime_error("DIMACS");}n=proj::rel::n;source=proj::rel::source;
  int rc=0;stage="projection";try{
   proj::g6::n=n;proj::g6::src=source;proj::g6::deadline=min(proj::rel::end,Clock::now()+chrono::milliseconds(max(1,ms*10/100)));try{rc=proj::g6::solve(tmp);}catch(proj::g6::Limit&){}
   if(rc){guard();if(rc==10)emit_model(model_file(tmp),false,nullptr);else terminal_rup(false,tmp);stage="affine";return rc;}
   if(proj::g6::proof.size()<=20000)for(auto c:proj::g6::proof){proj::rel::guard();if(!proj::rel::normalize(c))continue;if(proj::rel::known.insert(c).second){proj::rel::proof.push_back(c);proj::rel::active.insert(c);}}
   rc=proj::rel::project(tmp,true);
  }catch(proj::rel::Stop&){}
  g7steps=proj::rel::steps;g7clauses=proj::rel::proof.size();g7reason=proj::rel::reason;
  if(rc){guard();if(rc==10)emit_model(model_file(tmp),false,nullptr);else terminal_rup(false,tmp);return rc;}
  // Transactional handoff: only use active formula after complete source load.
  bool carryG7=share&&proj::rel::initialized;
  F residual=source;if(carryG7){residual.assign(proj::rel::active.begin(),proj::rel::active.end());fromG7=g7steps;}
  // On/off use identical G11 forward stages. ON spends a bounded slice on
  // local BDD feedback -> GF2 -> resumed projection; SHADOW performs the
  // same discovery but discards its messages. No source clauses are reloaded.
  if(mode!="off"&&carryG7&&n<=1500&&residual.size()<=10000){
   auto window=start+chrono::milliseconds(max(1,ms*52/100));
   bool stalled=false;
   for(int round=0;round<3&&Clock::now()<window;round++){
    stage="symbolic_feedback";Feedback f(n,min(window,Clock::now()+chrono::milliseconds(max(1,ms*7/100))),mode=="value"||mode=="memory"||mode=="store");
    bool mem=mode=="memory"||mode=="store"; f.remember=mem;
    if(mem)for(const auto&c:memory_messages)f.prior_dormant.insert(c);
    F revived;if(mode=="memory")revived=reactivate(residual,round,stalled,min(window,Clock::now()+chrono::milliseconds(max(1,ms/100))));
    try{f.run(residual);}catch(Limit&){}
    fb_screened+=f.screened;fb_rejected+=f.rejected;fb_proof_rejected+=f.proof_rejected;fb_credited+=f.credited;fb_predicted_lits+=f.predicted_lits;fb_pair_reduction+=f.pair_reduction;
    fb_rounds++;fb_clusters+=f.clusters;fb_candidates+=f.candidates;fb_pairs+=f.parity_pairs;
    if((f.additions.empty()&&f.dormant.empty()&&revived.empty()&&(!mem||pending.empty()))||mode=="shadow")break;
    proj::rel::end=end;
    // Publish only completed proofs. Helpers are ledger-only; boundary
    // clauses are admitted into the active formula, preserving equivalence.
    for(auto&c:f.emitted)proj::rel::emit(c);
    for(auto&c:f.dormant){pending.emplace(c,round);memory_messages.push_back(c);}memory_attempts+=f.dormant_attempts;
    for(auto&c:revived){pending.erase(c);memory_activated.push_back(c);if(find(f.additions.begin(),f.additions.end(),c)==f.additions.end())f.additions.push_back(c);}
    for(auto&c:f.additions)proj::rel::active.insert(c);
    fb_messages+=f.additions.size();fb_proof+=f.emitted.size();feedback_messages.insert(feedback_messages.end(),f.additions.begin(),f.additions.end());
    if(proj::rel::active.count({})){proj::rel::proof.push_back({});proj::rel::save_proof(tmp);terminal_rup(false,tmp);return 20;}
    residual.assign(proj::rel::active.begin(),proj::rel::active.end());
    // Re-extract affine rows from the actual enriched residual. G6 globals
    // must be reset, because the original solve used a different formula.
    if(Clock::now()<window){
     stage="feedback_affine";using namespace proj::g6;
     src=residual;known.clear();proof.clear();seen.clear();rows.clear();joined=blocked=0;detected=0;
     deadline=min(window,Clock::now()+chrono::milliseconds(max(1,ms*4/100)));int a=0;
     try{a=solve(tmp);}catch(proj::g6::Limit&){}
     fb_affine_rows+=detected;fb_affine_clauses+=proof.size();
     if(a==10){emit_model(model_file(tmp),true,nullptr);return 10;}
     if(a==20){terminal_rup(true,tmp);return 20;}
     proj::rel::end=end;
     if(proof.size()<=20000)for(auto c:proof){if(!proj::rel::normalize(c))continue;proj::rel::emit(c);proj::rel::active.insert(c);}
    }
    if((mode=="contract"||mode=="value"||mem)&&Clock::now()<window){
     stage="feedback_contract";proj::rel::end=min(window,Clock::now()+chrono::milliseconds(max(1,ms*4/100)));
     try{
      // A shorter proven clause subsumes each containing clause. Retain it
      // and remove supersets, so the next kernel receives fewer incidences.
      for(const auto& c:f.additions){if(c.empty()||!proj::rel::active.count(c))continue;vector<C> erase;
       for(const auto& d:proj::rel::active){proj::rel::guard();if(d.size()>c.size()&&proj::rel::sub(c,d))erase.push_back(d);}
       for(const auto&d:erase){proj::rel::active.erase(d);fb_subsumed++;}
      }
      // A proven unit fixes a variable exactly. Its opposite occurrences are
      // shortened by a single RUP resolution; store a reconstruction bucket.
      for(int k=0;k<64;k++){
       proj::rel::guard();int unit=0;for(const auto&c:proj::rel::active){proj::rel::guard();if(c.size()==1){unit=c[0];break;}}if(!unit)break;
       int v=abs(unit);proj::rel::Bucket bucket{v,{}};F add;
       for(const auto& c:proj::rel::active){proj::rel::guard();if(find(c.begin(),c.end(),unit)!=c.end())bucket.clauses.push_back(c);
        else if(find(c.begin(),c.end(),-unit)!=c.end()){bucket.clauses.push_back(c);C d=c;d.erase(find(d.begin(),d.end(),-unit));proj::rel::emit(d);if(d.empty()){if(proj::rel::proof.empty()||!proj::rel::proof.back().empty())proj::rel::proof.push_back({});proj::rel::save_proof(tmp);terminal_rup(false,tmp);return 20;}add.push_back(move(d));}}
       // No deadline check between mutation and reconstruction registration.
       for(const auto&c:bucket.clauses)proj::rel::active.erase(c);
       for(const auto&c:add)proj::rel::active.insert(c);
       proj::rel::stack.push_back(move(bucket));proj::rel::steps++;fb_units++;
      }
     }catch(proj::rel::Stop&){}
    }
    stage="feedback_projection";long long before=proj::rel::steps;
    proj::rel::end=min(window,Clock::now()+chrono::milliseconds(max(1,ms*6/100)));
    try{rc=proj::rel::project(tmp,true);}catch(proj::rel::Stop&){}
    fb_projection_steps+=proj::rel::steps-before;stalled=proj::rel::steps==before;
    if(rc){if(rc==10)emit_model(model_file(tmp),false,nullptr);else terminal_rup(false,tmp);return rc;}
    residual.assign(proj::rel::active.begin(),proj::rel::active.end());
   }
  }
  // At the representation switch, reconsider surviving dormant constraints
  // even if the last round made some progress: projection has no legal next
  // step, and a different kernel can benefit from an alternate relation.
  if(mode=="memory"&&carryG7&&proj::rel::reason=="no_bounded_projection"){
   auto last=reactivate(residual,3,true,min(start+chrono::milliseconds(max(1,ms*55/100)),Clock::now()+chrono::milliseconds(max(1,ms/100))));
   for(auto&c:last){pending.erase(c);proj::rel::active.insert(c);memory_activated.push_back(c);feedback_messages.push_back(c);fb_messages++;}
   if(!last.empty())residual.assign(proj::rel::active.begin(),proj::rel::active.end());
  }
  table::Engine t;t.n=n;t.src=residual;t.end=start+chrono::milliseconds(max(1,ms*60/100));stage="table";
  if(n<=2000&&residual.size()<=30000){try{rc=t.loaded(tmp);}catch(table::Stop&){} }else t.reason="input_budget";
  tableSteps=t.eliminated;tablereason=t.reason;
  if(rc){guard();if(rc==10)emit_model(model_file(tmp),carryG7,nullptr);else terminal_rup(carryG7,tmp);return rc;}
  bool carryTable=share&&t.initialized&&t.eliminated>0;const vector<Factor>* fs=carryTable?&t.fs:nullptr;
  if(carryTable){fromTable=t.eliminated;factors=t.fs.size();for(auto&f:t.fs)factorEntries+=f.t.size();}
  stage="ROBDD";Bridge b;b.n=n;b.end=start+chrono::milliseconds(max(1,ms*92/100));if(n>1000||(!fs&&residual.size()>30000)){bddreason="input_budget";return 0;}
  // OFF resets both the table and ROBDD stages to the original source.
  // ON hands exact tables directly to ROBDD, without expanding them to CNF.
  try{rc=b.run(fs,share?residual:source);}catch(sym::Stop&){}
  nodes=b.nodes.size();bddreason=b.reason;
  if(rc==10){emit_model(move(b.solution),carryG7,carryTable?&t:nullptr);return 10;}
  if(rc==20){F r=carryTable?encode_residual(t.fs):(share?residual:source);symbolic_proof(carryG7,carryTable?&t:nullptr,r,b.order,tmp);return 20;}
  return 0;
 }
};
int main(int argc,char**argv){if(argc!=5||(string(argv[4])!="on"&&string(argv[4])!="off"&&string(argv[4])!="shadow"&&string(argv[4])!="contract"&&string(argv[4])!="value"&&string(argv[4])!="memory"&&string(argv[4])!="store"))return 2;Runner r;r.mode=argv[4];r.output=argv[2];int rc=0;try{rc=r.run(argv[1],max(1,atoi(argv[3])));}catch(Limit&){}catch(proj::rel::Stop&){}catch(table::Stop&){}catch(exception&e){cerr<<e.what()<<'\n';return 2;}if(!r.feedback_messages.empty()||!r.memory_messages.empty()){string pp=r.output+".feedback.rup",mp=r.output+".messages";ofstream p(pp+".tmp"),m(mp+".tmp");for(auto&c:proj::rel::proof){for(int l:c)p<<l<<' ';p<<"0\n";}for(auto&c:r.feedback_messages){for(int l:c)m<<l<<' ';m<<"0\n";}p.close();m.close();if(!p||!m)return 2;auto side=[&](string suffix,const F& cs){if(cs.empty())return true;string file=r.output+suffix;ofstream q(file+".tmp");for(auto&c:cs){for(int l:c)q<<l<<' ';q<<"0\n";}q.close();return q&&rename((file+".tmp").c_str(),file.c_str())==0;};if(!side(".memory",r.memory_messages)||!side(".activated",r.memory_activated))return 2;if(rename((mp+".tmp").c_str(),mp.c_str())||rename((pp+".tmp").c_str(),pp.c_str()))return 2;}if(rc==0)std::remove(r.output.c_str());cout<<"status="<<rc<<" stage="<<r.stage<<" g7_steps="<<r.g7steps<<" g7_clauses="<<r.g7clauses<<" table_steps="<<r.tableSteps<<" handoff_g7="<<r.fromG7<<" handoff_table="<<r.fromTable<<" factors="<<r.factors<<" factor_entries="<<r.factorEntries<<" bdd_nodes="<<r.nodes<<" prefix_lines="<<r.proofLines<<" g7_reason="<<r.g7reason<<" table_reason="<<r.tablereason<<" fb_rounds="<<r.fb_rounds<<" fb_clusters="<<r.fb_clusters<<" fb_candidates="<<r.fb_candidates<<" fb_messages="<<r.fb_messages<<" fb_proof="<<r.fb_proof<<" fb_pairs="<<r.fb_pairs<<" fb_affine_rows="<<r.fb_affine_rows<<" fb_affine_clauses="<<r.fb_affine_clauses<<" fb_projection_steps="<<r.fb_projection_steps<<" fb_subsumed="<<r.fb_subsumed<<" fb_units="<<r.fb_units<<" fb_screened="<<r.fb_screened<<" fb_rejected="<<r.fb_rejected<<" fb_proof_rejected="<<r.fb_proof_rejected<<" fb_credited="<<r.fb_credited<<" fb_predicted_lits="<<r.fb_predicted_lits<<" fb_pair_reduction="<<r.fb_pair_reduction<<" memory_saved="<<r.memory_messages.size()<<" memory_activated="<<r.memory_activated.size()<<" memory_expired="<<r.memory_expired<<" memory_reassess="<<r.memory_reassess<<" memory_value="<<r.memory_activated_value<<" memory_stall="<<r.memory_activated_stall<<" memory_attempts="<<r.memory_attempts<<" bdd_reason="<<r.bddreason<<'\n';return rc;}
