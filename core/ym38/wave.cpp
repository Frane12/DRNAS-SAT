// Pure SU(2) isotropic Wilson heatbath and a spatially smeared scalar correlator.
#include <algorithm>
#include <array>
#include <cmath>
#include <complex>
#include <iomanip>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
using namespace std;
constexpr double pi=3.14159265358979323846;
struct Q { double a=1,b=0,c=0,d=0; };
Q operator+(Q x,Q y){return {x.a+y.a,x.b+y.b,x.c+y.c,x.d+y.d};}
Q operator*(double s,Q x){return {s*x.a,s*x.b,s*x.c,s*x.d};}
Q operator*(Q x,Q y){return {x.a*y.a-x.b*y.b-x.c*y.c-x.d*y.d,
 x.a*y.b+x.b*y.a+x.c*y.d-x.d*y.c,x.a*y.c+x.c*y.a+x.d*y.b-x.b*y.d,
 x.a*y.d+x.d*y.a+x.b*y.c-x.c*y.b};}
Q adj(Q x){return {x.a,-x.b,-x.c,-x.d};}
double length(Q x){return sqrt(x.a*x.a+x.b*x.b+x.c*x.c+x.d*x.d);}
Q unit(Q x){return (1/length(x))*x;}
using Links=vector<array<Q,4>>;
struct Lattice{
 int L,T,V;
 Links U;
 vector<array<int,4>> up,dn;
 mt19937_64 rng;
 uniform_real_distribution<double> uniform{0,1};
 Lattice(int l,int t,int seed):L(l),T(t),V(l*l*l*t),U(V),up(V),dn(V),rng(seed){
  int stride=1;
  for(int m=0;m<4;++m){
   int size=m==3?T:L;
   for(int i=0;i<V;++i){
    int x=(i/stride)%size;
    up[i][m]=i+stride*(x+1==size?1-size:1);
    dn[i][m]=i+stride*(x==0?size-1:-1);
   }
   stride*=size;
  }
 }
 Q draw(double k){
  // Haar scalar density sqrt(1-z^2), tilted by exp(k*z).
  double z,r;
  do{
   const double x=uniform(rng);
   z=k>1e-9?1+log1p(x*expm1(-2*k))/k:2*x-1;
   r=sqrt(max(0.,1-z*z));
  }while(uniform(rng)>r);
  double h=2*uniform(rng)-1,p=2*pi*uniform(rng),rad=r*sqrt(1-h*h);
  return {z,rad*cos(p),rad*sin(p),r*h};
 }
 Q staples(const Links& v,int i,int m,int dims)const{
  Q s{0,0,0,0};
  for(int n=0;n<dims;++n)if(n!=m){
   int j=dn[i][n];
   s=s+v[i][n]*v[up[i][n]][m]*adj(v[up[i][m]][n])
      +adj(v[j][n])*v[j][m]*v[up[j][m]][n];
  }
  return s;
 }
 void sweep(double beta){
  for(int i=0;i<V;++i)for(int m=0;m<4;++m){
   Q s=staples(U,i,m,4);double n=length(s);
   U[i][m]=n>0?draw(beta*n)*((1/n)*s):draw(0);
  }
 }
 double face(const Links& v,int i,int m,int n)const{
  return (v[i][m]*v[up[i][m]][n]*adj(v[up[i][n]][m])*adj(v[i][n])).a;
 }
 double action_sum()const{
  double s=0;
  for(int i=0;i<V;++i)for(int m=0;m<4;++m)for(int n=m+1;n<4;++n)s+=face(U,i,m,n);
  return s;
 }
 vector<double> observe()const{
  Links v=U,next=U;
  for(int round=0;round<3;++round){
   for(int i=0;i<V;++i)for(int m=0;m<3;++m)
    next[i][m]=unit(0.5*v[i][m]+0.125*staples(v,i,m,3));
   v.swap(next);
  }
  vector<array<complex<double>,3>> mode(T);
  vector<complex<double>> phase(2*L);
  for(int i=0;i<2*L;++i)phase[i]=polar(1.,pi*i/L);
  int space=L*L*L;
  for(int i=0;i<V;++i){
   array<int,3> pos{i%L,(i/L)%L,(i/(L*L))%L};
   for(int m=0;m<3;++m)for(int n=m+1;n<3;++n){
    double f=face(v,i,m,n);
    for(int axis=0;axis<3;++axis)
     mode[i/space][axis]+=f*phase[2*pos[axis]+(axis==m||axis==n)];
   }
  }
  vector<double> out{action_sum()/(6*V)};
  for(int d=0;d<=5;++d){
   double sum=0;
   for(int t=0;t<T;++t)for(int axis=0;axis<3;++axis)
    sum+=real(conj(mode[t][axis])*mode[(t+d)%T][axis]);
   out.push_back(sum/(3*T*space));
  }
  return out;
 }
 void checks(){
  for(auto& links:U)for(auto& q:links)q=draw(0);
  double old=action_sum();Q q=U[0][0],s=staples(U,0,0,4);
  U[0][0]=draw(0);
  double predicted=(U[0][0]*adj(s)).a-(q*adj(s)).a;
  if(abs(action_sum()-old-predicted)>1e-8)throw runtime_error("staple action mismatch");
  auto before=observe(); vector<Q> g(V);
  for(auto& a:g)a=draw(0);
  for(int i=0;i<V;++i)for(int m=0;m<4;++m)U[i][m]=g[i]*U[i][m]*adj(g[up[i][m]]);
  auto after=observe();
  for(size_t i=0;i<after.size();++i)
   if(abs(after[i]-before[i])>1e-9)throw runtime_error("gauge invariance mismatch");
 }
};
#ifndef YM38_LINK_LIBRARY
int main(int argc,char** argv){
 if(argc!=6) return 2;
 int l=stoi(argv[1]),seed=stoi(argv[2]),warm=stoi(argv[3]),samples=stoi(argv[4]);
 string start=argv[5];if(l<3||warm<0||samples<0)return 2;
 Lattice grid(l,16,seed);
 if(start=="check"){grid.checks();cout<<"checks passed\n";return 0;}
 if(start=="hot"){for(auto& a:grid.U)for(auto& q:a)q=grid.draw(0);}
 else if(start!="cold")return 2;
 cout<<"sweep,plaquette,c0,c1,c2,c3,c4,c5\n"<<setprecision(12);
 for(int i=0;i<warm+samples;++i){
  grid.sweep(2.35);
  if(i>=warm){
   auto row=grid.observe();cout<<i+1;
   for(double x:row)cout<<','<<x;
   cout<<'\n';
  }
 }
}
#endif
