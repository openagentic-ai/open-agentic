use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

use super::CompiledSkill;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum SkillSource {
    User,
    Evo,
    Imported,
}

impl Default for SkillSource {
    fn default() -> Self {
        SkillSource::User
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum SkillFormat {
    GoClaw,
    OpenClaw,
    AgentSkills,
}

impl Default for SkillFormat {
    fn default() -> Self {
        SkillFormat::GoClaw
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum SkillType {
    Code,
    Prompt,
    Channel,
    Account,
}

impl Default for SkillType {
    fn default() -> Self {
        SkillType::Code
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SkillGating {
    pub bins: Vec<String>,
    pub env: Vec<String>,
    pub files: Vec<String>,
}

impl SkillGating {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_bin(mut self, bin: &str) -> Self {
        self.bins.push(bin.to_string());
        self
    }

    pub fn with_env(mut self, env: &str) -> Self {
        self.env.push(env.to_string());
        self
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DynamicSkill {
    pub id: String,
    pub name: String,
    pub description: String,
    pub format: SkillFormat,
    pub skill_type: SkillType,
    pub code: Option<String>,
    pub instructions: Option<String>,
    pub language: String,
    pub source: SkillSource,
    pub gating: Option<SkillGating>,
    pub compatibility: Option<String>,
    pub metadata: HashMap<String, String>,
    pub allowed_tools: Vec<String>,
    pub created_by: String,
    pub created_at: DateTime<Utc>,
    pub version: String,
}

impl DynamicSkill {
    pub fn new_code(
        id: String,
        name: String,
        code: String,
        language: String,
        created_by: String,
    ) -> Self {
        Self {
            id,
            name,
            description: String::new(),
            format: SkillFormat::default(),
            skill_type: SkillType::Code,
            code: Some(code),
            instructions: None,
            language,
            source: SkillSource::default(),
            gating: None,
            compatibility: None,
            metadata: HashMap::new(),
            allowed_tools: Vec::new(),
            created_by,
            created_at: Utc::now(),
            version: "1.0.0".to_string(),
        }
    }

    pub fn new(
        id: String,
        name: String,
        code: String,
        language: String,
        created_by: String,
    ) -> Self {
        Self::new_code(id, name, code, language, created_by)
    }

    pub fn new_prompt(
        id: String,
        name: String,
        instructions: String,
        created_by: String,
    ) -> Self {
        Self {
            id,
            name,
            description: String::new(),
            format: SkillFormat::default(),
            skill_type: SkillType::Prompt,
            code: None,
            instructions: Some(instructions),
            language: "prompt".to_string(),
            source: SkillSource::default(),
            gating: None,
            compatibility: None,
            metadata: HashMap::new(),
            allowed_tools: Vec::new(),
            created_by,
            created_at: Utc::now(),
            version: "1.0.0".to_string(),
        }
    }

    pub fn with_source(mut self, source: SkillSource) -> Self {
        self.source = source;
        self
    }

    pub fn with_gating(mut self, gating: SkillGating) -> Self {
        self.gating = Some(gating);
        self
    }

    pub fn new_channel(
        id: String,
        name: String,
        metadata: HashMap<String, String>,
    ) -> Self {
        Self {
            id,
            name,
            description: String::new(),
            format: SkillFormat::default(),
            skill_type: SkillType::Channel,
            code: None,
            instructions: None,
            language: "channel".to_string(),
            source: SkillSource::default(),
            gating: None,
            compatibility: None,
            metadata,
            allowed_tools: Vec::new(),
            created_by: "user".to_string(),
            created_at: Utc::now(),
            version: "1.0.0".to_string(),
        }
    }

    pub fn new_account(
        id: String,
        name: String,
        metadata: HashMap<String, String>,
    ) -> Self {
        Self {
            id,
            name,
            description: String::new(),
            format: SkillFormat::default(),
            skill_type: SkillType::Account,
            code: None,
            instructions: None,
            language: "account".to_string(),
            source: SkillSource::default(),
            gating: None,
            compatibility: None,
            metadata,
            allowed_tools: Vec::new(),
            created_by: "user".to_string(),
            created_at: Utc::now(),
            version: "1.0.0".to_string(),
        }
    }

    pub fn is_prompt(&self) -> bool {
        self.skill_type == SkillType::Prompt
    }

    pub fn is_code(&self) -> bool {
        self.skill_type == SkillType::Code
    }
}

pub struct SharedSkillRegistry {
    inner: Arc<RwLock<SkillRegistryInner>>,
    compiled_skills: Arc<RwLock<HashMap<String, CompiledSkill>>>,
}

#[derive(Debug, Clone)]
struct SkillRegistryInner {
    skills: Vec<DynamicSkill>,
}

impl Default for SkillRegistryInner {
    fn default() -> Self {
        Self {
            skills: Vec::new(),
        }
    }
}

impl SharedSkillRegistry {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(RwLock::new(SkillRegistryInner::default())),
            compiled_skills: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub async fn register_skill(&self, skill: DynamicSkill) {
        let mut registry = self.inner.write().await;
        registry.skills.push(skill);
    }

    pub async fn register_compiled(&self, skill_id: &str, compiled: CompiledSkill) {
        let mut compiled_map = self.compiled_skills.write().await;
        compiled_map.insert(skill_id.to_string(), compiled);
    }

    pub async fn get_compiled_skill(&self, skill_id: &str) -> Option<CompiledSkill> {
        let compiled_map = self.compiled_skills.read().await;
        compiled_map.get(skill_id).cloned()
    }

    pub async fn get_skill(&self, id: &str) -> Option<DynamicSkill> {
        let registry = self.inner.read().await;
        registry.skills.iter().find(|s| s.id == id).cloned()
    }

    pub async fn get_skill_by_name(&self, name: &str) -> Option<DynamicSkill> {
        let registry = self.inner.read().await;
        registry.skills.iter().find(|s| s.name == name).cloned()
    }

    pub async fn get_all_skills(&self) -> Vec<DynamicSkill> {
        let registry = self.inner.read().await;
        registry.skills.clone()
    }

    pub async fn get_skills_by_type(&self, skill_type: SkillType) -> Vec<DynamicSkill> {
        let registry = self.inner.read().await;
        registry.skills
            .iter()
            .filter(|s| s.skill_type == skill_type)
            .cloned()
            .collect()
    }

    pub async fn get_skills_by_source(&self, source: SkillSource) -> Vec<DynamicSkill> {
        let registry = self.inner.read().await;
        registry.skills
            .iter()
            .filter(|s| s.source == source)
            .cloned()
            .collect()
    }

    pub async fn skill_exists(&self, name: &str) -> bool {
        let registry = self.inner.read().await;
        registry.skills.iter().any(|s| s.name == name)
    }

    pub fn clone_arc(&self) -> Arc<RwLock<SkillRegistryInner>> {
        Arc::clone(&self.inner)
    }

    pub fn clone_inner(&self) -> Arc<SharedSkillRegistry> {
        Arc::new(Self {
            inner: Arc::clone(&self.inner),
            compiled_skills: Arc::clone(&self.compiled_skills),
        })
    }
}

impl Default for SharedSkillRegistry {
    fn default() -> Self {
        Self::new()
    }
}
