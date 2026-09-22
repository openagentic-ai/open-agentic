# modeld — 本地模型调度器

确保本机指定的推理模型处于可用状态。职责只有三件：**显存预检 → 健康探测 → 必要时拉起**。
不做语义判断，不碰业务。

## 为什么需要它

单卡多租户的机器上，显存被别人占走时 vLLM 只抛一句
`Engine core initialization failed`，真因埋在 systemd journal 里。
2026-09-22 的一次事故里，模型反复起不来，排查了很久才发现是显存差 1 GiB——
那张卡上还跑着另一个进程，预留了 8.4 GB 却只用 1.2 GB。

modeld 的作用就是**在拉起之前先把账算清楚，把失败变成一句人话**。

## 接口

服务监听 `127.0.0.1:9998`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | 模型现在能不能用。走 `max_tokens=1` 的真实补全判定 |
| GET | `/gpu` | 显存全貌 + 占用者（诊断用） |
| POST | `/ensure` | 确保模型可用：够显存就拉起，不够就明确拒绝 |

```bash
curl -s http://127.0.0.1:9998/healthz
# {"model_uid":"Qwen3.8-27B","state":"ready","usable":true,"detail":""}

curl -s -X POST http://127.0.0.1:9998/ensure
# {"model_uid":"Qwen3.8-27B","state":"ready","action":"none"}

curl -s http://127.0.0.1:9998/gpu
# {"total_mib":24564,"used_mib":21193,"free_mib":2917,
#  "users":[{"pid":64297,"name":"VLLM::EngineCore","used_mib":21176}]}
```

三态语义：

| state | 含义 |
|---|---|
| `ready` | 可用（打了一次真实补全确认） |
| `loading` | 实例存在但未就绪，或服务暂时不可用 |
| `down` | 连不上，或返回了意料之外的错误 |

`/ensure` 的拒绝路径返回 **HTTP 409**，带缺口大小和占用者 PID。

### 探测为什么打补全

`/v1/models` 里列出模型 **≠ 可用**——实例加载中也会被列出。
只有真打一次补全才能回答「现在能不能用」。
补全会占用序列槽位（本地 vLLM 只有 2 个），所以结果按 `probe.cache_ttl_sec` 缓存，`/healthz` 与 `/ensure` 共用。

## 配置

`extensions/modeld/modeld.yaml`（mode 600，含 Xinference 凭证）。改参数不用动代码。

```yaml
xinference:
  base_url: "http://127.0.0.1:9997"
  username: "admin"
  password: "..."
  api_key: "..."

gpu:
  # nvidia-smi 报的总量与 vLLM 实际可用量之差 = 驱动/CUDA 上下文开销。
  # 预检必须按 vLLM 的口径算，否则会误判成"显存够"。
  driver_overhead_mib: 459

probe:
  cache_ttl_sec: 5
  launch_timeout_sec: 900

models:
  - model_uid: "Qwen3.8-27B"
    model_name: "Qwen3.8-27B"
    model_engine: "vllm"
    gpu_memory_utilization: 0.95
    max_model_len: 32768
    max_num_seqs: 2
    enforce_eager: true
```

配置是**必需输入**：文件缺失或结构非法会直接抛错，不像可选的策略层那样静默降级——
否则守护进程会带病运行。

## 部署

```bash
systemctl status  modeld
systemctl restart modeld
journalctl -u modeld -f
```

首次启用：

```bash
cp modeld.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now modeld
```

## 开发

```bash
cd extensions/modeld
/usr/bin/python3 -m pytest tests/ -q
```

零第三方依赖之外只用了 `fastapi` / `uvicorn` / `PyYAML`，全部是系统 python3 自带的，
和 `/opt/zhulu-server` 同一套范式（不用 venv）。

## 边界

- 只管**模型生命周期**。语义判断（分类/路由/验收）不在这里。
- 看到显存被别的进程占用时**只报告，不杀进程**——那可能是别人的生产服务。
- 当前只管配置里的第一个模型（`primary`），多模型留了结构但未启用。
