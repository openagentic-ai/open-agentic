use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq)]
pub struct Squad {
    pub id: String,
    pub name: String,
    pub description: String,
    pub squad_type: SquadType,
    pub lead_agent_id: String,
    pub members: Vec<SquadMember>,
    pub capabilities: Vec<String>,
    pub memory_namespace: String,
    pub collaborations: Vec<SquadCollaboration>,
    pub metadata: HashMap<String, String>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum SquadType {
    ProductGrowth,
    TechPlatform,
    MarketingGrowth,
    Custom(String),
}

#[derive(Debug, Clone, PartialEq)]
pub struct SquadMember {
    pub agent_id: String,
    pub role: SquadRole,
    pub capabilities: Vec<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum SquadRole {
    Lead,
    Executor,
    Coordinator,
}

#[derive(Debug, Clone, PartialEq)]
pub struct SquadCollaboration {
    pub target_squad_id: String,
    pub trigger: String,
}

impl Squad {
    pub fn new(
        id: String,
        name: String,
        squad_type: SquadType,
        lead_agent_id: String,
    ) -> Self {
        Self {
            id,
            name,
            description: String::new(),
            squad_type,
            lead_agent_id,
            members: Vec::new(),
            capabilities: Vec::new(),
            memory_namespace: String::new(),
            collaborations: Vec::new(),
            metadata: HashMap::new(),
        }
    }

    pub fn with_description(mut self, description: String) -> Self {
        self.description = description;
        self
    }

    pub fn with_member(mut self, member: SquadMember) -> Self {
        self.members.push(member);
        self
    }

    pub fn with_capability(mut self, capability: String) -> Self {
        self.capabilities.push(capability);
        self
    }

    pub fn with_memory_namespace(mut self, namespace: String) -> Self {
        self.memory_namespace = namespace;
        self
    }

    pub fn with_collaboration(mut self, collaboration: SquadCollaboration) -> Self {
        self.collaborations.push(collaboration);
        self
    }

    pub fn get_member(&self, agent_id: &str) -> Option<&SquadMember> {
        self.members.iter().find(|m| m.agent_id == agent_id)
    }

    pub fn get_lead(&self) -> Option<&SquadMember> {
        self.members.iter().find(|m| matches!(m.role, SquadRole::Lead))
    }

    pub fn is_member(&self, agent_id: &str) -> bool {
        self.members.iter().any(|m| m.agent_id == agent_id)
    }
}

impl SquadMember {
    pub fn new(agent_id: String, role: SquadRole) -> Self {
        Self {
            agent_id,
            role,
            capabilities: Vec::new(),
        }
    }

    pub fn with_capability(mut self, capability: String) -> Self {
        self.capabilities.push(capability);
        self
    }
}

impl SquadType {
    pub fn as_str(&self) -> &str {
        match self {
            SquadType::ProductGrowth => "ProductGrowth",
            SquadType::TechPlatform => "TechPlatform",
            SquadType::MarketingGrowth => "MarketingGrowth",
            SquadType::Custom(s) => s.as_str(),
        }
    }
}

impl Default for SquadType {
    fn default() -> Self {
        SquadType::Custom("Default".to_string())
    }
}
