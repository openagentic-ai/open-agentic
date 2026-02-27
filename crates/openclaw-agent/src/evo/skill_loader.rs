use std::path::Path;
use std::sync::Arc;

use chrono::Utc;

use crate::evo::registry::{DynamicSkill, SharedSkillRegistry, SkillGating, SkillType};
use crate::evo::{DynamicCompiler, ProgrammingLanguage};

#[derive(Debug)]
pub struct ParsedSkill {
    pub name: String,
    pub description: String,
    pub skill_type: SkillType,
    pub code: Option<String>,
    pub instructions: Option<String>,
    pub language: String,
    pub gating: Option<SkillGating>,
}

#[derive(Debug)]
pub struct Parameter {
    pub name: String,
    pub param_type: String,
    pub required: bool,
    pub description: String,
}

pub struct SkillLoader {
    registry: Arc<SharedSkillRegistry>,
    compiler: DynamicCompiler,
}

impl SkillLoader {
    pub fn new(registry: Arc<SharedSkillRegistry>) -> Self {
        Self {
            registry,
            compiler: DynamicCompiler::new(ProgrammingLanguage::Wasm),
        }
    }

    pub async fn load_from_file(&self, path: &Path) -> Result<DynamicSkill, String> {
        let content = tokio::fs::read_to_string(path)
            .await
            .map_err(|e| format!("Failed to read file: {}", e))?;

        self.parse_skill_md(&content)
    }

    pub async fn load_from_directory(&self, dir: &Path) -> Result<Vec<DynamicSkill>, String> {
        if !dir.exists() {
            return Ok(Vec::new());
        }

        let mut skills = Vec::new();
        
        let mut entries = tokio::fs::read_dir(dir)
            .await
            .map_err(|e| format!("Failed to read dir: {}", e))?;

        while let Some(entry) = entries.next_entry().await.map_err(|e| e.to_string())? {
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) == Some("md") {
                match self.load_from_file(&path).await {
                    Ok(skill) => skills.push(skill),
                    Err(e) => tracing::warn!("Failed to load {}: {}", path.display(), e),
                }
            }
        }

        Ok(skills)
    }

    pub fn parse_skill_md(&self, content: &str) -> Result<DynamicSkill, String> {
        let parsed = self.parse_manifest(content)?;
        
        let skill = DynamicSkill {
            id: format!("skill_{}", parsed.name),
            name: parsed.name,
            skill_type: parsed.skill_type,
            code: parsed.code,
            instructions: parsed.instructions,
            language: parsed.language,
            source: crate::evo::registry::SkillSource::default(),
            gating: parsed.gating,
            created_by: "user".to_string(),
            created_at: Utc::now(),
            version: "1.0.0".to_string(),
        };

        Ok(skill)
    }

    fn parse_manifest(&self, content: &str) -> Result<ParsedSkill, String> {
        let lines: Vec<&str> = content.lines().collect();
        
        let mut name = String::new();
        let mut description = String::new();
        let mut skill_type = SkillType::default();
        let mut language = String::new();
        let mut gating = None;
        let mut parameters = Vec::new();
        let mut dependencies = Vec::new();
        let mut in_code_block = false;
        let mut in_instructions_block = false;
        let mut code_lines = Vec::new();
        let mut instructions_lines = Vec::new();
        let mut current_section = String::new();

        for line in lines {
            let trimmed = line.trim();
            
            if trimmed.starts_with("# Skill:") {
                name = trimmed.trim_start_matches("# Skill:").trim().to_string();
            } else if trimmed.starts_with("## Type") {
                current_section = "type".to_string();
            } else if trimmed.starts_with("## Description") {
                current_section = "description".to_string();
            } else if trimmed.starts_with("## Language") {
                current_section = "language".to_string();
            } else if trimmed.starts_with("## Instructions") {
                current_section = "instructions".to_string();
            } else if trimmed.starts_with("## Parameters") {
                current_section = "parameters".to_string();
            } else if trimmed.starts_with("## Dependencies") {
                current_section = "dependencies".to_string();
            } else if trimmed.starts_with("## Gating") {
                current_section = "gating".to_string();
            } else if trimmed.starts_with("## Code") {
                current_section = "code".to_string();
            } else if trimmed.starts_with("```") {
                if in_code_block || in_instructions_block {
                    in_code_block = false;
                    in_instructions_block = false;
                } else if current_section == "code" {
                    in_code_block = true;
                } else if current_section == "instructions" {
                    in_instructions_block = true;
                }
            } else if in_code_block {
                code_lines.push(trimmed);
            } else if in_instructions_block {
                instructions_lines.push(trimmed);
            } else if !trimmed.is_empty() {
                match current_section.as_str() {
                    "type" => {
                        let t = trimmed.to_lowercase();
                        if t == "prompt" {
                            skill_type = SkillType::Prompt;
                        } else {
                            skill_type = SkillType::Code;
                        }
                    }
                    "description" => description.push_str(trimmed),
                    "language" => language.push_str(trimmed),
                    "instructions" => {
                        if !trimmed.starts_with('#') {
                            instructions_lines.push(trimmed);
                        }
                    }
                    "gating" => {
                        if trimmed.starts_with("requires:") {
                            gating = Some(SkillGating::new());
                        } else if trimmed.starts_with("- ") && gating.is_some() {
                            let item = trimmed.trim_start_matches("- ");
                            if item.starts_with("bins:") {
                                let bins = item.trim_start_matches("bins:")
                                    .trim_start_matches("[")
                                    .trim_end_matches("]")
                                    .split(',')
                                    .map(|s| s.trim().trim_matches('"').to_string())
                                    .collect();
                                gating.as_mut().unwrap().bins = bins;
                            } else if item.starts_with("env:") {
                                let env = item.trim_start_matches("env:")
                                    .trim_start_matches("[")
                                    .trim_end_matches("]")
                                    .split(',')
                                    .map(|s| s.trim().trim_matches('"').to_string())
                                    .collect();
                                gating.as_mut().unwrap().env = env;
                            }
                        }
                    }
                    "parameters" => {
                        if trimmed.starts_with("- ") {
                            let param_str = trimmed.trim_start_matches("- ");
                            let parts: Vec<&str> = param_str.splitn(2, ':').collect();
                            if parts.len() >= 2 {
                                let name_type = parts[0].trim();
                                let desc = parts[1].trim();
                                let (param_name, param_type) = if name_type.contains('(') {
                                    let idx = name_type.find('(').unwrap();
                                    (
                                        name_type[..idx].trim().to_string(),
                                        name_type[idx+1..name_type.len()-1].trim().to_string(),
                                    )
                                } else {
                                    (name_type.to_string(), "string".to_string())
                                };
                                parameters.push(Parameter {
                                    name: param_name,
                                    param_type,
                                    required: !param_str.contains("optional"),
                                    description: desc.to_string(),
                                });
                            }
                        }
                    }
                    "dependencies" => {
                        if trimmed.starts_with("- ") {
                            dependencies.push(trimmed.trim_start_matches("- ").to_string());
                        }
                    }
                    _ => {}
                }
            }
        }

        let code = if code_lines.is_empty() {
            None
        } else {
            Some(code_lines.join("\n"))
        };

        let instructions = if instructions_lines.is_empty() {
            None
        } else {
            Some(instructions_lines.join("\n"))
        };

        if language.is_empty() {
            language = "wasm".to_string();
        }

        Ok(ParsedSkill {
            name,
            description,
            skill_type,
            code,
            instructions,
            language,
            gating,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_code_skill() {
        let content = r#"# Skill: python_calculator

## Type
code

## Description
Execute Python code for mathematical calculations

## Language
python

## Parameters
- code: string (required) - Python code to execute

## Code
```python
def execute(params):
    code = params.get("code", "")
    return eval(code)
```
"#;

        let loader = SkillLoader::new(Arc::new(SharedSkillRegistry::new()));
        let result = loader.parse_skill_md(content);
        
        assert!(result.is_ok());
        let skill = result.unwrap();
        assert_eq!(skill.name, "python_calculator");
        assert!(skill.is_code());
        assert!(skill.code.is_some());
    }

    #[test]
    fn test_parse_prompt_skill() {
        let content = r#"# Skill: git_helper

## Type
prompt

## Description
Git operations helper

## Instructions
When user asks to view git history, use exec to run `git log --oneline -10`.
When user asks to create a branch, use exec to run `git checkout -b <branch_name>`.

## Gating
requires:
  bins: ["git"]
"#;

        let loader = SkillLoader::new(Arc::new(SharedSkillRegistry::new()));
        let result = loader.parse_skill_md(content);
        
        assert!(result.is_ok());
        let skill = result.unwrap();
        assert_eq!(skill.name, "git_helper");
        assert!(skill.is_prompt());
        assert!(skill.instructions.is_some());
        assert!(skill.gating.is_some());
    }
}
