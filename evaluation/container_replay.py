"""Run the development acceptance cases through a real server WebSocket."""
import argparse
import asyncio
import json
from pathlib import Path
import websockets


async def run(url):
    cases = json.loads(Path('evaluation/acceptance-v1.json').read_text(encoding='utf-8'))['cases']
    rows = []
    for case in cases:
        checks = []
        async with websockets.connect(url, max_size=4_000_000) as ws:
            ready = json.loads(await ws.recv())
            assert ready['type'] == 'ready'
            seq = 0
            previous = None
            for turn, step in enumerate(case['steps']):
                prefixes = step.get('prefixes') or []
                for text, final in [(p, False) for p in prefixes] + [(step['text'], True)]:
                    seq += 1
                    await ws.send(json.dumps(dict(event_id=f'e{seq}', turn_id=f't{turn}', sequence=seq,
                                                 text=text, is_final=final, timestamp_ms=seq*500)))
                    result = json.loads(await asyncio.wait_for(ws.recv(), 40))
                    if result.get('type') == 'error':
                        raise RuntimeError(result)
                passed = set(result['citations']) == set(step['gold'])
                if step.get('uncertain'):
                    passed &= bool(result['uncertainty']) and not result['citations']
                if step.get('suppress'):
                    passed &= result['decision'] == 'suppress' and result['claims'] == previous['claims'] and result['stats']['searches'] == previous['stats']['searches']
                if step.get('delta'):
                    passed &= result['reason'] == 'targeted_delta'
                if step.get('mixed'):
                    passed &= result['decision'] != 'suppress'
                if case.get('intent_count'):
                    passed &= len(result['sub_queries']) == case['intent_count']
                if step.get('preserve') is not None:
                    i = step['preserve']
                    passed &= len(result['claims']) > i and result['claims'][i] == previous['claims'][i]
                checks.append(bool(passed))
                previous = result
        rows.append({'id': case['id'], 'passed': all(checks)})
    return {'disclosure': 'Author-known local development acceptance through actual WebSockets; not official validation.',
            'url': url, 'passed': sum(r['passed'] for r in rows), 'total': len(rows), 'cases': rows}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--url', default='ws://127.0.0.1:8013/ws/stream')
    p.add_argument('--out', type=Path, default=Path('prototype/reports/container-replay.json'))
    args = p.parse_args()
    result = asyncio.run(run(args.url))
    args.out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f"{result['passed']}/{result['total']} container replay cases passed")
    raise SystemExit(0 if result['passed'] == result['total'] else 1)
