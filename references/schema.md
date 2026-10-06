# 项目格式

目录：project.json，research/sources.json，assets/source，work/sentences-zh.json，work/sentences-en.json，audio/tts-zh/manifest.json，audio/tts-en/manifest.json，outputs，qa。相对路径从项目根解析。

project.json：

    {
      "title": "用户主题",
      "watermark": "", "author_name": "",
      "languages": ["zh"],
      "target_duration_range": [115, 125],
      "font": null, "font_bold": null, "font_en": null,
      "music": null,
      "cover": {
        "photo": null, "crop": null,
        "title_zh": "", "title_en": "",
        "subtitle_zh": "", "subtitle_en": "", "credit": ""
      }
    }

每种语言的 sentences 为数组。可选 footer_credit 为底部短署名，protect_terms 为英文需要保持同一行的人名/赛事名列表：

    {
      "id": "s001",
      "text": "完整一句口播。",
      "title": "画面标题",
      "tag": "赛事或事件",
      "source_credit": "媒体 / 日期",
      "fact_credit": "事实来源：来源编号",
      "sources": ["V1", "S1"],
      "clips": [
        {"kind": "film", "file": "assets/source/source.mp4",
         "start": 10.0, "duration": 5.0,
         "crop": [0, 40, 640, 320], "note": "对应本句动作"}
      ]
    }

film 的 start/duration 指原片区间。evidence 使用 file、duration及可选crop；实际阅读时长来自该句声音。每句至少一个相关素材，sources 对应来源编号。渲染器检查区间重用，执行者检查crop与语义。多段按区间长度比例分配句子时间，控制合理速度；极慢/极快时补素材，不凑时长。

来源项包含 source_id、title、url、date、author、rights、file及用途。未确定授权时 rights 诚实注明，来源署名不能写成已获许可。

人物纪实可另存work/shot-map.json及逐句素材与镜头表.md，按[人物流程](profile-documentary.md)记录成片区间、原片区间、人物、事件年份、动作及匹配限制。此表是编辑与审核记录，不宣称既有render_news.py自动解析这些额外字段。只换画面时记录已满意音轨及字幕的基准版本和最终校验结果；项目专用渲染器不直接复制进通用Skill。

旁白 manifest 数组字段：id、file、duration、words、language；不包含服务标识、音色账号或凭据。manifest和实际音频属于项目工作数据，不进入分享Skill。目录中的tts仅为兼容既有工程的名称，本包不生成配音。

连续旁白分组示例，放在work/tts-groups-zh.json供包外音频准备过程参考：

    [{"id":"g001", "text":"完整一句口播。第二句口播。", "sentence_ids":["s001","s002"]}]

准备音频时的文本应等于这些句子tts字段（未指定时text字段）的串联；id仅字母数字、连字符和下划线。prepare_narration.py默认写audio/tts-zh/manifest.json，已有版本拒绝覆盖，可用--out-dir另存。新manifest保持逐句id、相对file、duration、words，并标continuous_group_cut=true、post_tempo=1.0。

render_news.py可选配置：target_duration_seconds为精确时长；visual字典可改background、headline_color、accent_color、caption_color、headline_size、tag_size、source_size、caption_size；默认值见visual.md。每句可增加visual_label（如“历史比赛画面 · 排名解读”），evidence_card为heading、lines（最多3行）、note（注明整理/转述及来源）。卡片不自动核查事实，不代替推文原截图与高亮翻译流程。


`author_name`为可选作者元数据，初始化可用`--author-name "你的公开署名"`；默认留空。执行者据此填写作者卡、标题或来源行，它不授权替换现有配音，也不表示渲染器自动改写口播。分享Skill不填使用者的真实名称。

标题边界：`render_news.py`的visual还支持`headline_y`（默认245）、`headline_line_spacing`（默认100）、`headline_min_gap`（默认30，1080px宽）。按实际字体适配；`headline_min_gap`不能小于30。包内画面上沿为535，封面照片上沿为650；自定义渲染器传自己的真实上沿。标题适配结果写入`work/render-语言-版本/headline-layout.json`，不随Skill分享。
