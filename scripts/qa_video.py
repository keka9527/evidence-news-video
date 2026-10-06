"""Decode a film and extract scheduled inspection frames; no STT/watch claim."""
import argparse,json,subprocess
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument("video");p.add_argument("--out-dir",required=True)
    p.add_argument("--shots");p.add_argument("--captions");a=p.parse_args()
    video=Path(a.video);out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    meta=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,color_range","-of","json",str(video)],text=True))
    check=subprocess.run(["ffmpeg","-v","error","-threads","2","-i",str(video),"-f","null","-"],capture_output=True)
    if check.returncode or check.stderr.strip():raise RuntimeError("Full decode failed.")
    length=float(meta["format"]["duration"]);times={0,max(0,length-.1)}
    if a.shots:
        for shot in json.loads(Path(a.shots).read_text(encoding="utf-8")):times.add(shot["timeline_start"]+shot["timeline_duration"]/2)
    if a.captions:
        for caption in json.loads(Path(a.captions).read_text(encoding="utf-8")):
            times.update([max(0,caption["start"]-.1),min(length-.04,caption["start"]+.04)])
    samples=[]
    for i,t in enumerate(sorted(times)):
        target=out/f"frame-{i:03}.jpg"
        r=subprocess.run(["ffmpeg","-v","error","-y","-threads","2","-ss",str(t),"-i",str(video),"-frames:v","1",str(target)],capture_output=True)
        if r.returncode or not target.is_file():raise RuntimeError("Frame extraction failed.")
        samples.append({"time":t,"file":target.name})
    detect=subprocess.run(["ffmpeg","-hide_banner","-threads","2","-i",str(video),"-vf","blackdetect=d=0.3:pix_th=0.04:pic_th=0.99","-af","silencedetect=noise=-44dB:d=2","-f","null","-"],capture_output=True,text=True,encoding="utf-8",errors="replace")
    if detect.returncode:raise RuntimeError("Black/silence detection failed.")
    events=[line for line in detect.stderr.splitlines() if any(x in line for x in ["black_start:","silence_start:","silence_end:"])]
    report={"metadata":meta,"full_decode":True,"sampled_frames":samples,"black_silence_events":events,"human_continuous_watch":False,"stt_done":False,"note":"Review extracted images and listen separately. These steps do not constitute a human watch."}
    (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Decode passed; extracted",len(samples),"frames. Review images and audio before delivery.")

if __name__=="__main__":main()
