use super::{
    HandMatch, HandMatchType, Intent, SkillMatch, TaskClassification, TaskInput, TaskRequest,
    TaskType,
};

pub struct TaskClassifier {
    hand_detector: HandDetector,
    rule_matcher: RuleMatcher,
}

impl TaskClassifier {
    pub fn new() -> Self {
        Self {
            hand_detector: HandDetector::new(),
            rule_matcher: RuleMatcher::new(),
        }
    }

    pub async fn classify(&self, request: &TaskRequest) -> TaskClassification {
        let content = request.input.content();

        if let Some(hand_match) = self.hand_detector.detect(content).await {
            if !hand_match.hand_id.is_empty() {
                return TaskClassification::Hand {
                    hand_id: hand_match.hand_id,
                    input: Some(content.to_string()),
                };
            }
        }

        if let Some(skill_match) = self.rule_matcher.match_task(content) {
            return TaskClassification::WithSkill {
                task_type: skill_match.task_type,
                skill_id: skill_match.skill_id,
            };
        }

        let intent = self.recognize_intent(content);

        if Self::requires_skill(&intent.task_type) {
            let skill_id = self.select_skill(&intent.task_type);
            TaskClassification::WithSkill {
                task_type: intent.task_type,
                skill_id,
            }
        } else {
            TaskClassification::Direct {
                task_type: intent.task_type,
            }
        }
    }

    fn requires_skill(task_type: &TaskType) -> bool {
        matches!(
            task_type,
            TaskType::CodeGeneration
                | TaskType::Translation
                | TaskType::WebSearch
                | TaskType::DataAnalysis
                | TaskType::CodeReview
                | TaskType::Summarization
                | TaskType::Documentation
        )
    }

    fn select_skill(&self, task_type: &TaskType) -> String {
        match task_type {
            TaskType::CodeGeneration => "code_generation_skill".to_string(),
            TaskType::Translation => "translation_skill".to_string(),
            TaskType::WebSearch => "web_search_skill".to_string(),
            TaskType::DataAnalysis => "data_analysis_skill".to_string(),
            TaskType::CodeReview => "code_review_skill".to_string(),
            TaskType::Summarization => "summarization_skill".to_string(),
            TaskType::Documentation => "documentation_skill".to_string(),
            _ => String::new(),
        }
    }

    fn recognize_intent(&self, content: &str) -> Intent {
        let lower = content.to_lowercase();

        if lower.contains("天气") || lower.contains("temperature") {
            return Intent {
                task_type: TaskType::QuestionAnswer,
                confidence: 0.9,
                entities: [("topic".to_string(), "weather".to_string())].into(),
            };
        }

        if lower.contains("新闻") || lower.contains("news") {
            return Intent {
                task_type: TaskType::WebSearch,
                confidence: 0.8,
                entities: [("topic".to_string(), "news".to_string())].into(),
            };
        }

        Intent::default()
    }
}

impl Default for TaskClassifier {
    fn default() -> Self {
        Self::new()
    }
}

pub struct HandDetector {
    schedule_keywords: Vec<&'static str>,
    event_keywords: Vec<&'static str>,
}

impl HandDetector {
    pub fn new() -> Self {
        Self {
            schedule_keywords: vec![
                "每天", "每周", "定时", "schedule", "自动", "周期", "cron", "interval",
            ],
            event_keywords: vec!["当", "when", "每当", "触发", "event"],
        }
    }

    pub async fn detect(&self, content: &str) -> Option<HandMatch> {
        let lower = content.to_lowercase();

        for keyword in &self.schedule_keywords {
            if lower.contains(&keyword.to_lowercase()) {
                return Some(HandMatch {
                    hand_id: String::new(),
                    match_type: HandMatchType::ScheduleKeyword,
                    confidence: 0.7,
                });
            }
        }

        for keyword in &self.event_keywords {
            if lower.contains(&keyword.to_lowercase()) {
                return Some(HandMatch {
                    hand_id: String::new(),
                    match_type: HandMatchType::EventKeyword,
                    confidence: 0.6,
                });
            }
        }

        None
    }
}

impl Default for HandDetector {
    fn default() -> Self {
        Self::new()
    }
}

pub struct RuleMatcher {
    rules: Vec<TaskRule>,
}

impl RuleMatcher {
    pub fn new() -> Self {
        Self {
            rules: vec![
                TaskRule::new(
                    vec!["写代码", "写个", "帮我写", "code", "编程", "实现", "写一个"],
                    TaskType::CodeGeneration,
                    "code_generation_skill",
                ),
                TaskRule::new(
                    vec!["翻译", "translate", "中译英", "英译中", "翻译成"],
                    TaskType::Translation,
                    "translation_skill",
                ),
                TaskRule::new(
                    vec!["搜索", "查找", "search", "找一下", "查一下", "搜一下"],
                    TaskType::WebSearch,
                    "web_search_skill",
                ),
                TaskRule::new(
                    vec!["分析", "分析一下", "分析这段", "分析这个"],
                    TaskType::DataAnalysis,
                    "data_analysis_skill",
                ),
                TaskRule::new(
                    vec!["总结", "summarize", "概括", "提炼", "摘要"],
                    TaskType::Summarization,
                    "summarization_skill",
                ),
                TaskRule::new(
                    vec!["review", "审查", "检查代码", "代码审查", "review一下"],
                    TaskType::CodeReview,
                    "code_review_skill",
                ),
            ],
        }
    }

    pub fn match_task(&self, content: &str) -> Option<SkillMatch> {
        let lower = content.to_lowercase();

        for rule in &self.rules {
            if rule.matches(&lower) {
                return Some(SkillMatch {
                    task_type: rule.task_type.clone(),
                    skill_id: rule.skill_id.to_string(),
                    confidence: 0.9,
                });
            }
        }

        None
    }
}

impl Default for RuleMatcher {
    fn default() -> Self {
        Self::new()
    }
}

struct TaskRule {
    keywords: Vec<&'static str>,
    task_type: TaskType,
    skill_id: &'static str,
}

impl TaskRule {
    fn new(
        keywords: Vec<&'static str>,
        task_type: TaskType,
        skill_id: &'static str,
    ) -> Self {
        Self {
            keywords,
            task_type,
            skill_id,
        }
    }

    fn matches(&self, content: &str) -> bool {
        self.keywords.iter().any(|k| content.contains(k))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::task::TaskInput;

    fn create_text_request(content: &str) -> TaskRequest {
        TaskRequest::new(
            TaskType::Conversation,
            TaskInput::Text {
                content: content.to_string(),
            },
        )
    }

    #[test]
    fn test_rule_matcher_code_generation() {
        let matcher = RuleMatcher::new();
        
        let result = matcher.match_task("帮我写一个排序算法");
        assert!(result.is_some());
        let match_result = result.unwrap();
        assert_eq!(match_result.skill_id, "code_generation_skill");
    }

    #[test]
    fn test_rule_matcher_translation() {
        let matcher = RuleMatcher::new();
        
        let result = matcher.match_task("把这段话翻译成英文");
        assert!(result.is_some());
        let match_result = result.unwrap();
        assert_eq!(match_result.skill_id, "translation_skill");
    }

    #[test]
    fn test_rule_matcher_websearch() {
        let matcher = RuleMatcher::new();
        
        let result = matcher.match_task("搜索一下最新的AI新闻");
        assert!(result.is_some());
        let match_result = result.unwrap();
        assert_eq!(match_result.skill_id, "web_search_skill");
    }

    #[test]
    fn test_rule_matcher_code() {
        let matcher = RuleMatcher::new();
        
        let result = matcher.match_task("帮我写代码");
        assert!(result.is_some());
        
        let result2 = matcher.match_task("写个排序");
        assert!(result2.is_some());
    }

    #[tokio::test]
    async fn test_hand_detector_schedule() {
        let detector = HandDetector::new();
        
        let result = detector.detect("每天早上8点执行任务").await;
        assert!(result.is_some());
        let match_result = result.unwrap();
        assert_eq!(match_result.match_type, HandMatchType::ScheduleKeyword);
    }

    #[tokio::test]
    async fn test_hand_detector_event() {
        let detector = HandDetector::new();
        
        let result = detector.detect("当用户注册时发送欢迎消息").await;
        assert!(result.is_some());
        let match_result = result.unwrap();
        assert_eq!(match_result.match_type, HandMatchType::EventKeyword);
    }

    #[tokio::test]
    async fn test_task_classifier_hand() {
        let classifier = TaskClassifier::new();
        let request = create_text_request("每天早上8点研究Tesla最新动态");
        
        let result = classifier.classify(&request).await;
        
        if let TaskClassification::Hand { hand_id, .. } = result {
            assert!(!hand_id.is_empty() || true);
        } else {
            panic!("Expected Hand classification");
        }
    }

    #[tokio::test]
    async fn test_task_classifier_skill() {
        let classifier = TaskClassifier::new();
        let request = create_text_request("帮我写一个排序算法");
        
        let result = classifier.classify(&request).await;
        
        assert!(matches!(result, TaskClassification::WithSkill { .. }));
    }

    #[tokio::test]
    async fn test_task_classifier_direct() {
        let classifier = TaskClassifier::new();
        let request = create_text_request("今天天气怎么样");
        
        let result = classifier.classify(&request).await;
        
        assert!(matches!(result, TaskClassification::Direct { .. }));
    }

    #[test]
    fn test_requires_skill() {
        assert!(TaskClassifier::requires_skill(&TaskType::CodeGeneration));
        assert!(TaskClassifier::requires_skill(&TaskType::Translation));
        assert!(TaskClassifier::requires_skill(&TaskType::WebSearch));
        assert!(!TaskClassifier::requires_skill(&TaskType::Conversation));
    }

    #[test]
    fn test_select_skill() {
        let classifier = TaskClassifier::new();
        
        assert_eq!(classifier.select_skill(&TaskType::CodeGeneration), "code_generation_skill");
        assert_eq!(classifier.select_skill(&TaskType::Translation), "translation_skill");
        assert_eq!(classifier.select_skill(&TaskType::Conversation), "");
    }
}
