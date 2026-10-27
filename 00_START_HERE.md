# VoiceTrail 给 Trae 的完整执行包

目标：做出能用真实声音检索本地影音资料的技术预览，并上传到个人 GitHub。它不是产品代码，不是已经运行的项目。

## 你只需要这样开始

1. 在个人项目位置解压本包。解压后包含 PROMPT_START.md 的文件夹默认叫 voicetrail-trae-kit，可以重命名为 voicetrail。不要放进公司代码仓库，不要把公司代码、内部文档、日志或素材复制进来。
2. 用 Trae 直接打开包含 PROMPT_START.md、AGENTS.md 的文件夹本身，不要只打开它的上一级。选择能执行终端和编辑文件的 Agent / SOLO 模式；具体名称取决于你的版本。
3. 新建一轮对话，引用或附加 PROMPT_START.md，发送其中全文。其余规格和任务文件已经在目录里，提示词会让它自己读取。
4. 只处理真正需要你的操作：GitHub交互登录、系统权限、补充真实测试素材。普通技术选择由它执行，不逐个确认。
5. 对话停了或换窗口时发 PROMPT_RESUME.md。不要另开多个窗口同时修改同一目录。

提示词不能使 Trae 在额度耗尽、权限弹窗、程序退出、电脑休眠后自动继续；续跑依靠落盘状态。不要装一个无限点击“继续”的脚本。

## 已填好的 GitHub 目标

- 个人账户：Xiangyu2141480（本次通过已连接的 GitHub 账户查询）。
- 新仓库首选名：voicetrail；若同名项目不是本项目，不覆盖。
- 开发阶段：私有备份。达到发布门槛后，主提示词已授权公开源码并发布技术预览，无需再次确认。
- 当前电脑上的 gh 登录仍需现场核验，不能假定与这里一致。
- 发布内容限本项目可公开源码、配置、文档和明确许可的演示资料；真实素材、声纹向量、数据库、模型缓存、公司资产都不上传，私有仓库也不上传。

## 文件怎么用

| 文件 | 使用时机 |
|---|---|
| PROMPT_START.md | 第一次，完整发送给 Trae |
| PROMPT_RESUME.md | 停顿、上下文用完或换窗口 |
| PROMPT_REVIEW.md | 想独立查是否真的做成了；审查窗口不与开发窗口同时写文件 |
| PROMPT_PUBLISH.md | 发布被登录或网络阻塞，恢复后补做；也可单独检查发布状态 |
| PROMPT_REPAIR.md | 出现错误，防止推倒重写 |
| AGENTS.md | 每轮执行的固定约束 |
| PROJECT_SPEC.md | 产品范围、接口与验收 |
| docs/superpowers/plans/2026-10-27-voicetrail-v01.md | 按任务执行的计划 |
| TASKS.md / STATE.md | 任务和断点；执行时更新 |
| docs/EVIDENCE.md | 真实验证证据，初始为未验证 |
| docs/THIRD_PARTY.md | 第三方来源、模型与样例许可，初始待核验 |

## 人必须负责的事

技术预览完成后，你要自己找用户试用。Trae不能替你产生“5位用户使用、3位再次使用”的事实。先看一个人能否安装、导入真实资料、找到片段并导出，再看演示和星标。

预计前几个工作段先处理环境和真实模型；不要因为还没有漂亮页面就催它跳过验证。

## 官方参考

- Trae SOLO：https://docs.trae.cn/ide_solo-mode
- GitHub建仓：https://cli.github.com/manual/gh_repo_create
- GitHub登录：https://cli.github.com/manual/gh_auth_login
- GitHub可见性：https://cli.github.com/manual/gh_repo_edit
- 参考模型卡：https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb

本包编写日期：2026-10-27。Trae实施前应重新核验具体库版本与命令，不照抄旧API。
