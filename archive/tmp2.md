经过上一轮的重构，现在系统中agent创建的逻辑其实已经非常清晰了。你来整体看下目前涉及到agent创建的代码，
  然后我们来一块看看是否有问题

⏺ 让我整体梳理目前涉及agent创建的代码逻辑：

  🔍 Agent创建流程分析

  流程1: 系统启动时的Root Agent创建

⏺ Read(src/aether_frame/framework/adk/adk_adapter.py)
  ⎿  Read 25 lines (ctrl+r to expand)

⏺ 流程2: 任务执行时的临时Agent创建

⏺ Read(src/aether_frame/agents/manager.py)
  ⎿  Read 30 lines (ctrl+r to expand)

⏺ 流程3: AdkDomainAgent的实际创建

⏺ Read(src/aether_frame/agents/adk/adk_domain_agent.py)
  ⎿  Read 25 lines (ctrl+r to expand)

⏺ 📊 Agent创建逻辑整体分析

  创建时机分析

  1. 系统启动时 (AdkFrameworkAdapter.initialize()):
    - 创建1个Root Agent (永久存在)
    - 用于ADK Runner绑定
    - 存储在AgentManager中: self._agents[root_agent_id]
  2. 每个任务执行时 (AgentManager.execute_with_runtime()):
    - 创建临时Agent (任务完成后销毁)
    - 复用同样的创建逻辑
    - 也存储在AgentManager中，但会在finally块中销毁

  🤔 发现的潜在问题

  问题1: Agent生命周期混乱

  # Root Agent (永久)
  root_agent_id = await self._agent_manager.create_agent(root_agent_config)  # 启动时创建
  # 永远不会被销毁

  # 临时Agent (临时)
  agent_id = await self._create_agent_with_runtime(agent_request.agent_config, runtime_context)
  # 在 finally 块中销毁: await self.destroy_agent(agent_id)

  Root Agent和临时Agent都存储在同一个字典中，生命周期管理复杂！

  问题2: Agent创建重复

  - Root Agent创建: AgentManager.create_agent()
  - 临时Agent创建: AgentManager._create_agent_with_runtime()
  - 两套几乎相同的创建逻辑

  问题3: 架构不一致

  # Root Agent: 直接访问私有属性
  root_domain_agent = self._agent_manager._agents[root_agent_id]  # ❌ 违反封装

  # 临时Agent: 正常流程
  agent = self._agents[agent_id]  # ✅ 内部访问

  问题4: 资源管理风险

  - Root Agent一直占用内存
  - 临时Agent可能泄露(如果finally失败)
  - AgentManager的_agents字典会无限增长(如果清理失败)

  🎯 建议的改进方案

  选项A: 分离Root Agent和临时Agent管理

  # AdkFrameworkAdapter
  self._root_agent: AdkDomainAgent  # 直接持有Root Agent
  self._agent_manager: AgentManager  # 只管理临时Agent

  选项B: 统一Agent池管理

  # AgentManager增加生命周期标识
  async def create_agent(self, agent_config: AgentConfig, permanent: bool = False) -> str:
      # permanent=True: Root Agent
      # permanent=False: 临时Agent

  选项C: 专门的Root Agent容器

  # 新增RootAgentManager
  class RootAgentManager:
      def get_root_agent(self) -> AdkDomainAgent
      
  # AgentManager只管临时Agent

  你觉得当前的Agent创建逻辑有什么问题？更倾向于哪种改进方案？