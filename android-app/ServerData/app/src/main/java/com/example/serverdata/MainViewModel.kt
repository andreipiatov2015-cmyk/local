package com.example.serverdata

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.serverdata.data.ApiClient
import com.example.serverdata.data.ApiException
import com.example.serverdata.data.Item
import com.example.serverdata.data.ServerAddress
import com.example.serverdata.data.Settings
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

sealed interface Screen {
    /** Главный экран: IP, порт, «Подключиться». */
    data object Connect : Screen
    data object List : Screen
    data class Detail(val itemId: String) : Screen
}

data class UiState(
    val screen: Screen = Screen.Connect,

    // экран подключения
    val hostInput: String = "",
    val portInput: String = "8000",
    val recent: kotlin.collections.List<ServerAddress> = emptyList(),
    val connecting: Boolean = false,
    val connectError: String? = null,

    // после подключения
    val server: ServerAddress? = null,
    val serverName: String? = null,
    val items: kotlin.collections.List<Item> = emptyList(),
    val loading: Boolean = false,
    /** Ошибка последнего обновления; старые данные при этом остаются на экране. */
    val error: String? = null,
    /** Время последней успешной синхронизации (мс). */
    val lastSync: Long? = null,
    val query: String = "",
)

class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val settings = Settings(app)

    private val _state = MutableStateFlow(
        UiState(
            hostInput = settings.lastHost,
            portInput = settings.lastPort,
            recent = settings.recent,
        )
    )
    val state: StateFlow<UiState> = _state.asStateFlow()

    private var connectJob: Job? = null
    private var refreshJob: Job? = null
    private var autoSyncJob: Job? = null

    // ---------- экран подключения ----------

    fun setHost(text: String) = _state.update { it.copy(hostInput = text, connectError = null) }
    fun setPort(text: String) =
        _state.update { it.copy(portInput = text.filter(Char::isDigit).take(5), connectError = null) }

    fun pickRecent(address: ServerAddress) = _state.update {
        it.copy(hostInput = address.host, portInput = address.port.toString(), connectError = null)
    }

    fun removeRecent(address: ServerAddress) {
        settings.removeRecent(address)
        _state.update { it.copy(recent = settings.recent) }
    }

    /** Проверить адрес, загрузить данные и перейти к списку. */
    fun connect() {
        val s = _state.value
        val address = validate(s.hostInput, s.portInput) ?: return
        if (connectJob?.isActive == true) return
        connectJob = viewModelScope.launch {
            _state.update { it.copy(connecting = true, connectError = null) }
            val client = ApiClient(address.baseUrl)
            try {
                val data = client.items()
                val name = runCatching { client.info().name }.getOrNull()
                settings.lastHost = address.host
                settings.lastPort = address.port.toString()
                settings.addRecent(address)
                _state.update {
                    it.copy(
                        connecting = false,
                        screen = Screen.List,
                        server = address,
                        serverName = name,
                        items = data.items,
                        lastSync = System.currentTimeMillis(),
                        error = null,
                        query = "",
                        recent = settings.recent,
                    )
                }
                startAutoSync(refreshNow = false)
            } catch (e: ApiException) {
                _state.update { it.copy(connecting = false, connectError = e.message) }
            } catch (e: Exception) {
                _state.update {
                    it.copy(connecting = false, connectError = "Ошибка: ${e.message ?: e.javaClass.simpleName}")
                }
            }
        }
    }

    private fun validate(hostRaw: String, portRaw: String): ServerAddress? {
        // Разрешаем вставить «http://1.2.3.4:8000/» целиком в поле IP.
        var host = hostRaw.trim().removePrefix("http://").removePrefix("https://").trimEnd('/')
        var portText = portRaw.trim()
        if (host.count { it == ':' } == 1) {
            portText = host.substringAfter(':')
            host = host.substringBefore(':')
        }
        val port = portText.toIntOrNull()
        val error = when {
            host.isEmpty() -> "Введите IP-адрес сервера"
            host.any { it.isWhitespace() } -> "В адресе не должно быть пробелов"
            port == null || port !in 1..65535 -> "Порт — число от 1 до 65535"
            else -> null
        }
        if (error != null) {
            _state.update { it.copy(connectError = error) }
            return null
        }
        _state.update { it.copy(hostInput = host, portInput = port.toString()) }
        return ServerAddress(host, port!!)
    }

    /** Отключиться и вернуться на главный экран. */
    fun disconnect() {
        stopAutoSync()
        refreshJob?.cancel()
        _state.update {
            it.copy(
                screen = Screen.Connect,
                server = null,
                serverName = null,
                items = emptyList(),
                lastSync = null,
                error = null,
                loading = false,
                query = "",
            )
        }
    }

    // ---------- навигация ----------

    fun openItem(id: String) = _state.update { it.copy(screen = Screen.Detail(id)) }

    /** @return true, если «назад» обработано внутри приложения. */
    fun back(): Boolean = when (_state.value.screen) {
        is Screen.Detail -> { _state.update { it.copy(screen = Screen.List) }; true }
        Screen.List -> { disconnect(); true }
        Screen.Connect -> false
    }

    fun setQuery(q: String) = _state.update { it.copy(query = q) }

    // ---------- синхронизация ----------

    /** Загрузить данные с сервера. Повторный вызов во время загрузки игнорируется. */
    fun refresh() {
        val address = _state.value.server ?: return
        if (refreshJob?.isActive == true) return
        refreshJob = viewModelScope.launch {
            _state.update { it.copy(loading = true) }
            val client = ApiClient(address.baseUrl)
            try {
                val data = client.items()
                val name = runCatching { client.info().name }.getOrNull()
                _state.update {
                    if (it.server != address) return@update it  // уже отключились
                    it.copy(
                        items = data.items,
                        serverName = name ?: it.serverName,
                        lastSync = System.currentTimeMillis(),
                        error = null,
                        loading = false,
                    )
                }
            } catch (e: ApiException) {
                _state.update { it.copy(error = e.message, loading = false) }
            } catch (e: Exception) {
                _state.update {
                    it.copy(error = "Ошибка: ${e.message ?: e.javaClass.simpleName}", loading = false)
                }
            }
        }
    }

    /** Автообновление, пока приложение на экране и есть подключение. */
    fun startAutoSync(refreshNow: Boolean = true) {
        if (_state.value.server == null) return
        autoSyncJob?.cancel()
        autoSyncJob = viewModelScope.launch {
            if (!refreshNow) delay(settings.intervalSec * 1000L)
            while (isActive) {
                refresh()
                delay(settings.intervalSec * 1000L)
            }
        }
    }

    /** Приложение свёрнуто — не тратим трафик и батарею. */
    fun stopAutoSync() {
        autoSyncJob?.cancel()
        autoSyncJob = null
    }
}
