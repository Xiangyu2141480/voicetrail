# VoiceTrail v0.1 Implementation Plan

> For agentic workers: Use superpowers:subagent-driven-development or superpowers:executing-plans if installed. Otherwise implement the equivalent task-by-task execution and review loop described here. Do not assume Trae has these skills.

**Goal:** 从本地影音库检索参考声音的相似原声片段，人工确认并导出，交付可运行的技术预览。

**Architecture:** 单实例FastAPI提供本地API及前端，单worker持久任务；SQLite按文件事务激活索引，NumPy检索固定版本的真实speaker embedding。原素材只读，数据、模型和导出独立于源码；UI直接操作真实服务。

**Tech Stack:** Python3.11 / FastAPI / SQLite / NumPy / FFmpeg / React / TypeScript / Vite / pytest / Playwright；具体依赖版本以实施时官方兼容说明和实际安装为准，提交锁文件。

**Spec:** PROJECT_SPEC.md。

## Global Constraints

- CPU必须可运行；一个真实本地speaker embedding模型；不用LLM、付费API或云推理。
- 参考样音目标10–30秒，有效语音接受3–60秒；不得用mock替代实际搜索验收。
- 仅处理用户明确选择目录，原素材只读；服务仅127.0.0.1，登记ID访问媒体。
- SQLite单worker任务，按文件事务，保留源和模型/预处理版本。
- 输出原声WAV ZIP与manifest；边界误差目标不超过100ms。
- 主文案为相似声音候选；余弦分数不是概率，不承诺跨年龄或完整diarization。
- GitHub目标Xiangyu2141480，新仓库先私有；T08门槛通过后自动公开技术预览。

## Review Focus

1. 中文/空格路径、损坏文件和无音轨：T01测试不得以shell拼接路径或生成空成功结果。
2. 静音、短句、不同录制与未知说话人：T02区分工程执行与真实检索质量，不自匹配刷分。
3. 文件在提取时变更、取消或服务崩溃：T03不激活部分索引，不重复片段，重启可恢复。
4. 浏览器越过注册目录读文件或跨站发写请求：T04验证登记ID、目录边界及本地会话/Origin约束。
5. 缓存断网、剪切边界、发布历史含私人资料：分别由T02、T05、T08验证，不以README声明代替测试。

## 执行方式

每个任务：先做能失败的行为检查，确认失败原因对应缺失能力；实现最小功能；运行相关验证；检视差异；完成一个可恢复提交；更新TASKS、STATE与EVIDENCE；继续下一任务。只为有实际风险的行为写测试，不为纯文案或实现细节堆断言。T01环境探测和文档更新无需机械TDD。

以下接口是实现基线；若官方依赖要求调整内部签名，先同步该任务所有调用与契约，记录原因，不改外部产品承诺。

### T01 环境与音频提取

**Files:** pyproject.toml、Python锁文件、frontend/package.json及锁文件、backend/app/media.py、backend/app/schemas.py、tests/test_media.py、.gitignore。

**Interfaces:** MediaInfo含duration_ms、has_audio、sample_rate、channels；inspect_media(path: Path) -> MediaInfo；extract_audio(path: Path, output: Path, start_ms: int = 0, end_ms: int | None = None) -> MediaInfo。失败抛有稳定类型的业务错误，不假装空音轨成功。

- [ ] 检查git与系统工具，创建项目级环境。写.gitignore先排除数据、模型、样本、导出、日志和凭证；不改变已有公司项目或全局配置。
- [ ] 写test_extract_normalizes_to_16k_mono，断言16kHz、单声道、时长误差<=100ms；写test_unicode_path_and_no_audio及test_corrupt_media，断言明确错误且无成功结果。
- [ ] 用pytest运行上述测试，确认失败来自尚未实现，而非测试本身错误。
- [ ] 实现FFprobe/FFmpeg参数数组调用，限制进程退出与超时，清理仅属于本次任务的临时文件。
- [ ] 运行pytest tests/test_media.py，实际检查生成文件可解码；记录工具版本并提交。具体命令前缀由实际环境统一记录在README，不能只写未运行的示例。

### T02 真实模型与最短检索

**Files:** backend/app/embedding.py、backend/app/search.py、scripts/smoke_model.py、scripts/evaluate_retrieval.py、tests/test_embedding_contract.py、tests/test_search.py、docs/THIRD_PARTY.md。

**Interfaces:** ModelInfo含id、revision、preprocessing_version、dimension；embed_audio(path: Path) -> np.ndarray，返回固定维度、有限值、L2归一化向量；rank_segments(reference: np.ndarray, vectors: np.ndarray, top_k: int) -> list[tuple[int, float]]，返回降序余弦分数。

- [ ] 从官方模型卡核验CPU依赖、API、权重许可与revision；优先SpeechBrain ECAPA，不凭印象照抄导入路径。确定模型下载和缓存位置。
- [ ] 对隔离数学逻辑写test_cosine_rank_order、test_dimension_mismatch_rejected、test_nonfinite_vector_rejected；对音频写test_silence_and_short_reference_rejected。固定测试向量仅限这些单测。
- [ ] 实现真实embedding适配器、规范化和分段；模型失败显示真实错误，生产路径不能自动降级成fake模型。
- [ ] 用真实多说话人不同录制运行smoke_model与evaluate_retrieval，报告取样方法、候选结果和失败；若数据不满足条件，将效果评测明确BLOCKED。
- [ ] 查询前冻结有标签的小样本清单，至少两位已知说话人分别查询；断言各自不同录制正例相似度高于全部明确负例（另一已知人和未知人），保存全部逐例分数/排序，不运行后挑样本。未通过则检索质量BLOCKED，不标实际可用。
- [ ] 缓存就绪后隔离网络重新运行实际模型；记录CPU、耗时、内存与模型revision。相关单测和真实smoke分别记录，不互相替代；提交。

### T03 持久增量索引

**Files:** backend/app/db.py、backend/app/jobs.py、backend/app/indexer.py、tests/test_indexer.py、tests/test_jobs.py。

**Interfaces:** enqueue_index(library_id: str) -> str；get_job(job_id: str) -> JobStatus；request_cancel(job_id: str) -> None。JobStatus含status、processed、total、error；数据库schema在本任务创建并版本化，后续只通过该接口访问任务。

- [ ] 建library、asset、source_revision、segment、job、reference、search_run、candidate、export表的最小schema；记录外键与事务边界。
- [ ] 写test_incremental_scan_does_not_duplicate、test_changed_source_discards_staging、test_crash_keeps_previous_generation、test_restart_recovers_running、test_cancel_never_activates_partial。断言可检索代际始终完整、片段数不因重扫翻倍。
- [ ] 实现单worker持久队列；每文件检查提取前后指纹，全部片段完成后一次事务激活。不同模型版本不混排。
- [ ] 运行上述回归，实际执行取消与重启；正常重扫不重算未变化文件，提供显式完整校验入口识别元数据未反映的变化；记录限制并提交。

### T04 API与回听标注

**Files:** backend/app/main.py、backend/app/schemas.py、backend/app/references.py、backend/app/candidates.py、tests/test_api.py、tests/test_media_access.py、frontend/src/api.ts。

**Interfaces:** 依照PROJECT_SPEC的HTTP契约；候选字段id、asset_id、source_revision、start_ms、end_ms、similarity、review_status。按实际OpenAPI生成或同步TS类型，不让前后端自行猜测。

- [ ] 写test_search_returns_source_timestamps、test_review_survives_restart、test_unregistered_asset_denied、test_path_escape_denied、test_cross_origin_write_denied。对标注重启后读回同一值，对恶意媒体访问返回拒绝。
- [ ] 实现loopback绑定、前端同源、开发来源白名单和本地进程会话令牌/等效CSRF约束；令牌不写repo或日志。不接受任意下载路径。
- [ ] 实现参考创建、搜索、候选稳定ID、标注与原位置预览。浏览器不支持的媒体提供FFmpeg本地音频预览，不能让播放器空白冒充可用。
- [ ] 运行API与访问边界测试，手动调用真实模型查询，核对时间范围及源版本；提交。

### T05 原声导出

**Files:** backend/app/export.py、tests/test_export.py。

**Interfaces:** enqueue_export(candidate_ids: list[str]) -> str；完成结果为ZIP下载ID。manifest每项含源文件标识、内容指纹、start_ms、end_ms、导出文件名与采样格式；私人路径只留用户本地导出，不进入公开报告。

- [ ] 写test_export_duration_and_boundaries，使用可控信号断言误差<=100ms；写test_stale_source_export_rejected、test_ffmpeg_failure_no_success_zip、test_export_does_not_modify_source，检查源哈希未变。
- [ ] FFmpeg解码重编码选定片段为WAV，完成后检查可解码与时长，再原子产出ZIP。无效时间范围与失效源版本明确报错，不静默剪错。
- [ ] 运行回归，并实际导出一组真人声音候选后回听；提交。

### T06 前端完整链路

**Files:** frontend/src/App.tsx、frontend/src/api.ts、frontend/src/components/下按职责拆分、tests/e2e/voicetrail.spec.ts、Playwright配置。

**Interfaces:** 使用T04真实API；前端状态来自API，不能从本地固定数组模拟成功。

- [ ] 做一个清晰主流程：资料和索引状态、参考样音、候选播放器与标注、导出。处理空态、加载、真实错误和取消，不加聊天页和无关仪表盘。
- [ ] 实现test_real_flow_import_search_review_export_restart，实际浏览器调用真实服务：导入→索引→样音→候选→回听→标注→下载播放→重启查状态。记录真实模型与数据集代号。
- [ ] 至少验证中文或空格文件名、无音轨与过短样音在界面能理解；检查窄窗口、键盘可达、音频控件和错误文案。
- [ ] 运行前端typecheck、生产build、相关测试和端到端；用实际浏览器检查页面。截图不代替功能证据；没有浏览器验收就保留BLOCKED。提交。

### T07 可复现运行和证据

**Files:** README.md（英文）、README.zh-CN.md、LICENSE、docs/THIRD_PARTY.md、docs/EVIDENCE.md、scripts/dev.py或等效单一启动脚本、scripts/verify.py。

**Interfaces:** README给出实际跑通过的初始化、模型准备、启动和验证命令；开发与发布使用同一个verify入口，机器检查失败时退出非0。

- [ ] 从干净项目环境按README启动；区分首次下载与断网重启。外部FFmpeg的安装单列，不承诺无依赖一键运行。
- [ ] 写清来源、代码许可、具体模型权重许可、数据许可、实测平台/语言和已知失败。代码默认MIT仅适用于自己原创部分；未经核验不为第三方改许可。
- [ ] 运行verify入口：后端必要回归、前端类型/构建、可执行的集成检查；真实模型smoke单列结果。真实模型未跑不能靠跳过成为绿色。
- [ ] 用实测数据填证据，未测保留未验证；整理可公开演示素材和截图，不能暴露私人资料。提交。

### T08 GitHub与技术预览

**Files:** .github/workflows/ci.yml、docs/RELEASE_REPORT.md；仅在实际拥有可复现命令后创建CI。

**Interfaces:** GitHub目标个人所有者Xiangyu2141480；最终报告含仓库URL、可见性、本地SHA、远端SHA、CI状态、tag/release与未验证项。

- [ ] 核验登录与目标仓库。无权限则本地交付并标PUBLISH_BLOCKED，不索要令牌、不改公司登录。git作者配置只在本仓库内设置，不能改全局。
- [ ] 用git diff --cached和待推送全部提交的文件清单、内容及秘密扫描检查发布范围；大文件、私有素材、权重、数据库、声纹向量、日志与内部资产不上传。扫描器结果需结合人工检查，不能保证零泄漏。
- [ ] 为新项目创建私有仓库并正常push。CLI可用时参考官方gh repo create OWNER/REPO --private --source=. --remote=origin --push，执行前核对现有remote和仓库状态，不盲跑同一命令。
- [ ] 配置真实CI并执行；CI不接私人素材。模型/真实音频测试可用明确许可小样本；普通CI可只跑离线隔离测试，但它的绿色不能替代本地真实链路证据。
- [ ] 公开门槛：T01–T07实际验收通过；T02固定有标签、不同录制的最小检索排序检查通过；真实浏览器全链路通过；第三方核验完成；全部准备公开历史检查通过；CI通过。缺一则保留私有并写具体原因，不反复触发同样失败。
- [ ] 条件满足后，对仅属于本项目的新仓库自动公开，发布v0.1.0-alpha.1技术预览。先查当前CLI帮助核验可见性与release参数，不猜命令；不手动关闭安全检查。
- [ ] 读取远端SHA与本地HEAD对照，CI结果、可见性和release均实际读回。最终写RELEASE_REPORT，完成本轮；不刷星、不向他人发推广消息。

## 最终自查

逐项对照SPEC：核心工作流、CPU真实模型、事务/恢复、原声导出、真实UI、本地边界、许可与公开历史、远端证据均有对应任务。商业需求、跨年代泛化、双平台桌面分发不在本次工程完成声明里。
