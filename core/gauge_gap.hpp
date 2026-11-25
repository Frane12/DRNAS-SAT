// Finite pure SU(2) graph, exact all-representation bound.
// Included inside namespace core_operator, after hash().
inline int gauge_run(const std::string& raw,std::istream& in,int n,const std::filesystem::path& out,Clock::time_point stop){
    int m,p;if(n<1||n>256||!(in>>m>>p)||m<0||m>1024||p<0||p>512)throw std::runtime_error("gauge dimensions");
    Q alpha=rational(in),target=rational(in);
    if(alpha<=0||target<=0)throw std::runtime_error("gauge positive parameters");
    using Edge=std::pair<int,int>;
    auto edge=[](int a,int b)->Edge{return {std::min(a,b),std::max(a,b)};};
    std::set<Edge> edges;std::vector<std::vector<int>> adj(n);
    for(int i=0;i<m;++i){int a,b;if(!(in>>a>>b)||a<0||a>=n||b<0||b>=n||a==b||!edges.insert(edge(a,b)).second)throw std::runtime_error("gauge edge");adj[a].push_back(b);adj[b].push_back(a);}
    Q magnetic=0,upper=0;
    std::set<std::set<Edge>> loops;
    for(int i=0;i<p;++i){
        int len;if(!(in>>len)||len<3||len>n)throw std::runtime_error("gauge loop length");
        Q k=rational(in);std::vector<int> v(len);std::set<int> unique;
        for(int& a:v)if(!(in>>a)||a<0||a>=n||!unique.insert(a).second)throw std::runtime_error("gauge loop vertex");
        std::set<Edge> cycle;for(int j=0;j<len;++j){auto e=edge(v[j],v[(j+1)%len]);if(!edges.count(e))throw std::runtime_error("gauge loop edge");cycle.insert(e);}
        if(!loops.insert(cycle).second)throw std::runtime_error("duplicate gauge loop");
        Q weight=k;if(weight<0)weight=-weight;magnetic+=2*weight;
        // Rayleigh trial 1 + (k/e) Tr(U_p), norm squared 1+(k/e)^2.
        Q e=alpha*3*len/4;
        Q u=-k*k*e/(e*e+k*k);if(u<upper)upper=u;
    }
    std::string extra;if(in>>extra)throw std::runtime_error("trailing gauge input");
    bool ok=false;int girth=n+1;Q lower=0;
    try{
        // BFS from each vertex; an edge to an already discovered vertex
        // other than the tree parent gives a candidate cycle length.
        for(int s=0;s<n;++s){
            tick(stop);std::vector<int> dist(n,-1),parent(n,-1);std::queue<int> q;
            dist[s]=0;q.push(s);
            while(!q.empty()){
                int u=q.front();q.pop();
                for(int v:adj[u]){
                    if(dist[v]<0){dist[v]=dist[u]+1;parent[v]=u;q.push(v);}
                    else if(parent[u]!=v&&parent[v]!=u)girth=std::min(girth,dist[u]+dist[v]+1);
                }
            }
        }
        if(girth<=n){lower=alpha*3*girth/4-magnetic;ok=lower-upper>=target;}
        tick(stop);
    }catch(const Limit&){ok=false;}
    if(ok){
        std::ofstream f(out,std::ios::binary);f<<"drnas-op-v1\n"<<hash(raw)<<"\ngauge-gap "<<girth<<" "<<upper<<" "<<lower<<"\n";f.close();
        if(!f)throw std::runtime_error("gauge evidence write");
    }
    std::cout<<"c {\"domain\":\"operator\",\"method\":\"su2_graph_gauss_cycle\",\"certificate\":\""<<(ok?"OPERATOR_EXACT":"none")<<"\"}\n";
    return ok?30:0;
}
