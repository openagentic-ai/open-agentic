use std::sync::Arc;

use crate::evo::registry::{DynamicSkill, SharedSkillRegistry, SkillGating, SkillType};

pub struct SkillPromptInjector {
    registry: Arc<SharedSkillRegistry>,
}

impl SkillPromptInjector {
    pub fn new(registry: Arc<SharedSkillRegistry>) -> Self {
        Self { registry }
    }

    pub async fn inject_to_prompt(&self, base_prompt: &str) -> String {
        let skills = self.registry.get_all_skills().await;
        
        let mut prompt_skills = Vec::new();
        for s in skills {
            if s.skill_type == SkillType::Prompt && self.check_gating(&s.gating).await {
                prompt_skills.push(s);
            }
        }

        if prompt_skills.is_empty() {
            return base_prompt.to_string();
        }

        let skills_section = prompt_skills
            .into_iter()
            .map(|s| {
                let instructions = s.instructions.unwrap_or_default();
                format!("### Skill: {}\n{}\n", s.name, instructions)
            })
            .collect::<Vec<_>>()
            .join("\n");

        format!(
            "{}\n\n## Available Skills\n{}\n",
            base_prompt, skills_section
        )
    }

    pub async fn inject_to_prompt_filtered(&self, base_prompt: &str, skill_names: &[String]) -> String {
        let skills = self.registry.get_all_skills().await;
        
        let mut prompt_skills = Vec::new();
        for s in skills {
            if s.skill_type == SkillType::Prompt 
                && skill_names.contains(&s.name) 
                && self.check_gating(&s.gating).await 
            {
                prompt_skills.push(s);
            }
        }

        if prompt_skills.is_empty() {
            return base_prompt.to_string();
        }

        let skills_section = prompt_skills
            .into_iter()
            .map(|s| {
                let instructions = s.instructions.unwrap_or_default();
                format!("### Skill: {}\n{}\n", s.name, instructions)
            })
            .collect::<Vec<_>>()
            .join("\n");

        format!(
            "{}\n\n## Active Skills\n{}\n",
            base_prompt, skills_section
        )
    }

    pub async fn check_gating(&self, gating: &Option<SkillGating>) -> bool {
        if let Some(gating) = gating {
            for bin in &gating.bins {
                if !self.command_exists(bin).await {
                    tracing::debug!("Skill gating: command '{}' not found", bin);
                    return false;
                }
            }
            
            for env_var in &gating.env {
                if std::env::var(env_var).is_err() {
                    tracing::debug!("Skill gating: env var '{}' not found", env_var);
                    return false;
                }
            }

            for file in &gating.files {
                if !std::path::Path::new(file).exists() {
                    tracing::debug!("Skill gating: file '{}' not found", file);
                    return false;
                }
            }
        }
        true
    }

    async fn command_exists(&self, cmd: &str) -> bool {
        tokio::process::Command::new("which")
            .arg(cmd)
            .output()
            .await
            .map(|o| o.status.success())
            .unwrap_or(false)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_inject_to_prompt_empty() {
        let registry = Arc::new(SharedSkillRegistry::new());
        let injector = SkillPromptInjector::new(registry);
        
        let prompt = "You are a helpful assistant.";
        let result = injector.inject_to_prompt(prompt).await;
        
        assert_eq!(result, prompt);
    }

    #[tokio::test]
    async fn test_inject_to_prompt_with_skills() {
        let registry = Arc::new(SharedSkillRegistry::new());
        
        let skill = DynamicSkill::new_prompt(
            "skill_git".to_string(),
            "git_helper".to_string(),
            "Use git commands to help with version control.".to_string(),
            "user".to_string(),
        );
        
        registry.register_skill(skill).await;
        
        let injector = SkillPromptInjector::new(registry);
        
        let prompt = "You are a helpful assistant.";
        let result = injector.inject_to_prompt(prompt).await;
        
        assert!(result.contains("## Available Skills"));
        assert!(result.contains("git_helper"));
    }

    #[tokio::test]
    async fn test_check_gating_no_requirements() {
        let registry = Arc::new(SharedSkillRegistry::new());
        let injector = SkillPromptInjector::new(registry);
        
        let gating = None;
        let result = injector.check_gating(&gating).await;
        
        assert!(result);
    }
}
