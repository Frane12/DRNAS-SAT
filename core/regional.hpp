#pragma once
// Exact sparse bucket projection with explicit source-indexed resolution.
namespace core_regional {
using C=std::vector<int>;using F=std::vector<C>;
using Time=toolbox::Time;
struct Result{
    int status=0,eliminated=0,generated=0,blocked=0,components=0,max_boundary=0;
    size_t residual=0;toolbox::Model model;std::string proof;
};
struct Step{int a,b,v;};
struct Frame{int v;std::vector<int> parents;};
inline Result solve(const toolbox::Input& f,const std::string& hash,Time stop,bool affine=false){
    Result r;r.residual=f.cs.size();
    if(f.n>2000000||f.cs.size()>3000000||toolbox::Clock::now()>=stop)return r;
    F db=f.cs;const size_t base=db.size();
    std::vector<char> live(base,1),done(f.n+1,0);
    std::vector<std::vector<int>> occ(2*f.n);
    std::vector<int> count(2*f.n,0),generation(f.n+1,0);
    std::vector<Step> steps;std::vector<Frame> frames;
    auto finish=[&](int id){
        std::ostringstream o;o<<"drnas-regional-resolution-v1 "<<hash<<"\n";
        for(auto s:steps)o<<"r "<<s.a<<' '<<s.b<<' '<<s.v<<"\n";
        o<<"end "<<id<<"\n";r.proof=o.str();r.status=20;return r;
    };
    for(int i=0;i<int(db.size());++i){
        if((i&1023)==0&&toolbox::Clock::now()>=stop)return r;
        if(db[i].empty())return finish(i);
        for(int l:db[i]){int k=toolbox::index_of(l);occ[k].push_back(i);++count[k];}
    }
    using Key=std::tuple<long long,int,int,int>;
    std::priority_queue<Key,std::vector<Key>,std::greater<Key>> q;
    auto schedule=[&](int v){
        if(done[v])return;
        int a=count[toolbox::index_of(v)],b=count[toolbox::index_of(-v)];
        int g=++generation[v];long long cost=1LL*a*b;
        if(a+b&&a+b<=96&&cost<=64)q.push({cost,a+b,v,g});
    };
    for(int v=1;v<=f.n;++v){if((v&1023)==0&&toolbox::Clock::now()>=stop)return r;schedule(v);}
    auto parents=[&](int l){std::vector<int> out;for(int i:occ[toolbox::index_of(l)])if(live[i])out.push_back(i);return out;};
    while(!q.empty()&&toolbox::Clock::now()<stop&&steps.size()<200000&&frames.size()<500000){
        auto [cost,degree,v,g]=q.top();q.pop();(void)cost;(void)degree;
        if(done[v]||g!=generation[v])continue;
        auto pos=parents(v),neg=parents(-v);std::map<C,Step> pending;
        std::set<int> boundary;bool eligible=true;
        for(int id:pos)for(int l:db[id])if(std::abs(l)!=v){boundary.insert(std::abs(l));if(boundary.size()>32)break;}
        if(boundary.size()<=32)for(int id:neg){for(int l:db[id])if(std::abs(l)!=v){boundary.insert(std::abs(l));if(boundary.size()>32)break;}if(boundary.size()>32)break;}
        if(boundary.size()>32&&!pos.empty()&&!neg.empty()){++r.blocked;continue;}
        for(int a:pos){
            for(int b:neg){
                if(toolbox::Clock::now()>=stop){eligible=false;break;}
                C c;for(int l:db[a])if(l!=v)c.push_back(l);
                for(int l:db[b])if(l!=-v)c.push_back(l);
                if(!toolbox::normalize(c))continue;
                if(c.empty()){steps.push_back({a,b,v});++r.generated;return finish(int(base+steps.size()-1));}
                if(c.size()>12){eligible=false;break;}
                pending.emplace(std::move(c),Step{a,b,v});
                if(pending.size()>pos.size()+neg.size()+4||steps.size()+pending.size()>200000){eligible=false;break;}
            }if(!eligible)break;
        }
        if(!eligible){++r.blocked;continue;}
        // Every non-tautological resolvent fits, or the entire pivot is skipped.
        std::vector<int> old=std::move(pos);old.insert(old.end(),neg.begin(),neg.end());
        std::set<int> touched;
        for(int id:old){live[id]=0;--r.residual;for(int l:db[id]){--count[toolbox::index_of(l)];touched.insert(std::abs(l));}}
        for(auto& entry:pending){
            int id=int(db.size());db.push_back(entry.first);live.push_back(1);steps.push_back(entry.second);
            ++r.residual;++r.generated;
            for(int l:db.back()){int k=toolbox::index_of(l);occ[k].push_back(id);++count[k];touched.insert(std::abs(l));}
        }
        done[v]=1;frames.push_back({v,std::move(old)});++r.eliminated;
        r.max_boundary=std::max(r.max_boundary,int(boundary.size()));
        for(int w:touched)if(w!=v)schedule(w);
    }
    if(toolbox::Clock::now()>=stop)return r;
    // Partition the exact residual by variable incidence, solve each component
    // using the existing native model constructor. No component failure means UNSAT.
    toolbox::Model model(f.n+1,0);
    if(r.residual){
        if(r.residual>(affine?300000u:50000u))return r;
        std::vector<int> parent(f.n+1,0);
        auto find=[&](int v){int x=v;while(parent[x]!=x)x=parent[x];while(parent[v]!=v){int w=parent[v];parent[v]=x;v=w;}return x;};
        for(int i=0;i<int(db.size());++i)if(live[i]){
            if((i&1023)==0&&toolbox::Clock::now()>=stop)return r;
            for(int l:db[i])if(!parent[std::abs(l)])parent[std::abs(l)]=std::abs(l);
            int a=find(std::abs(db[i][0]));
            for(int l:db[i]){int b=find(std::abs(l));if(a!=b){if(a>b)std::swap(a,b);parent[b]=a;}}
        }
        std::map<int,F> groups;
        for(int i=0;i<int(db.size());++i)if(live[i]){
            if((i&1023)==0&&toolbox::Clock::now()>=stop)return r;
            groups[find(std::abs(db[i][0]))].push_back(db[i]);
        }
        r.components=int(groups.size());
        std::vector<int> local(f.n+1,0);
        for(auto& entry:groups){
            if(toolbox::Clock::now()>=stop)return r;
            F& cs=entry.second;std::vector<int> vars{0};
            for(C& c:cs)for(int& l:c){int v=std::abs(l);if(!local[v]){local[v]=int(vars.size());vars.push_back(v);}l=l>0?local[v]:-local[v];}
            if(vars.size()>(affine?200001u:5001u)||cs.size()>(affine?300000u:20000u))return r;
            for(C& c:cs)c=fusion_kernel::norm(std::move(c));
            if(affine){
                auto now=toolbox::Clock::now();
                auto a=core_affine::solve(toolbox::Input{int(vars.size()-1),cs},now+(stop-now)/2);
                if(!a.model.empty()&&toolbox::satisfied(cs,a.model)){
                    for(size_t i=1;i<vars.size();++i){model[vars[i]]=a.model[i];local[vars[i]]=0;}
                    continue;
                }
                if(vars.size()>5001||cs.size()>20000)return r;
            }
            std::vector<int> a(vars.size(),-1);
            if(!fusion_kernel::verify(cs,a)){
                std::fill(a.begin(),a.end(),1);
                if(!fusion_kernel::verify(cs,a)&&!fusion_kernel::construct(cs,int(vars.size()-1),a,stop))return r;
            }
            if(!fusion_kernel::verify(cs,a))return r;
            for(size_t i=1;i<vars.size();++i){model[vars[i]]=a[i]>0;local[vars[i]]=0;}
        }
    }
    for(auto it=frames.rbegin();it!=frames.rend();++it){
        if(toolbox::Clock::now()>=stop)return r;
        int need=-1;
        for(int id:it->parents){
            bool sat=false;int bit=-1;
            for(int l:db[id]){if(std::abs(l)==it->v)bit=l>0;else if(toolbox::value(model,l)==1){sat=true;break;}}
            if(sat)continue;
            if(bit<0||(need>=0&&need!=bit))return r;
            need=bit;
        }
        if(need>=0)model[it->v]=int8_t(need);
    }
    if(toolbox::satisfied(f.cs,model)){r.status=10;r.model=std::move(model);}
    return r;
}
} // namespace core_regional
