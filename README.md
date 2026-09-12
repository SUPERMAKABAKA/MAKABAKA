# MAKABAKA

基于 [FastAPI](https://fastapi.tiangolo.com/) 构建的 Web 服务项目。

## 环境要求

- Python 3.9+

## 快速开始

1. 克隆仓库

   ```bash
   git clone <仓库地址>
   cd MAKABAKA
   ```

2. 创建并激活虚拟环境

   ```bash
   python -m venv .venv
   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1
   # macOS / Linux
   source .venv/bin/activate
   ```

3. 安装依赖

   ```bash
   pip install -r requirements.txt
   ```

4. 启动开发服务

   ```bash
   uvicorn main:app --reload
   ```

   服务启动后访问：

   - 根路径: http://127.0.0.1:8000/
   - 接口文档 (Swagger UI): http://127.0.0.1:8000/docs

## 接口一览

| 方法 | 路径            | 说明             |
| ---- | --------------- | ---------------- |
| GET  | `/`             | 返回欢迎信息     |
| GET  | `/hello/{name}` | 返回指定名字问候 |

## 团队协作

- 请从 `main` 分支切出功能分支进行开发，命名建议：`feature/xxx`、`fix/xxx`。
- 提交前请确保代码可运行，并通过 Pull Request 合并到 `main`。
- 不要提交 `.env`、密钥等敏感文件（已在 `.gitignore` 中排除）。

## 项目结构

```
MAKABAKA/
├── main.py            # FastAPI 应用入口
├── test_main.http     # 接口测试请求
├── requirements.txt   # 项目依赖
├── README.md          # 项目说明
└── .gitignore         # Git 忽略规则
```
