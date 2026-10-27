# VoiceTrail

在用户选择的本地影音资料中检索相似声音，回到原时间范围试听、人工标注并导出原声。

[English](README.md) · [规格](PROJECT_SPEC.md) · [实测证据](docs/EVIDENCE.md) · [第三方许可](docs/THIRD_PARTY.md)

**v0.1.0-alpha.1 是本地技术预览。** CPU 运行固定版本的真实 SpeechBrain ECAPA 模型。余弦分数用于排序，不是身份概率。当前界面为中文。

## 安装与启动

依赖：Python **3.11**、Node **24 LTS** / npm、[uv](https://docs.astral.sh/uv/) **≥0.13.6**、PATH 中可用的 FFmpeg 和 FFprobe。macOS 可用 Homebrew 安装：

```sh
brew install python@3.11 node@24 ffmpeg uv
git clone https://github.com/Xiangyu2141480/voicetrail.git
cd voicetrail
uv sync --locked --python 3.11
npm ci --prefix frontend
npm run build --prefix frontend
.venv/bin/python -m scripts.prepare_model
.venv/bin/python -m scripts.dev
```

打开 **http://127.0.0.1:8765**。终端保持运行，Ctrl+C 退出。单启动器保证单实例、单后台 worker，生产前端与 API 同源。Linux 先自行安装上述依赖和 libsndfile；CI 验证 Linux 工程路径，真实模型/浏览器性能仅在 macOS ARM64 实测。启动器使用 POSIX 文件锁，首版不支持 Windows。

首次准备模型从固定 Hugging Face revision 下载 **83,316,686 bytes** 权重，显示实际进度并核对 SHA256，只将 tensor 权重加载到已安装的模型结构，不执行远端 YAML/Python。失败返回非零退出码。准备后可离线启动：

```sh
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.prepare_model --offline
HF_HUB_OFFLINE=1 .venv/bin/python -m scripts.dev
```

默认数据目录：macOS 的 `~/Library/Application Support/VoiceTrail`，Linux 的 `~/.local/share/voicetrail`，均与源码隔离。通过 `VOICETRAIL_DATA` 指定其他目录，`VOICETRAIL_PORT` 改本地端口。数据库、参考、模型、预览和导出都保存在本地。模型准备会联网；普通索引、检索和导出只处理本地文件，不使用云推理。

## 使用流程

1. 粘贴你明确选定的本地文件夹路径，添加资料，再建立/更新索引。浏览器不能调用原生目录选择，实际访问由本机后端完成。
2. 上传主要由同一人说话的参考，建议 10–30 秒；接受 3–60 秒，且至少含 3 秒检测到的语音。
3. 检索、回听，再人工确认/排除/保留未定。分数不会自动确认身份。
4. 勾选片段、导出 ZIP：包含 16 kHz 单声道 PCM16 WAV 和来源清单，记录原时间范围及源内容指纹。

原素材只读，导出为原声解码重编码，不合成、不克隆。重扫保留未变素材的索引代际；服务中断后遗留任务显示 interrupted，需明确点击重试。失败文件显示原因。移除素材仅移除索引登记，不删除源文件。参考、标注和导出跨重启保留。

## 验证

```sh
.venv/bin/python -m scripts.verify
```

统一入口运行 24 项工程回归（阻断 socket 联网）、ruff、HTTP 契约一致性、前端类型和构建。CI 使用相同入口；工程绿色不代表真实说话人效果。

完整真实检查：

```sh
.venv/bin/python -m scripts.prepare_evaluation
npm exec --prefix frontend -- playwright install chromium
.venv/bin/python -m scripts.verify --real --report docs/verify_results.json
```

评测准备脚本流式读取官方 dev-clean 压缩包，只保留与冻结清单哈希一致的五个授权真人样本；可用 `--archive` 指定完整本地压缩包，`--offline` 核验已有素材。下载可能读取较大部分压缩包。额外生成的合成信号只测试错误处理，不参与人声效果评测。

`--real` 缺模型或样本直接失败；必须实际运行断网模型推理、冻结排序门槛、真实 API 索引/导出/重启，以及 Chromium 原声和导出播放、强制中断恢复、标注持久化。会更新证据 JSON/截图，音频和权重不进入 Git。

## 已验证与限制

实测：macOS 26.5.1 / ARM64、Apple M5 Pro、48 GiB RAM，CPU 四线程。冻结集为英语 clean 有声书五个片段、三位说话人；两位已知人的不同章节正例均高于所有已知/未知负例，逐例分数见 [检索结果](docs/retrieval_results.json)。

初次 API 实测：3 文件、总长 53.065 秒、10 个分窗；建索引 2.412 秒、未变化重扫 0.329 秒、查询约 0.010 秒，峰值 RSS 约 1.06 GB。属于小样本缓存实测，不代表大库性能。

真实浏览器已验证原声预览、ZIP 下载后 WAV 播放、取消、SIGKILL 后重试、重启标注与下载、中文/空格路径、短/静音/无音轨错误、390px 布局和键盘检索。[完整证据](docs/EVIDENCE.md)；[界面截图](docs/ui-desktop.png)。

不同章节不等于独立环境或跨年。中文语音、旧家庭录像、噪声/重叠发言、跨年龄、大型资料库、其他硬件，以及真实用户复用/节省时间均未验证。分段不等于说话人分离，不声称泛化准确率或身份确定性。

原创新代码 MIT；第三方依赖、权重、素材分别保持原许可。源码发行不含依赖二进制、权重或音频，完整清单见 [THIRD_PARTY.md](docs/THIRD_PARTY.md)。桌面安装包、云同步、训练和视频导出不在首版范围。
