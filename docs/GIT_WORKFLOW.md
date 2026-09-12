# 团队 Git 工作流规范

本项目采用 **Conventional Commits（提交信息规范）+ Git Flow（分支模型）**。所有成员请遵循本文档协作。

## 一、分支模型（Git Flow）

| 分支            | 用途                             | 切出自      | 合并回              |
| --------------- | -------------------------------- | ----------- | ------------------- |
| `main`          | 生产稳定分支，始终可发布         | —           | —                   |
| `develop`       | 集成开发分支                     | `main`      | `main`              |
| `feature/<名>`  | 新功能                           | `develop`   | `develop`           |
| `fix/<名>`      | 常规缺陷修复                     | `develop`   | `develop`           |
| `hotfix/<名>`   | 线上紧急修复                     | `main`      | `main` 和 `develop` |
| `release/<版本>`| 发布准备                         | `develop`   | `main`（并打 tag）  |

分支名一律使用小写 + 连字符，例如 `feature/user-auth`、`fix/login-error`。

## 二、提交信息规范（Conventional Commits）

格式：

```
<type>(<scope>): <subject>
```

**type 取值**：

- `feat` 新功能 · `fix` 修复 · `docs` 文档 · `style` 格式
- `refactor` 重构 · `perf` 性能 · `test` 测试
- `build` 构建/依赖 · `ci` CI 配置 · `chore` 杂项 · `revert` 回滚

**要求**：subject 用祈使语气、首字母小写、结尾不加句号、建议 <= 50 字符。破坏性变更在 footer 写 `BREAKING CHANGE:`，关联 issue 写 `Closes #123`。

示例：

```
feat(api): 新增用户问候接口

Closes #12
```

## 三、日常协作流程

```bash
# 1. 切到 develop 并同步最新代码
git switch develop
git pull --rebase origin develop

# 2. 切出功能分支
git switch -c feature/your-feature

# 3. 开发并小步提交（遵循提交规范）
git add <files>
git commit -m "feat(scope): 描述"

# 4. 推送分支
git push -u origin feature/your-feature

# 5. 到 GitHub 发起 Pull Request，目标分支 develop
# 6. 通过 Review 与 CI 后合并（推荐 Squash and merge），并删除功能分支
```

## 四、拉取 / 推送约定

- 默认使用 rebase 拉取，保持线性历史：`git pull --rebase`
- **禁止**直接向 `main` / `develop` 推送，一律通过 PR
- **禁止** `--force` 强推共享分支；整理个人分支用 `--force-with-lease`
- 推送新分支使用 `-u` 建立跟踪

## 五、建议：在 GitHub 上启用分支保护

仓库 **Settings -> Branches -> Add branch protection rule**，对 `main` 和 `develop`：

- Require a pull request before merging（合并前必须 PR）
- Require approvals（至少 1 人 Review 通过）
- Require status checks to pass（CI 通过）

这样可以从平台层面强制执行上面的规范。
