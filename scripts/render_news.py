"""Approved news preset layered on the unchanged portable base renderer."""
import importlib.util,json,math,sys,wave
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
from layout_guard import fit_headline

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('portable_video',HERE/'render_video.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
STYLE={'background':'#070B13','headline_color':'#D6AC29','accent_color':'#E66A22','caption_color':'#FFFFFF','headline_size':82,'tag_size':38,'source_size':26,'caption_size':50,'headline_y':245,'headline_line_spacing':100,'headline_min_gap':30}
CONFIG={}

def layer(row,fonts,watermark,en,progress):
    im=r.base(fonts,watermark,en);d=ImageDraw.Draw(im)
    r.put(im,(72,192),row.get('tag',''),fonts,STYLE['tag_size'],en,True,STYLE['accent_color'])
    titles=row['title'].split('\n');tag=row.get('tag','')
    tag_bottom=192+r.fnt(fonts,STYLE['tag_size'],en,True).getbbox(tag)[3] if tag else 160
    if STYLE['headline_min_gap']<30:raise ValueError('Headline gap must be at least 30px on this canvas')
    layout=fit_headline(titles,lambda n:r.fnt(fonts,n,en,True),video_top=535,
                        anchor=(67,STYLE['headline_y']),line_spacing=STYLE['headline_line_spacing'],
                        initial_size=STYLE['headline_size'],min_gap=STYLE['headline_min_gap'],tag_bottom=tag_bottom)
    r.HEADER_CHECKS.append({'row_id':row.get('id'),'kind':'body',**layout})
    for title,xy in zip(titles,layout['positions']):r.put(im,xy,title,fonts,layout['font_size'],en,True,STYLE['headline_color'])
    d.rectangle((30,535,1050,1395),fill=(0,0,0,0))
    if row.get('visual_label'):r.put(im,(55,551),row['visual_label'],fonts,27,en,True,'#E7EAF1')
    r.put(im,(72,1432),row['source_credit'],fonts,27,en,color='#C0C9D7')
    r.put(im,(72,1482),row.get('fact_credit',''),fonts,STYLE['source_size'],en,color=STYLE['accent_color'])
    size=STYLE['caption_size'] if not en else 53
    while True:
        try:lines=r.wrap(row['text'],fonts,size,926,en,row.get('protect_terms',[]))
        except ValueError:lines=['overflow']*4
        if len(lines)<=3:break
        size-=2
        if size<42:raise ValueError('Caption exceeds three readable lines')
    if not en:
        for i in range(1,len(lines)):
            if lines[i] and lines[i][0] in '，。！？、；：”’）' and len(lines[i-1])>1:
                lines[i]=lines[i-1][-1]+lines[i];lines[i-1]=lines[i-1][:-1]
    y=1740-len(lines)*(size+17);f=r.fnt(fonts,size,en,True)
    for line in lines:d.text(((1080-f.getlength(line))/2,y),line,font=f,fill=STYLE['caption_color'],stroke_width=2,stroke_fill=STYLE['background']);y+=size+17
    r.put(im,(72,1804),row.get('footer_credit',row['source_credit']),fonts,24,en,color='#929FAF')
    d.rectangle((70,1870,1010,1876),fill='#252E3C');d.rectangle((70,1870,70+round(940*progress),1876),fill=STYLE['accent_color'])
    card=row.get('evidence_card')
    if card:
        lines_card=card['lines']
        if len(lines_card)>3:raise ValueError('Evidence card supports at most three lines')
        d.rounded_rectangle((100,1020,980,1360),radius=18,fill='#101827')
        r.put(im,(138,1042),card['heading'],fonts,28,en,color='#BAC5D5')
        for i,t in enumerate(lines_card):
            if r.fnt(fonts,43,en,True).getlength(t)>800:raise ValueError('Evidence line too long')
            r.put(im,(138,1102+i*64),t,fonts,43,en,True,STYLE['headline_color'])
        r.put(im,(138,1304),card['note'],fonts,25,en,color='#9AA6B8')
    return im,lines,size

def cover(root,cfg,fonts,en,out):
    c=cfg['cover'];lang='en' if en else 'zh'
    if not c.get('photo') or not c.get('credit') or not c.get('title_'+lang):raise ValueError('Provide verified photo, title and source')
    photo=Image.open(r.path(root,c['photo'])).convert('RGB')
    if c.get('crop'):photo=photo.crop(tuple(c['crop']))
    im=r.base(fonts,cfg.get('watermark',''),en);titles=c['title_'+lang].split('\n')
    layout=fit_headline(titles,lambda n:r.fnt(fonts,n,en,True),video_top=650,
                        anchor=(66,280),line_spacing=150,initial_size=104 if en else 140,
                        min_size=54,max_width=934,tag_bottom=155)
    r.HEADER_CHECKS.append({'row_id':'cover','kind':'cover',**layout})
    for title,xy in zip(titles,layout['positions']):r.put(im,xy,title,fonts,layout['font_size'],en,True,STYLE['headline_color'])
    im.paste(ImageOps.fit(photo,(950,940)),(66,650))
    r.put(im,(72,1732),c.get('subtitle_'+lang,''),fonts,39 if en else 47,en,True)
    r.put(im,(72,1821),c['credit'],fonts,25,en,color='#929FAF');im.convert('RGB').save(out,quality=96)

def make_audio(root,rows,sounds,work,music):
    pieces=[];cursor=1/30;timed=[]
    for row in rows:
        sound=sounds[row['id']];pcm=work/(row['id']+'.wav')
        r.run(['-i',r.path(root,sound['file']),'-ar',48000,'-ac',1,'-c:a','pcm_s16le',pcm])
        with wave.open(str(pcm)) as w:data=w.readframes(w.getnframes())
        duration=len(data)/2/48000;gap=0 if sound.get('continuous_group_cut') else .16
        span=math.ceil((duration+gap)*30)/30
        ends=[float(w.get('endTime',w.get('end_time',duration))) for w in sound.get('words',[])]
        speech_end=min(duration,max(ends)) if ends else duration
        timed.append({**row,'start':cursor,'end':cursor+speech_end,'scene_end':cursor+span})
        pieces.append(data+b'\0\0'*(round(span*48000)-len(data)//2));cursor+=span
    target=CONFIG.get('target_duration_seconds');tail=.6
    if target is not None:
        tail=float(target)-cursor
        if not 0<=tail<=1:raise ValueError('Exact length needs script adjustment; no slow-down or long padding allowed')
    total=math.ceil((cursor+tail)*30-1e-8)/30;timed[-1]['scene_end']=total
    if timed[0]['end']>3:raise ValueError('Opening hook exceeds three seconds')
    raw=work/'narration-raw.wav'
    with wave.open(str(raw),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(b'\0\0'*1600)
        for data in pieces:w.writeframes(data)
        w.writeframes(b'\0\0'*round((total-cursor)*48000))
    voice=work/'narration.wav';mix=work/'mix.wav'
    r.run(['-i',raw,'-af','loudnorm=I=-16:TP=-1.5:LRA=7','-ar',48000,'-ac',1,voice])
    r.run(['-i',voice,'-c:a','libmp3lame','-b:a','192k',root/'outputs'/('narration-'+work.name.removeprefix('render-')+'.mp3')])
    if music:
        filt='[0:a]asplit=2[v][key];[1:a]volume=0.65[bed];[bed][key]sidechaincompress=threshold=0.01:ratio=12:attack=8:release=350[duck];[v][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89:level=false[a]'
        r.run(['-i',voice,'-stream_loop',-1,'-i',r.path(root,music),'-filter_complex',filt,'-map','[a]','-ar',48000,'-ac',2,'-t',total,mix])
    else:r.run(['-i',voice,'-ac',2,mix])
    return timed,total,mix

original_run=r.run
def run(args):
    args=list(args)
    for i in range(len(args)-3):
        if args[i:i+4]==['-c:v','copy','-c:a','aac']:
            args[i:i+2]=['-vf','setpts=N/(30*TB),setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709','-r',30,'-c:v','libx264','-preset','veryfast','-crf',18,'-threads',3];break
    return original_run(args)

def main():
    global CONFIG
    if len(sys.argv)>1 and sys.argv[1] not in ['-h','--help']:
        CONFIG=r.read(Path(sys.argv[1]).resolve()/'project.json')
        STYLE.update({k:v for k,v in CONFIG.get('visual',{}).items() if k in STYLE});r.BG=STYLE['background']
    r.layer=layer;r.cover=cover;r.make_audio=make_audio;r.run=run
    r.main()
    # Base renderer gives a short caption tail; cover the actual last syllable too.
    if '--language' in sys.argv:
        lang=sys.argv[sys.argv.index('--language')+1];version=sys.argv[sys.argv.index('--version')+1] if '--version' in sys.argv else 'v1'
        root=Path(sys.argv[1]).resolve();work=root/'work'/f'render-{lang}-{version}'
        caps=r.read(work/'captions.json');timed=r.read(work/'timed.json')
        for cap,row in zip(caps,timed):cap['end']=max(cap['end'],row['end'])
        r.save(work/'captions.json',caps)
        (root/'outputs'/f'{lang}-{version}.srt').write_text('\n\n'.join(f"{i+1}\n{r.stamp(c['start'])} --> {r.stamp(c['end'])}\n{c['text']}" for i,c in enumerate(caps))+'\n',encoding='utf-8')

if __name__=='__main__':main()
