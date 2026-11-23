// DRNAS R28-MIX2 research prototype. Source-CNF-derived gates, XOR macros and GF(2) closure.
// NOT original R28, and NOT a DRAT/LRAT/VeriPB certificate. UNSAT requires independent replay.
#include <algorithm>
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
using namespace std;
struct Gate { int y; bool is_or; int a,b; };
struct Eq { int a,b,y,rhs; };
struct Row { vector<uint64_t> bits;int rhs=0; };
static bool read_cnf(const string &path,int &n,vector<vector<int>>& cls) {
  ifstream f(path); if(!f)return false;
  string line;int expected=-1;vector<int> cur;bool header=false;
  while(getline(f,line)) {
    if(line.empty()||line[0]=='c'||line[0]=='%')continue;
    istringstream s(line);string token;
    while(s>>token){
      if(token=="c")break;
      if(token=="p"){
        string kind;
        if(header||!(s>>kind>>n>>expected)||kind!="cnf"||n<1||n>60000||expected<0||expected>600000)return false;
        header=true;break;
      }
      if(!header)return false;
      char *end=nullptr;errno=0;long x=strtol(token.c_str(),&end,10);
      if(errno||!end||*end||labs(x)>n)return false;
      if(x)cur.push_back(int(x));
      else{cls.push_back(move(cur));cur.clear();if(int(cls.size())>expected)return false;}
    }
  }
  return header&&cur.empty()&&int(cls.size())==expected;
}
static uint64_t key2(int a,int b){
  uint32_t x=a>0?uint32_t(a*2):uint32_t(-a*2+1),y=b>0?uint32_t(b*2):uint32_t(-b*2+1);
  if(x>y)swap(x,y);
  return (uint64_t(x)<<32)|y;
}
static void extract_gates(const vector<vector<int>>& c,vector<Gate>& gates,vector<Eq>& xors,int &ambiguous){
  unordered_set<uint64_t> binaries;binaries.reserve(c.size()*2);
  for(const auto& cl:c)if(cl.size()==2&&abs(cl[0])!=abs(cl[1]))binaries.insert(key2(cl[0],cl[1]));
  unordered_map<int,Gate> gm;gm.reserve(c.size()/4);
  unordered_set<int> blocked;
  ambiguous=0;
  for(const auto& cl:c){
    if(cl.size()!=3||abs(cl[0])==abs(cl[1])||abs(cl[1])==abs(cl[2])||abs(cl[0])==abs(cl[2]))continue;
    int maxid=max({abs(cl[0]),abs(cl[1]),abs(cl[2])});
    for(int j=0;j<3;++j){
      int output=cl[j],a=cl[(j+1)%3],b=cl[(j+2)%3];
      if(abs(output)!=maxid)continue;
      if(!binaries.count(key2(-output,-a))||!binaries.count(key2(-output,-b)))continue;
      int y=abs(output);
      Gate g{y,output<0,output<0?a:-a,output<0?b:-b};
      if(blocked.count(y))continue;
      if(gm.count(y)){
        const Gate& old=gm.at(y);
        if(old.is_or!=g.is_or||!((old.a==g.a&&old.b==g.b)||(old.a==g.b&&old.b==g.a))){
          gm.erase(y); blocked.insert(y);ambiguous++;
        }
      }else gm.emplace(y,g);
    }
  }
  for(const auto& pair:gm)gates.push_back(pair.second);
  sort(gates.begin(),gates.end(),[](const Gate& a,const Gate& b){return a.y<b.y;});
  for(const auto& g:gates){
    if(!g.is_or||g.a<=0||g.b<=0)continue;
    auto it1=gm.find(g.a),it2=gm.find(g.b);
    if(it1==gm.end()||it2==gm.end()||it1->second.is_or||it2->second.is_or)continue;
    const Gate& u=it1->second; const Gate& v=it2->second;
    int xa=abs(u.a),xb=abs(u.b);
    if(xa==xb)continue;
    auto sign_for=[](const Gate& g,int var)->int{
      if(abs(g.a)==var)return g.a>0?1:0;
      if(abs(g.b)==var)return g.b>0?1:0;
      return -1;
    };
    int a1=sign_for(u,xa),a2=sign_for(u,xb);
    int b1=sign_for(v,xa),b2=sign_for(v,xb);
    if(b1<0||b2<0||a1==b1||a2==b2)continue;
    int rhs=(a1==a2)?1:0;
    xors.push_back({xa,xb,g.y,rhs});
  }
}
class Basis{
  int n;size_t words;
  unordered_map<int,Row> basis;
  static int low(const vector<uint64_t>& bits){
    for(size_t w=0;w<bits.size();++w)if(bits[w])return int(w*64+__builtin_ctzll(bits[w]));
    return 0;
  }
  static void flip(vector<uint64_t>& bits,int x){bits[size_t(x)>>6]^=1ULL<<(x&63);}
  pair<vector<uint64_t>,int> reduce(vector<uint64_t> mask,int rhs)const{
    for(;;){
      int p=low(mask);
      if(!p||!basis.count(p))break;
      const Row& row=basis.at(p);
      for(size_t i=0;i<words;++i)mask[i]^=row.bits[i];
      rhs^=row.rhs;
    }
    return {move(mask),rhs};
  }
public:
  bool conflict=false;
  explicit Basis(int nn):n(nn),words(size_t(nn/64+1)){basis.reserve(size_t(nn));}
  bool add(const vector<int>& vars,int rhs){
    if(conflict)return false;
    vector<uint64_t> bits(words,0);
    for(int v:vars){if(v<1||v>n)throw runtime_error("invalid equation var");flip(bits,v);}
    auto r=reduce(move(bits),rhs);
    int pivot=low(r.first);
    if(!pivot){if(r.second)conflict=true;return false;}
    basis.emplace(pivot,Row{move(r.first),r.second});return true;
  }
  int fixed(int v)const{
    vector<uint64_t> bits(words,0);flip(bits,v);
    auto r=reduce(move(bits),0);
    return low(r.first)==0?r.second:-1;
  }
  int relation(int a,int b)const{
    vector<uint64_t> bits(words,0);flip(bits,a);flip(bits,b);
    auto r=reduce(move(bits),0);
    return low(r.first)==0?r.second:-1;
  }
  int rank()const{return int(basis.size());}
};
static bool bcp(const vector<vector<int>>&cls,vector<int8_t>&truth,int&new_facts){
  bool changed=true;
  while(changed){
    changed=false;
    for(const auto&c:cls){
      bool sat=false;int unknown=0,last=0;
      for(int lit:c){
        int x=truth[abs(lit)];
        if(x==-1){unknown++;last=lit;}
        else if((x==1)==(lit>0)){sat=true;break;}
      }
      if(sat)continue;
      if(!unknown)return true;
      if(unknown==1){int v=abs(last),val=last>0?1:0;
        if(truth[v]==-1){truth[v]=int8_t(val);++new_facts;changed=true;}
        else if(truth[v]!=val)return true;
      }
    }
  }
  return false;
}
int main(int argc,char**argv){
  if(argc!=2&&!(argc==3&&string(argv[2])=="--classify-only")){
    cerr<<"Usage: r28_mixed original.cnf [--classify-only]\n";return 2;
  }
  int n=0;vector<vector<int>>cls;
  if(!read_cnf(argv[1],n,cls)){cerr<<"DRNAS_MIX2_INVALID_SOURCE\n";return 78;}
  vector<Gate> gates;vector<Eq>xors;int ambiguous=0;
  extract_gates(cls,gates,xors,ambiguous);
  cout<<"c DRNAS_MIX2_SOURCE vars="<<n<<" clauses="<<cls.size()<<" gate_definitions="<<gates.size()<<" xor_macros="<<xors.size()<<" ambiguous="<<ambiguous<<"\n";
  if(argc==3){cout<<"s UNKNOWN\n";return 0;}
  if(xors.empty()){cout<<"c DRNAS_MIX2_REASON no_certified_source_xor_macro\ns UNKNOWN\n";return 0;}
  vector<int8_t>truth(size_t(n)+1,-1);
  int unit_count=0;
  if(bcp(cls,truth,unit_count)){cout<<"c DRNAS_MIX2_REASON source_unit_propagation_conflict\ns UNSATISFIABLE\n";return 20;}
  Basis basis(n);
  for(const auto&e:xors){basis.add({e.a,e.b,e.y},e.rhs);if(basis.conflict)break;}
  if(basis.conflict){cout<<"c DRNAS_MIX2_REASON source_xor_conflict\ns UNSATISFIABLE\n";return 20;}
  for(int v=1;v<=n;++v)if(truth[v]!=-1)basis.add({v},truth[v]);
  if(basis.conflict){cout<<"c DRNAS_MIX2_REASON xor_unit_conflict\ns UNSATISFIABLE\n";return 20;}
  for(int round=0;round<12;++round){
    int added=0;
    for(const auto&g:gates){
      int a=basis.fixed(abs(g.a)),b=basis.fixed(abs(g.b));
      if(a!=-1)a^=(g.a<0);
      if(b!=-1)b^=(g.b<0);
      vector<int> terms;int rhs=0;
      if(a!=-1&&b!=-1){terms={g.y};rhs=g.is_or?(a|b):(a&b);}
      else if(a!=-1){
        if((g.is_or&&a)||(!g.is_or&&!a)){terms={g.y};rhs=a;}
        else{terms={g.y,abs(g.b)};rhs=(g.b<0);}
      }else if(b!=-1){
        if((g.is_or&&b)||(!g.is_or&&!b)){terms={g.y};rhs=b;}
        else{terms={g.y,abs(g.a)};rhs=(g.a<0);}
      }else{
        int rel=basis.relation(abs(g.a),abs(g.b));
        if(rel!=-1){
          rel^=(g.a<0)^(g.b<0);
          if(rel==0){terms={g.y,abs(g.a)};rhs=g.a<0;}
          else{terms={g.y};rhs=g.is_or?1:0;}
        }
      }
      if(!terms.empty()){
        if(basis.add(terms,rhs))added++;
        if(basis.conflict)break;
      }
    }
    if(basis.conflict){cout<<"c DRNAS_MIX2_REASON gate_affine_conflict\ns UNSATISFIABLE\n";return 20;}
    int fixed_new=0;
    for(int v=1;v<=n;++v){
      int fx=basis.fixed(v);
      if(fx==-1)continue;
      if(truth[v]==-1){truth[v]=int8_t(fx);fixed_new++;}
      else if(truth[v]!=fx){cout<<"c DRNAS_MIX2_REASON wrong_unit_in_source\ns UNSATISFIABLE\n";return 20;}
    }
    int bcp_new=0;
    if(bcp(cls,truth,bcp_new)){
      cout<<"c DRNAS_MIX2_REASON source_clause_conflict round="<<round<<" rank="<<basis.rank()
          <<" assigned="<<unit_count+fixed_new+bcp_new<<"\ns UNSATISFIABLE\n";return 20;
    }
    for(int v=1;v<=n;++v)if(truth[v]!=-1)basis.add({v},truth[v]);
    if(basis.conflict){cout<<"c DRNAS_MIX2_REASON source_unit_affine_conflict\ns UNSATISFIABLE\n";return 20;}
    cout<<"c DRNAS_MIX2_ROUND round="<<round<<" derived="<<added<<" new_fixed="<<fixed_new
        <<" new_bcp="<<bcp_new<<" rank="<<basis.rank()<<"\n";
    if(!added&&!fixed_new&&!bcp_new)break;
  }
  cout<<"c DRNAS_MIX2_REASON no_contradiction\ns UNKNOWN\n";return 0;
}
