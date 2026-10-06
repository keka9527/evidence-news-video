"""Create an empty, portable project without overwriting existing work."""
import argparse,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("project");p.add_argument("--title",required=True)
    p.add_argument("--watermark",default="")
    p.add_argument("--author-name",default="")
    a=p.parse_args();root=Path(a.project)
    root.mkdir(parents=True,exist_ok=True)
    if any(root.iterdir()):p.error("Project must be empty; resume existing files separately.")
    for folder in ["research","assets/source","work","audio/tts-zh","audio/tts-en","outputs","qa"]:
        (root/folder).mkdir(parents=True,exist_ok=True)
    config={"title":a.title,"watermark":a.watermark,"author_name":a.author_name,"languages":["zh"],"target_duration_range":[115,125],"font":None,"font_bold":None,"font_en":None,"music":None,"cover":{"photo":None,"crop":None,"title_zh":"","title_en":"","subtitle_zh":"","subtitle_en":"","credit":""}}
    (root/"project.json").write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")
    for file in ["research/sources.json","work/sentences-zh.json","work/sentences-en.json"]:
        (root/file).write_text("[]\n",encoding="utf-8")
    print("Project initialized. No credentials or media copied.")

if __name__=="__main__":main()
