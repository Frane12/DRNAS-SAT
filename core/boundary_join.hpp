#pragma once
// Local witness banks plus conditional boundary join. SAT-only: sampled tables
// are not complete projections and failure of a join is never a proof.
namespace core_boundary {
using V=std::vector<int>;using F=std::vector<V>;using M=toolbox::Model;using Time=toolbox::Time;
struct Result{
    M model;int banks=0,models=0,alternatives=0,passes=0,best=-1,joined=0,merges=0,table_attempts=0;
};
template<class Solver>
Result solve(const toolbox::Input& f,const std::vector<V>& vars,const V& group,
             const V& local,const std::vector<V>& internal,const std::vector<V>& incident,
             Time stop,Solver solve_local){
    Result r;auto now=[](){return toolbox::Clock::now();};auto live=[&](){return now()<stop;};
    const int k=int(vars.size());if(k<2||k>20000||!live())return r;
    std::vector<F> inside(k);
    std::vector<V> boundary(k),cross(k);V cuts;
    for(int g=0;g<k;++g){
        if(!live())return r;
        for(int i:internal[g]){
            V c;for(int l:f.cs[i])c.push_back(l>0?local[std::abs(l)]:-local[std::abs(l)]);
            inside[g].push_back(std::move(c));
        }
    }
    for(int i=0;i<int(f.cs.size());++i){
        if((i&255)==0&&!live())return r;
        const auto& c=f.cs[i];if(c.empty())return r;
        int g=group[std::abs(c[0])];bool cut=false;
        for(int l:c)if(group[std::abs(l)]!=g){cut=true;break;}
        if(!cut)continue;
        cuts.push_back(i);
        for(int l:c){int v=std::abs(l),h=group[v];boundary[h].push_back(local[v]);cross[h].push_back(i);}
    }
    for(int g=0;g<k;++g)for(V* a:{&boundary[g],&cross[g]}){
        std::sort(a->begin(),a->end());a->erase(std::unique(a->begin(),a->end()),a->end());
    }
    std::vector<std::vector<M>> bank(k);std::vector<std::set<V>> signatures(k);
    M m(f.n+1,0);std::mt19937 rng(261120265);
    V selected(k,-1);
    auto apply=[&](int g,int p){selected[g]=p;for(size_t j=0;j<vars[g].size();++j)m[vars[g][j]]=bank[g][p][j+1];};
    auto store=[&](int g,M a)->int{
        if(a.size()!=vars[g].size()+1||!toolbox::satisfied(inside[g],a))return -1;
        for(size_t j=1;j<a.size();++j)if(a[j]!=0&&a[j]!=1)return -1;
        V sig;for(int v:boundary[g])sig.push_back(a[v]);
        if(signatures[g].count(sig)){
            for(int p=0;p<int(bank[g].size());++p){
                bool same=true;for(int v:boundary[g])if(bank[g][p][v]!=a[v]){same=false;break;}
                if(same)return p;
            }return -1;
        }
        if(bank[g].size()>=12)return -1;
        signatures[g].insert(std::move(sig));if(bank[g].empty())++r.banks;else ++r.alternatives;
        bank[g].push_back(std::move(a));++r.models;return int(bank[g].size()-1);
    };
    auto attempt=[&](int g,const F& extra,Time end)->int{
        if(now()>=end)return -1;
        F cs=inside[g];cs.insert(cs.end(),extra.begin(),extra.end());
        M a=solve_local(int(vars[g].size()),cs,end);
        if(a.empty()||!toolbox::satisfied(cs,a))return -1;
        return store(g,std::move(a));
    };
    V order(k);std::iota(order.begin(),order.end(),0);
    std::stable_sort(order.begin(),order.end(),[&](int a,int b){return inside[a].size()>inside[b].size();});
    Time initial=now()+(stop-now())*2/3;
    for(int j=0;j<k&&now()<initial;++j){
        int g=order[j];auto t=now();Time end=t+(initial-t)/(k-j);
        int p=attempt(g,{},end);if(p>=0)apply(g,p);
        else for(int v:vars[g])m[v]=rng()&1u;
    }
    auto bad_clause=[&](int i){for(int l:f.cs[i])if(toolbox::value(m,l)==1)return false;return true;};
    auto score=[&](int g){int bad=0;for(int i:cross[g])bad+=bad_clause(i);return bad;};
    auto conditional=[&](int g){
        F extra;for(int i:cross[g]){
            V c;bool skip=false;for(int l:f.cs[i]){
                int v=std::abs(l);
                if(group[v]==g)c.push_back(l>0?local[v]:-local[v]);
                else if(toolbox::value(m,l)==1){skip=true;break;}
            }
            if(!skip)extra.push_back(std::move(c));
        }return extra;
    };
    auto novel_constraint=[&](int g){
        F extra;
        // Exclude only already sampled boundary signatures, not source models.
        if(boundary[g].empty())return extra;
        for(const auto& a:bank[g]){
            V c;for(int v:boundary[g])c.push_back(a[v]?-v:v);extra.push_back(std::move(c));
        }return extra;
    };
    auto check=[&](){
        int bad=0;for(const auto& c:f.cs){bool sat=false;for(int l:c)if(toolbox::value(m,l)==1){sat=true;break;}bad+=!sat;}
        if(r.best<0||bad<r.best)r.best=bad;
        if(!bad){r.model=m;r.joined=k;return true;}return false;
    };
    if(check())return r;
    // A table-join CNF is equisatisfiable with the *sampled* banks only.
    // Selectors imply all boundary bits of their witnessed local assignment.
    auto table_join=[&](Time end){
        if(r.banks!=k||k>400||now()>=end)return false;
        V index(f.n+1,0);int n=0;
        for(int g=0;g<k;++g)for(int v:boundary[g])index[vars[g][v-1]]=++n;
        F cs;std::vector<V> selectors(k);
        for(int g=0;g<k;++g){
            if(now()>=end)return false;
            for(const auto& a:bank[g]){
                int q=++n;selectors[g].push_back(q);
                for(int v:boundary[g]){
                    int b=index[vars[g][v-1]];cs.push_back({-q,a[v]?b:-b});
                }
            }
            cs.push_back(selectors[g]);if(n>5000||cs.size()>60000)return false;
        }
        for(int i:cuts){
            V c;for(int l:f.cs[i]){int v=index[std::abs(l)];if(!v)return false;c.push_back(l>0?v:-v);}cs.push_back(std::move(c));
            if(cs.size()>60000||now()>=end)return false;
        }
        ++r.table_attempts;M a=solve_local(n,cs,end);
        if(a.size()!=size_t(n+1)||!toolbox::satisfied(cs,a))return false;
        for(int g=0;g<k;++g){
            int p=-1;for(int j=0;j<int(selectors[g].size());++j)if(a[selectors[g][j]]==1){p=j;break;}
            if(p<0)return false;apply(g,p);
        }
        return check();
    };
    auto merge_pair=[&](int g,int h,Time end){
        if(g==h||vars[g].size()+vars[h].size()>320||now()>=end)return false;
        V ids=incident[g];ids.insert(ids.end(),incident[h].begin(),incident[h].end());
        std::sort(ids.begin(),ids.end());ids.erase(std::unique(ids.begin(),ids.end()),ids.end());
        int ng=int(vars[g].size()),nh=int(vars[h].size());F cs;
        for(int i:ids){
            if(now()>=end)return false;
            V c;bool skip=false;
            for(int l:f.cs[i]){
                int v=std::abs(l),z=group[v];
                if(z==g||z==h){int q=local[v]+(z==h?ng:0);c.push_back(l>0?q:-q);}
                else if(toolbox::value(m,l)==1){skip=true;break;}
            }
            if(!skip)cs.push_back(std::move(c));
        }
        M a=solve_local(ng+nh,cs,end);
        if(a.size()!=size_t(ng+nh+1)||!toolbox::satisfied(cs,a))return false;
        M x(ng+1,0),y(nh+1,0);
        for(int v=1;v<=ng;++v)x[v]=a[v];
        for(int v=1;v<=nh;++v)y[v]=a[ng+v];
        int px=store(g,std::move(x)),py=store(h,std::move(y));
        if(px<0||py<0)return false;apply(g,px);apply(h,py);++r.merges;return true;
    };
    for(int pass=0;pass<8&&live();++pass){
        ++r.passes;V active;std::vector<char> seen(k,0);
        auto add=[&](int g){if(!seen[g]){seen[g]=1;active.push_back(g);}};
        for(int g=0;g<k;++g)if(bank[g].empty())add(g);
        for(int i:cuts)if(bad_clause(i))for(int l:f.cs[i])add(group[std::abs(l)]);
        if(active.empty())break;
        std::shuffle(active.begin(),active.end(),rng);
        for(size_t j=0;j<active.size()&&live();++j){
            int g=active[j];auto t=now();Time end=t+(stop-t)/int(active.size()-j+1);
            if(bank[g].empty()){
                int p=attempt(g,conditional(g),t+(end-t)/2);
                if(p<0)p=attempt(g,{},end);if(p>=0)apply(g,p);continue;
            }
            int old=selected[g],best=old,cost=score(g);
            for(int p=0;p<int(bank[g].size());++p){
                if(!live())return r;apply(g,p);int c=score(g);
                if(c<cost){best=p;cost=c;}
            }
            apply(g,best);if(!cost)continue;
            // First try a witness respecting all current neighboring values.
            int p=attempt(g,conditional(g),t+(end-t)/2);
            if(p>=0){apply(g,p);continue;}
            if(bank[g].size()<12&&!boundary[g].empty()){
                p=attempt(g,novel_constraint(g),end);
                if(p>=0){apply(g,p);if(score(g)>cost)apply(g,best);}
            }
        }
        if(check())return r;
        if(!live())break;
        // Try simultaneous boundary reconciliation if single-region repair stalls.
        for(int i:cuts)if(bad_clause(i)&&live()){
            V gs;for(int l:f.cs[i])gs.push_back(group[std::abs(l)]);
            std::sort(gs.begin(),gs.end());gs.erase(std::unique(gs.begin(),gs.end()),gs.end());
            if(gs.size()>=2){auto t=now();merge_pair(gs[0],gs[1],t+(stop-t)/12);break;}
        }
        if(check())return r;
        if(pass==1||pass==3){auto t=now();if(table_join(t+(stop-t)/4))return r;}
    }
    if(live())check();return r;
}
} // namespace core_boundary
