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
      welcome: '娆㈣繋浣跨敤 OpenAgentic',
      'error.not_found': '璧勬簮鏈壘鍒?,
      'error.timeout': '璇锋眰瓒呮椂',
      'error.invalid_input': '杈撳叆鏃犳晥',
      'error.internal': '鍐呴儴閿欒',
      'search.placeholder': '鎼滅储...',
      'search.no_results': '鏈壘鍒扮粨鏋?,
      'search.loading': '鎼滅储涓?..',
      'tool.web_search': '缃戦〉鎼滅储宸ュ叿',
      'tool.image_gen': '鍥惧儚鐢熸垚宸ュ叿',
      'tool.filesystem': '鏂囦欢绯荤粺宸ュ叿',
      'tool.calculator': '璁＄畻鍣ㄥ伐鍏?,
      'status.connected': '宸茶繛鎺?,
      'status.disconnected': '宸叉柇寮€',
      'status.error': '閿欒',
      'action.submit': '鎻愪氦',
      'action.cancel': '鍙栨秷',
      'action.confirm': '纭',
      'action.retry': '閲嶈瘯',
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
  { code: 'zh', name: '涓枃' },
];
