#include <bits/stdc++.h>
using namespace std;
namespace g6 {
#define main general6_entry
#include "affine.cpp"
#undef main
}
namespace rel {
using C=vector<int>;using F=vector<C>;using Clock=chrono::steady_clock;
struct Stop{};
struct Bucket{int v;F clauses;};
struct Plan{int v=0;long long pairs=0;int scope=0;F add;};
bool initialized=false;int n;F source,proof;set<C> active,known;vector<Bucket> stack;
Clock::time_point end;long long considered=0,attempts=0,resolutions=0,subsumed=0,shared=0,peak=0,steps=0;int widest=0;string reason="none",method="projection";
constexpr int max_scope=12,max_clause=12,max_pairs=8192,max_active=100000,max_proof=100000;
void guard(){if(Clock::now()>=end){reason="deadline";throw Stop{};}if(proof.size()>max_proof||active.size()>max_active){reason="budget";throw Stop{};}}
bool cmp(int a,int b){return abs(a)<abs(b)||(abs(a)==abs(b)&&a<b);}
bool normalize(C&c){sort(c.begin(),c.end(),cmp);c.erase(unique(c.begin(),c.end()),c.end());for(size_t i=1;i<c.size();++i)if(c[i]==-c[i-1])return false;return true;}
bool read(const string&f){ifstream in(f);if(!in)return false;string line;C c;long long m=-1,got=0;while(getline(in,line)){guard();istringstream s(line);string t;s>>t;if(t.empty()||t=="c")continue;if(t=="%")break;if(t=="p"){string fmt;if(m!=-1||!(s>>fmt>>n>>m)||fmt!="cnf"||n<0||n>2000000||m<0||m>10000000)return false;if(n>10000||m>100000){reason="input_budget";throw Stop{};}continue;}s.clear();s.str(line);long long l;while(s>>l){if(m<0||l>n||l< -n)return false;if(!l){++got;if(normalize(c))source.push_back(c);c.clear();}else c.push_back((int)l);}}
return m>=0&&got==m&&c.empty();}
bool model_ok(const vector<int>&a){for(const auto&c:source){bool sat=false;for(int l:c)if(a[abs(l)]==(l>0)){sat=true;break;}if(!sat)return false;}return true;}
void save_proof(const string&f){ofstream o(f);for(const auto&c:proof){for(int l:c)o<<l<<' ';o<<"0\n";}if(!o)throw runtime_error("proof write failed");}
void save_model(const string&f,const vector<int>&a){ofstream o(f);o<<"v ";for(int i=1;i<=n;i++)o<<(a[i]?i:-i)<<' ';o<<"0\n";if(!o)throw runtime_error("model write failed");}
void emit(const C&c){guard();if(known.insert(c).second)proof.push_back(c);}
bool sub(const C&a,const C&b){return includes(b.begin(),b.end(),a.begin(),a.end(),cmp);}
// The conjunction of the bucket's clauses is a local Boolean relation.
// Resolving all opposite-polarity clauses implements its existential projection.
// A tautological resolvent contributes no restriction. Subsumption is exact.
optional<Plan> plan(int v,const vector<const C*>&pos,const vector<const C*>&neg,int scope){
 guard();++attempts;Plan p;p.v=v;p.pairs=(long long)pos.size()*neg.size();p.scope=scope;
 if(!p.pairs)return p;
 if(scope>max_scope||p.pairs>max_pairs)return nullopt;
 set<C> out;
 for(auto a:pos)for(auto b:neg){guard();C c;for(int l:*a)if(abs(l)!=v)c.push_back(l);for(int l:*b)if(abs(l)!=v)c.push_back(l);if(!normalize(c))continue;if(c.size()>max_clause)return nullopt;out.insert(move(c));}
 vector<C> ordered(out.begin(),out.end());sort(ordered.begin(),ordered.end(),[](const C&a,const C&b){return a.size()!=b.size()?a.size()<b.size():a<b;});
 for(auto&c:ordered){guard();bool redundant=false;if(p.add.size()<2048){for(const auto&d:p.add){if(sub(d,c)){redundant=true;break;}}}if(redundant)continue;p.add.push_back(move(c));}
 // Bound total residual growth; do not turn projection into unrestricted resolution.
 if(p.add.size()>pos.size()+neg.size()+128)return nullopt;
 return p;
}
int project(const string&out,bool adaptive){
 if(!initialized){for(const C&c:source){guard();active.insert(c);known.insert(c);}initialized=true;}if(active.count({})){proof.push_back({});save_proof(out);return 20;}
 if(active.empty()&&stack.empty()){vector<int>a(n+1);save_model(out,a);return 10;}
 while(!active.empty()){
  guard();peak=max(peak,(long long)active.size());
  vector<vector<const C*>> pos(n+1),neg(n+1);for(auto&c:active){guard();for(int l:c)(l>0?pos[l]:neg[-l]).push_back(&c);}
  vector<tuple<long long,int,int>> candidates;
  for(int v=1;v<=n;v++){if(pos[v].empty()&&neg[v].empty())continue;long long pairs=(long long)pos[v].size()*neg[v].size();if(pairs>max_pairs)continue;int scope=0;if(pairs){set<int> vars;for(auto c:pos[v])for(int l:*c)if(abs(l)!=v)vars.insert(abs(l));for(auto c:neg[v])for(int l:*c)if(abs(l)!=v)vars.insert(abs(l));scope=vars.size();if(scope>max_scope)continue;}candidates.emplace_back(pairs,scope,v);}
  considered+=candidates.size();sort(candidates.begin(),candidates.end());if(!adaptive)sort(candidates.begin(),candidates.end(),[](auto a,auto b){return get<2>(a)<get<2>(b);});
  optional<Plan> best;tuple<long long,int,long long,int> bestkey{LLONG_MAX,INT_MAX,LLONG_MAX,INT_MAX};
  int examined=0;
  for(auto [pairs,scope,v]:candidates){guard();if(examined++>=32&&best)break;auto p=plan(v,pos[v],neg[v],scope);if(!p)continue;long long removed=pos[v].size()+neg[v].size();auto key=make_tuple((long long)p->add.size()-removed,scope,pairs,v);if(!best||key<bestkey){bestkey=key;best=move(p);}if(!adaptive||pairs==0)break;}
  if(!best){reason="no_bounded_projection";return 0;}auto&p=*best;Bucket b{p.v,{}};for(auto c:pos[p.v])b.clauses.push_back(*c);for(auto c:neg[p.v])b.clauses.push_back(*c);
  for(const auto&c:p.add){guard();emit(c);++resolutions;if(c.empty()){if(proof.empty()||!proof.back().empty())proof.push_back({});save_proof(out);return 20;}}
  for(const auto&c:b.clauses)active.erase(c);
  for(const auto&c:p.add)active.insert(c);
  stack.push_back(move(b));widest=max(widest,p.scope);++steps;
 }
 vector<int>a(n+1,0);
 for(auto it=stack.rbegin();it!=stack.rend();++it){guard();int needed=-1;for(const auto&c:it->clauses){bool satisfied=false;int sign=-1;for(int l:c){if(abs(l)==it->v)sign=l>0;else if(a[abs(l)]==(l>0)){satisfied=true;break;}}if(!satisfied){if(sign<0||(needed!=-1&&needed!=sign))throw runtime_error("projection reconstruction invariant");needed=sign;}}a[it->v]=needed<0?0:needed;}
 if(!model_ok(a))throw runtime_error("source model invariant");
 save_model(out,a);return 10;
}
int solve(const string&input,const string&out,int ms,const string&mode){
 end=Clock::now()+chrono::milliseconds(ms);if(!read(input))throw runtime_error("invalid DIMACS");
 if(mode=="hybrid"||mode=="no-share"){
  g6::n=n;g6::src=source;g6::deadline=min(end,Clock::now()+chrono::milliseconds(max(1,ms/3)));int s=0;try{s=g6::solve(out);}catch(g6::Limit&){}
  if(s){method="affine";return s;}
  // Transport complete, ordered affine RUP additions, never unproved row guesses.
  // All carried clauses remain in the final UNSAT proof, and all SAT models
  // are checked on the original source. Discard oversized prefixes atomically.
  if(mode=="hybrid"&&g6::proof.size()<=20000){for(auto c:g6::proof){guard();if(!normalize(c))continue;if(known.insert(c).second){proof.push_back(c);active.insert(c);++shared;}}}
  method=shared?"affine+projection":"projection";
 }
 return project(out,mode!="fixed");
}
}
