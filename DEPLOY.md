# 部署规则（Deployment Rules）

> 本文件是本项目**唯一的部署权威规则**。
> 任何会话、任何工具、任何 CI 任务在部署本项目时，必须遵守本文。

---

## 1. 唯一部署目标（不可变更）

| 项 | 值 |
|---|---|
| 托管平台 | **EdgeOne Makers**（`edgeone` CLI，连接器版） |
| 项目名 | `price-collector-demo` |
| Project ID | `makers-w8in1esdzuub` |
| 控制台 | https://console.cloud.tencent.com/edgeone/pages/project/makers-w8in1esdzuub |
| 部署形态 | 静态前端 + Python 云函数**同域**部署 |
| 费用 | 免费套餐 |
| Docker | **禁止使用**（不构建镜像、不起容器） |

### 🔴 硬性禁令

1. **禁止创建新项目。** 不得使用 `edgeone makers create`，不得使用 `--anonymous`（会创建临时项目），
   不得把 `-n` 写成任何 `price-collector-demo` 以外的值。
2. **禁止改项目名。** 即使部署失败、即使提示项目不存在，也不得换名重试——先向用户报告。
3. **禁止并行多目标。** 不得同时推送到 GitHub Pages / Render / CloudStudio 等其它托管；
   唯一线上出口是上面这个 EdgeOne 项目。
4. **禁止用 `npx edgeone`。** 公开版（1.6.40+）无 `skills` 后端，会导致 token 无效。

---

## 2. 部署命令契约（必须逐字遵循）

```bash
export PAGES_SOURCE=skills                 # 必需：启用连接器后端
edgeone makers deploy ./deploy \
  -n price-collector-demo \
  -t "$EDGEONE_API_TOKEN" \
  --json
```

- CLI 版本必须锁定 **`edgeone@1.6.17-beta.1`**（连接器专属版）。
- 安装方式必须用 `npm install -g edgeone@1.6.17-beta.1`，**不能用 npx**（npm 内部 bug）。
- 子命令必须用 **`makers deploy`**，不能用 `pages deploy`（两者对 `-t` 的校验路径不同）。

### 部署产物 `deploy/` 的装配规则

由 `build_deploy.py` 生成（纯标准库，无第三方依赖）：

```
deploy/
├── index.html / app.js / style.css      # 前端静态资源（来自 web/）
├── cloud-functions/
│   ├── api/health.py                    # GET /api/health
│   ├── api/search.py                    # GET /api/search
│   ├── api/insights.py                  # GET /api/insights（AI 比价洞察）
│   ├── api/netcheck.py                  # GET /api/netcheck（连通性自检）
│   └── price_collector/                 # 🔴 采集包必须在这里
└── price_collector/                     # 项目根兜底副本
```

🔴 **关键约束**：EdgeOne 构建器**只扫描 `cloud-functions/` 下的 `.py`** 作为辅助模块。
若 `price_collector` 只放在项目根，云函数导入失败会**静默返回 404**（不报错、路由不注册）——
这正是历史上"线上没有实际内容"的根因。任何时候调整装配脚本，都必须保持此结构。

---

## 3. Git 推送自动同步

- 触发条件：推送 `main` 分支 → `.github/workflows/deploy.yml` 自动构建并部署。
- GitHub Secrets 要求：`EDGEONE_API_TOKEN`（必需）；
  `PC_CPS_TB_APPKEY` / `PC_CPS_TB_SECRET` / `PC_CPS_TB_ADZONE` / `PC_CPS_JD_APPKEY` / `PC_CPS_JD_SECRET`（可选，CPS 凭据）。
- 工作流内置**项目守卫**：部署后解析 `--json` 的 `projectId`，
  若不等于 `makers-w8in1esdzuub` 则判定为"疑似新建项目"并让任务失败告警。

### 写入 Secret 的正确姿势（易踩坑）

```bash
# ✅ 正确：省略 -b，从 stdin 读取
python -c "import json,os,sys; sys.stdout.write(TOKEN)" | gh secret set EDGEONE_API_TOKEN -R afdk1991/proj-08

# ❌ 错误：-b - 会把 "-" 当成字面量，Secret 值变成单个短横线，CI 报 Invalid token
# ❌ 错误：print() 会带尾随换行污染密钥，必须用 sys.stdout.write
```

---

## 4. 部署后验收（每次必做，不通过不算完成）

必须验证以下三项，全部符合才算部署成功：

| 检查项 | 期望 |
|---|---|
| `GET /` | 200，返回前端首页 |
| `GET /api/health` | 200，返回 `{"status":"ok","runtime":"python3.10"}`（证明云函数真在跑） |
| `GET /api/search?keyword=蓝牙耳机` | 200，返回 JSON；重点看 `source_status` 字段（如实反映各平台 `ok/empty/needs_config/api_error`）与 `live_platforms` 计数 |

> ⚠️ **验收口径已改正**：不得再用 `source=mock` 验收（该参数现在被忽略，永远走真实抓取 live）。
> 由于云端/未知 IP 直接抓京东/淘宝/拼多多/苏宁会被反爬拦截，`total` 完全可能 = 0。
> **正确的"成功"定义是：接口返回真实结构 + `source_status` 如实说明每个平台的可用状态**，而不是伪造/要求有数据。
> 想让国内平台真正返回商品，见第 7 节「启用联盟 API」。

### 访问鉴权说明

该项目开启了预览访问鉴权，访问需带 `?eo_token=...&eo_time=...`
（由 `deploy --json` 输出的 `url` 字段给出），且需保持 Cookie 会话。
**裸域名直连会返回 401**，这是正常现象，不是部署失败。
如需免 token 公网访问，须在 EdgeOne 控制台关闭访问鉴权或绑定自定义域名（CLI 未暴露该能力）。

---

## 5. 排错速查

| 现象 | 根因 | 处理 |
|---|---|---|
| `/api/search` 404，但 `/api/health` 200 | 采集包未打进 `cloud-functions/` | 检查 `build_deploy.py` 第 3 步 |
| `Invalid EDGEONE_PAGES_API_TOKEN` | CLI 版本不对 / Secret 被写成 `-` | 锁 `1.6.17-beta.1`；用 stdin 重写 Secret |
| `npm error ... edgesOut` | 用了 `npx` | 改 `npm install -g` |
| 云函数 500 且带 ImportError | 辅助模块缺失 | 见上面第 2 节结构约束 |
| 页面空白无数据 | 前端 `fetch('/api/search')` 失败 | 先 curl 验 API，再看前端 |

---

## 7. 真实抓取状态与如何启用国内数据（联盟 API）

本项目**已实现真实抓取流水线**（非 mock）：`pipeline.run()` 并发调用各平台 `fetch()`，
结果经清洗/评分/推荐后返回。但"能否抓到真实商品"取决于数据源是否被反爬拦截、以及是否配置了联盟 API 凭据。

### 7.1 当前真实状态（云端 IP 实测）

| 平台 | 状态 | 原因 |
|---|---|---|
| **`dangdang` 当当网** | **`ok`** ✅ | **免密钥真实抓取**：当当搜索页为静态 HTML 承载商品、对机房/云端 IP 无强制风控。实测 0.4s 返回约 60 条真实商品（名称 / 现价 / 定价 / 店铺 / 详情链接），是全项目首个稳定可用的**国内**真实源。字段取自 `p.price span.price_n`（现价）、`span.price_r`（定价）、`p.name a[title]`、`p.link a[title]` |
| `amazon` | `ok`（偶发 `empty`） | 海外站对此 IP 较宽松，偶尔限流返回空 |
| `jd` / `taobao` / `pdd` / `suning` / `tmall` … | `empty` | 直连被反爬/风控拦截（验证页 / 403 / 空壳），免密无法穿透 |
| `tb_cps`（淘宝联盟） | `api_error: scope ids is 381 …` | 现有淘宝联盟账号**未开通** `taobao.tbk.dg.material.optional`（通用物料搜索）权限 |
| `jd_cps`（京东联盟） | `needs_config` | 未填写京东联盟 AppKey/Secret |
| 其它 30+ 平台 | `empty` | 同上，反爬拦截 |

> 结论：**不是"没写抓取代码"，而是被反爬 + 联盟权限双重阻断，且历史代码静默吞错让人误以为没实现。**
> 现每个平台状态已如实上报（见 `source_status`），不再静默空结果。

### 7.2 京东 / 淘宝 / 拼多多：需用联盟官方 API（当当已可免密钥直连）

> ✅ **好消息**：国内数据不必全靠联盟 API —— **当当网已实现免密钥真实抓取**（见 7.1），
> 搜索当当即可拿到真实商品参与比价，无需任何账号、权限或密钥。

但若还需**京东 / 淘宝 / 天猫 / 拼多多**的真实数据，因其网页直连被反爬系统性拦截，
合规且稳定的来源仍是各平台联盟开放 API（非网页爬虫）。项目已内置 `tb_cps` / `jd_cps`，配置好凭据即返回真实商品+价格：

**淘宝/天猫（tb_cps）**
1. 登录 [pub.alimama.com](https://pub.alimama.com) 注册淘宝客，拿到 AppKey / AppSecret / 推广位 adzone_id。
2. **申请 `taobao.tbk.dg.material.optional` 接口权限**（当前账号缺此权限，状态会显示 `api_error`）。
3. 把凭据写入（二选一）：
   - 环境变量：`PC_CPS_TB_APPKEY` / `PC_CPS_TB_SECRET` / `PC_CPS_TB_ADZONE`
   - 或 `price_collector/_cps_config.py`（已存在，含占位值）
   - 或 GitHub Secret（CI 用）：`PC_CPS_TB_APPKEY` 等

**京东（jd_cps）**
1. 登录 [union.jd.com](https://union.jd.com) 注册京东联盟，创建应用拿 AppKey / AppSecret，申请 `jd.union.open.goods.query` 权限。
2. 填写 `PC_CPS_JD_APPKEY` / `PC_CPS_JD_SECRET`（当前为空）。

配置就绪后，`tb_cps`/`jd_cps` 的 `can_live()` 返回 True，fetch 走官方 API 返回真实数据，
`source_status` 变为 `ok`，`live_platforms` 增加，前端比价立即有真实商品。

### 7.3 备选：浏览器渲染 + 代理爬虫（需另建基础设施）

若要"免密钥直连抓京东/淘宝"，必须突破反爬：需要 **Playwright/无头浏览器 + 住宅代理/IP 轮换**，
且目标站常需登录态 Cookie。这套不在本免费 stdlib 云函数支持范围内，需独立部署
（容器 + 浏览器二进制 + 代理池），属于另一条技术栈，不在本项目交付内。

---

## 6. 本地开发 vs 线上部署（不要混淆）

- 本地调试：`python server.py` → http://127.0.0.1:8765
- **交付标准是线上部署并验收通过**，不是本地能跑。
- 本地部署命令与 CI 完全一致，唯一区别是 token 来源（本地取 `~/.edgeone/` 凭据，CI 取 Secrets）。
