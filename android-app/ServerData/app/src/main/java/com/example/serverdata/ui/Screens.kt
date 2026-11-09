package com.example.serverdata.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.serverdata.MainViewModel
import com.example.serverdata.Screen
import com.example.serverdata.UiState
import com.example.serverdata.data.Item
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun App(state: UiState, vm: MainViewModel) {
    when (val screen = state.screen) {
        Screen.Connect -> ConnectScreen(state, vm)
        Screen.List -> ListScreen(state, vm)
        is Screen.Detail -> {
            val item = state.items.firstOrNull { it.id == screen.itemId }
            if (item == null) ListScreen(state, vm) else DetailScreen(record = item, onBack = { vm.back() })
        }
    }
}

// ======================= Главный экран: подключение =======================

@Composable
fun ConnectScreen(state: UiState, vm: MainViewModel) {
    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 32.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("Подключение к серверу", style = MaterialTheme.typography.headlineSmall)
            Text(
                "В локальной сети — внутренний IP сервера (например 192.168.1.10). " +
                    "Удалённо — внешний IP роутера и проброшенный порт.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            OutlinedTextField(
                value = state.hostInput,
                onValueChange = vm::setHost,
                label = { Text("IP-адрес") },
                placeholder = { Text("192.168.1.10") },
                singleLine = true,
                enabled = !state.connecting,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Next),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = state.portInput,
                onValueChange = vm::setPort,
                label = { Text("Порт") },
                placeholder = { Text("8000") },
                singleLine = true,
                enabled = !state.connecting,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Next),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = state.tokenInput,
                onValueChange = vm::setToken,
                label = { Text("Токен доступа (необязательно)") },
                placeholder = { Text("оставьте пустым, если не настроен") },
                singleLine = true,
                enabled = !state.connecting,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text, imeAction = ImeAction.Go),
                keyboardActions = KeyboardActions(onGo = { vm.connect() }),
                modifier = Modifier.fillMaxWidth(),
            )

            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Подключаться по HTTPS", modifier = Modifier.weight(1f))
                Switch(checked = state.useHttps, onCheckedChange = vm::setUseHttps, enabled = !state.connecting)
            }
            if (state.tokenInput.isNotBlank() && !state.useHttps) {
                Text(
                    "Без HTTPS токен передаётся по сети открытым текстом. Включите, если " +
                        "сервер поддерживает https, иначе используйте только в доверенной сети.",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            state.connectError?.let {
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            }

            Button(
                onClick = vm::connect,
                enabled = !state.connecting,
                modifier = Modifier.fillMaxWidth().height(52.dp),
            ) {
                if (state.connecting) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(12.dp))
                    Text("Подключение…")
                } else {
                    Text("Подключиться")
                }
            }

            if (state.recent.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text("Недавние", style = MaterialTheme.typography.titleSmall)
                state.recent.forEach { address ->
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable(enabled = !state.connecting) { vm.pickRecent(address) }
                            .padding(vertical = 4.dp),
                    ) {
                        Text(address.toString(), modifier = Modifier.weight(1f))
                        IconButton(onClick = { vm.removeRecent(address) }) {
                            Icon(Icons.Default.Close, contentDescription = "Удалить из недавних")
                        }
                    }
                }
            }
        }
    }
}

// ======================= Список данных =======================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ListScreen(state: UiState, vm: MainViewModel) {
    val q = state.query.trim()
    val visible = if (q.isEmpty()) state.items else state.items.filter { it.matches(q) }

    Scaffold(
        topBar = {
            TopAppBar(
                navigationIcon = {
                    IconButton(onClick = vm::disconnect) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Отключиться")
                    }
                },
                title = {
                    Column {
                        Text(state.serverName ?: "Сервер", maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(
                            state.server?.toString().orEmpty(),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                actions = {
                    IconButton(onClick = vm::refresh, enabled = !state.loading) {
                        Icon(Icons.Default.Refresh, contentDescription = "Обновить")
                    }
                },
            )
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            if (state.loading) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
            } else {
                Spacer(Modifier.height(4.dp))
            }

            state.error?.let { ErrorBanner(it, onRetry = vm::refresh) }

            OutlinedTextField(
                value = state.query,
                onValueChange = vm::setQuery,
                placeholder = { Text("Поиск") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                trailingIcon = {
                    if (state.query.isNotEmpty()) {
                        IconButton(onClick = { vm.setQuery("") }) {
                            Icon(Icons.Default.Clear, contentDescription = "Очистить")
                        }
                    }
                },
                singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
            )

            Text(
                buildString {
                    append("Записей: ${visible.size}")
                    if (q.isNotEmpty()) append(" из ${state.items.size}")
                    state.lastSync?.let { append(" · обновлено в ${formatTime(it)}") }
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp),
            )

            if (visible.isEmpty()) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        if (q.isNotEmpty()) "Ничего не найдено" else "На сервере пока нет данных",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(visible, key = { it.id }) { item ->
                        ItemCard(item, onClick = { vm.openItem(item.id) })
                    }
                }
            }
        }
    }
}

@Composable
private fun ItemCard(item: Item, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(item.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            item.subtitle?.let {
                Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            // Первые два поля — для быстрого просмотра прямо в списке.
            item.fields.take(2).forEach { (name, value) ->
                Text(
                    "$name: $value",
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun ErrorBanner(message: String, onRetry: () -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
        shape = MaterialTheme.shapes.medium,
    ) {
        Row(Modifier.padding(start = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(
                message,
                color = MaterialTheme.colorScheme.onErrorContainer,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.weight(1f).padding(vertical = 8.dp),
            )
            TextButton(onClick = onRetry) { Text("Повторить") }
        }
    }
}

// ======================= Карточка записи =======================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DetailScreen(record: Item, onBack: () -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(record.title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Назад")
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
        ) {
            item {
                Text(record.title, style = MaterialTheme.typography.headlineSmall)
                record.subtitle?.let {
                    Text(it, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.height(16.dp))
            }
            if (record.fields.isNotEmpty()) {
                item {
                    Card(colors = CardDefaults.cardColors()) {
                        Column(Modifier.padding(horizontal = 16.dp)) {
                            record.fields.forEachIndexed { i, (name, value) ->
                                if (i > 0) HorizontalDivider()
                                Row(Modifier.fillMaxWidth().padding(vertical = 12.dp)) {
                                    Text(
                                        name,
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.weight(0.45f),
                                    )
                                    Text(
                                        value,
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = FontWeight.Medium,
                                        modifier = Modifier.weight(0.55f),
                                    )
                                }
                            }
                        }
                    }
                }
            }
            item {
                Spacer(Modifier.height(16.dp))
                Text(
                    buildString {
                        append("ID: ${record.id}")
                        record.updatedAt?.let { append(" · изменено: $it") }
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

// ======================= helpers =======================

private fun Item.matches(q: String): Boolean =
    title.contains(q, ignoreCase = true) ||
        subtitle?.contains(q, ignoreCase = true) == true ||
        id.contains(q, ignoreCase = true) ||
        fields.any { (_, v) -> v.contains(q, ignoreCase = true) }

private fun formatTime(ms: Long): String =
    SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date(ms))
