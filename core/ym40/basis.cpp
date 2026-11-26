// YM40: gauge-invariant spatial scalar basis; all operators live on one time slice.
#define YM38_LINK_LIBRARY
#include "../ym38/wave.cpp"
constexpr int K=8, D=6, B=16;
using Vec=array<double,K>;
vector<Vec> amplitudes(const Lattice& g) {
 int L=g.L, space=L*L*L;
 vector<Vec> x(g.T);
 Links v=g.U,next=v;
 auto add=[&](int round){
  for(int i=0;i<g.V;i++)for(int m=0;m<3;m++)for(int n=m+1;n<3;n++){
   double f=g.face(v,i,m,n); auto &a=x[i/space];
   if(round==0)a[0]+=f;
   if(round==1)a[1]+=f;
   if(round==3){
    a[2]+=f; a[3]+=f*f;
    int im=g.up[i][m],in=g.up[i][n],imm=g.up[im][m],inn=g.up[in][n];
    Q m2=v[i][m]*v[im][m],n2=v[i][n]*v[in][n];
    Q top=v[inn][m]*v[g.up[inn][m]][m],right=v[imm][n]*v[g.up[imm][n]][n];
    a[4]+=(m2*right*adj(top)*adj(n2)).a;
    a[5]+=(m2*v[imm][n]*adj(v[in][m]*v[g.up[in][m]][m])*adj(v[i][n])).a;
    a[6]+=f*g.face(v,im,m,n);
   }
   if(round==6)a[7]+=f;
  }
 };
 add(0);
 for(int round=1;round<=6;round++){
  for(int i=0;i<g.V;i++)for(int m=0;m<3;m++)
   next[i][m]=unit(.5*v[i][m]+.125*g.staples(v,i,m,3));
  v.swap(next);
  if(round==1||round==3||round==6)add(round);
 }
 for(auto& a:x)for(double &z:a)z/=sqrt(3.*space);
 return x;
}
int main(int argc,char**argv){
 if(argc!=8)return 2;
 int l=stoi(argv[1]),t=stoi(argv[2]),seed=stoi(argv[3]),warm=stoi(argv[4]),samples=stoi(argv[5]);
 string start=argv[6]; double beta=stod(argv[7]);
 if(l<4||t<2*D||warm<0||samples<0||samples%B||beta<=0)return 2;
 Lattice g(l,t,seed);
 if(start=="hot"||start=="check")for(auto& u:g.U)for(auto& q:u)q=g.draw(0);
 else if(start!="cold")return 2;
 if(start=="check"){
  auto x=amplitudes(g);vector<Q> h(g.V);for(auto& q:h)q=g.draw(0);
  for(int i=0;i<g.V;i++)for(int m=0;m<4;m++)g.U[i][m]=h[i]*g.U[i][m]*adj(h[g.up[i][m]]);
  auto y=amplitudes(g);
  for(int j=0;j<t;j++)for(int k=0;k<K;k++)if(abs(x[j][k]-y[j][k])>1e-8)throw runtime_error("gauge invariance");
  cout<<"YM40 gauge test PASS\n";return 0;
 }
 vector<double> block(1+K+D*K*K);cout<<setprecision(16);
 for(int s=0;s<warm+samples;s++){
  g.sweep(beta);if(s<warm)continue;
  auto x=amplitudes(g);
  block[0]+=g.action_sum()/(6.*g.V*B);
  for(int j=0;j<t;j++)for(int k=0;k<K;k++)block[1+k]+=x[j][k]/(t*B);
  for(int d=0;d<D;d++)for(int j=0;j<t;j++)for(int a=0;a<K;a++)for(int b=0;b<K;b++)
   block[1+K+d*K*K+a*K+b]+=(x[j][a]*x[(j+d)%t][b]+x[j][b]*x[(j+d)%t][a])/(2.*t*B);
  if((s-warm+1)%B==0){for(size_t i=0;i<block.size();i++)cout<<(i?",":"")<<block[i];cout<<'\n';fill(block.begin(),block.end(),0);}
 }
}
