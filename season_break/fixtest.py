import pickle, sys, os, json, time
sys.path.insert(0, '/tmp/t11')
from nt.llm import LLM
out = '/home/claude/nobodys_town/TEST/fixtest'
e = pickle.load(open(out + '/state.pkl', 'rb'))
llm = LLM('live', float(sys.argv[2]) if len(sys.argv) > 2 else 3.0, os.path.join(out, 'api_calls.jsonl'))
orig = llm.call_json
def spy(role, system, messages, max_tokens=600, **kw):
    r = orig(role, system, messages, max_tokens, **kw)
    if role.startswith('world') and len(messages) == 3:
        print('\n=== SECOND ASK:', messages[2]['content'][:400])
        try:
            a = json.loads(messages[1]['content'][messages[1]['content'].index('{'):messages[1]['content'].rindex('}') + 1])
            for x, y in zip(a.get('options', []), (r[0] or {}).get('options', [])):
                if x.get('record') != y.get('record'): print('  BEFORE:', str(x.get('record'))[:220], '\n  AFTER: ', str(y.get('record'))[:220])
        except Exception as ex: print('  (could not diff)', ex)
    return r
llm.call_json = spy
e.reopen(out, llm); e.compress = True; e.workers = 16
for _ in range(int(sys.argv[1])):
    t = time.time(); e.run_day(); print(f'\nday {e.w.day} {e.w.date_str} done in {time.time()-t:.0f}s, spent ${llm.meter.spent:.2f}', flush=True)
