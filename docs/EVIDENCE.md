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

## 真实声音检索

- 样本来源及许可：待核验；私人路径不写进提交文件。
- 说话人数、录制次数、语言、噪声和年代：待实测。
- 参考与检索样本是否不同录制：待核验。
- 已知匹配、未知负例及人工标注方法：待核验。
- 冻结样本清单、两位已知人分别查询的全部逐例分数、正例是否优于全部明确负例：未验证。这是技术预览公开门槛，不是泛化准确率。
- 候选排序、误检、漏检：未验证；未经完整标注不报准确率/召回率。
- 首次下载与处理耗时、每小时素材建库耗时、峰值内存、索引大小：待实测。
- 缓存后离线重启：未验证。

## 真实UI与导出

导入、索引、参考、查询、回听、确认、导出播放、重启保留：均未验证。记录浏览器、真实后端与模型，不用截图代替结果。

## 用户验证

真实试用人数：尚未进行。再次使用与节省时间：尚未测量。工程完成不能自动改写本节。
