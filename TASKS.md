# 任务队列

以下状态依据实际实现、验证与远端读回更新。

| ID | 状态 | 交付 | 依赖 | 完成证据 |
|---|---|---|---|---|
| T01 | DONE | 项目环境与真实音频提取 | 无 | docs/EVIDENCE.md；Python 3.11 正式回归通过；58ef2f9 与环境锁提交 |
| T02 | DONE | 真实模型、样音与相似检索最短链路 | T01 | docs/retrieval_results.json；两位不同录制正例均高于全部负例；阻断网络离线 smoke 通过；87a223c 与评测提交 |
| T03 | DONE | 持久索引、增量更新、取消与恢复 | T01/T02 | 7 项事务/错误回归；真实索引与重扫；Playwright 实际取消、SIGKILL 中断后重试通过；72ebe43 与 UI 验收提交 |
| T04 | DONE | API、原位置预览与人工标注 | T02/T03 | 5 项 API 行为回归；docs/api_results.json 真实查询/预览与标注重启通过；72ebe43 |
| T05 | DONE | 原声ZIP导出及来源清单 | T04 | 4 项边界/哈希/失败/取消回归；真实 ZIP 解码、浏览器下载 WAV 播放、重启通过；72ebe43 与 UI 验收提交 |
| T06 | DONE | 实际浏览器完整流程 | T04/T05 | ego_results.json 与 e2e_results.json；真实完整流程/错误/390px/键盘/重启通过；typecheck/build；UI 验收提交见 git log |
| T07 | DONE | 文档、许可、性能与可复现检查 | T02–T06 | fc8652a/0943fa5；中英 README/MIT/55 Python与123 npm许可条目；第二干净环境 verify --real exit0，9检查/24回归/真实浏览器全过；docs/verify_results.json |
| T08 | DOING | 个人仓库上传、CI与技术预览发布 | T01–T07 | 私有备份已推送0943fa5；CI40513773269与40514354263实际成功；完整历史扫描通过，待最终证据提交CI/公开/release读回 |

缺模型或样本时，模型效果验收标BLOCKED；仍可用明确的测试替身实现纯工程路径，但不得将T02实际验收和公开发布门槛标DONE。依赖条件按需要区分实现依赖与真实验证依赖。

任务状态仅TODO/DOING/DONE/BLOCKED。每项DONE记录证据和提交。新增任务限修复当前范围内缺陷，先写明它阻止哪个验收，不增加新产品方向。
