use std::sync::Arc;

use openclaw_agent::evo::registry::{DynamicSkill, SharedSkillRegistry};
use openclaw_agent::squad::{Squad, SquadRegistry, SquadType};
use openclaw_memory::factory::MemoryBackend;

pub struct SquadService {
    squad_registry: Arc<SquadRegistry>,
    agent_memory: Arc<openclaw_agent::squad::AgentMemoryService>,
    squad_memory: Arc<openclaw_agent::squad::SquadMemoryService>,
}

impl SquadService {
    pub async fn new(
        skill_registry: Arc<SharedSkillRegistry>,
        memory_backend: Arc<dyn MemoryBackend>,
    ) -> Result<Self, String> {
        let squad_registry = Arc::new(SquadRegistry::new());

        let agent_mem = Arc::new(openclaw_agent::squad::AgentMemoryService::new(
            memory_backend.clone(),
        ));
        let squad_mem = Arc::new(openclaw_agent::squad::SquadMemoryService::new(
            memory_backend,
        ));

        Self::load_squad_definitions(skill_registry, &squad_registry).await?;

        Ok(Self {
            squad_registry,
            agent_memory: agent_mem,
            squad_memory: squad_mem,
        })
    }

    async fn load_squad_definitions(
        skill_registry: Arc<SharedSkillRegistry>,
        squad_registry: &Arc<SquadRegistry>,
    ) -> Result<(), String> {
        let skills = skill_registry.get_all_skills().await;

        for skill in skills {
            if skill.is_squad() {
                Self::parse_and_create_squad(&skill, squad_registry).await?;
            }
        }

        if !squad_registry.list_squads().await.is_empty() {
            tracing::info!(
                "Loaded {} squads from skills",
                squad_registry.list_squads().await.len()
            );
        }

        Ok(())
    }

    async fn parse_and_create_squad(
        skill: &DynamicSkill,
        squad_registry: &Arc<SquadRegistry>,
    ) -> Result<(), String> {
        let metadata = &skill.metadata;

        let squad_id = metadata
            .get("id")
            .cloned()
            .unwrap_or_else(|| skill.id.clone());
        let name = metadata
            .get("name")
            .cloned()
            .unwrap_or_else(|| skill.name.clone());
        let description = metadata.get("description").cloned().unwrap_or_default();
        let squad_type_str = metadata.get("type").cloned().unwrap_or_default();
        let lead_agent_id = metadata.get("lead_agent_id").cloned().unwrap_or_default();
        let memory_namespace = metadata
            .get("memory_namespace")
            .cloned()
            .unwrap_or_else(|| format!("squad:{}", squad_id));

        let squad_type = match squad_type_str.as_str() {
            "ProductGrowth" => SquadType::ProductGrowth,
            "TechPlatform" => SquadType::TechPlatform,
            "MarketingGrowth" => SquadType::MarketingGrowth,
            _ => SquadType::Custom(squad_type_str),
        };

        let mut squad = Squad::new(squad_id.clone(), name, squad_type, lead_agent_id)
            .with_description(description)
            .with_memory_namespace(memory_namespace);

        if let Some(members_str) = metadata.get("members") {
            let members: Vec<&str> = members_str.split(',').collect();
            for member in members {
                let member = member.trim();
                if !member.is_empty() {
                    squad = squad.with_member(openclaw_agent::squad::SquadMember::new(
                        member.to_string(),
                        openclaw_agent::squad::SquadRole::Executor,
                    ));
                }
            }
        }

        squad_registry.create_squad(squad).await?;

        Ok(())
    }

    pub fn squad_registry(&self) -> Arc<SquadRegistry> {
        self.squad_registry.clone()
    }

    pub fn agent_memory_service(&self) -> Arc<openclaw_agent::squad::AgentMemoryService> {
        self.agent_memory.clone()
    }

    pub fn squad_memory_service(&self) -> Arc<openclaw_agent::squad::SquadMemoryService> {
        self.squad_memory.clone()
    }
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use async_trait::async_trait;
    use openclaw_core::{Message, Result as OpenClawResult};
    use openclaw_memory::factory::MemoryBackend;
    use openclaw_memory::recall::RecallResult;
    use openclaw_memory::types::{MemoryItem, MemoryRetrieval};

    use super::*;

    struct MockMemoryBackend;
    #[async_trait]
    impl MemoryBackend for MockMemoryBackend {
        async fn store(&self, _memory: MemoryItem) -> OpenClawResult<()> {
            Ok(())
        }
        async fn recall(&self, _query: &str) -> OpenClawResult<RecallResult> {
            Ok(RecallResult {
                items: Vec::new(),
                query: String::new(),
                total_found: 0,
            })
        }
        async fn add(&self, _message: Message) -> OpenClawResult<()> {
            Ok(())
        }
        async fn retrieve(&self, _query: &str, _limit: usize) -> OpenClawResult<MemoryRetrieval> {
            Ok(MemoryRetrieval::new())
        }
    }

    #[tokio::test]
    async fn test_service_creation() {
        let registry = SharedSkillRegistry::new();
        let backend = Arc::new(MockMemoryBackend) as Arc<dyn MemoryBackend>;
        let service = SquadService::new(Arc::new(registry), backend).await;
        assert!(service.is_ok());
    }

    #[tokio::test]
    async fn test_load_squad_from_skill() {
        let mut skill = DynamicSkill::new_squad(
            "squad_product".to_string(),
            "Product Squad".to_string(),
            std::collections::HashMap::new(),
        );
        skill.metadata.insert("id".to_string(), "squad_1".to_string());
        skill.metadata.insert("name".to_string(), "Product Team".to_string());
        skill.metadata.insert("type".to_string(), "ProductGrowth".to_string());
        skill.metadata.insert("lead_agent_id".to_string(), "agent_lead".to_string());
        skill.metadata.insert("members".to_string(), "agent_1,agent_2".to_string());

        let new_registry = Arc::new(SharedSkillRegistry::new());
        new_registry.register_skill(skill).await;

        let backend = Arc::new(MockMemoryBackend) as Arc<dyn MemoryBackend>;
        let service = SquadService::new(new_registry, backend).await.unwrap();

        let squads = service.squad_registry().list_squads().await;
        assert_eq!(squads.len(), 1);
        assert_eq!(squads[0].id, "squad_1");
    }

    #[tokio::test]
    async fn test_squad_registry_access() {
        let registry = SharedSkillRegistry::new();
        let backend = Arc::new(MockMemoryBackend) as Arc<dyn MemoryBackend>;
        let service = SquadService::new(Arc::new(registry), backend).await.unwrap();

        let squad_reg = service.squad_registry();
        let squads = squad_reg.list_squads().await;
        assert!(squads.is_empty());
    }
}
