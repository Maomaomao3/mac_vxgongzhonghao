# 公众号 AI Studio

本地 macOS PySide6 应用：文章 URL → 正文解析 → AI 独立重构 → Pexels 配图 → 编辑预览 → 官方 API 草稿。

## 架构与依赖

- `config.py`：顶部全局默认配置，首次启动创建用户配置 JSON。
- `crawler.py`：requests + BeautifulSoup，仅解析正文，清除明确广告节点；验证页提示使用手动正文。
- `ai.py`：DeepSeek/OpenAI Chat Completions 兼容接口，指定 SI 主题，禁止编造实时数据。
- `images.py`：Pexels 搜索、署名元数据、Pillow 图片压缩。
- `rendering.py`：Markdown 转 HTML、bleach 清洗、微信内联样式。
- `wechat.py`：stable_token 缓存、永久封面、正文图片、draft/add。
- `app.py`：PySide6 界面与 QThread 工作线程，进度、日志、编辑预览、同步。
- `tests/test_core.py`：解析失败、广告清理、URL、HTML 清洗、权限、token 缓存测试。

`requirements.txt` 列出全部运行和打包依赖。建议 Python 3.13。

## 安装与启动

```bash
cd '/path/to/wechat-ai-studio'
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

始终使用 `.venv/bin/python -m pip`，避免 Conda 的 python 与系统 pip 错配。
点击“打开配置文件”，填写并保存 JSON，每次执行任务自动重新加载：

```json
{
  "AI_BASE_URL": "https://api.deepseek.com",
  "AI_MODEL": "deepseek-chat",
  "AI_API_KEY": "",
  "PEXELS_API_KEY": "",
  "WECHAT_APP_ID": "",
  "WECHAT_APP_SECRET": "",
  "IMAGE_COUNT": 2,
  "AUTHOR": ""
}
```

OpenAI 可将 AI_BASE_URL 改为 `https://api.openai.com/v1`，AI_MODEL 填账户可用模型。
模型名称需要按供应商当前支持情况填写。无联网检索，生成内容不代表已经核验最新趋势。

配置路径：`~/Library/Application Support/WeChatAIStudio/config.json`（首次创建权限 600）。
也可在首次运行前修改 config.py 顶部全局变量；已有 JSON 的值优先。
配置和输出在 .app 外部，升级应用不覆盖它们。密钥不显示在日志中。

Pexels Key：在 https://www.pexels.com/api/ 申请。图片依 Pexels License 免费使用，非“无版权”；保留摄影师及来源链接。
微信 AppID/AppSecret：从自己公众号后台的开发配置获取；确认具备素材/草稿权限，并配置调用机器的公网出口 IP 白名单。
官方 access_token 自动获取，与后台网页 token/Cookie 无关；本项目不需要网页登录 Cookie。

## 使用

1. 粘贴微信文章 URL，点击生成。参考正文将发给配置的模型服务。
2. 如遇验证页，在浏览器自行阅读，将正文粘贴到备用输入框再生成；合理请求头不保证绕过验证。
3. 在左侧编辑 Markdown，在右侧查看含图片和署名的预览。配图关键词由文章标题生成。
4. 点击同步才会上传封面、正文图片并创建草稿；不会调用发布接口。
5. 在公众号后台核对事实、版权、排版后人工发布。

输出目录：`~/Library/Application Support/WeChatAIStudio/outputs/<任务ID>/`。
article.md 保存生成/同步时的正文，bundle.json 保存来源和图片信息；图片下载到任务目录。
已有同步记录时阻止再次提交。失败后可能留下永久素材；先检查后台草稿，确认未创建后删除该任务的 sync_attempt.json 才能重试。
QTextBrowser 预览与微信最终排版可能有差异，须在后台检查。
不保证可靠识别所有软广告；只移除明确 DOM 广告节点。

## 测试

```bash
.venv/bin/python -m unittest discover -s tests -v
```

无密钥单元测试不代表外部 API 已通过实测。

## 打包 macOS .app

在目标 Mac 架构的 Python 环境打包：

```bash
.venv/bin/python -m PyInstaller --noconfirm --clean --windowed --name WeChatAIStudio --osx-bundle-identifier local.wechat.ai.studio app.py
open dist/WeChatAIStudio.app
```

产物为 `dist/WeChatAIStudio.app`。Apple Silicon / Intel 应分别使用对应架构构建。
自用包未进行 Developer ID 签名和公证；向其他 Mac 分发需使用自己的 Apple Developer 身份签名、公证。
不把 config.json 或密钥打进应用。不要从应用包内部修改配置。

## 参考文档

- https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create
- https://api-docs.deepseek.com/api/create-chat-completion/
- https://www.pexels.com/api/documentation/
- https://www.pexels.com/legal-pages/license/
- https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html

本次微信官方文档页面读取失败，接口实现仍需用具有权限的真实公众号验证，不宣称已完成线上联调。

## 本次本地验证

- 2026-11-11：独立虚拟环境安装成功（Python 3.14）。
- 7 项核心测试通过，包含模拟微信草稿提交与图片 URL 替换。
- Qt offscreen 窗口构建/事件循环启动检查通过；未进行真实桌面视觉验收。
- 未使用真实密钥进行 AI、Pexels、微信联调；未执行 .app 构建。

## 长文与无图库密钥模式（更新）

正文超过 40000 字符时，不再拒绝读取：按最多 12000 字符切分，逐段调用 AI 提炼观点、事实与不确定性，再根据汇总笔记重构。分段保留全部输入字符，摘要属于有损提炼；长文会增加调用次数、耗时与费用。多轮摘要未有效缩短时会明确停止。

PEXELS_API_KEY 留空时跳过自动配图，文章仍可生成和预览。点击“选择本地配图”导入 1～3 张有权使用的图片，第一张作封面；至少有一张图后才启用同步按钮。本地图片不会被标为 Pexels 来源。

更新后 12 项测试通过，另通过无图文章 GUI 预览检查；没有执行真实 AI 付费请求。

## 原文图片与零配图配置（更新）

`IMAGE_SOURCE` 默认 `original`：从正文 img 的 data-src/src 提取微信图片链接、去重并下载，最多取 IMAGE_COUNT 张可用图片；跳过小图标。保存原始文件和压缩上传版，GIF 上传使用静态图。来源署名为参考文章，不标记为 Pexels。图片可能包含二维码或软广告，使用前仍需查看预览；重构正文与原图不一定语义匹配。

`IMAGE_COUNT: 0` 现在合法，表示不自动配图。若需要原图，设为 1～3；保留用户现有 0 配置，不会擅自覆盖。`IMAGE_SOURCE` 可为 original/pexels/none。
“打开配置文件”不再依赖配置校验，因此配置错误也能打开修正。纯文本备用输入没有原图元数据；抓取被验证拦住时仍需自行补图。

## 取消图片数量配置（最新）

不再需要 IMAGE_COUNT，已有配置中的该字段会被忽略（包括原来的 0）。IMAGE_SOURCE=original 下载全部识别到的可用原文图片，仍会去重、跳过小图标和失败项；并不保证覆盖背景图等未识别图片。IMAGE_SOURCE=none 才表示关闭自动配图；pexels 模式默认两张。原图较多时下载、上传耗时增加，草稿仍受微信正文大小限制。

## 本地审核后发表

生成并编辑 → 同步草稿 → 审核预览 → 点击“审核通过并发表”。按钮点击即批准当前版本，不再弹出第二次确认。
程序绑定正文、来源和图片内容哈希以及公众号 AppID，并在提交前检查后台草稿是否被修改。编辑正文会使待审版本失效，需要重新同步；更换公众号也会阻止旧草稿发表。
发表调用 freepublish/submit，随后最多查询 12 次（间隔 5 秒）；publish_status=0 才显示成功和文章链接。仍在处理时可点击“查询发表结果”，仅查询已有任务。提交结果未知时禁止自动重复提交，请先在微信后台核对。
任务目录保存 review_record.json 与 publish_<版本哈希>.json。重启后的旧任务目前需到微信后台查询，界面尚不提供历史任务载入。
只发表文章，不调用粉丝群发接口。账号必须具有发表权限，AppID/AppSecret 不代表自动拥有权限。
本地模拟测试覆盖成功、重复操作、版本变化、后台修改、超时与平台拒绝；没有真实调用发表接口。微信官方文档页面本次仍无法读取，需真实账号联调确认权限与行为。

## 原文展示与技术结构改写（最新）

新增“读取原文（不调用 AI）”按钮与“原文展示 · 只读 / AI 改写 · 编辑与预览”标签页。原文读取成功后可查看完整技术结构，再选择 AI 改写；原文页不允许同步/发表，避免把参考原文误当成待发布版本。source.json/source.html 在调用 AI 前保存，旧任务没有保存原始 HTML，需要重新读取。

HTML 来源默认采用结构改写：按批处理普通 p 段落；标题层级、代码块、内联代码所在段落、表格、列表等技术结构保留，AI 独立分析放到末尾。超长单段暂不改写，避免截断。模型返回必须逐段完整对应。段落内部强调样式可能因改写被简化；模型仍可能改变语义，技术事实必须人工复核。

HTML 清洗保留安全样式、代码、表格和合并单元格；原图下载成功后按原有标记位置插入。源文件中的脚本不执行。QTextBrowser 与微信对 CSS 的支持不同，不保证像素级复刻，也不保证代码语法高亮完全一致。

手动粘贴的纯文本无法恢复丢失的代码/表格结构，仍用观点重构流程。完整长文可能超过单篇草稿限制，上传前明确拦截，请拆分成系列文章。

## 润色定位调整（最新，覆盖此前 SI 点评模式）

AI 以作者/编辑口吻直接润色正文：保留亮点和有效经验，补清术语指代、操作目的与衔接。必要说明必须有原文依据，不凭空添加技术事实。取消末尾独立 AI 分析和强行 SI 视角，不输出优缺点评分或对原作者的评论。结构模式继续原样保留代码、表格和章节结构。
旧生成结果不会自动变化，需重新点击 AI 润色。纯文本长文路径仍有摘要步骤，可能丢失细节，技术教程建议使用结构化网页来源。

## 零配图同步（最新）

正文零张图片也可同步或发表。程序不再要求手选封面：无图时本地生成默认几何封面，上传为永久封面素材，不插入正文，不调用图库或 AI。默认封面可在微信草稿箱检查。有图时继续使用第一张作为封面。本地图片多选已取消 3 张限制，仍受微信接口实际大小、格式和权限约束。

## 平台判定大小（最新，覆盖此前本地长度校验说明）

已取消同步前的 20000 HTML 字符 / 1000000 字节硬拦截，以及标题 64 字、作者 8 字的本地限制。原文标题不再截断。完整提交给微信接口，由平台判定是否接受；平台拒绝时显示微信错误码，不代表可无限长度发表。不自动截断、拆篇或重复提交。仍保留非空标题/正文与稿件格式检查、账号版本核对、防重复发表机制。

## 中文传输修复

JSON 请求明确以 ensure_ascii=False 序列化为 UTF-8 字节，并声明 application/json; charset=utf-8。避免平台将 Unicode 转义作为可见正文。代码中的反斜杠仍按标准 JSON 编码，不进行全局 unicode_escape 解码。已生成的远端草稿或已发表文章不会自动被修改；需重新同步校验，不自动重复发表。

## Markdown 与原文样式兼容

抓取后另存 source.md；无特殊样式的标题、段落、列表等转为 Markdown，必要字体/颜色样式、代码块与表格保留为精简 HTML，形成 Markdown + HTML 混合编辑稿，避免丢失缩进和合并单元格。同步时去掉可继承的重复样式、空样式和无属性 span，不截断正文。
本次对保存长文测量：HTML 从 938454 字节减至 566200 字节，文字及代码内容校验一致。仍不保证通过微信的内容大小限制，未自动拆篇或实际提交。

## 代码块对比度修复

修复原文深色主题的浅色代码文字被放到浅灰背景的问题。原文提取和最终 HTML 渲染统一代码块为浅灰背景、深色文字，清理子节点残留文字颜色和重复 padding；不改变文本、换行和缩进。既有本地稿件重新渲染也会应用修复。旧远端草稿不会自动更新。

## 排版版本与草稿复用

草稿版本指纹现在包含渲染后的 HTML，样式修复后不再复用相同正文的旧草稿。实际提交的正文保存为任务目录下 submitted_content.html，便于与微信预览核对。此变更不会修改或删除已有远端草稿；再次同步会按新版本创建草稿，需使用新草稿预览链接。
