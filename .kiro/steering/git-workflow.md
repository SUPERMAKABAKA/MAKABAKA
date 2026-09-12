---
inclusion: always
---

# Git 协作规范（Conventional Commits + Git Flow）

本文件是团队的 Git 提交、拉取、推送、分支与 PR 规范。当协助用户进行 Git 相关操作（生成 commit message、创建分支、推送、发起 PR）时，必须遵循以下约定。

## 提交信息规范（Conventional Commits）

格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

- **type（必填）**，只能是以下之一：
  - `feat`：新功能
  - `fix`：修复缺陷
  - `docs`：仅文档变更
  - `style`：不影响逻辑的格式调整（空格、分号、格式化）
  - `refactor`：重构（既非新增功能也非修复缺陷）
  - `perf`：性能优化
  - `test`：新增或修改测试
  - `build`：构建系统或依赖变更（如 requirements.txt）
  - `ci`：CI 配置变更
  - `chore`：杂项（不修改 src 或 test 的其他改动）
  - `revert`：回滚某次提交
- **scope（可选）**：影响范围，如 `api`、`auth`、`deps`。
- **subject（必填）**：简短描述，使用祈使语气，首字母小写，结尾不加句号，建议不超过 50 字符。
- **body（可选）**：说明改动的动机与背景，每行不超过 72 字符。
- **footer（可选）**：
  - 破坏性变更以 `BREAKING CHANGE:` 开头。
  - 关联 issue 用 `Closes #123`、`Refs #123`。

示例：

```
feat(api): 新增用户问候接口

支持通过路径参数返回个性化问候语。

Closes #12
```

## 分支模型（Git Flow）

- `main`：生产稳定分支，只接受来自 `develop` 或 `hotfix/*` 的合并，始终可发布。
- `develop`：集成开发分支，功能分支从此切出并合回。
- `feature/<描述>`：新功能分支，从 `develop` 切出，完成后 PR 合回 `develop`。命名如 `feature/user-auth`。
- `fix/<描述>`：常规缺陷修复分支，从 `develop` 切出。
- `hotfix/<描述>`：线上紧急修复分支，从 `main` 切出，修复后同时合回 `main` 和 `develop`。
- `release/<版本>`：发布准备分支，从 `develop` 切出，稳定后合入 `main` 并打 tag。

分支命名一律使用小写字母加连字符（kebab-case）。

## 工作流程

1. 同步最新代码：`git switch develop` 后 `git pull --rebase origin develop`。
2. 切出功能分支：`git switch -c feature/xxx`。
3. 小步提交，遵循上面的提交规范。
4. 推送分支：`git push -u origin feature/xxx`。
5. 在 GitHub 上发起 Pull Request，目标分支为 `develop`。
6. 通过 Code Review 与 CI 后合并；合并方式优先使用 Squash and merge 保持历史整洁。
7. 合并后删除已完成的功能分支。

## 拉取 / 推送约定

- 拉取默认使用 rebase 保持线性历史：`git pull --rebase`。
- 禁止直接向 `main` 或 `develop` 推送，必须通过 PR。
- 禁止使用 `--force` 强制推送到共享分支；如需整理个人分支，使用 `--force-with-lease`。
- 推送新分支时使用 `-u` 建立跟踪：`git push -u origin <branch>`。

## Kiro 行为约束

- 生成 commit message 时严格遵循 Conventional Commits 格式，type 从上面的白名单中选取。
- 需要提交时，若用户未指定分支，先确认当前不在 `main`/`develop` 上直接提交。
- 推送前提醒用户目标分支，遵循“经 PR 合并”的原则。
- 不提交敏感文件（`.env`、密钥等，已在 `.gitignore` 中排除）。
