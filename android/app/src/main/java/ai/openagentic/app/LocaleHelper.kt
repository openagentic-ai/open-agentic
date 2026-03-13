package ai.openagentic.app

import android.content.Context
import android.content.res.Configuration
import java.util.Locale

object LocaleHelper {

    private const val PREF_NAME = "openagentic"
    private const val KEY_LANGUAGE = "language"

    /** Supported languages */
    const val LANG_EN = "en"
    const val LANG_ZH = "zh"
    const val LANG_SYSTEM = "system"

    fun getSavedLanguage(context: Context): String {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        return prefs.getString(KEY_LANGUAGE, LANG_SYSTEM) ?: LANG_SYSTEM
    }

    fun saveLanguage(context: Context, language: String) {
        context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_LANGUAGE, language)
            .apply()
    }

    /** Wrap context with the saved locale */
    fun applyLocale(context: Context): Context {
        val lang = getSavedLanguage(context)
        if (lang == LANG_SYSTEM) return context
        return updateContextLocale(context, lang)
    }

    private fun updateContextLocale(context: Context, language: String): Context {
        val locale = when (language) {
            LANG_ZH -> Locale.SIMPLIFIED_CHINESE
            LANG_EN -> Locale.ENGLISH
            else -> return context
        }

        Locale.setDefault(locale)

        val config = Configuration(context.resources.configuration)
        config.setLocale(locale)

        return context.createConfigurationContext(config)
    }

    /** Get display name for a language code */
    fun getDisplayName(language: String): String {
        return when (language) {
            LANG_EN -> "English"
            LANG_ZH -> "中文"
            LANG_SYSTEM -> "System / 跟随系统"
            else -> language
        }
    }
}
