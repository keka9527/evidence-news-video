"""Fail-closed, allowlisted packaging; reports never echo suspect values."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path

ALLOWED_ROOT={"SKILL.md","LICENSE","THIRD_PARTY_NOTICES.md","README.md","requirements.txt",".gitignore"}
ALLOWED_DIR={"agents","references","scripts"}
ALLOWED_SUFFIX={".md",".py",".mjs",".yaml",".yml",".json"}
BLOCKED_PART={".git",".secrets","node_modules","__pycache__",".pytest_cache","outputs","qa","work","audio"}
RULES=[
    ("personal-home-path",r"(?i)(?:[A-Z]:[\\/](?:Users|Documents and Settings)[\\/][^\s\"']+|/(?:Users|home)/[^/\s]+/)"),
    ("email-address",r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    ("private-key",r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ("bearer-value",r"(?i)Bearer\s+[A-Za-z0-9._-]{20,}"),
    ("token-prefix",r"\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b"),
    ("assigned-secret",r"""(?ix)(?:api[_-]?key|access[_-]?(?:token|key)|app[_-]?(?:secret|id)|account[_-]?id|user[_-]?id|uid|authorization|password)["']?\s*[:=]\s*["']([A-Za-z0-9+/=_-]+)["']"""),
    ("phone-number",r"(?<!\w)(?:\+86[ -]?)?1[3-9]\d{9}(?!\w)")
]

def audit(root,forbid=()):
    accepted=[];excluded=[];findings=[]
    for f in sorted(root.rglob("*")):
        if not f.is_file():continue
        rel=f.relative_to(root);name=rel.as_posix()
        if f.is_symlink():findings.append({"file":name,"rule":"symlink"});continue
        ok=(len(rel.parts)==1 and rel.name in ALLOWED_ROOT) or (len(rel.parts)>1 and rel.parts[0] in ALLOWED_DIR and f.suffix.lower() in ALLOWED_SUFFIX)
        blocked=any(x in BLOCKED_PART for x in rel.parts) or f.name=="LOCAL_POLICY.md" or ".env" in f.name.lower()
        if not ok or blocked:excluded.append(name);continue
        try:body=f.read_text(encoding="utf-8")
        except UnicodeError:findings.append({"file":name,"rule":"not-utf8-text"});continue
        for rule,pattern in RULES:
            if re.search(pattern,body):findings.append({"file":name,"rule":rule})
        for token in forbid:
            if token and token.casefold() in body.casefold():findings.append({"file":name,"rule":"forbidden-identity-token"})
        accepted.append(f)
    if not (root/"SKILL.md").is_file():findings.append({"file":"SKILL.md","rule":"missing-entrypoint"})
    return accepted,{"passed":not findings,"included_files":[f.relative_to(root).as_posix() for f in accepted],"excluded_files":excluded,"findings":findings,"limitations":"Pattern scan plus manual review; does not guarantee recognition of all personal information."}

def main():
    p=argparse.ArgumentParser();p.add_argument("--skill-dir",required=True);p.add_argument("--output",required=True)
    p.add_argument("--report");p.add_argument("--forbid-token",action="append",default=[])
    a=p.parse_args();root=Path(a.skill_dir).resolve();dest=Path(a.output).resolve()
    if dest.is_relative_to(root):p.error("Archive must be outside the skill folder.")
    if dest.exists():p.error("Archive exists; choose a new filename.")
    files,report=audit(root,a.forbid_token)
    report_path=Path(a.report) if a.report else dest.with_suffix(".audit.json")
    if report_path.resolve().is_relative_to(root):p.error("Audit report must be outside the skill folder.")
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if not report["passed"]:raise SystemExit("Privacy audit rejected packaging; inspect relative filenames and rule IDs in report.")
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temp,"w",zipfile.ZIP_DEFLATED) as z:
            for f in files:z.writestr(f.relative_to(root).as_posix(),f.read_bytes())
        with zipfile.ZipFile(temp) as z:
            if z.testzip() is not None:raise RuntimeError("ZIP integrity failed.")
            if sorted(z.namelist())!=sorted(report["included_files"]):raise RuntimeError("ZIP member mismatch.")
            for info in z.infolist():
                if info.filename.startswith("/") or ".." in Path(info.filename).parts:raise RuntimeError("Unsafe ZIP path.")
                body=z.read(info).decode("utf-8")
                if any(re.search(pattern,body) for _,pattern in RULES) or any(t and t.casefold() in body.casefold() for t in a.forbid_token):raise RuntimeError("ZIP privacy recheck failed.")
        temp.replace(dest)
    finally:
        if temp.exists():temp.unlink()
    report.update(archive_integrity="pass",sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),archive_files=len(files))
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Privacy audit and ZIP recheck passed;",len(files),"files packaged.")

if __name__=="__main__":main()
