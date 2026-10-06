"""Portable 9:16 renderer: real footage, full-sentence captions and explicit assets."""
import argparse,json,math,os,re,subprocess,wave
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
from layout_guard import fit_headline

W,H,FPS,SR=1080,1920,30,48000
BG="#070b13"
HEADER_CHECKS=[]

def run(args):
    r=subprocess.run(["ffmpeg","-v","error","-y",*map(str,args)],capture_output=True)
    if r.returncode:raise RuntimeError("FFmpeg failed; check files, filters and installed codecs.")

def read(p):return json.loads(p.read_text(encoding="utf-8"))
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
def path(root,value):return Path(value) if Path(value).is_absolute() else root/value

def verify_master_resolution(file):
    result=subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height","-of","json",str(file)],capture_output=True,text=True)
    if result.returncode:raise RuntimeError("Cannot verify master resolution: ffprobe failed.")
    streams=json.loads(result.stdout).get("streams",[])
    if not streams or (streams[0].get("width"),streams[0].get("height"))!=(W,H):
        raise ValueError("Master is not 1080x1920; fix export and explain the actual limitation before delivery.")

def choose_fonts(root,cfg):
    win=Path(os.environ.get("WINDIR",""))/"Fonts"
    choices=[win/"msyh.ttc",Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),Path("/System/Library/Fonts/PingFang.ttc")]
    main=path(root,cfg["font"]) if cfg.get("font") else next((p for p in choices if p.is_file()),None)
    if not main:raise ValueError("Provide a CJK-capable font in project.json.")
    bold=path(root,cfg["font_bold"]) if cfg.get("font_bold") else (win/"msyhbd.ttc" if (win/"msyhbd.ttc").is_file() else main)
    english=path(root,cfg["font_en"]) if cfg.get("font_en") else next((p for p in [win/"arial.ttf",Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")] if p.is_file()),main)
    return main,bold,english

def fnt(fonts,size,en=False,bold=False):return ImageFont.truetype(str(fonts[2] if en else fonts[1] if bold else fonts[0]),size)
def put(im,xy,text,fonts,size=34,en=False,bold=False,color="white"):
    ImageDraw.Draw(im).text(xy,text,font=fnt(fonts,size,en,bold),fill=color)

def wrap(text,fonts,size,width,en=False,protect=()):
    if not text.strip():return []
    if en:
        escaped=[re.escape(s) for s in sorted(protect,key=len,reverse=True)]
        tokens=re.findall("|".join(escaped+[r"\S+"]),text);sep=" "
    else:
        tokens=re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*|\d+(?:\.\d+)?|.",text);sep=""
    font=fnt(fonts,size,en,True);lines=[];line=""
    for token in tokens:
        candidate=(line+sep+token) if line else token
        if font.getlength(candidate)>width and line:
            if token in "，。！？、；：”’）" and font.getlength(line+token)<=width+20:line+=token;continue
            lines.append(line);line=token
        else:line=candidate
        if font.getlength(line)>width+20:raise ValueError("A protected word/name does not fit; shorten or reduce font.")
    if line:lines.append(line)
    return lines

def base(fonts,watermark,en):
    im=Image.new("RGBA",(W,H),BG)
    if watermark:
        size=49
        while fnt(fonts,size,en,True).getlength(watermark)>400:size-=1
        put(im,(W-72-fnt(fonts,size,en,True).getlength(watermark),79),watermark,fonts,size,en,True)
    return im

def layer(row,fonts,watermark,en,progress):
    im=base(fonts,watermark,en);d=ImageDraw.Draw(im)
    put(im,(72,192),row.get("tag",""),fonts,31,en,True,"#ffad83")
    titles=row["title"].split("\n")
    tag=row.get("tag","");tag_bottom=192+fnt(fonts,31,en,True).getbbox(tag)[3] if tag else 160
    layout=fit_headline(titles,lambda n:fnt(fonts,n,en,True),video_top=535,
                        initial_size=85 if en else 92,tag_bottom=tag_bottom)
    HEADER_CHECKS.append({"row_id":row.get("id"),"kind":"body",**layout})
    for title,xy in zip(titles,layout["positions"]):put(im,xy,title,fonts,layout["font_size"],en,True,"#fff8ee")
    d.rectangle((30,535,1050,1395),fill=(0,0,0,0))
    put(im,(72,1432),row["source_credit"],fonts,27,en,color="#c0c9d7")
    put(im,(72,1482),row.get("fact_credit",""),fonts,26,en,color="#ffad83")
    size=53 if en else 56
    while True:
        try:lines=wrap(row["text"],fonts,size,926,en,row.get("protect_terms",[]))
        except ValueError:lines=["overflow"]*4
        if len(lines)<=3:break
        size-=2
        if size<42:raise ValueError("Caption exceeds three readable lines; edit the sentence.")
    y=1740-len(lines)*(size+17);f=fnt(fonts,size,en,True)
    for line in lines:
        d.text(((W-f.getlength(line))/2,y),line,font=f,fill="white",stroke_width=2,stroke_fill=BG);y+=size+17
    put(im,(72,1804),row.get("footer_credit",row["source_credit"]),fonts,24,en,color="#929faf")
    d.rectangle((70,1870,1010,1876),fill="#252e3c")
    d.rectangle((70,1870,70+round(940*progress),1876),fill="#ff7b3e")
    return im,lines,size

def cover(root,cfg,fonts,en,out):
    c=cfg["cover"];label="en" if en else "zh"
    if not c.get("photo") or not c.get("credit") or not c.get("title_"+label):
        raise ValueError("Provide a verified cover photo, title and photo credit.")
    photo=Image.open(path(root,c["photo"])).convert("RGB")
    if c.get("crop"):photo=photo.crop(tuple(c["crop"]))
    im=base(fonts,cfg.get("watermark",""),en)
    titles=c["title_"+label].split("\n")
    layout=fit_headline(titles,lambda n:fnt(fonts,n,en,True),video_top=650,
                        anchor=(66,280),line_spacing=150,initial_size=104 if en else 140,
                        min_size=54,max_width=934,tag_bottom=155)
    HEADER_CHECKS.append({"row_id":"cover","kind":"cover",**layout})
    for title,xy in zip(titles,layout["positions"]):put(im,xy,title,fonts,layout["font_size"],en,True,"#fff8ee")
    im.paste(ImageOps.fit(photo,(950,940)),(66,650))
    put(im,(72,1732),c.get("subtitle_"+label,""),fonts,39 if en else 47,en,True)
    put(im,(72,1821),c["credit"],fonts,25,en,color="#929faf")
    im.convert("RGB").save(out,quality=96)

def stamp(sec):
    n=round(sec*1000);h,n=divmod(n,3600000);m,n=divmod(n,60000);s,n=divmod(n,1000)
    return f"{h:02}:{m:02}:{s:02},{n:03}"

def make_audio(root,rows,sounds,work,music):
    cursor=1/FPS;timed=[];raw=work/"narration-raw.wav"
    with wave.open(str(raw),"wb") as target:
        target.setnchannels(1);target.setsampwidth(2);target.setframerate(SR)
        target.writeframes(b"\x00\x00"*round(SR/FPS))
        for i,row in enumerate(rows):
            sound=sounds[row["id"]];pcm=work/(row["id"]+".wav")
            run(["-i",path(root,sound["file"]),"-ar",SR,"-ac",1,"-c:a","pcm_s16le",pcm])
            with wave.open(str(pcm)) as source:data=source.readframes(source.getnframes())
            duration=len(data)/2/SR;gap=.24 if i<len(rows)-1 else .8
            span=math.ceil((duration+gap)*FPS)/FPS
            target.writeframes(data);target.writeframes(b"\x00\x00"*(round(span*SR)-len(data)//2))
            timed.append({**row,"start":cursor,"end":cursor+duration,"scene_end":cursor+span});cursor+=span
    if timed[0]["end"]>3:raise ValueError("Opening hook is longer than three seconds; shorten it before rendering.")
    voice=work/"narration.wav";mix=work/"mix.wav"
    run(["-i",raw,"-af","loudnorm=I=-16:TP=-1.5:LRA=7","-ar",SR,"-ac",1,voice])
    if music:
        filt="[0:a]asplit=2[v][key];[1:a]volume=0.65[bed];[bed][key]sidechaincompress=threshold=0.01:ratio=12:attack=8:release=350[duck];[v][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89:level=false[a]"
        run(["-i",voice,"-stream_loop",-1,"-i",path(root,music),"-filter_complex",filt,"-map","[a]","-ar",SR,"-ac",2,"-t",cursor,mix])
    else:run(["-i",voice,"-ac",2,mix])
    return timed,cursor,mix

def main():
    HEADER_CHECKS.clear()
    p=argparse.ArgumentParser();p.add_argument("project");p.add_argument("--language",choices=["zh","en"],required=True)
    p.add_argument("--version",default="v1")
    p.add_argument("--preview-720p",action="store_true",help="Generate an optional lightweight preview only when requested; master remains 1080x1920.")
    a=p.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+",a.version):p.error("Use a simple version identifier.")
    root=Path(a.project).resolve();cfg=read(root/"project.json");lang=a.language;en=lang=="en"
    out=root/"outputs";work=root/"work"/f"render-{lang}-{a.version}"
    if work.exists() or (out/f"{lang}-{a.version}.mp4").exists():p.error("Version exists; choose a new version.")
    rows=read(root/f"work/sentences-{lang}.json")
    if not rows or len({r["id"] for r in rows})!=len(rows):raise ValueError("Provide nonempty sentences with unique IDs.")
    known={s["source_id"] for s in read(root/"research/sources.json")}
    sounds={r["id"]:r for r in read(root/f"audio/tts-{lang}/manifest.json")}
    if set(sounds)!=set(r["id"] for r in rows):raise ValueError("TTS IDs must match sentences.")
    intervals=[]
    for row in rows:
        if not re.fullmatch(r"[A-Za-z0-9_-]+",row["id"]):raise ValueError("Unsafe sentence ID.")
        if not row.get("sources") or not set(row["sources"])<=known:raise ValueError("Sentence source references missing.")
        if not row.get("clips"):raise ValueError("Every sentence needs corresponding media.")
        for clip in row["clips"]:
            file=path(root,clip["file"]).resolve()
            if not file.is_file() or clip["duration"]<=0:raise ValueError("Media missing or invalid duration.")
            if clip["kind"]=="film":
                lo=clip["start"];hi=lo+clip["duration"]
                if any(f==file and max(lo,l)<min(hi,h)-.001 for f,l,h in intervals):raise ValueError("Repeated footage interval.")
                intervals.append((file,lo,hi))
            elif clip["kind"]!="evidence":raise ValueError("Unsupported media kind.")
    fonts=choose_fonts(root,cfg);out.mkdir(exist_ok=True);work.mkdir()
    timed,total,mix=make_audio(root,rows,sounds,work,cfg.get("music"))
    low,high=cfg.get("target_duration_range",[180,300])
    if not low<=total<=high:raise ValueError("Narration duration outside requested range; revise script.")
    cov=out/f"{lang}-{a.version}-cover.jpg";cover(root,cfg,fonts,en,cov)
    first=work/"first.mp4";run(["-loop",1,"-i",cov,"-vf","scale=in_range=pc:out_range=tv,format=yuv420p","-frames:v",1,"-r",FPS,"-c:v","libx264","-color_range","tv","-threads",2,first])
    files=[first];shots=[];captions=[]
    for i,row in enumerate(timed):
        im,lines,size=layer(row,fonts,cfg.get("watermark",""),en,(i+1)/len(timed));overlay=work/(row["id"]+".png");im.save(overlay)
        span=row["scene_end"]-row["start"];weights=sum(c["duration"] for c in row["clips"]);cursor=row["start"]
        for j,clip in enumerate(row["clips"]):
            frames=round(span*FPS*clip["duration"]/weights) if j<len(row["clips"])-1 else round((row["scene_end"]-cursor)*FPS)
            if frames<1:raise ValueError("Empty shot.")
            duration=frames/FPS;file=path(root,clip["file"]);crop=clip.get("crop")
            prep=("crop="+":".join(str(n) for n in [crop[2],crop[3],crop[0],crop[1]])+",") if crop else ""
            inputs=["-ss",clip["start"],"-t",clip["duration"],"-i",file] if clip["kind"]=="film" else ["-loop",1,"-i",file]
            speed=clip["duration"]/duration if clip["kind"]=="film" else 1
            if clip["kind"]=="film" and not .5<=speed<=1.8:raise ValueError("Extreme playback speed; improve shot coverage.")
            filt=f"[0:v]{prep}setpts=(PTS-STARTPTS)/{speed:.9f},split[fg][b];[b]scale=1020:860:force_original_aspect_ratio=increase,crop=1020:860,gblur=sigma=25,eq=brightness=-0.19:saturation=0.55[blur];[fg]scale=1020:860:force_original_aspect_ratio=decrease[front];[blur][front]overlay=(W-w)/2:(H-h)/2,pad=1080:1920:30:535:color=0x070b13[bg];[bg][1:v]overlay=0:0,setsar=1,format=yuv420p[v]"
            dst=work/f"{row['id']}-{j}.mp4"
            run([*inputs,"-loop",1,"-i",overlay,"-filter_complex",filt,"-map","[v]","-t",duration,"-r",FPS,"-an","-c:v","libx264","-preset","veryfast","-crf",18,"-color_range","tv","-threads",3,dst])
            files.append(dst);shots.append({**clip,"sentence_id":row["id"],"timeline_start":cursor,"timeline_duration":duration});cursor+=duration
        captions.append({"start":row["start"],"end":row["scene_end"]-.08,"text":"\n".join(lines),"font_size":size})
        print(f"Rendered {lang} sentence {i+1}/{len(timed)}",flush=True)
    playlist=work/"concat.txt"
    playlist.write_text("\n".join("file '"+f.name+"'" for f in files),encoding="utf-8")
    silent=work/"silent.mp4";run(["-f","concat","-safe",0,"-i",playlist,"-c","copy",silent])
    final=out/f"{lang}-{a.version}.mp4";preview=out/f"{lang}-{a.version}-720p.mp4"
    # Cover and body are explicitly encoded in the same limited color range.
    run(["-i",silent,"-i",mix,"-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-b:a","192k","-t",total,"-movflags","+faststart",final])
    verify_master_resolution(final)
    if a.preview_720p:
        run(["-i",final,"-vf","scale=720:1280","-c:v","libx264","-preset","veryfast","-crf",23,"-threads",3,"-c:a","aac","-b:a","128k","-movflags","+faststart",preview])
    save(work/"headline-layout.json",HEADER_CHECKS)
    save(work/"timed.json",timed);save(work/"shots.json",shots);save(work/"captions.json",captions)
    (out/f"{lang}-{a.version}.srt").write_text("\n\n".join(f"{i+1}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}" for i,c in enumerate(captions))+"\n",encoding="utf-8")
    print(f"Complete: {lang}-{a.version}; duration={total:.3f}s")

if __name__=="__main__":main()
