#include <bits/stdc++.h>
#include <coroutine>
#include "projection.hpp"
#include "unified_reason.hpp"
using namespace toolbox;

struct Move {int literal, bad;};
struct Cursor {
    struct promise_type {
        Move last{};
        Cursor get_return_object() {return {std::coroutine_handle<promise_type>::from_promise(*this)};}
        std::suspend_always initial_suspend() noexcept {return {};}
        std::suspend_always final_suspend() noexcept {return {};}
        std::suspend_always yield_value(Move move) {last=move;return {};}
        void return_void() {}
        void unhandled_exception() {std::rethrow_exception(std::current_exception());}
    };
    std::coroutine_handle<promise_type> handle;
    Cursor(const Cursor&)=delete;
    Cursor(std::coroutine_handle<promise_type> h):handle(h) {}
    ~Cursor(){handle.destroy();}
    Move step(){
        handle.resume();
        if(handle.done()) throw std::runtime_error("repair ended before charged flip");
        return handle.promise().last;
    }
};
#include "observe.hpp"

Clauses read_rows(const std::string& path,int n){
    std::ifstream stream(path);
    if(!stream)throw std::runtime_error("missing input rows");
    Clauses rows;std::string line;
    while(std::getline(stream,line)){
        Clause c;std::istringstream in(line);int x;
        for(;;){
            if(!(in>>x)||x>n||x< -n)throw std::runtime_error("invalid row");
            if(!x) break;
            c.push_back(x);
        }
        if(!normalize(c))throw std::runtime_error("unexpected tautology");
        rows.push_back(std::move(c));
    }
    return rows;
}

struct Lane {
    Model fixed, model;
    Clauses clauses;
    std::unique_ptr<Projection> projection;
    uint64_t steps=0;
    Lane(const char* input,int n,const std::string& proof):fixed(n+1,-1),model(n+1,0),clauses(read_rows(input,n)){
        Proof p(proof);
        if(!reduce_root(n,clauses,fixed,p))throw std::runtime_error("unexpected root conflict");
        projection=std::make_unique<Projection>(n,clauses);
        if(!projection->run(p,after(.15)))throw std::runtime_error("unexpected projection conflict");
        clauses=projection->residual();
        CaseStats cs;UnifiedStats us;
        if(projection->projected&&!clauses.empty()&&!cooperate(n,clauses,fixed,p,after(.09),cs,us,2))
            throw std::runtime_error("unexpected residual conflict");
        std::vector<int> balance(n+1);
        for(const auto& c:clauses)for(int l:c)balance[abs(l)]+=l>0?1:-1;
        for(int v=1;v<=n;v++)model[v]=fixed[v]>=0?fixed[v]:balance[v]>0;
    }
    void write_model(const char* path){
        for(size_t i=1;i<fixed.size();++i)if(fixed[i]>=0)model[i]=fixed[i];
        projection->reconstruct(model);
        std::ofstream out(path);out<<"v ";
        for(size_t i=1;i<model.size();++i){
            if(fixed[i]>=0)model[i]=fixed[i];
            out<<(model[i]?int(i):-int(i))<<" ";
        }
        out<<"0\n";out.close();if(!out)throw std::runtime_error("model write failed");
    }
};

int main(int argc,char**argv){
    if(argc!=7)return 2;
    const int n=std::stoi(argv[1]);
    const int cap=2160000,window=10000;
    const std::string policy=argv[5];
    if(n!=500 || (policy!="mean"&&policy!="force-first"&&policy!="force-rank" && policy!="patience" && policy!="clock"))return 2;
    Lane a(argv[2],n,std::string(argv[4])+".a"),b(argv[3],n,std::string(argv[4])+".b");
    Lane* lanes[]={&a,&b};
    Cursor ac=observe(n,a.clauses,a.model,Time::max(),a.steps);
    Cursor bc=observe(n,b.clauses,b.model,Time::max(),b.steps);
    Cursor* cursors[]={&ac,&bc};
    int total=0,split=0,samples=0,selected=-1,winner=-1;
    long long sums[2]={};
    int probe_best[2]={INT_MAX,INT_MAX};
    int switched_at=0, switched_after=0;
    for(int j=0;j<2;++j)if(satisfied(lanes[j]->clauses,lanes[j]->model)){winner=j;break;}
    // Both order-specific states and RNGs remain alive on a single CPU.
    // Even identical prefix flips are charged separately.
    while(winner<0 && total+2<=cap && samples<window){
        Move x=ac.step();++total;
        if(!x.bad){winner=0;break;}
        Move y=bc.step();++total;
        if(!y.bad){winner=1;break;}
        if(!split && x.literal!=y.literal)split=int(a.steps);
        if(split){
            sums[0]+=x.bad;sums[1]+=y.bad;++samples;
            probe_best[0]=std::min(probe_best[0],x.bad);
            probe_best[1]=std::min(probe_best[1],y.bad);
        }
    }
    if(winner<0 && samples==window){
        selected=policy=="force-rank"?1:policy=="force-first"?0:int(sums[1]<sums[0]);
        int active=selected;
        int best=probe_best[active];
        int last_record=total;
        const int probe_end=total;
        while(total<cap){
            Move m=cursors[active]->step();++total;
            if(!m.bad){winner=active;break;}
            if(m.bad<best){
                best=m.bad;
                last_record=total;
            }
            if(!switched_at && total<cap &&
               ((policy=="patience" && total-last_record>=window) ||
                (policy=="clock" && total-probe_end>=window))){
                switched_at=total;
                switched_after=total-probe_end;
                active=1-active;
            }
        }
    }
    if(winner>=0)lanes[winner]->write_model(argv[6]);
    std::cout<<"{\"status\":\""<<(winner<0?"UNKNOWN":"SAT")<<"\",\"split\":"<<split
             <<",\"samples\":"<<samples<<",\"sums\":["<<sums[0]<<","<<sums[1]<<"],\"selected\":"<<selected
             <<",\"switch_at\":"<<switched_at<<",\"switch_after\":"<<switched_after
             <<",\"winner\":"<<winner<<",\"lane_flips\":["<<a.steps<<","<<b.steps<<"],\"charged\":"<<total<<"}\n";
}
