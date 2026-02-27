use std::path::{Path, PathBuf};
use std::sync::Arc;

use chrono::Utc;

use crate::evo::registry::{DynamicSkill, SharedSkillRegistry, SkillFormat, SkillGating, SkillType};
use crate::evo::{DynamicCompiler, ProgrammingLanguage};

#[derive(Debug)]
pub struct ParsedSkill {
    pub name: String,
    pub description: String,
    pub format: SkillFormat,
    pub skill_type: SkillType,
    pub code: Option<String>,
    pub instructions: Option<String>,
    pub language: String,
    pub gating: Option<SkillGating>,
    pub compatibility: Option<String>,
    pub metadata: std::collections::HashMap<String, String>,
    pub allowed_tools: Vec<String>,
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

    pub fn detect_format(content: &str) -> SkillFormat {
        if content.starts_with("---") {
            return SkillFormat::AgentSkills;
        }
        
        if content.contains("## Type") {
            return SkillFormat::GoClaw;
        }
        
        SkillFormat::OpenClaw
    }

    pub async fn load_from_file(&self, path: &Path) -> Result<DynamicSkill, String> {
        let content = tokio::fs::read_to_string(path)
            .await
            .map_err(|e| format!("Failed to read file: {}", e))?;

        let format = Self::detect_format(&content);
        
        match format {
            SkillFormat::AgentSkills => self.parse_agentskills(&content, path),
            SkillFormat::GoClaw => self.parse_goclaw(&content),
            SkillFormat::OpenClaw => self.parse_goclaw(&content),
        }
    }

    fn parse_agentskills(&self, content: &str, path: &Path) -> Result<DynamicSkill, String> {
        let (frontmatter, body) = self.split_frontmatter(content)?;
        
        let parsed = self.parse_yaml_frontmatter(&frontmatter)?;
        
        let dir_name = path.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unknown");
        
        let version = parsed.metadata.get("version").cloned().unwrap_or_else(|| "1.0.0".to_string());
        
        let skill = DynamicSkill {
            id: format!("skill_{}", parsed.name),
            name: parsed.name,
            description: parsed.description,
            format: SkillFormat::AgentSkills,
            skill_type: SkillType::Prompt,
            code: None,
            instructions: Some(body),
            language: "prompt".to_string(),
            source: crate::evo::registry::SkillSource::default(),
            gating: None,
            compatibility: parsed.compatibility,
            metadata: parsed.metadata,
            allowed_tools: parsed.allowed_tools,
            created_by: "user".to_string(),
            created_at: Utc::now(),
            version,
        };

        Ok(skill)
    }

    fn split_frontmatter(&self, content: &str) -> Result<(String, String), String> {
        let mut lines = content.lines();
        
        let first_line = lines.next().ok_or("Empty content")?;
        if first_line.trim() != "---" {
            return Err("Missing frontmatter start".to_string());
        }
        
        let mut frontmatter_lines = Vec::new();
        let mut body_lines = Vec::new();
        let mut in_frontmatter = true;
        
        for line in lines {
            if in_frontmatter {
                if line.trim() == "---" {
                    in_frontmatter = false;
                } else {
                    frontmatter_lines.push(line);
                }
            } else {
                body_lines.push(line);
            }
        }
        
        Ok((frontmatter_lines.join("\n"), body_lines.join("\n")))
    }

    fn parse_yaml_frontmatter(&self, frontmatter: &str) -> Result<ParsedSkill, String> {
        let mut name = String::new();
        let mut description = String::new();
        let mut license = None;
        let mut compatibility = None;
        let mut metadata = std::collections::HashMap::new();
        let mut allowed_tools = Vec::new();
        
        for line in frontmatter.lines() {
            let line = line.trim();
            
            if line.starts_with("name:") {
                name = line.trim_start_matches("name:").trim().to_string();
            } else if line.starts_with("description:") {
                description = line.trim_start_matches("description:").trim().to_string();
            } else if line.starts_with("license:") {
                license = Some(line.trim_start_matches("license:").trim().to_string());
            } else if line.starts_with("compatibility:") {
                compatibility = Some(line.trim_start_matches("compatibility:").trim().to_string());
            } else if line.starts_with("metadata:") {
                // 简单处理，实际应该用 yaml 解析器
            } else if line.starts_with("allowed-tools:") {
                let tools = line.trim_start_matches("allowed-tools:").trim();
                allowed_tools = tools.split_whitespace().map(|s| s.to_string()).collect();
            } else if line.starts_with("  ") && line.contains(":") {
                let parts: Vec<&str> = line.trim().splitn(2, ':').collect();
                if parts.len() == 2 {
                    let key = parts[0].trim();
                    let value = parts[1].trim();
                    if key != "author" && key != "version" {
                        continue;
                    }
                    metadata.insert(key.to_string(), value.to_string());
                }
            }
        }
        
        Ok(ParsedSkill {
            name,
            description,
            format: SkillFormat::AgentSkills,
            skill_type: SkillType::Prompt,
            code: None,
            instructions: None,
            language: "prompt".to_string(),
            gating: None,
            compatibility,
            metadata,
            allowed_tools,
        })
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
            
            if path.is_dir() {
                let skill_md = path.join("SKILL.md");
                if skill_md.exists() {
                    match self.load_from_file(&skill_md).await {
                        Ok(skill) => skills.push(skill),
                        Err(e) => tracing::warn!("Failed to load {}: {}", skill_md.display(), e),
                    }
                }
            } else if path.extension().and_then(|s| s.to_str()) == Some("md") {
                match self.load_from_file(&path).await {
                    Ok(skill) => skills.push(skill),
                    Err(e) => tracing::warn!("Failed to load {}: {}", path.display(), e),
                }
            }
        }

        Ok(skills)
    }

    fn parse_goclaw(&self, content: &str) -> Result<DynamicSkill, String> {
        let parsed = self.parse_manifest(content)?;
        
        let skill = DynamicSkill {
            id: format!("skill_{}", parsed.name),
            name: parsed.name,
            description: parsed.description,
            format: SkillFormat::GoClaw,
            skill_type: parsed.skill_type,
            code: parsed.code,
            instructions: parsed.instructions,
            language: parsed.language,
            source: crate::evo::registry::SkillSource::default(),
            gating: parsed.gating,
            compatibility: None,
            metadata: std::collections::HashMap::new(),
            allowed_tools: Vec::new(),
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
            format: SkillFormat::GoClaw,
            skill_type,
            code,
            instructions,
            language,
            gating,
            compatibility: None,
            metadata: std::collections::HashMap::new(),
            allowed_tools: Vec::new(),
        })
    }

    pub async fn load_all_paths(&self) -> Result<Vec<DynamicSkill>, String> {
        let mut all_skills = Vec::new();
        
        let paths = Self::get_skill_paths();
        
        for path in paths {
            match self.load_from_directory(Path::new(&path)).await {
                Ok(skills) => {
                    tracing::debug!("Loaded {} skills from {}", skills.len(), path);
                    all_skills.extend(skills);
                }
                Err(e) => {
                    tracing::debug!("Failed to load {}: {}", path, e);
                }
            }
        }
        
        Ok(all_skills)
    }

    pub fn get_skill_paths() -> Vec<String> {
        let mut paths = Vec::new();
        
        paths.push("./skills".to_string());
        paths.push("./openclaw/skills".to_string());
        
        if let Ok(home) = std::env::var("HOME") {
            paths.push(format!("{}/.openclaw/skills", home));
            paths.push(format!("{}/.agentskills/skills", home));
        }
        
        #[cfg(unix)]
        {
            paths.push("/usr/local/share/openclaw/skills".to_string());
        }
        
        paths
    }

    pub fn parse_skill_md(&self, content: &str) -> Result<DynamicSkill, String> {
        let format = Self::detect_format(content);
        
        match format {
            SkillFormat::AgentSkills => {
                self.parse_agentskills(content, Path::new("SKILL.md"))
            }
            SkillFormat::GoClaw | SkillFormat::OpenClaw => {
                self.parse_goclaw(content)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_agentskills_format() {
        let content = r#"---
name: pdf-processing
description: Extract text from PDFs
---

# Instructions
Step by step..."#;
        
        let format = SkillLoader::detect_format(content);
        assert_eq!(format, SkillFormat::AgentSkills);
    }

    #[test]
    fn test_detect_goclaw_format() {
        let content = r#"# Skill: weather

## Type
prompt

## Instructions
..."#;
        
        let format = SkillLoader::detect_format(content);
        assert_eq!(format, SkillFormat::GoClaw);
    }

    #[test]
    fn test_parse_agentskills() {
        let content = r#"---
name: pdf-processing
description: Extract text and tables from PDF files.
compatibility: Requires python3, pdftotext
metadata:
  author: example-org
  version: "1.0"
allowed-tools: Bash Read
---

# PDF Processing

Step 1: Use pdftotext to extract text."#;

        let loader = SkillLoader::new(Arc::new(SharedSkillRegistry::new()));
        let result = loader.parse_skill_md(content);
        
        assert!(result.is_ok());
        let skill = result.unwrap();
        assert_eq!(skill.name, "pdf-processing");
        assert_eq!(skill.format, SkillFormat::AgentSkills);
        assert!(skill.instructions.is_some());
    }

    #[test]
    fn test_parse_code_skill() {
        let content = r#"# Skill: python_calculator

## Type
code

## Language
python

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
    }

    #[test]
    fn test_parse_prompt_skill() {
        let content = r#"# Skill: git_helper

## Type
prompt

## Instructions
When user asks to view git history, use exec to run `git log`.

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
    }
}
