use std::collections::HashMap;
use std::sync::Arc;

use tokio::sync::RwLock;

use super::types::{Squad, SquadCollaboration, SquadMember, SquadRole, SquadType};

#[derive(Clone)]
pub struct SquadRegistry {
    squads: Arc<RwLock<HashMap<String, Squad>>>,
    relations: Arc<RwLock<HashMap<String, Vec<String>>>>,
}

impl SquadRegistry {
    pub fn new() -> Self {
        Self {
            squads: Arc::new(RwLock::new(HashMap::new())),
            relations: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub async fn create_squad(&self, squad: Squad) -> Result<(), String> {
        let id = squad.id.clone();
        
        if self.get_squad(&id).await.is_some() {
            return Err(format!("Squad '{}' already exists", id));
        }

        self.squads.write().await.insert(id, squad);
        Ok(())
    }

    pub async fn get_squad(&self, id: &str) -> Option<Squad> {
        self.squads.read().await.get(id).cloned()
    }

    pub async fn list_squads(&self) -> Vec<Squad> {
        self.squads.read().await.values().cloned().collect()
    }

    pub async fn update_squad(&self, squad: Squad) -> Result<(), String> {
        let id = squad.id.clone();
        
        if self.get_squad(&id).await.is_none() {
            return Err(format!("Squad '{}' not found", id));
        }

        self.squads.write().await.insert(id, squad);
        Ok(())
    }

    pub async fn delete_squad(&self, id: &str) -> Result<(), String> {
        if self.squads.write().await.remove(id).is_none() {
            return Err(format!("Squad '{}' not found", id));
        }
        self.relations.write().await.remove(id);
        Ok(())
    }

    pub async fn add_member(&self, squad_id: &str, member: SquadMember) -> Result<(), String> {
        let mut squads = self.squads.write().await;
        
        let squad = squads.get_mut(squad_id)
            .ok_or_else(|| format!("Squad '{}' not found", squad_id))?;
        
        if squad.members.iter().any(|m| m.agent_id == member.agent_id) {
            return Err(format!("Agent '{}' is already a member of squad '{}'", 
                member.agent_id, squad_id));
        }
        
        squad.members.push(member);
        Ok(())
    }

    pub async fn remove_member(&self, squad_id: &str, agent_id: &str) -> Result<(), String> {
        let mut squads = self.squads.write().await;
        
        let squad = squads.get_mut(squad_id)
            .ok_or_else(|| format!("Squad '{}' not found", squad_id))?;
        
        let original_len = squad.members.len();
        squad.members.retain(|m| m.agent_id != agent_id);
        
        if squad.members.len() == original_len {
            return Err(format!("Agent '{}' not found in squad '{}'", agent_id, squad_id));
        }
        
        Ok(())
    }

    pub async fn create_collaboration(
        &self, 
        from_squad: &str, 
        to_squad: &str, 
        trigger: String,
    ) -> Result<(), String> {
        if self.get_squad(from_squad).await.is_none() {
            return Err(format!("Squad '{}' not found", from_squad));
        }
        if self.get_squad(to_squad).await.is_none() {
            return Err(format!("Squad '{}' not found", to_squad));
        }

        let collaboration = SquadCollaboration {
            target_squad_id: to_squad.to_string(),
            trigger,
        };

        let mut squads = self.squads.write().await;
        let squad = squads.get_mut(from_squad)
            .ok_or_else(|| format!("Squad '{}' not found", from_squad))?;
        
        squad.collaborations.push(collaboration);

        self.relations.write().await
            .entry(from_squad.to_string())
            .or_default()
            .push(to_squad.to_string());

        Ok(())
    }

    pub async fn get_collaborations(&self, squad_id: &str) -> Vec<SquadCollaboration> {
        self.squads.read().await
            .get(squad_id)
            .map(|s| s.collaborations.clone())
            .unwrap_or_default()
    }

    pub async fn get_related_squads(&self, squad_id: &str) -> Vec<String> {
        self.relations.read().await
            .get(squad_id)
            .cloned()
            .unwrap_or_default()
    }

    pub async fn find_squad_by_agent(&self, agent_id: &str) -> Option<Squad> {
        let squads = self.squads.read().await;
        squads.values()
            .find(|s| s.is_member(agent_id))
            .cloned()
    }

    pub async fn find_squads_by_type(&self, squad_type: &SquadType) -> Vec<Squad> {
        let squads = self.squads.read().await;
        squads.values()
            .filter(|s| &s.squad_type == squad_type)
            .cloned()
            .collect()
    }

    pub async fn get_squad_agents(&self, squad_id: &str) -> Vec<String> {
        self.squads.read().await
            .get(squad_id)
            .map(|s| s.members.iter().map(|m| m.agent_id.clone()).collect())
            .unwrap_or_default()
    }
}

impl Default for SquadRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_and_get_squad() {
        let registry = SquadRegistry::new();
        
        let squad = Squad::new(
            "squad_1".to_string(),
            "Test Squad".to_string(),
            SquadType::ProductGrowth,
            "agent_lead".to_string(),
        );
        
        registry.create_squad(squad).await.unwrap();
        
        let found = registry.get_squad("squad_1").await;
        assert!(found.is_some());
        assert_eq!(found.unwrap().name, "Test Squad");
    }

    #[tokio::test]
    async fn test_create_duplicate_squad() {
        let registry = SquadRegistry::new();
        
        let squad = Squad::new(
            "squad_1".to_string(),
            "Test Squad".to_string(),
            SquadType::ProductGrowth,
            "agent_lead".to_string(),
        );
        
        registry.create_squad(squad.clone()).await.unwrap();
        let result = registry.create_squad(squad).await;
        
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_list_squads() {
        let registry = SquadRegistry::new();
        
        registry.create_squad(Squad::new(
            "squad_1".to_string(),
            "Squad 1".to_string(),
            SquadType::ProductGrowth,
            "lead_1".to_string(),
        )).await.unwrap();
        
        registry.create_squad(Squad::new(
            "squad_2".to_string(),
            "Squad 2".to_string(),
            SquadType::TechPlatform,
            "lead_2".to_string(),
        )).await.unwrap();
        
        let squads = registry.list_squads().await;
        assert_eq!(squads.len(), 2);
    }

    #[tokio::test]
    async fn test_add_and_remove_member() {
        let registry = SquadRegistry::new();
        
        let squad = Squad::new(
            "squad_1".to_string(),
            "Test Squad".to_string(),
            SquadType::ProductGrowth,
            "agent_lead".to_string(),
        );
        registry.create_squad(squad).await.unwrap();
        
        let member = SquadMember::new("agent_1".to_string(), SquadRole::Executor);
        registry.add_member("squad_1", member).await.unwrap();
        
        let squad = registry.get_squad("squad_1").await.unwrap();
        assert_eq!(squad.members.len(), 1);
        
        registry.remove_member("squad_1", "agent_1").await.unwrap();
        
        let squad = registry.get_squad("squad_1").await.unwrap();
        assert_eq!(squad.members.len(), 0);
    }

    #[tokio::test]
    async fn test_collaboration() {
        let registry = SquadRegistry::new();
        
        registry.create_squad(Squad::new(
            "squad_product".to_string(),
            "Product Squad".to_string(),
            SquadType::ProductGrowth,
            "lead_1".to_string(),
        )).await.unwrap();
        
        registry.create_squad(Squad::new(
            "squad_tech".to_string(),
            "Tech Squad".to_string(),
            SquadType::TechPlatform,
            "lead_2".to_string(),
        )).await.unwrap();
        
        registry.create_collaboration(
            "squad_product",
            "squad_tech",
            "task_type == feature_implementation".to_string(),
        ).await.unwrap();
        
        let collaborations = registry.get_collaborations("squad_product").await;
        assert_eq!(collaborations.len(), 1);
        assert_eq!(collaborations[0].target_squad_id, "squad_tech");
    }

    #[tokio::test]
    async fn test_find_squad_by_agent() {
        let registry = SquadRegistry::new();
        
        let mut squad = Squad::new(
            "squad_1".to_string(),
            "Test Squad".to_string(),
            SquadType::ProductGrowth,
            "agent_lead".to_string(),
        );
        squad.members.push(SquadMember::new(
            "agent_1".to_string(),
            SquadRole::Executor,
        ));
        
        registry.create_squad(squad).await.unwrap();
        
        let found = registry.find_squad_by_agent("agent_1").await;
        assert!(found.is_some());
        assert_eq!(found.unwrap().id, "squad_1");
    }
}
