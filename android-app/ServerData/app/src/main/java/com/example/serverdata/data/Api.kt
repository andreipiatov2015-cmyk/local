package com.example.serverdata.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.net.ConnectException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import java.net.UnknownHostException

/** Одна запись с сервера. fields — пары «название → значение» в порядке сервера. */
data class Item(
    val id: String,
    val title: String,
    val subtitle: String?,
    val updatedAt: String?,
    val fields: List<Pair<String, String>>,
)

data class ServerInfo(val name: String, val version: String?, val updatedAt: String?)

data class ItemsResponse(val updatedAt: String?, val items: List<Item>)

/** Ошибка с уже понятным пользователю текстом. */
class ApiException(message: String, cause: Throwable? = null) : Exception(message, cause)

/**
 * Клиент для API сервера (см. SERVER_API.md).
 * Использует только стандартные средства Android: HttpURLConnection и org.json.
 */
class ApiClient(baseUrl: String) {

    private val base = normalizeUrl(baseUrl)

    suspend fun info(): ServerInfo = withContext(Dispatchers.IO) {
        val json = parseObject(get("/api/info"))
        ServerInfo(
            name = json.str("name") ?: "Сервер",
            version = json.str("version"),
            updatedAt = json.str("updated_at"),
        )
    }

    suspend fun items(): ItemsResponse = withContext(Dispatchers.IO) {
        val json = parseObject(get("/api/items"))
        val array = json.optJSONArray("items")
            ?: throw ApiException("В ответе /api/items нет списка \"items\"")
        val items = (0 until array.length()).mapNotNull { i ->
            array.optJSONObject(i)?.let(::parseItem)
        }
        ItemsResponse(updatedAt = json.str("updated_at"), items = items)
    }

    private fun parseItem(obj: JSONObject): Item? {
        val id = obj.str("id") ?: return null
        val fieldsObj = obj.optJSONObject("fields")
        val fields = mutableListOf<Pair<String, String>>()
        if (fieldsObj != null) {
            val keys = fieldsObj.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                fields += key to formatValue(fieldsObj.opt(key))
            }
        }
        return Item(
            id = id,
            title = obj.str("title") ?: "Запись $id",
            subtitle = obj.str("subtitle"),
            updatedAt = obj.str("updated_at"),
            fields = fields,
        )
    }

    private fun formatValue(value: Any?): String = when (value) {
        null, JSONObject.NULL -> "—"
        is Boolean -> if (value) "да" else "нет"
        is Double -> if (value % 1.0 == 0.0 && value < 1e15) value.toLong().toString() else value.toString()
        else -> value.toString()
    }

    private fun get(path: String): String {
        val url = try {
            URL(base + path)
        } catch (e: Exception) {
            throw ApiException("Неверный адрес сервера: $base", e)
        }
        val conn = url.openConnection() as HttpURLConnection
        conn.connectTimeout = 10_000
        conn.readTimeout = 15_000
        conn.useCaches = false
        conn.setRequestProperty("Accept", "application/json")
        try {
            val code = conn.responseCode
            if (code !in 200..299) {
                throw ApiException("Сервер ответил: код $code ($path)")
            }
            return conn.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } catch (e: ApiException) {
            throw e
        } catch (e: UnknownHostException) {
            throw ApiException("Сервер не найден. Проверьте адрес и интернет.", e)
        } catch (e: ConnectException) {
            throw ApiException("Не удалось подключиться. Сервер запущен? Порт открыт?", e)
        } catch (e: SocketTimeoutException) {
            throw ApiException("Сервер не отвечает (таймаут).", e)
        } catch (e: IOException) {
            throw ApiException("Ошибка сети: ${e.message ?: e.javaClass.simpleName}", e)
        } finally {
            conn.disconnect()
        }
    }

    private fun parseObject(text: String): JSONObject = try {
        JSONObject(text)
    } catch (e: JSONException) {
        throw ApiException("Сервер вернул не JSON. Проверьте API на сервере.", e)
    }

    companion object {
        /** "192.168.1.10:8000/" → "http://192.168.1.10:8000" */
        fun normalizeUrl(raw: String): String {
            var url = raw.trim().trimEnd('/')
            if (url.isNotEmpty() && !url.startsWith("http://") && !url.startsWith("https://")) {
                url = "http://$url"
            }
            return url
        }
    }
}

/** Строка или null (если поля нет или там null). Числовой id тоже станет строкой. */
private fun JSONObject.str(key: String): String? =
    if (isNull(key)) null else opt(key)?.toString()?.takeIf { it.isNotBlank() }
