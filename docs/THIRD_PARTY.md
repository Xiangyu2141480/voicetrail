# 第三方与样例来源

此文件初始没有完成许可核验。按实际使用填写，保留必要的许可证和署名；不能把自己代码的MIT许可覆盖到第三方内容。

| 项目或素材 | 官方来源URL | 固定版本/revision | 代码或权重许可 | 用法与分发范围 | 核验状态 |
|---|---|---|---|---|---|
| SpeechBrain ECAPA | https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb/tree/0f99f2d0ebe89ac095bcc5903c4dd8f72b367286 | 0f99f2d0ebe89ac095bcc5903c4dd8f72b367286 | 官方模型卡标注 Apache-2.0；SpeechBrain 代码 Apache-2.0 | 仅下载 embedding_model.ckpt 到本地；不分发权重，不执行远端 YAML/Python | 模型卡/API/hyperparams 已核验，运行待验证 |
| FFmpeg | https://ffmpeg.org/legal.html | 本机 9.0.2 | 本机构建含 enable-gpl / enable-version3，GPL v3+ | 用户安装的外部依赖，不分发二进制 | ffmpeg -version 构建参数已核验 |
| 其他实际依赖 | 实施时填写 | 待定 | 待核验 | 待填 | 待核验 |
| LibriSpeech dev-clean | https://www.openslr.org/12/ ; https://huggingface.co/datasets/k2-fsa/LibriSpeech | 镜像 2dd4206a992cd7a475e1ce2e82b708b014319152；精确 ID/SHA 见 evaluation_manifest.json | OpenSLR 官方页面 CC BY 4.0 | Vassil Panayotov / Daniel Povey 等，LibriVox 衍生；本地评测音频不上传 | 许可与来源已核验；不同章节录制，非独立录音环境 |

比较和参考：[ClipTalk](https://github.com/GML-MMGroup/ClipTalk)、[VidXP](https://github.com/grayhatdevelopers/vidxp)。参考产品设计不代表可直接复制代码；复制实现必须按其实际许可证处理。
