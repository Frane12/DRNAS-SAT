#include <bits/stdc++.h>
using namespace std;
using C=vector<int>;using Clock=chrono::steady_clock;
struct Stop{}; struct Factor{C v; vector<uint8_t> t;};
struct Step{int pivot;Factor joined,projected;vector<Factor> messages;};
struct Plan{int pivot;vector<int> ix;Step step;long long cost;};
struct Engine {
 int n=0; vector<C> src; vector<Factor> fs; vector<Step> trail; Clock::time_point end;
 bool factorize=true,initialized=false; long long ops=0,attempts=0,eliminated=0,splits=0,removed=0,peak=0,stored=0,prooflines=0;int width=0;string reason="none";
 void guard(){if(Clock::now()>=end){reason="deadline";throw Stop{};}if(stored>16000000){reason="table_budget";throw Stop{};}}
 void tick(){if((++ops&4095)==0)guard();}
 bool read(string p){ifstream f(p);string line;long long m=-1,count=0;C c;while(getline(f,line)){guard();istringstream s(line);string a;s>>a;if(a.empty()||a=="c")continue;if(a=="%")break;if(a=="p"){string fmt;if(!(s>>fmt>>n>>m)||fmt!="cnf"||n<0||m<0)return false;if(n>2000||m>30000){reason="input_budget";throw Stop{};}continue;}s.clear();s.str(line);long long l;while(s>>l){if(m<0||abs(l)>n)return false;if(l)c.push_back(l);else{count++;sort(c.begin(),c.end());c.erase(unique(c.begin(),c.end()),c.end());bool taut=false;for(int x:c)if(binary_search(c.begin(),c.end(),-x))taut=true;if(!taut)src.push_back(c);c.clear();}}}return m>=0&&count==m&&c.empty();}
 int index(const C&v,const vector<int>&a){int z=0;for(size_t j=0;j<v.size();j++)z|=a[v[j]]<<j;return z;}
 C scope(const vector<int>&ix){set<int> s;for(int i:ix)s.insert(fs[i].v.begin(),fs[i].v.end());return C(s.begin(),s.end());}
 vector<int> mapping(const C&v,const C&sub){vector<int> p;for(int x:sub)p.push_back(lower_bound(v.begin(),v.end(),x)-v.begin());return p;}
 int extract(int a,const vector<int>&p){int z=0;for(size_t i=0;i<p.size();i++)z|=((a>>p[i])&1)<<i;return z;}
 // An exact relation splits iff its support equals the Cartesian product of
 // the two projected supports. Count equality suffices since inclusion holds.
 pair<Factor,Factor> project_partition(const Factor&f,int mask){Factor a,b;for(size_t i=0;i<f.v.size();i++)((mask>>i&1)?a.v:b.v).push_back(f.v[i]);a.t.assign(1u<<a.v.size(),0);b.t.assign(1u<<b.v.size(),0);auto pa=mapping(f.v,a.v),pb=mapping(f.v,b.v);for(size_t i=0;i<f.t.size();i++){tick();if(f.t[i]){a.t[extract(i,pa)]=1;b.t[extract(i,pb)]=1;}}return {move(a),move(b)};}
 int count(const Factor&f){return accumulate(f.t.begin(),f.t.end(),0);}
 vector<Factor> decompose(Factor f){guard();int k=f.v.size(),cnt=count(f);if(cnt==(int)f.t.size())return {};if(!cnt)return {{{},{0}}};if(!factorize||k<=1)return {move(f)};
  vector<int> masks;for(int i=0;i<k;i++)masks.push_back(1<<i);if(k<=7){for(int i=0;i<k;i++)for(int j=i+1;j<k;j++)if(k>2)masks.push_back((1<<i)|(1<<j));}if(k>=4)masks.push_back((1<<(k/2))-1);
  for(int mask:masks){tick();auto [a,b]=project_partition(f,mask);if((long long)count(a)*count(b)==cnt){auto aa=decompose(move(a)),bb=decompose(move(b));aa.insert(aa.end(),make_move_iterator(bb.begin()),make_move_iterator(bb.end()));return aa;}}
  return {move(f)};}
 Plan plan(int pivot,const vector<int>&ix,const C&v){guard();++attempts;Factor j{v,vector<uint8_t>(1u<<v.size(),1)};for(int i:ix){const auto& f=fs[i];auto p=mapping(v,f.v);for(size_t a=0;a<j.t.size();a++){tick();if(j.t[a])j.t[a]=f.t[extract(a,p)];}}
  int pos=lower_bound(v.begin(),v.end(),pivot)-v.begin();Factor q;q.v=v;q.v.erase(q.v.begin()+pos);q.t.resize(1u<<q.v.size());int low=(1<<pos)-1;for(size_t a=0;a<q.t.size();a++){tick();int z=(a&low)|((a&~low)<<1);q.t[a]=j.t[z]||j.t[z|(1<<pos)];}auto msg=decompose(q);long long cost=(long long)j.t.size()*ix.size();return {pivot,ix,{pivot,move(j),move(q),move(msg)},cost};}
 void emit(ofstream&o,const C&c){if(++prooflines>250000){reason="proof_budget";throw Stop{};}if((prooflines&511)==0)guard();for(int l:c)o<<l<<' ';o<<"0\n";}
 C clause(const C&v,int mask){C c;for(size_t i=0;i<v.size();i++)c.push_back(mask>>i&1?-v[i]:v[i]);return c;}
 // When factoring a projected relation, derive each shorter forbidden cube
 // from the full boundary clauses by resolution over omitted variables.
 void cube(ofstream&o,C c,const C&extra,size_t i){if(i==extra.size())return;c.push_back(extra[i]);cube(o,c,extra,i+1);c.back()=-extra[i];cube(o,c,extra,i+1);c.pop_back();emit(o,c);}
 void proof(string out){ofstream o(out);if(!o)throw runtime_error("proof open");for(auto&s:trail){auto&q=s.projected;for(size_t a=0;a<q.t.size();a++)if(!q.t[a])emit(o,clause(q.v,a));for(auto&f:s.messages){if(f.v==q.v)continue;C extra;set_difference(q.v.begin(),q.v.end(),f.v.begin(),f.v.end(),back_inserter(extra));for(size_t a=0;a<f.t.size();a++)if(!f.t[a])cube(o,clause(f.v,a),extra,0);} }if(!o)throw runtime_error("proof write");}
 int run(string in,string out){if(!read(in))throw runtime_error("invalid DIMACS");return loaded(out);}
 int loaded(string out){for(auto&c:src){if(c.empty()){ofstream o(out);emit(o,{});return 20;}if(c.size()>14){reason="clause_scope";return 0;}Factor f;for(int l:c)f.v.push_back(abs(l));sort(f.v.begin(),f.v.end());int mask=0;for(int l:c)if(l<0)mask|=1<<(lower_bound(f.v.begin(),f.v.end(),abs(l))-f.v.begin());f.t.assign(1u<<f.v.size(),1);f.t[mask]=0;fs.push_back(move(f));}
  initialized=true;while(!fs.empty()){guard();vector<vector<int>> occ(n+1);long long active=0;for(size_t i=0;i<fs.size();i++){active+=fs[i].t.size();for(int v:fs[i].v)occ[v].push_back(i);}peak=max(peak,active);if(active>4000000){reason="active_budget";return 0;}vector<tuple<long long,int,int,C>> candidates;for(int v=1;v<=n;v++)if(!occ[v].empty()){tick();C s=scope(occ[v]);if(s.size()<=14)candidates.emplace_back((1LL<<s.size())*occ[v].size(),s.size(),v,move(s));}if(candidates.empty()){reason="separator_width";return 0;}sort(candidates.begin(),candidates.end());optional<Plan> best;tuple<int,long long,long long> key{INT_MAX,LLONG_MAX,LLONG_MAX};for(size_t i=0;i<min<size_t>(factorize?3:1,candidates.size());i++){auto&[cost,k,v,s]=candidates[i];if(i&&cost>get<0>(candidates[0])*3)break;Plan p=plan(v,occ[v],s);int w=0;long long size=0;for(auto&f:p.step.messages){w=max(w,(int)f.v.size());size+=f.t.size();}auto score=make_tuple(w,size,p.cost);if(!best||score<key){best=move(p);key=score;}if(w==0)break;}
   auto p=move(*best);auto&s=p.step;width=max(width,(int)s.joined.v.size()-1);if(s.messages.size()>1)splits+=s.messages.size()-1;set<int> used;for(auto&f:s.messages)used.insert(f.v.begin(),f.v.end());removed+=s.projected.v.size()-used.size();bool conflict=s.messages.size()==1&&s.messages[0].v.empty()&&s.messages[0].t[0]==0;vector<Factor> next;size_t j=0;for(size_t i=0;i<fs.size();i++){if(j<p.ix.size()&&(int)i==p.ix[j])j++;else next.push_back(move(fs[i]));}for(auto&f:s.messages)if(!conflict)next.push_back(f);fs=move(next);stored+=s.joined.t.size()+s.projected.t.size();for(auto&f:s.messages)stored+=f.t.size();trail.push_back(move(s));++eliminated;if(conflict){fs={{{},{0}}};proof(out);return 20;}
  }
  vector<int>a(n+1,0);for(auto it=trail.rbegin();it!=trail.rend();it++){guard();a[it->pivot]=0;if(!it->joined.t[index(it->joined.v,a)]){a[it->pivot]=1;if(!it->joined.t[index(it->joined.v,a)])throw runtime_error("reconstruction invariant");}}for(auto&c:src){bool ok=false;for(int l:c)if(a[abs(l)]==(l>0))ok=true;if(!ok)throw runtime_error("source model invariant");}ofstream o(out);o<<"v ";for(int v=1;v<=n;v++)o<<(a[v]?v:-v)<<' ';o<<"0\n";if(!o)throw runtime_error("model write");return 10;
 }
};
