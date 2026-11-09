package com.example.serverdata.data

import android.content.Context

/** Адрес сервера в виде IP (или имени) и порта. */
data class ServerAddress(val host: String, val port: Int) {
    val baseUrl: String get() = "http://$host:$port"
    override fun toString() = "$host:$port"

    companion object {
        /** "192.168.1.10:8000" → ServerAddress, иначе null. */
        fun parse(text: String): ServerAddress? {
            val idx = text.lastIndexOf(':')
            if (idx <= 0) return null
            val port = text.substring(idx + 1).toIntOrNull() ?: return null
            return ServerAddress(text.substring(0, idx), port)
        }
    }
}

/** Сохранённые настройки: последний адрес, недавние подключения, интервал обновления. */
class Settings(context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    var lastHost: String
        get() = prefs.getString(KEY_HOST, "") ?: ""
        set(value) = prefs.edit().putString(KEY_HOST, value).apply()

    var lastPort: String
        get() = prefs.getString(KEY_PORT, "8000") ?: "8000"
        set(value) = prefs.edit().putString(KEY_PORT, value).apply()

    /** Секунды между автообновлениями. */
    val intervalSec: Int get() = prefs.getInt(KEY_INTERVAL, 30)

    /** Недавние адреса, самый свежий первым (до 5 штук). */
    var recent: List<ServerAddress>
        get() = (prefs.getString(KEY_RECENT, "") ?: "")
            .split('\n')
            .mapNotNull { ServerAddress.parse(it) }
        set(value) = prefs.edit()
            .putString(KEY_RECENT, value.take(5).joinToString("\n"))
            .apply()

    fun addRecent(address: ServerAddress) {
        recent = listOf(address) + recent.filter { it != address }
    }

    fun removeRecent(address: ServerAddress) {
        recent = recent.filter { it != address }
    }

    private companion object {
        const val KEY_HOST = "host"
        const val KEY_PORT = "port"
        const val KEY_INTERVAL = "interval_sec"
        const val KEY_RECENT = "recent"
    }
}
