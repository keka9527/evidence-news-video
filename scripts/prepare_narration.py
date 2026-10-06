"""Split continuous TTS groups into sentences; trim only timestamp gaps, never tempo."""
import argparse,json,math,re,subprocess,wave
from pathlib import Path

SR=48000
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def resolve(root,p):return Path(p) if Path(p).is_absolute() else root/p
def canonical(text):return ''.join(c for c in str(text) if c.isalnum()).casefold()
def times(word):
    a=word.get('startTime',word.get('start_time'));b=word.get('endTime',word.get('end_time'))
    if a is None or b is None or not 0<=float(a)<=float(b):raise ValueError('Invalid word timestamps')
    return float(a),float(b)

def prepare(root,groups,out,lang,threshold=.65,keep=.35):
    rows=load(root/f'work/sentences-{lang}.json');by={r['id']:r for r in rows}
    if len(by)!=len(rows):raise ValueError('Duplicate sentence IDs')
    ids=[s for g in groups for s in g.get('sentence_ids',[])]
    if ids!=[r['id'] for r in rows]:raise ValueError('Groups must cover sentences once, in timeline order')
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+',s) for s in ids):raise ValueError('Unsafe sentence ID')
    if not 0<keep<threshold:raise ValueError('Pause keep must be positive and less than threshold')
    if (out/'manifest.json').exists() or any((out/(s+'.wav')).exists() for s in ids):raise ValueError('Output exists; use a fresh output directory')
    staged=[];report=[]
    for group in groups:
        words=group.get('words',[])
        if not words:raise ValueError('TTS group has no word timestamps')
        targets=[canonical(by[s].get('tts',by[s]['text'])) for s in group['sentence_ids']]
        if any(not t for t in targets) or ''.join(canonical(w['word']) for w in words)!=''.join(targets):
            raise ValueError('Timestamp transcript differs from sentence TTS text; correct it before splitting')
        limits=[];total=0
        for t in targets:total+=len(t);limits.append(total)
        ends=[];count=0;next_boundary=0
        for i,w in enumerate(words):
            count+=len(canonical(w['word']))
            if next_boundary<len(limits) and count>limits[next_boundary]:raise ValueError('Word block crosses a sentence boundary')
            if next_boundary<len(limits) and count==limits[next_boundary]:ends.append(i);next_boundary+=1
            elif not canonical(w['word']) and ends and count==limits[next_boundary-1]:ends[-1]=i
        if len(ends)!=len(targets):raise ValueError('Sentence boundaries could not be resolved')
        pcm=subprocess.check_output(['ffmpeg','-v','error','-i',str(resolve(root,group['file'])),'-ar',str(SR),'-ac','1','-f','s16le','pipe:1'])
        duration=len(pcm)/2/SR;intervals=[times(w) for w in words]
        if any(a>duration+.05 or b>duration+.05 for a,b in intervals):raise ValueError('Timestamp exceeds decoded audio')
        cuts=[]
        lead=max(0,intervals[0][0]-.12)
        if lead:cuts.append((0,lead))
        for (_,end),(start,_) in zip(intervals,intervals[1:]):
            if start-end>threshold:cuts.append((end+keep/2,start-keep/2))
        stop=min(duration,intervals[-1][1]+.18)
        if stop<duration:cuts.append((stop,duration))
        ticks=[(round(a*SR),round(b*SR)) for a,b in cuts]
        if any(b<a or (i and a<ticks[i-1][1]) for i,(a,b) in enumerate(ticks)):raise ValueError('Invalid or overlapping trim intervals')
        cursor=0;chunks=[]
        for a,b in ticks:chunks.append(pcm[cursor*2:a*2]);cursor=b
        chunks.append(pcm[cursor*2:]);clean=b''.join(chunks)
        def mapped(t):
            n=round(t*SR);return (n-sum(max(0,min(n,b)-a) for a,b in ticks if n>a))/SR
        adjusted=[{**w,'startTime':mapped(a),'endTime':mapped(b)} for w,(a,b) in zip(words,intervals)]
        begin=0;first_word=0
        for sentence,end_word in zip(group['sentence_ids'],ends):
            finish=(adjusted[end_word]['endTime']+adjusted[end_word+1]['startTime'])/2 if end_word+1<len(words) else len(clean)/2/SR
            a,b=round(begin*SR),round(finish*SR);data=clean[a*2:b*2]
            if not data:raise ValueError('Empty sentence audio')
            actual=len(data)/2/SR
            ww=[{**w,'startTime':max(0,w['startTime']-a/SR),'endTime':min(actual,w['endTime']-a/SR)} for w in adjusted[first_word:end_word+1]]
            record={'id':sentence,'file':str((out/(sentence+'.wav')).relative_to(root)),'duration':actual,'words':ww,'language':lang,'speed':group.get('speed',0),'post_tempo':1.0,'continuous_group_cut':True,'source_group':group['id']}
            staged.append((out/(sentence+'.wav'),data,record));begin=finish;first_word=end_word+1
        report.append({'group':group['id'],'decoded_duration':duration,'prepared_duration':len(clean)/2/SR,'removed_intervals':[[a/SR,b/SR] for a,b in ticks]})
    out.mkdir(parents=True,exist_ok=True)
    for dest,data,_ in staged:
        with wave.open(str(dest),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes(data)
    manifest=[r for _,_,r in staged]
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'groups':report,'post_tempo':1.0,'timeline_seconds_before_tail':1/30+sum(math.ceil(r['duration']*30)/30 for r in manifest)}
    (out/'pause-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest,report

def main():
    p=argparse.ArgumentParser();p.add_argument('project');p.add_argument('--language',choices=['zh','en'],required=True)
    p.add_argument('--groups',required=True);p.add_argument('--out-dir');p.add_argument('--pause-threshold',type=float,default=.65);p.add_argument('--pause-keep',type=float,default=.35)
    a=p.parse_args();root=Path(a.project).resolve();out=resolve(root,a.out_dir or f'audio/tts-{a.language}').resolve()
    if not out.is_relative_to(root):p.error('Prepared audio must stay in the project')
    manifest,report=prepare(root,load(resolve(root,a.groups)),out,a.language,a.pause_threshold,a.pause_keep)
    print(f"Prepared {len(manifest)} sentences; native timeline {report['timeline_seconds_before_tail']:.3f}s; no tempo change")

if __name__=='__main__':main()
