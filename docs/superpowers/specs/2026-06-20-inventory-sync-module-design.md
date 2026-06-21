# ERP 库存同步模块 — 设计文档

> 2026-06-20 ｜ 基于 brainstorm 确认的方案

---

## 1. 目标

从 ERP 系统自动下载库存 XLSX，过滤清洗后生成迪拜仓库存文件，供后续分配算法使用。

---

## 2. 业务流程

```
Playwright 打开 ERP 登录页
  │
  ▼
自动填账号密码登录（持久化上下文保存 Cookie）
  │
  ▼
导航到库存管理页面
  │
  ▼
点击「查看所有库存」→ Box 明细弹窗出现
  │
  ▼
点击「下载」→ XLSX 文件保存到 data/inventory/current/
  │
  ▼
Pandas 后处理：
  1. 移除箱号字段含中文的行
  2. 只保留仓库名称 == "迪拜仓" 的行
  3. 提取 SKU + 当前库存 两列
  4. 同 SKU 的当前库存求和
  │
  ▼
输出：dubai_inventory.xlsx（列：SKU | 当前库存）
```

---

## 3. 关键字段

| ERP 原始字段名 | 用途 | 说明 |
|---|---|---|
| SKU | 与订单 `partner_sku` 匹配 | 去空格，保留原始大小写 |
| 当前库存 | 可分配数量 | 非数字 → 按 0 处理并记录警告 |
| 箱号 | 过滤条件 | 含任何中文字符 → 整行移除 |
| 仓库名称 | 过滤条件 | 只保留 `"迪拜仓"` |

---

## 4. ERP 登录

- **登录页 URL**: `http://www.erpzd.com/#/login?redirect=%2Fcustomer%2Fbox%2Fstock%2Findex`
- **目标页**: `http://www.erpzd.com/#/customer/box/stock/index`
- **方式**: Playwright 持久化上下文（`channel="msedge"`），保存到 `runtime/erp_profile/`
- **账号密码**: 从 `.env` 读取 `ERP_USERNAME` / `ERP_PASSWORD`
- **登录字段**: 待观察实际页面确定 input selector

### 状态维护

- 首次运行 → 自动填密码登录
- 后续运行 → 持久化上下文恢复登录状态，直接打开目标页
- Cookie 失效 → 重新执行登录流程

---

## 5. 文件 I/O

### 原始下载
- 保存路径: `data/inventory/current/inventory_raw.xlsx`
- 每次下载前，旧文件移动到 archive 并加时间戳

### 处理输出
- 输出路径: `data/inventory/current/dubai_inventory.xlsx`
- 固定两列: `SKU` | `当前库存`

### 归档规则
- `data/inventory/archive/inventory_raw_YYYYMMDD_HHMMSS.xlsx`
- `data/inventory/archive/dubai_inventory_YYYYMMDD_HHMMSS.xlsx`

---

## 6. 新增/修改文件

### 新建

| 文件 | 职责 |
|---|---|
| `backend/app/services/inventory_client.py` | Playwright 打开 ERP → 点击查看 → 点击下载 → 保存 XLSX |
| `backend/app/services/inventory_parser.py` | Pandas 读取 XLSX → 过滤箱号 → 过滤仓库 → 汇总 SKU → 输出 XLSX |
| `frontend/src/views/InventoryView.vue` | 库存数据表格（SKU + 当前库存），搜索 + 分页 + 下载 |

### 修改

| 文件 | 变更 |
|---|---|
| `backend/app/core/paths.py` | 新增 INVENTORY_CURRENT_DIR / INVENTORY_ARCHIVE_DIR / ERP_PROFILE_DIR |
| `backend/app/core/config.py` | 新增 `erp_base_url`, `erp_username`, `erp_password` 配置项 |
| `backend/app/api/routes_tasks.py` | 新增 `POST /api/tasks/sync-inventory` |
| `backend/app/api/routes_data.py` | 新增 `GET /api/data/inventory/preview`, `GET /api/files/inventory/latest` |
| `backend/app/schemas/task.py` | 新增 InventoryRow schema |
| `frontend/src/api/index.ts` | 新增库存 API |
| `frontend/src/stores/task.ts` | 新增 `triggerSyncInventory()` |
| `frontend/src/views/DashboardView.vue` | 新增「同步库存」按钮 |
| `frontend/src/router/index.ts` | 新增 `/inventory` 路由 |
| `frontend/src/App.vue` | 侧栏新增「库存数据」菜单 |
| `.env` / `.env.example` | 新增 ERP 配置项 |

---

## 7. API 设计

```
POST /api/tasks/sync-inventory      → 创建后台任务，启动库存同步
GET  /api/tasks/{task_id}           → 查询任务状态（已有）
GET  /api/data/inventory/preview    → 分页返回库存数据
GET  /api/files/inventory/latest    → 下载最新库存文件
```

### 任务状态流转

```
PENDING → RUNNING → SUCCESS
                 → FAILED
                 → WAITING_LOGIN（首次需登录时）
```

---

## 8. 数据处理规则

### inventory_parser.py

```python
# 1. 读取 XLSX
df = pd.read_excel(file_path, dtype=str)

# 2. 移除箱号含中文的行（正则匹配中文字符）
df = df[~df['箱号'].str.contains(r'[一-鿿]', na=False)]

# 3. 只保留迪拜仓
df = df[df['仓库名称'] == '迪拜仓']

# 4. 提取两列
df = df[['SKU', '当前库存']].copy()

# 5. 清洗 SKU（去空格）
df['SKU'] = df['SKU'].astype(str).str.strip()

# 6. 当前库存转数值，非数字 → 0
df['当前库存'] = pd.to_numeric(df['当前库存'], errors='coerce').fillna(0).astype(int)

# 7. 按 SKU 汇总
df = df.groupby('SKU', as_index=False)['当前库存'].sum()
```

### 异常处理

- 文件不存在 → 任务 FAILED，message 说明原因
- 缺少必需列 → 返回明确错误，列出实际列名
- 箱号列缺失 → 跳过中文过滤步骤，记录警告
- 仓库名称列缺失 → 不过滤仓库，记录警告

---

## 9. 前端 InventoryView

- **表格列**: SKU | 当前库存
- **搜索**: 按 SKU 关键词
- **分页**: 同订单页面（20/50/100/200）
- **下载按钮**: 下载 `dubai_inventory.xlsx`
- **统计**: 显示 SKU 数量和总库存件数

---

## 10. 与 Noon 下载模块差异总结

| | Noon 订单下载 | ERP 库存同步 |
|---|---|---|
| 平台 | Noon Directship | erpzd.com |
| 认证方式 | 手动登录 | 自动填密码 |
| 下载流程 | 点 Export → 等异步生成 → 下载 | 点查看 → 弹窗 → 点下载 |
| 文件格式 | CSV | XLSX |
| 后处理 | 提取 3 列 + 解析时间 | 过滤箱号 + 过滤仓库 + 汇总 SKU |
| 持久化目录 | `runtime/noon_profile/` | `runtime/erp_profile/` |
| 输出文件 | `noon_pending_orders.csv` | `dubai_inventory.xlsx` |

---

## 11. 配置项新增

```env
# ERP
ERP_BASE_URL=http://www.erpzd.com
ERP_USERNAME=
ERP_PASSWORD=
ERP_STOCK_PAGE_URL=http://www.erpzd.com/#/customer/box/stock/index
ERP_LOGIN_URL=http://www.erpzd.com/#/login?redirect=%2Fcustomer%2Fbox%2Fstock%2Findex
```
