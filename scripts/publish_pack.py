"""Validate researched posting data and emit copy-ready platform packages."""
import argparse,json,re
from pathlib import Path
from urllib.parse import urlparse

PLATFORMS={"videohao":"视频号","douyin":"抖音","xiaohongshu":"小红书"}
STATUSES={"verified_platform":"平台热点已核实","verified_aggregator":"热榜聚合记录已交叉核查（官方未复核）","topic_only":"普通主题标签","unverified":"未核实"}

def load(p):return json.loads(p.read_text(encoding="utf-8"))
def local(root,value):return Path(value) if Path(value).is_absolute() else root/value

def validate(root,data):
    for key in ["title","language","checked_at","fact_summary","verification_note","evidence","platforms"]:
        if not data.get(key):raise ValueError("Missing publish field: "+key)
    for key in ["video_file","cover_file"]:
        if not data.get(key) or not local(root,data[key]).is_file():raise ValueError("Missing delivery file: "+key)
    if data.get("preview_file") and not local(root,data["preview_file"]).is_file():raise ValueError("Missing delivery file: preview_file")
    evidence={e["id"]:e for e in data["evidence"]}
    if len(evidence)!=len(data["evidence"]):raise ValueError("Evidence IDs must be unique.")
    for e in evidence.values():
        u=urlparse(e["url"])
        if u.scheme not in ["http","https"] or not u.hostname:raise ValueError("Evidence needs a valid public URL.")
        if not e.get("checked_at"):raise ValueError("Evidence needs a check timestamp.")
    if set(data["platforms"])!=set(PLATFORMS):raise ValueError("Provide all three platforms.")
    copies=[]
    for platform,content in data["platforms"].items():
        titles=[content.get("recommended_title",""),*content.get("alternative_titles",[])]
        if len(titles)!=3 or len(set(titles))!=3 or not all(t.strip() for t in titles):raise ValueError("Each platform needs one recommended and two distinct alternative titles.")
        if not content.get("copy") or not content.get("recommendation_reason"):raise ValueError("Each platform needs recommended copy and rationale.")
        copies.append(content["copy"].strip())
        tags=content.get("tags",[])
        if not 5<=len(tags)<=8 or len({t["text"] for t in tags})!=len(tags):raise ValueError("Need five to eight distinct tags per platform.")
        for tag in tags:
            if not tag.get("text") or "#" in tag["text"] or re.search(r"[\s\r\n]",tag["text"]):raise ValueError("Use plain, nonempty tag names without spaces or #.")
            status=tag.get("status")
            if status not in STATUSES:raise ValueError("Unknown tag verification status.")
            if status=="unverified":raise ValueError("Remove unverified hotspot labels or explicitly reclassify as topic_only.")
            refs=tag.get("evidence",[])
            if not set(refs)<=set(evidence):raise ValueError("Unknown tag evidence reference.")
            if status=="verified_platform":
                if tag.get("origin_platform")!=platform or not any(evidence[e]["kind"]=="platform_hot" for e in refs):raise ValueError("Platform hotspots require direct target-platform evidence.")
            if status=="verified_aggregator":
                sites={urlparse(evidence[e]["url"]).hostname for e in refs if evidence[e]["kind"]=="aggregator"}
                if len(sites)<2 or tag.get("origin_platform")!=platform:raise ValueError("Aggregator status needs two sites for this platform.")
            if status.startswith("verified_") and not tag.get("checked_at"):raise ValueError("Verified topics need a check timestamp.")
    if len(set(copies))!=3:raise ValueError("Write different copy for each platform.")
    return evidence

def cell(s):return str(s).replace("|","｜").replace("\n"," ")

def render(data,evidence):
    lines=["# 平台发布包","",f"主题：{data['title']}",f"版本：{data['language']}；使用已确认成片，不重新制作视频。",f"核查时间：{data['checked_at']}","",
           f"成片：{data['video_file']}",f"预览：{data.get('preview_file') or data.get('preview_note','本次发布包未附预览。')}",f"封面：{data['cover_file']}","",
           "状态：仅完成发布准备，尚未执行上传或公开发布。","","> "+data["verification_note"],""]
    lines+=["## 事实口径",""]+["- "+f for f in data["fact_summary"]]+[""]
    for platform,label in PLATFORMS.items():
        c=data["platforms"][platform];tags=" ".join("#"+t["text"] for t in c["tags"])
        lines.extend([f"## {label}","","### 推荐标题（直接用）","",c["recommended_title"],"",
                      "### 推荐文案及话题（整段可复制）","",c["copy"],"",tags,"",
                      "### 备用标题","",*["- "+t for t in c["alternative_titles"]],"",
                      "推荐理由："+c["recommendation_reason"],"","### 话题核查说明","",
                      "| 话题 | 身份 | 核实平台 | 证据 |","|---|---|---|---|"])
        for t in c["tags"]:
            refs=", ".join(t.get("evidence",[])) or "主题推荐，不声称热度"
            origin=PLATFORMS.get(t.get("origin_platform"),t.get("origin_platform","—")) or "—"
            lines.append(f"| #{cell(t['text'])} | {STATUSES[t['status']]} | {cell(origin)} | {cell(refs)} |")
        verified=sum(t["status"]=="verified_platform" for t in c["tags"])
        lines+=["",f"直接核实的本平台热点：{verified}个。普通主题标签不表示平台热榜已存在同名话题。",""]
    lines+=["## 核查来源（发布说明，非文案区）",""]
    for eid,e in evidence.items():
        lines.append(f"- {eid}：[{' '.join(e['title'].split())}]({e['url']})；核查：{e['checked_at']}。"+e.get("note",""))
    lines+=["","素材来源署名不等于再发布授权；权利及原片清晰度说明沿用成片交付说明。",""]
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser();p.add_argument("project");p.add_argument("--input",default="work/publish-content.json")
    p.add_argument("--output",default="平台发布包.md");a=p.parse_args();root=Path(a.project).resolve()
    data=load(local(root,a.input));evidence=validate(root,data);out=local(root,a.output)
    if out.exists():p.error("Publish package exists; choose a new filename to preserve the original.")
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(render(data,evidence),encoding="utf-8")
    print("Publish package ready for all three platforms. No upload or account operation performed.")

if __name__=="__main__":main()
