# VoiceTrail v0.1.0-alpha.1 交付报告

T01–T08 已按规格完成：真实 CPU 相似声音检索、本地索引与恢复、原声回听/标注/WAV ZIP 导出、浏览器验收、可复现安装、许可核验、个人 GitHub 上传及公开预发布。未用模拟向量或预置结果替代真实功能。

## 远端读回

| 项目 | 实际读回结果 |
|---|---|
| 账户/仓库 | `Xiangyu2141480` / [Xiangyu2141480/voicetrail](https://github.com/Xiangyu2141480/voicetrail) |
| 可见性 | PUBLIC，`gh repo view` 返回 `isPrivate=false` |
| 发布版本 | [v0.1.0-alpha.1](https://github.com/Xiangyu2141480/voicetrail/releases/tag/v0.1.0-alpha.1) |
| Release 状态 | `isDraft=false`、`isPrerelease=true`，发布时间 `2026-10-27T13:46:54Z` |
| 发布源码 SHA | `18b4dd98b687a05294a2337ca5587caa0c0d5175` |
| 远端 main 快照 | 发布后、交付报告提交前：`18b4dd98b687a05294a2337ca5587caa0c0d5175`，与当时本地 HEAD 相符 |
| 实际 fetch 标签 SHA | `git rev-parse v0.1.0-alpha.1` = `18b4dd98b687a05294a2337ca5587caa0c0d5175` |
| CI | [40514847301](https://github.com/Xiangyu2141480/voicetrail/actions/runs/40514847301) 与 [40514845290](https://github.com/Xiangyu2141480/voicetrail/actions/runs/40514845290) 对发布 SHA 均 completed/success |
| 附加发行资产 | `assets=[]`；仅 GitHub 源码归档，不附录音、权重、数据库、向量或依赖二进制 |

此报告与完成状态作为后续文档提交进入 main；其自身提交 SHA 无法在同一提交正文中自引用。最终 main/本地 HEAD、最后文档 CI 在交付消息中实际读回，版本标签保持上述已验证源码快照。

## 实际检查

- 新建独立个人项目，未写入公司仓库。源码、数据和模型缓存隔离，原素材只读。
- 第二干净源码副本/全新 .venv/npm 安装，对代码提交 `0943fa5f46b940d5552b98c45689fdac4c961ab1` 执行统一 `verify --real`：9 检查全部成功，exit 0，总101.453秒。24项工程回归通过；浏览器测试26.4秒/runner27.0秒。
- 5个冻结授权英语真人片段、3说话人：两位已知人的不同章节正例均高于全部明确负例；保存每个分数。没有自匹配或运行后挑选成功样本。
- socket 阻断的真实模型/API 测试通过；真实 Chromium 和 ego-browser 均完成回听与导出后 WAV 播放。测试涵盖取消/SIGKILL/显式恢复、源变化、具体错误、标注/参考/导出重启持久化、390px及键盘。
- 原声导出使用解码重编码、输出可解码WAV和来源指纹/时间范围；边界误差回归≤100ms，源 SHA 未改变，失败不产成功ZIP。
- 全部公开历史在发布前复核：9个可达提交、205个独立blob，后缀/大小/文本凭证/私人路径扫描无问题，并人工检查源码范围与截图。扫描是启发式检查，不是零泄漏保证；此最终文档也在push前再次扫描。
- 原创新代码 MIT；55 个 Python / 123 个 npm 锁条目记录来源与许可，保留可取得的上游 LICENSE/NOTICE。FFmpeg、权重与素材许可单列。

机器结果：[verify](verify_results.json)、[冻结排序](retrieval_results.json)、[API](api_results.json)、[Chromium](e2e_results.json)、[ego-browser](ego_results.json)。完整过程、失败原因与修复见 [EVIDENCE.md](EVIDENCE.md)；许可见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 本地启动

已初始化的项目中：

```sh
.venv/bin/python -m scripts.dev
```

打开 `http://127.0.0.1:8765`；Ctrl+C退出。首次安装、模型准备和完整复核命令见 [中文README](../README.zh-CN.md)。本轮所有验证服务已停止，没有声称持续后台执行；临时干净源码副本已清理。

## 验证边界与下一步

真实运行平台为 macOS ARM64 / Apple M5 Pro / CPU四线程。Linux只有工程CI证据；Windows不支持。英语clean有声书不同章节不代表独立环境、中文、噪声旧家庭录像或跨年龄可靠识别。余弦分数不是身份概率，分窗不是完整说话人分离；工程confirmed标注不是人类身份审听证明。

真实试用人数、复用和节省时间尚未测量，不算工程DONE的成果。下一步只需用户以自己的同年代清晰录音做第一次真实导入：提供10–30秒单人参考，回听正例和负例，确认导出的片段是否满足实际需要。
