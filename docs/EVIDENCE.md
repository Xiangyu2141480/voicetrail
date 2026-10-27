# 实测证据

所有记录区分正式环境、临时环境和真实模型验收；未运行的门槛仍为未验证。

## 环境

- OS/架构：macOS 26.5.1 / ARM64
- CPU/RAM：Apple M5 Pro / 48 GiB
- Python/Node/FFmpeg：项目 Python 3.11.18（Homebrew）/.venv；Node 24.21.0、npm 11.19.0、FFmpeg 9.0.2
- 模型repo/revision/许可/预处理版本：SpeechBrain spkrec-ecapa-voxceleb / 0f99f2d0ebe89ac095bcc5903c4dd8f72b367286 / 模型卡 Apache-2.0 / pcm16k-vad2-window10-hop5-v1
- 设备后端：设计 CPU/4 threads，真实模型运行结果待记录

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
- 冻结清单 SHA cbaeeb06e7fcf06dab550a01594abd47079b2d006907158389560f5c07ffd2f1；两查询的全量逐例分数见 retrieval_results.json。2277 正例0.709754，负例0.248479/0.020344；2035 正例0.776059，负例0.143877/0.124603，最低排序门槛通过。这不是泛化准确率，实际分窗 UI 搜索仍待验证。
- 候选排序、误检、漏检：未验证；未经完整标注不报准确率/召回率。
- 首次权重83,316,686 bytes（约79.5 MiB），准备70.863s；其他建库性能待实测。
- 缓存后离线重启：通过，smoke 明确阻断所有 socket 网络连接；本地固定 revision 权重 SHA256 校验后加载。

## 真实UI与导出

导入、索引、参考、查询、回听、确认、导出播放、重启保留：均未验证。记录浏览器、真实后端与模型，不用截图代替结果。

## 用户验证

真实试用人数：尚未进行。再次使用与节省时间：尚未测量。工程完成不能自动改写本节。
