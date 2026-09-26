"""Replays real runtime events; labels are used only after answer emission."""
import argparse
import asyncio
import hashlib
import json
import platform
from pathlib import Path
from statistics import median
from time import perf_counter
from prototype.runtime import LiveRuntime
from prototype.server import TranscriptMessage


def percentile(values, p):
    return sorted(values)[min(len(values)-1, int((len(values)-1)*p))] if values else None


async def run(backend='lightweight', reuse=True, rerank=True, final_only=False):
    dataset=Path(__file__).with_name('acceptance-v1.json')
    cases=json.loads(dataset.read_text(encoding='utf-8'))['cases']
    load_start=perf_counter()
    runtime=LiveRuntime(backend=backend,reuse=reuse,rerank=rerank)
    load_ms=(perf_counter()-load_start)*1000
    rows=[]; latencies=[]; supported=emitted=expected=correct=0; false_ids=[]; early=eligible=0
    full_trace=[]
    for case in cases:
        connection=runtime.connection(); seq=0; checks=[]; previous=None
        for turn,step in enumerate(case['steps']):
            text=step['text']; before_count=connection.search_count
            prefixes=step.get('prefixes')
            if prefixes is None and turn==0 and case['category'] not in {'unsupported','refinement'}:
                tokens=text.split(); prefixes=[' '.join(tokens[:max(2,len(tokens)//2)]),text.rstrip('?')]
            final=None
            if not final_only and prefixes:
                eligible+=1; triggered=False
                for prefix in prefixes:
                    seq+=1
                    output=await connection.handle(TranscriptMessage(event_id=f'e{seq}',turn_id=f't{turn}',text=prefix,timestamp_ms=seq*500,is_final=False))
                    triggered |= output['decision']=='provisional_retrieve'
                early+=triggered
            seq+=1
            message=TranscriptMessage(event_id=f'e{seq}',turn_id=f't{turn}',text=text,timestamp_ms=seq*500,is_final=True,
                                      revision_of=f'e{seq-1}' if step.get('correct') and not final_only else None)
            output=await connection.handle(message);latencies.append(output['latency_ms'])
            citations=output['citations']; gold=step['gold']; good=set(citations)&set(gold)
            expected+=len(gold);correct+=len(good)
            for claim in output['claims']:
                if claim['citations']:
                    emitted+=1
                    valid=all(c in {x.chunk_id for x in runtime.chunks} and c in claim['candidate_ids'] for c in claim['citations'])
                    exact=any(claim['text']==e['text'] for e in claim['evidence'])
                    supported+=valid and exact
                    if not valid:false_ids.append(case['id'])
            passed=set(citations)==set(gold)
            if step.get('uncertain'):passed=not citations and bool(output['uncertainty'])
            if step.get('delta'):passed &= output['reason']=='targeted_delta'
            if step.get('preserve') is not None:
                i=step['preserve'];passed &= bool(previous and len(output['claims'])>i and len(previous['claims'])>i and output['claims'][i]==previous['claims'][i])
            if step.get('suppress'):passed &= output['decision']=='suppress' and connection.search_count==before_count and output['claims']==previous['claims']
            if step.get('mixed'):passed &= output['decision']!='suppress'
            if case.get('intent_count'):passed &= len(output['sub_queries'])==case['intent_count']
            checks.append({'query':text,'pass':bool(passed),'gold':gold,'citations':citations,'decision':output['decision'],'reason':output['reason'],'latency_ms':output['latency_ms'],'clarification':output['clarification']})
            previous=output
        rows.append({'id':case['id'],'category':case['category'],'pass':all(s['pass'] for s in checks),'steps':checks,'searches':connection.search_count,'reuses':connection.reuse_count})
        full_trace.extend(connection.telemetry)
        await connection.close()
    categories={kind:{'passed':sum(r['pass'] for r in rows if r['category']==kind),'total':sum(r['category']==kind for r in rows)} for kind in sorted({r['category'] for r in rows})}
    trace_fields=('event_type','timestamp_s','server_ms','session_id','event_id','turn_id','token_cost','payload')
    traced=sum(all(field in event for field in trace_fields) for event in full_trace)
    trace_rate=traced/len(full_trace) if full_trace else None
    total_token_cost=sum(event.get('token_cost',{}).get('input_tokens',0)+event.get('token_cost',{}).get('output_tokens',0) for event in full_trace)
    result={'status':'local acceptance results','official_validation':'pending','disclosure':'Author-known synthetic control. Not blind held-out performance. Exact extraction attribution is not answer correctness.',
            'configuration':{'backend':backend,'parser':runtime.decomposer.method,'reuse':reuse,'rerank':rerank,'final_only':final_only,'python':platform.python_version(),'machine':platform.machine(),'platform':platform.platform(),'corpus_hash':runtime.corpus_hash,'dataset_sha256':hashlib.sha256(dataset.read_bytes()).hexdigest()},
            'cases':{'passed':sum(r['pass'] for r in rows),'total':len(rows),'categories':categories},
            'metrics':{'attribution':{'supported':supported,'emitted':emitted,'rate':supported/emitted if emitted else None},'intent_coverage':{'correct':correct,'expected':expected,'rate':correct/expected if expected else None},'early_retrieval':{'triggered':early,'eligible':eligible,'rate':early/eligible if eligible else None},'trace_coverage':{'complete':traced,'events':len(full_trace),'rate':trace_rate},'token_cost':{'tokens':total_token_cost,'estimated_usd':0.0,'basis':'non_generative_pipeline'},'fabricated_ids':false_ids,'searches':sum(r['searches'] for r in rows),'cache_reuses':sum(r['reuses'] for r in rows),'warm_endpoint_ms':{'p50':median(latencies),'p95':percentile(latencies,.95)},'model_load_ms':round(load_ms,2)},'case_results':rows}
    return result,full_trace


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--backend',choices=['lightweight','dense'],default='lightweight');parser.add_argument('--no-reuse',action='store_true');parser.add_argument('--no-rerank',action='store_true');parser.add_argument('--final-only',action='store_true');parser.add_argument('--out',type=Path,default=Path('prototype/reports/scorecard.json'));args=parser.parse_args()
    result,trace=asyncio.run(run(args.backend,not args.no_reuse,not args.no_rerank,args.final_only))
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    args.out.with_suffix('.jsonl').write_text('\n'.join(json.dumps(e,ensure_ascii=False) for e in trace),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['cases','metrics']},indent=2))


if __name__=='__main__':main()
