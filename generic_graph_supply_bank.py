"""Independently specified synthetic graph contracts; no private data."""
import hashlib
import json
from copy import deepcopy
from itertools import product
import phase0_generic_dag as dag

ERROR={"error":"ValueError"}
def ok(value):return {"value":json.loads(json.dumps(value,ensure_ascii=True))}
def case(label,args,want):return {"label":label,"args":args,"expected":want}
def altered(obj,key,value):
    result=deepcopy(obj);result[key]=value;return result
def bank():
    out=[]
    def add(name,contract,rows):
        if len({c["label"] for c in rows})!=len(rows):raise ValueError("duplicate_case_label")
        out.append((dag,name,contract,rows))
    a={"id":"DEMO.1","depends_on":[],"priority":1}
    b={"id":"DEMO.2","depends_on":["DEMO.1"],"priority":0}
    c={"id":"DEMO.3","depends_on":[],"priority":2}
    steps=[a,b,c]
    rows=[]
    for states in product(("pending","verified"),repeat=3):
        status=dict(zip(("DEMO.1","DEMO.2","DEMO.3"),states))
        expected=[]
        if states[1]=="pending" and states[0]=="verified":expected.append(b)
        if states[0]=="pending":expected.append(a)
        if states[2]=="pending":expected.append(c)
        rows.append(case("/".join(states),[steps,status],ok(expected)))
    all_pending={s["id"]:"pending" for s in steps}
    for label,graph,state in (
        ("empty",[],{}),("not list",{},{}),("bad node",[0],{}),
        ("duplicate id",[a,a],{"DEMO.1":"pending"}),("invalid id",[altered(a,"id","bad")],{"bad":"pending"}),
        ("negative priority",[altered(a,"priority",-1)],{"DEMO.1":"pending"}),
        ("large priority",[altered(a,"priority",4)],{"DEMO.1":"pending"}),
        ("boolean priority",[altered(a,"priority",True)],{"DEMO.1":"pending"}),
        ("missing dependency",[altered(a,"depends_on",["DEMO.9"])],{"DEMO.1":"pending"}),
        ("self dependency",[altered(a,"depends_on",["DEMO.1"])],{"DEMO.1":"pending"}),
        ("cycle",[altered(a,"depends_on",["DEMO.2"]),b],{"DEMO.1":"pending","DEMO.2":"pending"}),
        ("duplicate dependency",[a,altered(b,"depends_on",["DEMO.1","DEMO.1"])],{"DEMO.1":"pending","DEMO.2":"pending"}),
        ("wrong dependency type",[altered(a,"depends_on","DEMO.2")],{"DEMO.1":"pending"}),
        ("bad dependency id",[altered(a,"depends_on",["bad"])],{"DEMO.1":"pending"}),
        ("status absent",steps,{}),("unknown status",steps,dict(all_pending,**{"DEMO.1":"unknown"})),
        ("extra status",steps,dict(all_pending,**{"DEMO.4":"pending"})),
        ("21 steps",[{"id":"DEMO."+str(i),"depends_on":[],"priority":0} for i in range(1,22)],
                        {"DEMO."+str(i):"pending" for i in range(1,22)})):
        rows.append(case(label,[graph,state],ERROR))
    graph=[{"id":"DEMO."+str(i),"depends_on":[],"priority":0} for i in range(1,21)]
    ordered=sorted(graph,key=lambda s:s["id"])
    rows.append(case("20 steps",[graph,{s["id"]:"pending" for s in graph}],ok(ordered)))
    rows.append(case("priority tie",[[altered(c,"priority",1),a],{"DEMO.1":"pending","DEMO.3":"pending"}],ok([a,altered(c,"priority",1)])))
    add("dependency_frontier","Accept 1..20 unique valid DAG nodes, complete pending/verified statuses, reject bad dependencies/cycles; return ready pending nodes sorted by priority then ID.",rows)

    frozen="class ProductContract:\n    def test_control(self): pass\n    def test_a(self): pass\n    def test_b(self): pass\n"
    manifest={"schema":1,"goal_id":"DEMO","approval":"host-reviewed","model":"qwen3.5:9b",
              "source_path":"sample.py","function":"compute","test_module":"test_sample",
              "frozen_sha256":hashlib.sha256(frozen.encode()).hexdigest(),"positive_controls":["test_control"],
              "steps":[dict(a,target_test="test_a",anchor="x > 0",task="repair first condition"),
                       dict(b,target_test="test_b",anchor="y == 0",task="repair second condition")],
              "budget":{"concurrent_model_calls":1,"attempts_per_step":2,"num_ctx":4096,
                        "num_predict":900,"max_prompt_chars":6500,"model_downloads":False}}
    rows=[case("valid",[manifest,frozen],ok(manifest)),
          case("no mapping",[[],frozen],ERROR),case("extra key",[dict(manifest,extra=0),frozen],ERROR),
          case("wrong frozen text",[manifest,frozen+"\n"],ERROR)]
    for key,values in {
        "schema":[0,2],"approval":["model",""],"goal_id":["x","DE","A"*57],
        "source_path":["/sample.py","a/../sample.py","a\\sample.py","sample.txt"],
        "function":["bad name","a.b.c","a."],"test_module":["sample","test_"],
        "model":["unknown"],"frozen_sha256":["a"*63,"a"*64],"budget":[{},None],
        "positive_controls":[[],["test_control","test_control"],["test_other"]],
        "steps":[[],[manifest["steps"][0]]]
    }.items():
        for i,value in enumerate(values):
            rows.append(case(key+" invalid "+str(i),[altered(manifest,key,value),frozen],ERROR))
    for key,values in {
        "id":["bad","OTHER.1","DEMO.2"],"depends_on":[["DEMO.1"],["DEMO.9"],["DEMO.2"]],
        "target_test":["bad","test_control","test_b"],"anchor":["","x\ny","x +","a"*251],
        "task":["","x"*481],"priority":[-1,4,True]
    }.items():
        for i,value in enumerate(values):
            m=deepcopy(manifest);m["steps"][0][key]=value
            rows.append(case("step "+key+" "+str(i),[m,frozen],ERROR))
    for key,value in (("num_ctx",0),("num_ctx",4097),("num_predict",901),("attempts_per_step",3),
                       ("model_downloads",True),("concurrent_model_calls",2),("max_prompt_chars",6501),
                       ("num_predict",True)):
        m=deepcopy(manifest);m["budget"][key]=value
        rows.append(case("budget "+key+" "+str(value),[m,frozen],ERROR))
    m=altered(manifest,"model","qwen2.5-coder:7b")
    rows.append(case("other approved model",[m,frozen],ok(m)))
    m=deepcopy(manifest);m["budget"]["num_ctx"]=1024
    rows.append(case("smaller context",[m,frozen],ok(m)))
    add("validate","Require exact host-reviewed schema, valid scope, approved model, frozen suite hash and complete unique tests, acyclic graph, bounded budget and valid steps.",rows)

    def results(control,x,y):
        return {"test_control (fixture.T.test_control)":control,
                "test_a (fixture.T.test_a)":x,"test_b (fixture.T.test_b)":y}
    rows=[]
    for control,x,y in product(("ok","FAIL"),repeat=3):
        rows.append(case(control+"/"+x+"/"+y,[manifest,results(control,x,y)],
                         ok({"test_control":control,"test_a":x,"test_b":y})))
    valid=results("ok","FAIL","FAIL")
    for label,value in (
        ("empty",{}),("wrong type",[]),("extra",dict(valid,extra="ok")),
        ("bad outcome",altered(valid,"test_a (fixture.T.test_a)","ERROR")),
        ("wrong name",{"test_control (fixture.T.test_control)":"ok","test_a":"FAIL","test_b (fixture.T.test_b)":"FAIL"}),
        ("duplicate short name",{"test_control (one)":"ok","test_control (two)":"ok","test_b (three)":"FAIL"}),
        ("wrong inventory",{"test_control (one)":"ok","test_other (two)":"ok","test_b (three)":"FAIL"})):
        rows.append(case(label,[manifest,value],ERROR))
    add("normalize","Return exactly one complete frozen test inventory with unambiguous verbose test identities and only ok/FAIL outcomes.",rows)

    rows=[]
    for states in product(("pending","verified"),repeat=2):
        statuses=dict(zip(("DEMO.1","DEMO.2"),states))
        for control,x,y in product(("ok","FAIL"),repeat=3):
            # In this specific chain, A is the first step; B depends on A.
            want=ERROR
            if control=="ok" and not(states[0]=="verified" and x!="ok") and not(states[1]=="verified" and y!="ok"):
                if states[0]=="pending" and x=="FAIL":want=ok(manifest["steps"][0])
                elif states==("verified","pending") and y=="FAIL":want=ok(manifest["steps"][1])
                elif states==("verified","verified") and x==y=="ok":want=ok(None)
            rows.append(case("/".join((*states,control,x,y)),[manifest,statuses,results(control,x,y)],want))
    rows.extend([case("missing statuses",[manifest,{},valid],ERROR),
                 case("invalid state",[manifest,{"DEMO.1":"bad","DEMO.2":"pending"},valid],ERROR)])
    add("next_ready","With complete observations and green controls, choose first reachable pending red step; reject changed verified steps and passing unverified targets; return None only when fully verified and green.",rows)

    rows=[]
    for x,y,u,v in product(("ok","FAIL"),repeat=4):
        before=results("ok",x,y);after=results("ok",u,v)
        if (x=="ok" and u=="FAIL") or (y=="ok" and v=="FAIL"):want="rejected_regression"
        elif x!="FAIL" or u!="ok":want="rejected_no_progress"
        elif v=="ok":want="all_frozen_tests_green"
        else:want="strict_partial_improvement"
        rows.append(case(x+y+" to "+u+v,[manifest,manifest["steps"][0],before,after,{"DEMO.1":"pending","DEMO.2":"pending"}],ok(want)))
    rows.extend([case("control regresses",[manifest,manifest["steps"][0],valid,results("FAIL","ok","FAIL"),{"DEMO.1":"pending"}],ok("rejected_regression")),
                 case("already verified",[manifest,manifest["steps"][0],valid,results("ok","ok","FAIL"),{"DEMO.1":"verified"}],ERROR),
                 case("no active id",[manifest,manifest["steps"][0],valid,results("ok","ok","FAIL"),{}],ERROR)])
    add("assess","Reject regression first; then require active pending red target repaired and strict reduction of failures; classify fully green or strict partial improvement.",rows)

    rows=[case("valid",[frozen],ok(["test_control","test_a","test_b"])),
          case("one",["class ProductContract:\n    def test_a(self): pass\n"],ok(["test_a"])),
          case("ignore helpers",["class ProductContract:\n    def helper(self): pass\n    def test_a(self): pass\n"],ok(["test_a"])),
          case("wrong class",["class Other:\n    def test_a(self): pass\n"],ERROR),
          case("empty class",["class ProductContract: pass\n"],ERROR),
          case("duplicate tests",["class ProductContract:\n    def test_a(self): pass\n    def test_a(self): pass\n"],ERROR),
          case("duplicate class",[frozen+frozen],ERROR),case("none",[None],ERROR),
          case("oversized",["#"*45001],ERROR)]
    add("test_names","Extract unique test_ methods from exactly one nonempty ProductContract class; reject wrong type, oversized or ambiguous suite.",rows)
    return out
