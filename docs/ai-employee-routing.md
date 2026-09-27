# AI 员工任务分流

OpenAgentic 现在把 JEV 放在任务收件口，作为总控的前置判断器。JEV 只做封闭选项判断，岗位 Agent 仍由后续编排层执行。

## 开启方式

```bash
export OPENAGENTIC_JEV_ENABLED=1
export JEV_API_KEY=your-key
export OPENAGENTIC_TASK_ROUTING_ENABLED=1
```

也可以用 `TYPESAFE_API_KEY` 作为密钥回退。没有密钥、没有开启开关、JEV 请求失败或返回非法选项时，任务仍按原流程创建，不会阻塞任务入口。

## 任务流

```text
POST /api/tasks
  ↓
JEV 判断 department / role / task_type / priority / risk / needs_human_decision
  ↓
岗位注册表确认 role，任务写入 metadata_json.routing 和 metadata_json.employee
  ↓
高风险或需要本人决定 → waiting_user → POST /api/tasks/{id}/approve
普通任务 → planned
  ↓
总控读取路由结果，交给队列和岗位 Agent
```

路由结果使用稳定的机器标识，例如：

```json
{
  "department": "engineering",
  "role": "integration_ops",
  "task_type": "recurring",
  "priority": "P1",
  "risk": "medium",
  "needs_human_decision": false,
  "confidence": 0.83
}
```

当前这一步负责“判断、登记和审批拦截”，不会自动调用岗位 Agent，也不会替本人执行高风险操作。这样可以先观察真实任务的分流质量，再接入具体 Agent 的执行器。

岗位注册表已经固定了 9 个岗位标识。`POST /api/tasks/{id}/approve` 是本人审批闸门；批准后任务进入 `planned`，后续执行器可以从 `metadata_json.employee.role` 找到对应 Agent。
