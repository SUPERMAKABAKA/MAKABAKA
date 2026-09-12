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

## 接入 Amazon Bedrock（真实 LLM 与 embedding）

系统默认使用离线 Mock 实现（`mock` LLM + `deterministic` embedding），可零配置本地运行。
若要接入 Amazon Bedrock 的真实模型（区域：新加坡 ap-southeast-1），无需改代码，按以下步骤操作。

### 1. 在 AWS 控制台准备

1. 创建 IAM 用户并生成访问密钥，附加 `AmazonBedrockFullAccess` 权限（生产环境建议收敛为仅 `bedrock:InvokeModel`）。
2. 控制台切到 **Asia Pacific (Singapore) ap-southeast-1**，进入 **Bedrock → Model access**，开通：
   - `amazon.titan-embed-text-v2:0`（Titan Text Embeddings V2，1024 维）
   - `amazon.nova-lite-v1:0`（对话模型 Nova Lite）

### 2. 配置环境变量

```bash
# 切换实现为 Bedrock（不改代码）
export LLM_IMPL=bedrock
export EMBEDDER_IMPL=bedrock

# AWS 凭证（boto3 默认凭证链）
export AWS_ACCESS_KEY_ID=你的AccessKeyId
export AWS_SECRET_ACCESS_KEY=你的SecretAccessKey
export AWS_REGION=ap-southeast-1
```

Windows PowerShell 用 `$env:LLM_IMPL="bedrock"` 形式设置。

### 3. 必须重新灌库

embedding 维度从 Mock 的 64 维变为 Titan V2 的 1024 维，同一 Chroma 库不能混用不同维度。
切换到 Bedrock embedding 后，务必清空旧向量库并重新灌库：

```bash
# 删除旧向量库（64 维）
rm -rf .chroma          # Windows: Remove-Item -Recurse -Force .chroma

# 用 Bedrock embedding 重新灌库
python -m scripts.ingest
```

灌库侧与检索侧必须使用同一 embedder 实现，否则维度不匹配会报错。

### 可配置项（app/config.py 的 Settings）

| 配置 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `bedrock_region` | `ap-southeast-1` | Bedrock 区域 |
| `bedrock_llm_model_id` | `amazon.nova-lite-v1:0` | 对话模型 |
| `bedrock_embed_model_id` | `amazon.titan-embed-text-v2:0` | embedding 模型 |
| `bedrock_embed_dim` | `1024` | embedding 维度 |
