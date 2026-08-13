#!/usr/bin/env python3
import argparse,json
from collections import defaultdict
from pathlib import Path
def main(root,result_path,model_id):
    root=Path(root); result=json.loads(Path(result_path).read_text(encoding="utf-8-sig")); thresholds=json.loads((root/"config"/"QUALITY_THRESHOLDS.json").read_text(encoding="utf-8-sig"))["thresholds"]; registry_path=root/"config"/"MODEL_REGISTRY.json"; registry=json.loads(registry_path.read_text(encoding="utf-8-sig")); grouped=defaultdict(list)
    for row in result["results"]: grouped[row["category"]].append(row["quality"])
    performance=result["stability_success_rate"]>=thresholds["stability_success_rate"] and result["average_tokens_per_second"]>=thresholds["minimum_tokens_per_second"] and result["average_ttft_seconds"]<=thresholds["maximum_average_ttft_seconds"]
    scores={k:sum(v)/len(v) for k,v in grouped.items()}; qualification={k:("qualified" if score>=thresholds.get(k,1.0) and performance else "not_qualified") for k,score in scores.items()}; registry["models"][model_id]["qualification"]=qualification; registry["models"][model_id]["status"]="qualified_for_selected_tasks" if "qualified" in qualification.values() else "not_qualified"
    routing_path=root/"config"/"ROUTING_POLICY.json";routing=json.loads(routing_path.read_text(encoding="utf-8-sig"))
    for category,status in qualification.items():
        candidates=routing.get("task_rules",{}).get(category,{}).setdefault("local_candidates",[])
        if status=="qualified" and model_id not in candidates:candidates.append(model_id)
        if status!="qualified" and model_id in candidates:candidates.remove(model_id)
    temp=registry_path.with_suffix(".tmp"); temp.write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding="utf-8-sig"); temp.replace(registry_path);rtmp=routing_path.with_suffix(".tmp");rtmp.write_text(json.dumps(routing,ensure_ascii=False,indent=2),encoding="utf-8-sig");rtmp.replace(routing_path); print(json.dumps({"model_id":model_id,"qualification":qualification,"category_scores":scores},ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--root",required=True); p.add_argument("--result",required=True); p.add_argument("--model-id",required=True); a=p.parse_args(); main(a.root,a.result,a.model_id)
