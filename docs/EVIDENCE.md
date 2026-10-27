# 实测证据

所有记录区分正式环境、临时环境和真实模型验收；未运行的门槛仍为未验证。

## 环境

- OS/架构：macOS 26.5.1 / ARM64
- CPU/RAM：Apple M5 Pro / 48 GiB
- Python/Node/FFmpeg：项目 Python 3.11.18（Homebrew）/.venv；Node 24.21.0、npm 11.19.0、FFmpeg 9.0.2
- 模型repo/revision/许可/预处理版本：SpeechBrain spkrec-ecapa-voxceleb / 0f99f2d0ebe89ac095bcc5903c4dd8f72b367286 / 模型卡 Apache-2.0 / pcm16k-vad2-window10-hop5-v1
- 设备后端：真实 CPU/4 threads，固定 revision 已通过模型、API 与浏览器验收

## 检查记录

| 日期/任务 | 实际命令或操作 | 数据集代号与范围 | 结果与退出码 | 证据/提交 | 限制 |
|---|---|---|---|---|---|
| 2026-10-27/T01 | `.bootstrap/bin/python -m pytest tests/test_media.py -q`（实现前） | 可控正弦/无音轨/损坏文件 | exit 2，缺 media 模块，符合缺失能力 | tests/test_media.py | 临时 Python 3.9 |
| 2026-10-27/T01 | 相同命令（实现后） | 16k mono、2s 切片、中文空格路径、损坏/无音轨 | exit 0，4 passed | backend/app/media.py | 待正式 Python 3.11 重跑 |
| 2026-10-27/T01 | `npm install` / `npm audit --json` | 前端依赖 | 安装后 0 vulnerabilities；初选 Vite 有漏洞，改为 7.3.7 | frontend/package-lock.json | 还未构建 UI |
| 2026-10-27/T01–T02 | `.venv/bin/python -m pytest tests/test_media.py tests/test_search.py tests/test_embedding_contract.py -q` | FFmpeg 音频/隔离向量/静音 | exit 0，8 passed | tests / uv.lock | 正式 Python 3.11；不代表真实声音质量 |
| 2026-10-27/T03 | `.venv/bin/python -m pytest tests/test_indexer.py -q` | 测试专用模型/可控信号 | exit 0，5 passed | tests/test_indexer.py | 验证事务，真实索引待验收 |
| 2026-10-27/T02 | `.venv/bin/python -m scripts.smoke_model <reference>` | 冻结样本 2277-149896-0032 | exit 0；CPU 实际向量 192维、L2 norm 1.0 | backend/app/embedding.py | 首次准备 70.863s；提取+推理 0.163s；峰值 RSS 711,016,448 bytes |
| 2026-10-27/T02 | `.venv/bin/python -m scripts.evaluate_retrieval --dataset <evaluation>` | 冻结的5个样本/3说话人/不同章节 | exit 0；两位已知人的不同录制正例均高于全部负例 | docs/evaluation_manifest.json / docs/retrieval_results.json | 9.703s；峰值 RSS 1,117,962,240 bytes；小样本，不报告泛化准确率 |
| 2026-10-27/T02 | `HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.smoke_model --offline <reference>` | 冻结 reference；socket.connect/create_connection 明确抛错 | exit 0；实际模型缓存重启、192维/归一化向量；network_connections_blocked=true | scripts/smoke_model.py | load 2.690s，提取+推理0.152s，峰值 RSS710,705,152 bytes |

## 真实声音检索

- 样本来源及许可：LibriSpeech dev-clean，OpenSLR 官方标注 CC BY 4.0，精确 ID 与哈希见冻结清单。
- 说话人数、录制次数、语言、噪声和年代：3 位说话人，5 个章节音频片段，英语有声书 clean 子集；录制年代未核验。
- 参考与检索样本是否不同录制：同人不同 chapter ID，非同一录音复制裁切；独立环境/跨年不成立。
- 已知匹配、未知负例及人工标注方法：官方 speaker/chapter IDs；2277/2035 为已知，2086 为未知；无人工身份确认。
- 冻结清单 SHA cbaeeb06e7fcf06dab550a01594abd47079b2d006907158389560f5c07ffd2f1；两查询的全量逐例分数见 retrieval_results.json。2277 正例0.709754，负例0.248479/0.020344；2035 正例0.776059，负例0.143877/0.124603，最低排序门槛通过。这不是泛化准确率；实际分窗 UI 结果另见 api_results.json 和 e2e_results.json。
- 候选排序、误检、漏检：未验证；未经完整标注不报准确率/召回率。
- 首次权重83,316,686 bytes（约79.5 MiB），准备70.863s；其他建库性能待实测。
- 缓存后离线重启：通过，smoke 明确阻断所有 socket 网络连接；本地固定 revision 权重 SHA256 校验后加载。

## 真实UI与导出

API 工程与真实验收：23 项 pytest 通过；ruff 通过。最初 T04/T05 测试 exit 2，缺 main/export 模块；实现后访问保护/重启标注/源版本/900 Hz 边界/源 SHA/失败无 ZIP/取消共 9 项通过。

`.venv/bin/python -m scripts.integration` exit 0：明确禁止 socket 网络连接，使用冻结 5 样本，在隔离数据库中真实处理中文/空格文件名的 3 个目标文件（总 53.065 秒），生成 10 片段。首次缓存 API 启动 12.571 秒、索引 2.412 秒、未变化重扫 0.329 秒，两次检索约 0.010 秒；重扫片段 ID 不变。峰值 RSS 1,059,815,424 bytes。具体逐片段排序见 api_results.json；分窗采用最佳正例高于全部负例的补充门槛，不替换冻结全样本门槛。

真实 API 下 WAV 预览与 ZIP 内 WAV 均可解码、时间范围误差 <=100ms；新建应用实例/重新加载真实模型后，两个参考、候选稳定 ID、confirmed 标注和 ZIP 下载仍有效。该过程通过 TestClient 调用真实模型，尚不等于真实浏览器播放。

React 已接真实 API；`npm run build` exit 0，同时 typecheck 通过。

`npm run e2e`（配置冻结 evaluation 和模型缓存）最新 exit 0：1 passed (24.6s)，Chromium 141.0.7390.37，固定真实模型。完整 UI 导入 3 个真人文件 + 无音轨/损坏错误素材，实际取消索引、索引运行时 SIGKILL 服务、重启读回 interrupted 并显式重试；3/5 完成，2 个错误原因可读。短 2 秒参考、5 秒静音、无音轨参考均显示真实错误；参考与命中目标来自不同章节录制，不是自匹配。

浏览器首个真人候选原声和下载 ZIP 中解包的真实 WAV 均 duration=10 秒、readyState=4、currentTime>0.2 秒、media error=null。confirmed/rejected 标注和 ZIP 在新服务进程后保留，390px 无横向溢出、键盘 Enter 可检索、JavaScript errors=[]。具体结果见 e2e_results.json，截图 ui-desktop.png / ui-mobile.png。这验证解码/播放，不声称人类身份审听完成。

ego-lite 0.6.0.12 独立操作生产同源界面：添加目录、索引、上传真人参考、检索、回听、确认、选择、导出下载、解包后在真实浏览器播放 WAV 全部完成；结果 ego_results.json / ego-desktop.png。任务空间验收后已关闭；未升级浏览器。

发现并修复：最初 Playwright 未识别项目外测试文件的 ESM，exit 1；给 tests/e2e 明确 type=module 并指向项目安装的入口后，完整测试通过，未删断言。文件索引最初丢失具体 MediaError，新增“无音轨应显示具体原因”回归实际先失败，再保留安全错误文字修复；indexer 7 passed，随后真实 E2E 再通过。

## 可复现安装与发布检查

2026-10-27/T07：从提交 fc8652a 创建独立干净源码副本，`uv sync --locked --python 3.11` 新建 .venv 并安装 51 个包，`npm ci --prefix frontend` 安装成功且 audit 0 vulnerabilities；`prepare_model --offline` / `prepare_evaluation --offline` 成功。未复用原项目虚拟环境。

首次 `scripts.verify --real`：工程回归 24 passed (6.65s)、ruff/契约/typecheck/build、断网真实 smoke、冻结排序、真实 API 全部成功，但最终 exit 1：E2E 期望 3/5 个文件，页面实际显示 6/9。原因是旧 UI 素材与新准备脚本素材混在共享目录中，产生重复真人文件和第三个错误文件；不是把检索效果失败改成成功。修复为 E2E 逐次创建独立临时资料库，从冻结清单校验所有原始 SHA 后仅复制 3 真人目标，另放 2 个错误素材。保持原断言，不删测试、不放宽门槛；重新验收结果如下。

`scripts.verify --real` 在空数据目录实际 exit 1，明确要求冻结样本，不存在 mock/skip 的绿色降级。`prepare_evaluation --archive` 使用由五个授权原始 FLAC 构成的本地 tar 实际取样、逐 SHA 验证，再离线复核成功；在线 HTTPS 下载传输未在本轮再次下载完整 archive。

冷初始化 CLI 显示状态修复：已缓存权重在导入模型库期间原先显示 downloading，现提前识别缓存，实际离线运行输出 loading / 83,316,686 bytes 后 ready，exit 0。权重、架构及推理路径未改变。

许可清单生成成功：55 个 Python 锁条目 / 123 个 npm 锁条目，含平台变体；保存上游许可与 NOTICE。原文本只规范化换行和行末空白，哈希对应原分发文本。源码/权重/素材/外部 FFmpeg 许可分列，不分发依赖二进制或真人音频。

首次远端 CI [40513773269](https://github.com/Xiangyu2141480/voicetrail/actions/runs/40513773269) 对提交 fc8652ab5ccaa5fa0929446ea391930d6a7109b0 实际 completed/success。Ubuntu 24.04 安装 CPU PyTorch 锁、FFmpeg 后运行统一工程入口与全历史扫描；不替代本地真实门槛。

修复提交 0943fa5f46b940d5552b98c45689fdac4c961ab1 再创建第二个干净源码副本与全新 .venv/npm 安装，`prepare_evaluation --offline` 成功；`.venv/bin/python -m scripts.verify --real --report docs/verify_results.json` 实际 exit 0，9 个检查全部通过，总 101.453 秒。工程 24 passed (7.67s)，浏览器 1 passed (测试26.4s / runner27.0s)。冻结两查询分数与初次一致；API 再实测索引1.088秒、重扫0.336秒、查询约0.012秒，峰值RSS1,052,770,304 bytes。冷环境已缓存权重的 smoke 加载43.743秒，说明缓存不意味着各机器/冷初始化都固定为数秒。

最终机器报告为 verify_results.json / retrieval_results.json / api_results.json / e2e_results.json；桌面/窄屏截图人工检查未含私人绝对路径，测试语音未上传。该轮浏览器实际取消/SIGKILL/恢复/回听/ZIP下载后WAV播放/标注跨进程保留均成功。对应修复 CI [40514354263](https://github.com/Xiangyu2141480/voicetrail/actions/runs/40514354263) completed/success。

## 用户验证

真实试用人数：尚未进行。再次使用与节省时间：尚未测量。工程完成不能自动改写本节。
