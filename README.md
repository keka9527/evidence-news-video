# evidence-news-video

基于可核查来源和真实素材制作竖版新闻、赛事解读及人物纪实视频的Agent Skill。公开准备版：**1.2.5-public**。

## 功能

- 1080×1920、9:16、30fps；一条作品一个交付文件夹。
- 口播逐句去重、删废话，按人物成长阶段和动作匹配素材。
- 两行标题留在深色标题区，真实字体边界与画面至少留30px间隔。
- 整句字幕、来源标注、镜头区间去重和抽帧检查。
- 本地旁白切分、字幕时间轴、音乐自动压低和满意音轨保护。
- 视频号、抖音、小红书各自的标题、文案和已核查/普通话题发布包。

## 安装

将仓库中的整个Skill目录放入宿主的skills目录，例如`~/.codex/skills/evidence-news-video/`；确认SKILL.md直接位于该目录内。使用时指定`$evidence-news-video`与主题、来源或用户素材。

需要Python 3.10+、Pillow、FFmpeg/ffprobe与可用中文字体。Python依赖见requirements.txt。STT使用宿主提供的工具或模型；本仓库不附带识别模型或配音生成服务。依赖不足时说明缺口，不自动安装或购买服务。

## 配音输入

使用者提供旁白音频，或在包外准备音频与真实时间戳。接入方法见[声音说明](references/audio.md)与[项目格式](references/schema.md)。没有旁白输入时，本公开版不能直接生成带解说成片；不要将脚本、文案或提交任务称为成片。

    python scripts/init_project.py ./project --title "用户主题" --watermark "@your-brand" --author-name "你的公开署名"
    python scripts/prepare_narration.py ./project --language zh --groups audio/input/groups.json
    python scripts/render_news.py ./project --language zh --version v1
    python scripts/qa_video.py ./project/outputs/zh-v1.mp4 --out-dir ./project/qa/zh-v1
    python scripts/publish_pack.py ./project --input work/publish-content.json --output 平台发布包.md

这些命令之间需要按工作流填好事实来源、逐句稿件、真实素材、封面和旁白输入，不能在空项目中直接渲染。

## 隐私与发布

个人水印、姓名、输出目录等只写入本机LOCAL_POLICY.md或具体项目；本仓库不包含个人配置、凭据、样片、成品、下载缓存或旧版本。准备、渲染和发布文案不等于实际上传授权，本Skill不执行公开发布。

版权要求见[第三方声明](THIRD_PARTY_NOTICES.md)。LICENSE保留引用的上游代码所需的MIT声明；新增内容未另行指定整仓库授权。公开可见不等于允许任意再分发。素材来源署名也不等于获得媒体片段的再发布许可。
