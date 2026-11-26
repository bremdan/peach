# Peach fork 专属规则（bremdan）

本文件只补充本 fork 的私事，不替代根目录 `AGENTS.md`；根目录规则继续全程有效。

## 分支纪律

- agent 任务分支按工具实际命名 `opencode/<issue编号>-<时间戳>`（例如 `opencode/issue4-20261126075153`），从最新 `master` 拉出；不再要求手工改成 `agent/opencode/<任务>`。
- 一个分支只承载一个可独立验收的目标；合并后删除该分支。
- agent 绝不直接向 `master` 推送，代码改动一律经 PR。

## 提交身份

- 提交作者必须是仓库主人 bremdan 本人；绝不冒用维护者或任何仓库历史作者的身份。
- agent 产生的提交须在提交信息末尾带 `Co-Authored-By` 署名，口径与 `scripts/co_author.py` 中 OpenCode 的登记一致：
  `Co-Authored-By: OpenCode (<实际模型>) <noreply@opencode.ai>`

## 验收口径

- 每一步的验收标准以对应 issue 正文写明的为准。
- 验收数据在仓库主人本机（参考照片、试点数据、本机 GPU 等）时，PR 内只验逻辑，并在 PR 描述中如实标注「待原环境验收」；不许把推测写成已验证。

## 测试纪律

- 只用仓库统一测试入口 `./scripts/test.sh`：日常 `auto`，影响面不明用 `full`。
- 逐文件暂存，禁止 `git add .`。
- 测试结果（命令、通过/失败数、跳过项及原因）必须贴进 PR 描述。

## PR 纪律

- PR 正文须含四节：「目标 / 实际改动 / 影响面表（数据层、API、页面、契约、测试、文档）/ 测试结果」。
- 用 `Refs #<issue 编号>` 关联 issue；禁止使用 `Fixes` / `Closes` / `Resolves` 自动关单。
- 合并只能由仓库主人执行。

## 版本纪律

- 不改版本号，不动已发布版本段。
- 本 fork 的治理改动不进 `CHANGELOG.md`。
