#include <algorithm>
#include <functional>
#include <cmath>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <numeric>
#include <random>
#include <queue>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
using namespace std;
using C=vector<int>; using F=vector<C>; using Clock=chrono::steady_clock; using TP=Clock::time_point;
static C norm(C c){sort(c.begin(),c.end());c.erase(unique(c.begin(),c.end()),c.end());return c;}
static bool has(const C& c,int x){return binary_search(c.begin(),c.end(),x);}
static bool taut(const C& c){for(int x:c)if(has(c,-x))return true;return false;}
static C res(const C& a,const C& b,int v){C c;for(int x:a)if(x!=v)c.push_back(x);for(int x:b)if(x!=-v)c.push_back(x);return norm(c);}
static int sign(int x){return x>0?1:-1;}
static bool expired(TP t){return Clock::now()>=t;}
static long ms(TP t){return chrono::duration_cast<chrono::milliseconds>(Clock::now()-t).count();}
struct Input{int n=0,m=0;F c;};
static Input readcnf(const string& path){ifstream f(path);if(!f)throw runtime_error("input open");Input d;string s;C c;bool header=false;while(getline(f,s)){istringstream in(s);string p;if(!(in>>p))continue;if(p=="c")continue;if(p=="%")break;if(p=="p"){string k;in>>k>>d.n>>d.m;if(header||k!="cnf"||d.n<0||d.m<0)throw runtime_error("header");header=true;continue;}if(!header)throw runtime_error("missing header");in.clear();in.str(s);int x;while(in>>x){if(x){if(abs((long long)x)>d.n)throw runtime_error("literal range");c.push_back(x);}else{d.c.push_back(norm(c));c.clear();}}if(!in.eof())throw runtime_error("invalid token");}if(!header||!c.empty()||(int)d.c.size()!=d.m)throw runtime_error("clause count");return d;}
static bool verify(const F& f,const vector<int>& a){for(auto& c:f){bool ok=false;for(int x:c)if(a[abs(x)]==sign(x)){ok=true;break;}if(!ok)return false;}return true;}
[[maybe_unused]] static bool up(const F& f,int n,const C& assume,vector<int>* out=nullptr){vector<int>a(n+1);for(int x:assume){if(a[abs(x)]==-sign(x))return false;a[abs(x)]=sign(x);}bool ch=true;while(ch){ch=false;for(auto&c:f){bool sat=false;int k=0,l=0;for(int x:c){if(a[abs(x)]==sign(x)){sat=true;break;}if(!a[abs(x)]){++k;l=x;}}if(sat)continue;if(!k)return false;if(k==1){a[abs(l)]=sign(l);ch=true;}}}if(out)*out=move(a);return true;}
#include "assumption_propagator.hpp"
struct Step{C c;int a=-1,b=-1,v=0;};struct Elim{int v;F old;};
struct Prep{const Input& in;F all;vector<char> live;map<C,int> lookup;vector<set<int>> occ;vector<char> active;vector<Step> proof;vector<Elim> stack;int gates=0,units=0,ssr=0,subs=0,probes=0;TP until;
 Prep(const Input& d,TP t):in(d),all(d.c),live(d.m),occ(2*d.n+2),active(d.n+1,1),until(t){for(int i=0;i<d.m;i++)activate(i);}
 int ix(int x)const{return 2*abs(x)+(x<0);}const set<int>& at(int x)const{return occ[ix(x)];}
 void activate(int i){const C&c=all[i];if(taut(c)||lookup.count(c))return;live[i]=1;lookup[c]=i;for(int x:c)occ[ix(x)].insert(i);}
 void erase(int i){if(!live[i])return;live[i]=0;lookup.erase(all[i]);for(int x:all[i])occ[ix(x)].erase(i);}
 int add(C c,int a,int b,int v){auto it=lookup.find(c);if(it!=lookup.end())return it->second;int i=all.size();all.push_back(c);live.push_back(0);proof.push_back({move(c),a,b,v});activate(i);return i;}
 bool empty()const{return lookup.count(C{});}F residual()const{F d;for(auto&[c,i]:lookup)d.push_back(c);return d;}
 void commit(int v,const set<int>& rem,const map<C,Step>& R){Elim e{v,{}};for(int i:rem)e.old.push_back(all[i]);stack.push_back(move(e));for(int i:rem)erase(i);for(auto&[c,s]:R)add(c,s.a,s.b,s.v);active[v]=0;}
 bool prop(){bool ch=false;while(!expired(until)&&!empty()){int id=-1;for(auto&[c,i]:lookup)if(c.size()==1){id=i;break;}if(id<0)break;int l=all[id][0],v=abs(l);set<int> rem=at(l);rem.insert(at(-l).begin(),at(-l).end());map<C,Step> R;for(int j:at(-l)){int a=l>0?id:j,b=l>0?j:id;C c=res(all[a],all[b],v);R[c]={c,a,b,v};}commit(v,rem,R);++units;ch=true;}return ch;}
 bool project(int v,int growth,const set<int>* def=nullptr){if(!active[v])return false;auto &p=at(v),&q=at(-v);if(!def&&p.size()*q.size()>2400)return false;if(def)for(int id:*def)if(!live[id])return false;set<int> rem=p;rem.insert(q.begin(),q.end());map<C,Step> R;for(int i:p)for(int j:q){if(def&&!def->count(i)&&!def->count(j))continue;C c=res(all[i],all[j],v);if(taut(c))continue;if(c.size()>18)return false;auto t=lookup.find(c);if(t!=lookup.end()&&!rem.count(t->second))continue;R[c]={c,i,j,v};if(R.size()>rem.size()+growth)return false;}commit(v,rem,R);return true;}
 struct Gate{int v;set<int> ids;};
 vector<Gate> detect(){vector<Gate> out;map<C,map<int,int>> group;for(auto&[c,i]:lookup){if(c.size()<2||c.size()>5)continue;C v;for(int x:c)v.push_back(abs(x));v=norm(v);if(v.size()!=c.size())continue;int mask=0;for(size_t j=0;j<v.size();j++)if(has(c,-v[j]))mask|=1<<j;group[v][mask]=i;if(c.size()>=3)for(int o:c){set<int> ids{i};for(int a:c)if(a!=o){auto t=lookup.find(norm({-o,-a}));if(t==lookup.end())break;ids.insert(t->second);}if(ids.size()==c.size())out.push_back({abs(o),move(ids)});}}for(auto&[v,masks]:group)for(int p=0;p<2;p++){set<int> ids;for(auto&[mask,id]:masks)if(__builtin_parity((unsigned)mask)==p)ids.insert(id);if(ids.size()==(size_t(1)<<(v.size()-1)))for(int x:v)out.push_back({x,ids});}return out;}
 int gatepass(){auto g=detect();sort(g.begin(),g.end(),[&](auto&a,auto&b){return make_tuple(a.ids.size(),at(a.v).size()+at(-a.v).size(),a.v)<make_tuple(b.ids.size(),at(b.v).size()+at(-b.v).size(),b.v);});int k=0;for(auto&x:g){if(expired(until)||empty())break;if(project(x.v,8,&x.ids)){++k;++gates;}}return k;}
 int strengthen(){vector<int> ids;for(auto&[c,i]:lookup)ids.push_back(i);sort(ids.begin(),ids.end(),[&](int a,int b){return all[a].size()<all[b].size();});int ch=0;for(int i:ids){if(expired(until)||empty())break;if(!live[i])continue;C A=all[i];if(A.empty())break;int pick=*min_element(A.begin(),A.end(),[&](int x,int y){return at(x).size()<at(y).size();});vector<int> cand(at(pick).begin(),at(pick).end());for(int j:cand)if(i!=j&&live[j]&&includes(all[j].begin(),all[j].end(),A.begin(),A.end())){erase(j);++subs;++ch;}for(int l:A){vector<int> js(at(-l).begin(),at(-l).end());for(int j:js){if(!live[j]||i==j||A.size()>all[j].size())continue;bool ok=true;for(int x:A)if(x!=l&&!has(all[j],x)){ok=false;break;}if(!ok)continue;int v=abs(l),a=l>0?i:j,b=l>0?j:i;C c=res(all[a],all[b],v);add(c,a,b,v);erase(j);++ssr;++ch;}}}return ch;}
 bool bve(int growth){bool ch=false;while(!expired(until)&&!empty()&&!lookup.empty()){prop();if(empty()||lookup.empty())break;vector<tuple<long long,int,int>> vs;for(int v=1;v<=in.n;v++)if(active[v]){long long p=at(v).size(),q=at(-v).size();vs.emplace_back(p*q-p-q,p+q,v);}sort(vs.begin(),vs.end());bool ok=false;for(int g:{0,growth}){for(auto [cost,deg,v]:vs){if(expired(until))break;if(project(v,g)){ok=true;ch=true;break;}}if(ok)break;}if(!ok)break;}return ch;}
 int probe(bool pairs){F d=residual();AssumptionPropagator closure(d,in.n);vector<pair<int,int>> vs;for(int v=1;v<=in.n;v++)if(active[v]&&at(v).size()+at(-v).size())vs.push_back({-(int)(at(v).size()+at(-v).size()),v});sort(vs.begin(),vs.end());for(auto [s,v]:vs){for(int l:{v,-v}){if(expired(until))return 0;if(!closure.run({l})){add({-l},-1,-1,0);++probes;return 1;}}}if(!pairs)return 0;int k=0,lim=min(24,(int)vs.size());for(int i=0;i<lim;i++)for(int j=i+1;j<lim;j++)for(int a:{vs[i].second,-vs[i].second})for(int b:{vs[j].second,-vs[j].second}){if(expired(until)||k>=32)return k;C c=norm({-a,-b});if(!lookup.count(c)&&!closure.run({a,b})){add(c,-1,-1,0);++probes;++k;}}return k;}
 void run(bool attack){for(int i=0;i<6&&!expired(until)&&!empty();i++){prop();if(!gatepass())break;}for(int i=0;i<18&&!expired(until)&&!empty()&&!lookup.empty();i++){prop();int ch=strengthen();bool b=bve(attack?8:4);if(empty()||lookup.empty())break;ch+=gatepass();if(attack&&!b&&!ch)ch+=probe(true);if(!b&&!ch)break;}}
 bool lift(vector<int>& a)const{for(auto i=stack.rbegin();i!=stack.rend();++i){int need=0;for(auto&c:i->old){bool ok=false;int l=0;for(int x:c){if(abs(x)==i->v)l=x;else if(a[abs(x)]==sign(x))ok=true;}if(ok)continue;if(!l|| (need&&need!=sign(l)))return false;need=sign(l);}a[i->v]=need?need:-1;}return verify(in.c,a);}
 bool audit(TP deadline) const {
     F replay = in.c;
     replay.reserve(in.c.size() + proof.size());
     AssumptionPropagator rup(replay, in.n);
     for (const Step& step : proof) {
         if (expired(deadline)) return false;
         if (step.v) {
             const int end = static_cast<int>(replay.size());
             if (step.a < 0 || step.a >= end || step.b < 0 || step.b >= end)
                 return false;
             const C& left = replay[step.a];
             const C& right = replay[step.b];
             if (!has(left, step.v) || !has(right, -step.v) ||
                 res(left, right, step.v) != step.c) return false;
         } else {
             C assumptions;
             assumptions.reserve(step.c.size());
             for (int literal : step.c) assumptions.push_back(-literal);
             if (rup.run(assumptions)) return false;
         }
         replay.push_back(step.c);
         rup.index_next();
     }
     for (const auto& [clause, id] : lookup)
         if (id < 0 || size_t(id) >= replay.size() || replay[id] != clause) return false;
     return true;
 }
 void drat(const string& path) const {
     ofstream out(path);
     bool ended = false;
     for (const Step& step : proof) {
         for (int literal : step.c) out << literal << ' ';
         out << "0\n";
         if (step.c.empty()) { ended = true; break; }
     }
     if (!ended && find(in.c.begin(), in.c.end(), C{}) != in.c.end()) out << "0\n";
     out.close();
     if (!out) throw runtime_error("resolution proof write failed");
 }
};
#include "parity_proof.hpp"
// Complete explicit parity patterns; GF(2) elimination builds a SAT candidate only.
static bool gf2(const F& f,int n,vector<int>& a,TP until,F* contradiction=nullptr){map<C,set<unsigned>> g;for(auto&c:f){if(c.empty()||c.size()>8||taut(c))continue;C v;for(int x:c)v.push_back(abs(x));v=norm(v);if(v.size()!=c.size())continue;unsigned mask=0;for(size_t i=0;i<v.size();i++)if(has(c,-v[i]))mask|=1u<<i;g[v].insert(mask);}int words=(n+63)/64;struct Row{vector<uint64_t>x;int b;};map<int,Row> p;for(auto&[v,s]:g)for(int k=0;k<2;k++){if(expired(until))return false;int num=0;for(unsigned x:s)if(__builtin_parity(x)==k)++num;if(num!=(1<<(v.size()-1)))continue;Row r{vector<uint64_t>(words),1-k};for(int x:v)r.x[(x-1)/64]^=1ull<<((x-1)%64);for(;;){int j=-1;for(int w=0;w<words;w++)if(r.x[w]){j=w*64+__builtin_ctzll(r.x[w]);break;}if(j<0){if(r.b){if(contradiction)compile_parity(g,f,n,until,*contradiction);return false;}break;}auto z=p.find(j);if(z==p.end()){p.emplace(j,move(r));break;}for(int w=0;w<words;w++)r.x[w]^=z->second.x[w];r.b^=z->second.b;}}if(p.empty())return false;a.assign(n+1,-1);vector<uint64_t>x(words);for(auto it=p.rbegin();it!=p.rend();++it){int k=it->first,b=it->second.b;for(int w=0;w<words;w++)b^=__builtin_parityll(it->second.x[w]&x[w]);if(b){x[k/64]|=1ull<<(k%64);a[k+1]=1;}}return verify(f,a);}
// Direct capacity certificate: disjoint demands and a partition into pairwise mutex resources.
static pair<int,int> capacity(const F& f){vector<C> groups;set<int> U;for(auto&c:f)if(c.size()>=3&&c.front()>0){for(int x:c)if(!U.insert(x).second)return {0,0};groups.push_back(c);}if(U.empty()||U.size()>2500)return {0,0};map<int,set<int>> G;for(int x:U)G[x];for(auto&c:f)if(c.size()==2&&c.back()<0&&U.count(-c[0])&&U.count(-c[1])){G[-c[0]].insert(-c[1]);G[-c[1]].insert(-c[0]);}set<int> seen;int k=0;for(int v:U)if(seen.insert(v).second){C q{v};for(size_t i=0;i<q.size();i++)for(int w:G[q[i]])if(seen.insert(w).second)q.push_back(w);for(int x:q)if(G[x].size()+1!=q.size())return {0,0};++k;}return {(int)groups.size(),k};}
struct Limit{};struct BDD{struct Node{int v,l,h;};vector<Node> nd{{INT32_MAX,0,0},{INT32_MAX,1,1}};unordered_map<uint64_t,int> uniq,cache;TP until;int cap;long long calls=0;BDD(TP t,int c):until(t),cap(c){}void check(){if(expired(until)||(int)nd.size()>=cap)throw Limit{};}
 static uint64_t k3(int a,int b,int c){return (uint64_t(a)<<42)|(uint64_t(b)<<21)|uint64_t(c);}int mk(int v,int l,int h){if(l==h)return l;auto k=k3(v,l,h);auto it=uniq.find(k);if(it!=uniq.end())return it->second;if((nd.size()&1023)==0)check();int id=nd.size();nd.push_back({v,l,h});uniq[k]=id;return id;}
 int app(int op,int a,int b){if(a>b)swap(a,b);if(a==b)return a;if(!op){if(!a)return 0;if(a==1)return b;}else{if(!a)return b;if(a==1)return 1;}auto k=k3(op,a,b);auto it=cache.find(k);if(it!=cache.end())return it->second;if((++calls&4095)==0)check();int v=min(nd[a].v,nd[b].v);Node x=nd[a],y=nd[b];int l=app(op,x.v==v?x.l:a,y.v==v?y.l:b),h=app(op,x.v==v?x.h:a,y.v==v?y.h:b);int z=mk(v,l,h);cache[k]=z;return z;}
};
static vector<int> order(const F& f,int n,int mode,TP until,int& width){vector<set<int>> g(n+1);set<int> alive;for(auto&c:f)for(int x:c){int v=abs(x);alive.insert(v);for(int y:c)if(v!=abs(y))g[v].insert(abs(y));}vector<int> o;while(!alive.empty()){if(expired(until))throw Limit{};vector<pair<int,int>> cand;for(int x:alive)cand.push_back({g[x].size(),x});sort(cand.begin(),cand.end());long long best=INT64_MAX;int v=0;for(int i=0;i<min((int)cand.size(),mode?1:24);i++){int x=cand[i].second;long long fill=0;for(int a:g[x])for(int b:g[x])if(a<b&&!g[a].count(b))++fill;long long score=fill*10000+g[x].size();if(score<best){best=score;v=x;}}auto ns=g[v];width=max(width,(int)ns.size());for(int a:ns){g[a].erase(v);for(int b:ns)if(a!=b)g[a].insert(b);}alive.erase(v);o.push_back(v);}return o;}
struct BResult{int status=0,nodes=0,width=0;vector<int>a;};
// Exact existential bucket elimination, with independent semantic replay of AND/OR.
static BResult bdd(const F& f,int n,int mode,TP until,int cap){BResult R;try{for(auto&c:f)if(c.empty()){R.status=-1;return R;}auto o=order(f,n,mode,until,R.width);vector<int> rank(n+1,-1);for(size_t i=0;i<o.size();i++)rank[o[i]]=i;BDD b(until,cap);vector<vector<int>> buckets(o.size());vector<int> init,roots;struct Op{int op,a,b,z;};vector<Op> tr;struct E{int i,r,z;vector<int> ins;};vector<E> es;bool bad=false;auto push=[&](int z){if(!z)bad=true;else if(z!=1)buckets[b.nd[z].v].push_back(z);};for(auto c:f){sort(c.begin(),c.end(),[&](int x,int y){return rank[abs(x)]>rank[abs(y)];});int z=0;for(int x:c)z=x>0?b.mk(rank[abs(x)],z,1):b.mk(rank[abs(x)],1,z);init.push_back(z);push(z);}for(int i=0;i<(int)o.size()&&!bad;i++){b.check();auto ins=buckets[i];int r=1;for(int a:ins){int z=b.app(0,r,a);tr.push_back({0,r,a,z});r=z;if(!r)break;}int z=r;if(r>1&&b.nd[r].v==i){auto t=b.nd[r];z=b.app(1,t.l,t.h);tr.push_back({1,t.l,t.h,z});}es.push_back({i,r,z,move(ins)});push(z);}R.nodes=b.nd.size();if(!bad){R.a.assign(n+1,-1);auto eval=[&](int z){while(z>1){auto t=b.nd[z];z=R.a[o[t.v]]>0?t.h:t.l;}return z;};for(auto it=es.rbegin();it!=es.rend();++it){R.a[o[it->i]]=-1;if(!eval(it->r))R.a[o[it->i]]=1;if(!eval(it->r))return R;}if(verify(f,R.a))R.status=1;return R;}
 // Audit construction, all original residual clauses, operation semantics and bucket accounting.
 for(size_t i=2;i<b.nd.size();i++){auto t=b.nd[i];if(t.l==t.h||t.l>=(int)i||t.h>=(int)i||t.v>=b.nd[t.l].v||t.v>=b.nd[t.h].v)return R;}
 for(size_t j=0;j<f.size();j++){C c=f[j];sort(c.begin(),c.end(),[&](int x,int y){return rank[abs(x)]<rank[abs(y)];});int z=init[j];for(int x:c){if(z<2)return R;auto t=b.nd[z];if(t.v!=rank[abs(x)]||(x>0?t.h:t.l)!=1)return R;z=x>0?t.l:t.h;}if(z!=0)return R;}
 unordered_set<uint64_t> checked;long long ticks=0;auto eq=[&](auto&& self,int op,int a,int c,int z)->bool{if(a>c)swap(a,c);if(a==c)return z==a;if(!op){if(!a)return z==0;if(a==1)return z==c;}else{if(!a)return z==c;if(a==1)return z==1;}uint64_t k=(uint64_t(op)<<63)|BDD::k3(a,c,z);if(checked.count(k))return true;if((++ticks&4095)==0&&expired(until))throw Limit{};int v=min({b.nd[a].v,b.nd[c].v,b.nd[z].v});auto at=[&](int x,bool h){return b.nd[x].v==v?(h?b.nd[x].h:b.nd[x].l):x;};if(!self(self,op,at(a,false),at(c,false),at(z,false))||!self(self,op,at(a,true),at(c,true),at(z,true)))return false;checked.insert(k);return true;};for(auto t:tr)if(!eq(eq,t.op,t.a,t.b,t.z))return R;for(auto&x:buckets)x.clear();bad=false;for(int z:init)push(z);size_t ti=0;for(auto&e:es){if(bad||e.ins!=buckets[e.i])return R;int r=1;for(int a:e.ins){if(ti>=tr.size())return R;auto t=tr[ti++];if(t.op!=0||t.a!=r||t.b!=a)return R;r=t.z;if(!r)break;}if(r!=e.r)return R;int z=r;if(r>1&&b.nd[r].v==e.i){if(ti>=tr.size())return R;auto t=tr[ti++];if(t.op!=1||t.a!=b.nd[r].l||t.b!=b.nd[r].h)return R;z=t.z;}if(z!=e.z)return R;push(z);}if(bad&&ti==tr.size())R.status=-1;return R;
 }catch(Limit&){return R;}}
#include "repair.hpp"
// Bounded model construction with verified exact-one domains and single/swap moves; never an UNSAT oracle.
static bool construct(const F& f,int n,vector<int>& a,TP until){mt19937 gen(42);set<C> S(f.begin(),f.end());vector<C> groups;vector<int> owner(n+1,-1),chosen;vector<vector<int>> oc(n+1);for(int i=0;i<(int)f.size();i++){if(f[i].empty())return false;for(int x:f[i])oc[abs(x)].push_back(i);}for(auto&c:f)if(c.size()>=3&&c.size()<=64){bool ok=true;for(int x:c)if(owner[abs(x)]>=0)ok=false;for(size_t i=0;i<c.size()&&ok;i++)for(size_t j=i+1;j<c.size();j++)if(!S.count(norm({-c[i],-c[j]}))){ok=false;break;}if(ok){int k=groups.size();groups.push_back(c);for(int x:c)owner[abs(x)]=k;}}
 vector<int> best_model;size_t best_bad=f.size()+1;
 vector<int> count(f.size()),bad,pos(f.size(),-1),mark(f.size(),0);int stamp=0;auto clausecount=[&](int i){int c=0;for(int x:f[i])c+=a[abs(x)]==sign(x);return c;};auto remove=[&](int i){int k=pos[i];if(k<0)return;int j=bad.back();bad[k]=j;pos[j]=k;bad.pop_back();pos[i]=-1;};auto addbad=[&](int i){if(pos[i]<0){pos[i]=bad.size();bad.push_back(i);}};auto move=[&](C v,bool commit){++stamp;vector<int> hit;for(int x:v)for(int i:oc[x])if(mark[i]!=stamp){mark[i]=stamp;hit.push_back(i);}for(int x:v)a[x]*=-1;int delta=0;for(int i:hit){int c=clausecount(i);delta+=(c==0)-(count[i]==0);if(commit){count[i]=c;if(c)remove(i);else addbad(i);}}if(!commit)for(int x:v)a[x]*=-1;return delta;};for(int restart=0;!expired(until)&&restart<100;restart++){a.assign(n+1,-1);for(int x=1;x<=n;x++)a[x]=gen()&1?1:-1;for(auto&g:groups){for(int x:g)a[abs(x)]=-sign(x);int l=g[gen()%g.size()];a[abs(l)]=sign(l);}bad.clear();fill(pos.begin(),pos.end(),-1);for(int i=0;i<(int)f.size();i++){count[i]=clausecount(i);if(!count[i])addbad(i);}for(int t=0;t<20000&&!expired(until);t++){if(bad.size()<best_bad){best_bad=bad.size();best_model=a;}if(bad.empty())return verify(f,a);auto& c=f[bad[gen()%bad.size()]];vector<C> moves;for(int l:c){int v=abs(l),g=owner[v];if(g<0)moves.push_back({v});else{int cur=0;for(int x:groups[g])if(a[abs(x)]==sign(x)){cur=abs(x);break;}if(!cur)continue;if(cur!=v)moves.push_back({v,cur});else for(int x:groups[g])if(abs(x)!=cur)moves.push_back({cur,abs(x)});}}if(moves.empty())break;int best=INT32_MAX,j=0;if(gen()%100<30)j=gen()%moves.size();else for(int i=0;i<(int)moves.size();i++){int d=move(moves[i],false);if(d<best||(d==best&&(gen()&1))){best=d;j=i;}}move(moves[j],true);}}if(!best_model.empty())a=std::move(best_model);return false;}
#include "general4.hpp"
#include "fusion.hpp"
