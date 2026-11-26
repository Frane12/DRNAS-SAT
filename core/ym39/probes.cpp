// Reuse the exact YM38 link convention, generator, Wilson update and geometry.
#define YM38_LINK_LIBRARY
#include "../ym38/wave.cpp"

constexpr int channels=7, lags=8;
using Direction=array<complex<double>,3>;
using Amplitudes=array<Direction,channels>;
vector<double> observe_probes(const Lattice& grid, const string& mode="auto"){
 const int l=grid.L, tmax=grid.T, space=l*l*l;
 Links v=grid.U, next=v;
 for(int round=0;round<3;++round){
  for(int i=0;i<grid.V;++i)for(int m=0;m<3;++m)
   next[i][m]=unit(0.5*v[i][m]+0.125*grid.staples(v,i,m,3));
  v.swap(next);
 }
 Links twice=v;
 for(int i=0;i<grid.V;++i)for(int m=0;m<3;++m)
  twice[i][m]=v[i][m]*v[grid.up[i][m]][m];
 vector<complex<double>> phase(2*l+2);
 for(int j=0;j<int(phase.size());++j)phase[j]=polar(1.,pi*j/l);
 vector<Amplitudes> times(tmax);
 for(int i=0;i<grid.V;++i){
  auto& a=times[i/space];const array<int,3> pos{i%l,i/l%l,i/(l*l)%l};
  for(int normal=0;normal<3;++normal){
   int m=(normal+1)%3,n=(normal+2)%3;
   int m2=grid.up[grid.up[i][m]][m],n2=grid.up[grid.up[i][n]][n];
   double f=grid.face(v,i,m,n), big=(twice[i][m]*twice[m2][n]*adj(twice[n2][m])*adj(twice[i][n])).a;
   for(int ax=0;ax<3;++ax){
    int inside=ax!=normal;
    auto moving=phase[2*pos[ax]+inside]*f;
    a[0][ax]+=moving;
    a[1][ax]+=phase[2*pos[ax]+2*inside]*big;
    // Subtract a fixed offset, then remove the remaining ensemble mean in analysis.
    a[2][ax]+=f-0.9;
    a[3][ax]+=big-0.7;
    int sign=(normal==(ax+1)%3)-(normal==(ax+2)%3);
    a[4][ax]+=double(sign)*moving;
    a[5][ax]+=sign*f;
   }
   if(!pos[normal]){
    Q winding;int j=i;
    for(int k=0;k<l;++k){winding=winding*v[j][normal];j=grid.up[j][normal];}
    a[6][normal]+=winding.a;
   }
  }
 }
 vector<double> cross;
 if(mode!="auto"){
  // Symmetric off-diagonal correlator of the moving small and large squares.
  for(int d=0;d<lags;++d){
   double sum=0;
   for(int t=0;t<tmax;++t)for(int ax=0;ax<3;++ax){
    auto& a=times[t];auto& b=times[(t+d)%tmax];
    sum+=real(conj(a[0][ax])*b[1][ax]+conj(a[1][ax])*b[0][ax]);
   }
   cross.push_back(sum/(6*tmax*space));
  }
  if(mode=="cross")return cross;
 }
 vector<double> out{grid.action_sum()/(6*grid.V)};
 for(int ch=0;ch<channels;++ch){
  double scale=(ch==6)?l*l:space, mean=0;
  for(auto& a:times)for(auto z:a[ch])mean+=z.real();
  out.push_back(mean/(3*tmax*sqrt(scale)));
  for(int d=0;d<lags;++d){
   double sum=0;
   for(int t=0;t<tmax;++t)for(int ax=0;ax<3;++ax)
    sum+=real(conj(times[t][ch][ax])*times[(t+d)%tmax][ch][ax]);
   out.push_back(sum/(3*tmax*scale));
  }
 }
 out.insert(out.end(),cross.begin(),cross.end());
 return out;
}
int main(int argc,char** argv){
 if(argc!=7 && argc!=8)return 2;
 string mode=argc==8?argv[7]:"auto";
 if(mode!="auto" && mode!="cross" && mode!="both")return 2;
 int l=stoi(argv[1]),seed=stoi(argv[2]),warm=stoi(argv[3]),samples=stoi(argv[4]);
 string start=argv[5];double beta=stod(argv[6]);
 if(l<4 || warm<0 || samples<0 || samples%16 || beta<=0)return 2;
 Lattice grid(l,24,seed);
 if(start=="hot"||start=="check"){for(auto& v:grid.U)for(auto& q:v)q=grid.draw(0);}
 else if(start!="cold")return 2;
 if(start=="check"){
  auto before=observe_probes(grid,mode);vector<Q> g(grid.V);
  for(auto& a:g)a=grid.draw(0);
  for(int i=0;i<grid.V;++i)for(int m=0;m<4;++m)
   grid.U[i][m]=g[i]*grid.U[i][m]*adj(g[grid.up[i][m]]);
  auto after=observe_probes(grid,mode);
  for(size_t i=0;i<after.size();++i)if(abs(after[i]-before[i])>1e-8)throw runtime_error("gauge check");
  // Flip one periodic sheet per spatial direction. Each contractible loop
  // crosses evenly, whereas every measured once-winding loop changes sign.
  auto winding_before=observe_probes(grid);
  for(int i=0;i<grid.V;++i){
   int pos=i;
   for(int m=0;m<3;++m){
    if(pos%l==0)grid.U[i][m]=(-1.)*grid.U[i][m];
    pos/=l;
   }
  }
  auto winding_after=observe_probes(grid);
  int mean_winding=1+6*(lags+1);
  if(abs(winding_before[mean_winding])<1e-10)throw runtime_error("degenerate winding control");
  for(size_t j=0;j<winding_before.size();++j){
   double expected=int(j)==mean_winding?-winding_before[j]:winding_before[j];
   if(abs(winding_after[j]-expected)>1e-8)throw runtime_error("center selection rule");
  }
  cout<<"YM39 gauge-invariance controls passed\n";return 0;
 }
 vector<double> block(mode=="cross"?lags:1+channels*(lags+1)+(mode=="both"?lags:0));
 cout<<setprecision(15);
 for(int i=0;i<warm+samples;++i){
  grid.sweep(beta);
  if(i<warm)continue;
  auto row=observe_probes(grid,mode);
  for(size_t j=0;j<row.size();++j)block[j]+=row[j]/16;
  if((i-warm+1)%16==0){
   for(size_t j=0;j<row.size();++j)cout<<(j?",":"")<<block[j];
   cout<<'\n';fill(block.begin(),block.end(),0.);
  }
 }
}
