#pragma once
// Bounded community decomposition and conditional local SAT construction.
// Partition is a scheduling hint only. The complete original model is checked.
namespace core_communities {
using V=std::vector<int>;using F=std::vector<V>;using Time=toolbox::Time;
struct Result{
    toolbox::Model model;int groups=0,cut=0,local_solved=0,passes=0,best=-1,max_group=0;
};
inline Result solve(const toolbox::Input& f,Time stop){
    Result r;auto live=[&](){return toolbox::Clock::now()<stop;};
    if(f.n<64||f.n>200000||f.cs.size()>1000000||!live())return r;
    // Build a sparse primal graph. Long clauses are retained for verification
    // and conditional solving, not expanded into quadratic graph edges.
    using Edge=std::pair<int,int>;
    std::vector<V> adj(f.n+1);
    size_t edges=0;
    for(size_t i=0;i<f.cs.size();++i){
        if((i&255)==0&&!live())return r;
        const auto& c=f.cs[i];if(c.empty())return r;if(c.size()>8)continue;
        for(size_t j=0;j<c.size();++j)for(size_t k=j+1;k<c.size();++k){
            int a=std::abs(c[j]),b=std::abs(c[k]);if(a==b)continue;
            adj[a].push_back(b);adj[b].push_back(a);edges+=2;
            if(edges>12000000)return r;
        }
    }
    std::vector<std::vector<Edge>> graph(f.n+1);
    V label(f.n+1),size(f.n+1,1),order(f.n),vol(f.n+1);
    std::iota(label.begin(),label.end(),0);std::iota(order.begin(),order.end(),1);
    long long total=0;
    for(int v=1;v<=f.n;++v){
        if((v&255)==0&&!live())return r;
        auto& a=adj[v];std::sort(a.begin(),a.end());
        for(size_t i=0;i<a.size();){size_t j=i+1;while(j<a.size()&&a[j]==a[i])++j;
            // Cap multiplicity so repeated XOR encodings do not dominate.
            int w=std::min(4,int(j-i));graph[v].push_back({a[i],w});vol[v]+=w;total+=w;i=j;
        }
        V().swap(a);
    }
    adj.clear();if(!total)return r;
    V degree=vol;
    std::mt19937 rng(261120263);
    // Local modularity moves with an explicit group-size cap.
    for(int sweep=0;sweep<10&&live();++sweep){
        std::shuffle(order.begin(),order.end(),rng);int changed=0;
        for(int v:order){
            if(!live())return r;
            int old=label[v];if(!degree[v])continue;
            std::map<int,int> weights;
            for(auto [u,w]:graph[v])weights[label[u]]+=w;
            --size[old];vol[old]-=degree[v];
            int best=old;
            auto score=[&](int g){return double(weights[g])-double(degree[v])*vol[g]/total;};
            double gain=score(old);
            for(const auto& [g,w]:weights){
                if(size[g]>=160)continue;
                double s=double(w)-double(degree[v])*vol[g]/total;
                if(s>gain+1e-9){best=g;gain=s;}
            }
            ++size[best];vol[best]+=degree[v];label[v]=best;changed+=best!=old;
        }
        if(!changed)break;
    }
    // Merge strongly connected small clusters, without creating huge regions.
    V parent(f.n+1);std::iota(parent.begin(),parent.end(),0);
    auto root=[&](int v){while(parent[v]!=v){parent[v]=parent[parent[v]];v=parent[v];}return v;};
    for(int pass=0;pass<6&&live();++pass){
        std::map<Edge,int> links;
        for(int v=1;v<=f.n;++v){
            if((v&255)==0&&!live())return r;
            for(auto [u,w]:graph[v])if(v<u){
                int a=root(label[v]),b=root(label[u]);if(a==b)continue;if(a>b)std::swap(a,b);links[{a,b}]+=w;
            }
        }
        V best(f.n+1,-1);std::vector<double> strength(f.n+1,0);
        for(auto [ab,w]:links){
            auto [a,b]=ab;
            if(size[a]+size[b]>160)continue;
            double s=double(w)/std::max(1,std::min(vol[a],vol[b]));
            if(s>strength[a]){strength[a]=s;best[a]=b;}
            if(s>strength[b]){strength[b]=s;best[b]=a;}
        }
        int merged=0;
        for(int a=1;a<=f.n;++a)if(best[a]>a&&best[best[a]]==a&&strength[a]>=.035){
            int b=best[a];parent[b]=a;size[a]+=size[b];vol[a]+=vol[b];++merged;
        }
        if(!merged)break;
    }
    std::map<int,int> ids;std::vector<V> vars;
    V group(f.n+1),local(f.n+1);
    for(int v=1;v<=f.n;++v){
        int g=root(label[v]);auto [it,new_group]=ids.emplace(g,int(vars.size()));
        if(new_group)vars.push_back({});
        group[v]=it->second;local[v]=int(vars[it->second].size())+1;vars[it->second].push_back(v);
    }
    r.groups=int(vars.size());
    for(auto& vs:vars)r.max_group=std::max(r.max_group,int(vs.size()));
    if(r.groups<2||r.max_group>160)return r;
    std::vector<V> incident(vars.size()),internal(vars.size());
    for(int i=0;i<int(f.cs.size());++i){
        if((i&255)==0&&!live())return r;
        V gs;for(int l:f.cs[i])gs.push_back(group[std::abs(l)]);
        std::sort(gs.begin(),gs.end());gs.erase(std::unique(gs.begin(),gs.end()),gs.end());
        if(gs.size()==1)internal[gs[0]].push_back(i);else ++r.cut;
        for(int g:gs)incident[g].push_back(i);
    }
    // A weak-cut region policy should not waste budget on dense random CNFs.
    if(r.cut>int(f.cs.size()/8)||r.max_group<8)return r;
    graph.clear();
    toolbox::Model m(f.n+1,-1);
    V sequence(vars.size());std::iota(sequence.begin(),sequence.end(),0);
    std::stable_sort(sequence.begin(),sequence.end(),[&](int a,int b){return internal[a].size()>internal[b].size();});
    auto build=[&](int g,bool only_internal){
        F out;
        for(int i:(only_internal?internal[g]:incident[g])){
            V c;bool skip=false;
            for(int l:f.cs[i]){
                int v=std::abs(l);
                if(group[v]==g)c.push_back(l>0?local[v]:-local[v]);
                else if(m[v]<0||toolbox::value(m,l)==1){skip=true;break;}
            }
            if(!skip)out.push_back(fusion_kernel::norm(std::move(c)));
        }
        return out;
    };
    auto solve_region=[&](int g,const F& cs,Time end)->bool{
        int n=int(vars[g].size());if(toolbox::Clock::now()>=end)return false;
        toolbox::Input local_input{n,cs};
        auto a=core_affine::solve(local_input,toolbox::Clock::now()+(end-toolbox::Clock::now())/3,true);
        if(!a.model.empty()&&toolbox::satisfied(cs,a.model)){
            for(int j=0;j<n;++j)m[vars[g][j]]=a.model[j+1];return true;
        }
        if(toolbox::Clock::now()>=end)return false;
        auto b=fusion_kernel::fusion_solve(fusion_kernel::Input{n,int(cs.size()),cs},end,false,0);
        if(b.status!=1||b.model.size()!=size_t(n+1)||!fusion_kernel::verify(cs,b.model))return false;
        for(int j=0;j<n;++j)m[vars[g][j]]=b.model[j+1]>0;return true;
    };
    for(size_t i=0;i<sequence.size()&&live();++i){
        int g=sequence[i];auto now=toolbox::Clock::now();
        auto end=now+(stop-now)*3/(4*int(sequence.size()-i));
        auto cs=build(g,false);
        if(solve_region(g,cs,now+(end-now)*3/4)||solve_region(g,build(g,true),end))++r.local_solved;
        else for(int v:vars[g])if(m[v]<0)m[v]=rng()&1u;
    }
    for(int v=1;v<=f.n;++v)if(m[v]<0)m[v]=0;
    for(int pass=0;pass<4&&live();++pass){
        ++r.passes;V bad_groups;std::vector<char> bad(vars.size(),0);int unsatisfied=0;
        for(const auto& c:f.cs){
            bool sat=false;for(int l:c)if(toolbox::value(m,l)==1){sat=true;break;}
            if(sat)continue;++unsatisfied;
            for(int l:c){int g=group[std::abs(l)];if(!bad[g]){bad[g]=1;bad_groups.push_back(g);}}
        }
        if(r.best<0||unsatisfied<r.best)r.best=unsatisfied;
        if(!unsatisfied){r.model=std::move(m);return r;}
        std::shuffle(bad_groups.begin(),bad_groups.end(),rng);
        for(size_t i=0;i<bad_groups.size()&&live();++i){
            int g=bad_groups[i];auto now=toolbox::Clock::now();
            auto end=now+(stop-now)/int(bad_groups.size()-i);
            // A successful conditional solve preserves all currently satisfied
            // incident clauses. Failed attempts never modify the incumbent.
            solve_region(g,build(g,false),end);
        }
    }
    if(toolbox::satisfied(f.cs,m)){r.best=0;r.model=std::move(m);}
    return r;
}
} // namespace core_communities
