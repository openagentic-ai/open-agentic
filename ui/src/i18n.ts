import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

const resources = {
  en: {
    translation: {
      welcome: 'Welcome to OpenAgentic',
      'error.not_found': 'Resource not found',
      'error.timeout': 'Request timeout',
      'error.invalid_input': 'Invalid input',
      'error.internal': 'Internal error',
      'search.placeholder': 'Search...',
      'search.no_results': 'No results found',
      'search.loading': 'Searching...',
      'tool.web_search': 'Web Search Tool',
      'tool.image_gen': 'Image Generation Tool',
      'tool.filesystem': 'Filesystem Tool',
      'tool.calculator': 'Calculator Tool',
      'status.connected': 'Connected',
      'status.disconnected': 'Disconnected',
      'status.error': 'Error',
      'action.submit': 'Submit',
      'action.cancel': 'Cancel',
      'action.confirm': 'Confirm',
      'action.retry': 'Retry',
    },
  },
  zh: {
    translation: {
      welcome: '欢迎使用 OpenAgentic',
      'error.not_found': '资源未找到',
      'error.timeout': '请求超时',
      'error.invalid_input': '输入无效',
      'error.internal': '内部错误',
      'search.placeholder': '搜索...',
      'search.no_results': '未找到结果',
      'search.loading': '搜索中...',
      'tool.web_search': '网页搜索工具',
      'tool.image_gen': '图像生成工具',
      'tool.filesystem': '文件系统工具',
      'tool.calculator': '计算器工具',
      'status.connected': '已连接',
      'status.disconnected': '已断开',
      'status.error': '错误',
      'action.submit': '提交',
      'action.cancel': '取消',
      'action.confirm': '确认',
      'action.retry': '重试',
    },
  },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
  });

export default i18n;

export const changeLanguage = (lang: string) => {
  i18n.changeLanguage(lang);
};

export const getCurrentLanguage = () => {
  return i18n.language;
};

export const supportedLanguages = [
  { code: 'en', name: 'English' },
  { code: 'zh', name: '中文' },
];
