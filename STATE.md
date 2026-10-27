# 执行断点

- 项目阶段：T01/T02 已真实通过；T03 工程事务实现与回归完成，待 API 下的真实索引。
- 当前任务：T04 API / T05 导出，实现后接 T06 真浏览器完成 T03 的真实验收。
- 当前状态：RUNNING（仅表示当前会话正在执行）。
- 最近有效提交：c2ccc53，持久任务/代际索引；87a223c，模型适配器。最新评测证据提交随后落盘，git log 为准。
- GitHub目标：Xiangyu2141480/voicetrail；gh api user 已返回目标账户；首选仓库未找到。
- 最近通过的验证：Python 3.11 media/search/embedding contract 8 passed；indexer 5 passed；真实 CPU 模型 smoke；冻结5样本/两查询排序；禁止网络的离线重启/推理；前端 audit 0 vulnerabilities。
- 未验证：真实持久索引/性能、API访问边界、UI、导出、CI、发布；中文/旧录像/跨年泛化。
- 阻塞：无外部阻塞。项目依赖只在 .venv；Homebrew 提供缺失的 Python3.11/FFmpeg。无待用户授权事项。
- 下一条动作：写 T04 API/媒体访问/标注安全回归并实现同源 FastAPI，再 T05 ZIP 导出；之后 React 实际浏览器全链路。
- 恢复环境：`.venv/bin/python`；依赖锁 `uv.lock`；包管理器 `.bootstrap/bin/uv`；前端 `npm`。
- 本地资料：VoiceTrail 的应用数据目录 / evaluation 子目录，精确相对资料与标签见 docs/evaluation_manifest.json；实际资料与权重只在本地且不上传。
- GitHub：认证账户已核验，首选仓库不存在；还未建仓/上传；首次核心闭环后先私有，T08全部门槛满足才公开并发布。

## 每次结束前更新

记录任务ID、实现变化、命令退出结果、证据位置、失败尝试与不同假设、外部阻塞、最后提交、远端同步状态、下一条明确动作。不要写凭证、私人绝对路径或真实素材内容。

RUNNING表示当前会话正在执行，不能表示会话结束后仍在后台。平台停止后下次读取git和文件确认事实。
