use std::sync::Arc;

use openclaw_core::Message;
use openclaw_memory::factory::MemoryBackend;
use openclaw_memory::types::MemoryItem;

pub struct AgentMemoryService {
    memory_backend: Arc<dyn MemoryBackend>,
}

impl AgentMemoryService {
    pub fn new(memory_backend: Arc<dyn MemoryBackend>) -> Self {
        Self { memory_backend }
    }

    fn agent_namespace(&self, agent_id: &str) -> String {
        format!("agent:{}", agent_id)
    }

    pub async fn store_session(
        &self,
        agent_id: &str,
        messages: Vec<Message>,
    ) -> Result<(), String> {
        let namespace_key = self.agent_namespace(agent_id);

        for message in messages {
            let mut item = MemoryItem::from_message(message, 0.8);
            item.metadata.tags.push(namespace_key.clone());
            
            self.memory_backend
                .store(item)
                .await
                .map_err(|e| e.to_string())?;
        }

        Ok(())
    }

    pub async fn store_knowledge(&self, agent_id: &str, content: String) -> Result<(), String> {
        let namespace_key = self.agent_namespace(agent_id);
        
        let item = MemoryItem::summary(content.clone(), 1, content.len() / 4);
        let mut item = item;
        item.metadata.tags.push(namespace_key);

        self.memory_backend
            .store(item)
            .await
            .map_err(|e| e.to_string())?;

        Ok(())
    }

    pub async fn query_cross_session(
        &self,
        agent_id: &str,
        query: &str,
    ) -> Result<Vec<MemoryItem>, String> {
        let namespace_key = self.agent_namespace(agent_id);

        let retrieval = self
            .memory_backend
            .retrieve(query, 10000)
            .await
            .map_err(|e| e.to_string())?;

        let filtered: Vec<MemoryItem> = retrieval
            .items
            .into_iter()
            .filter(|item| item.metadata.tags.contains(&namespace_key))
            .collect();

        Ok(filtered)
    }

    pub async fn query_across_agents(
        &self,
        agent_ids: &[String],
        query: &str,
    ) -> Result<Vec<MemoryItem>, String> {
        let mut all_results = Vec::new();

        for agent_id in agent_ids {
            let items = self.query_cross_session(agent_id, query).await?;
            all_results.extend(items);
        }

        all_results.sort_by(|a, b| {
            b.importance_score
                .partial_cmp(&a.importance_score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        Ok(all_results)
    }
}

pub struct SquadMemoryService {
    memory_backend: Arc<dyn MemoryBackend>,
}

impl SquadMemoryService {
    pub fn new(memory_backend: Arc<dyn MemoryBackend>) -> Self {
        Self { memory_backend }
    }

    fn squad_namespace(&self, squad_id: &str) -> String {
        format!("squad:{}", squad_id)
    }

    pub async fn store_shared(
        &self,
        squad_id: &str,
        content: String,
    ) -> Result<(), String> {
        let namespace_key = self.squad_namespace(squad_id);

        let item = MemoryItem::summary(content.clone(), 1, content.len() / 4);
        let mut item = item;
        item.metadata.tags.push(namespace_key);

        self.memory_backend
            .store(item)
            .await
            .map_err(|e| e.to_string())?;

        Ok(())
    }

    pub async fn query_squad(
        &self,
        squad_id: &str,
        query: &str,
    ) -> Result<Vec<MemoryItem>, String> {
        let namespace_key = self.squad_namespace(squad_id);

        let retrieval = self
            .memory_backend
            .retrieve(query, 10000)
            .await
            .map_err(|e| e.to_string())?;

        let filtered: Vec<MemoryItem> = retrieval
            .items
            .into_iter()
            .filter(|item| item.metadata.tags.contains(&namespace_key))
            .collect();

        Ok(filtered)
    }

    pub async fn get_shared_memories(
        &self,
        squad_id: &str,
    ) -> Result<Vec<MemoryItem>, String> {
        self.query_squad(squad_id, "").await
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

    use super::super::AgentMemoryService;
    use super::super::SquadMemoryService;

    struct MockBackend;
    #[async_trait]
    impl MemoryBackend for MockBackend {
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
    async fn test_agent_namespace_format() {
        let service = AgentMemoryService::new(Arc::new(MockBackend) as Arc<dyn MemoryBackend>);
        
        let ns = service.agent_namespace("agent_123");
        assert_eq!(ns, "agent:agent_123");
    }

    #[tokio::test]
    async fn test_squad_namespace_format() {
        let service = SquadMemoryService::new(Arc::new(MockBackend) as Arc<dyn MemoryBackend>);
        
        let ns = service.squad_namespace("squad_product");
        assert_eq!(ns, "squad:squad_product");
    }
}
