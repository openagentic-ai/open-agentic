package ai.openagentic.app.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.combinedClickable
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ai.openagentic.app.ChatMessage
import ai.openagentic.app.ChatUiState
import ai.openagentic.app.R

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    uiState: ChatUiState,
    onSendMessage: (String) -> Unit,
    onUpdateSettings: (String, String, String) -> Unit,
    onConnect: () -> Unit,
    onDismissError: () -> Unit,
    onLanguageChange: (String) -> Unit = {},
    currentLanguage: String = "system",
) {
    var inputText by remember { mutableStateOf("") }
    var showSettings by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()

    // Auto-scroll to bottom when new messages arrive
    LaunchedEffect(uiState.messages.size) {
        if (uiState.messages.isNotEmpty()) {
            listState.animateScrollToItem(uiState.messages.size - 1)
        }
    }

    Scaffold(
        modifier = Modifier.imePadding(),
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(stringResource(R.string.app_name), fontSize = 20.sp)
                        Spacer(modifier = Modifier.width(8.dp))
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .clip(CircleShape)
                                .background(
                                    if (uiState.isConnected) Color(0xFF4CAF50)
                                    else Color(0xFFE0E0E0)
                                )
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { showSettings = true }) {
                        Icon(Icons.Default.Settings, contentDescription = stringResource(R.string.settings))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Error banner
            AnimatedVisibility(visible = uiState.errorMessage != null) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    color = MaterialTheme.colorScheme.errorContainer,
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = uiState.errorMessage ?: "",
                            modifier = Modifier.weight(1f),
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            fontSize = 13.sp,
                        )
                        TextButton(onClick = onDismissError) {
                            Text(stringResource(R.string.dismiss))
                        }
                    }
                }
            }

            // Chat messages
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                state = listState,
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (uiState.messages.isEmpty()) {
                    item {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(top = 100.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(
                                    text = stringResource(R.string.app_name),
                                    fontSize = 24.sp,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = if (uiState.isConnected) stringResource(R.string.ask_me_anything)
                                    else stringResource(R.string.tap_gear_to_connect),
                                    fontSize = 14.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }

                items(uiState.messages) { message ->
                    MessageBubble(message = message)
                }

                // Typing indicator
                if (uiState.isLoading && (uiState.messages.isEmpty() || uiState.messages.last().isUser)) {
                    item {
                        Row(modifier = Modifier.padding(start = 4.dp)) {
                            Text(
                                text = stringResource(R.string.thinking),
                                fontSize = 13.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }

            // Input bar
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shadowElevation = 8.dp,
            ) {
                Row(
                    modifier = Modifier
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text(stringResource(R.string.type_a_message)) },
                        maxLines = 4,
                        shape = RoundedCornerShape(24.dp),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                        keyboardActions = KeyboardActions(
                            onSend = {
                                if (inputText.isNotBlank()) {
                                    onSendMessage(inputText)
                                    inputText = ""
                                }
                            }
                        ),
                    )

                    Spacer(modifier = Modifier.width(8.dp))

                    // Mic button
                    IconButton(
                        onClick = { /* TODO: voice input */ },
                        modifier = Modifier.size(48.dp),
                    ) {
                        Icon(
                            Icons.Default.Mic,
                            contentDescription = stringResource(R.string.voice_input),
                            tint = MaterialTheme.colorScheme.primary,
                        )
                    }

                    // Send button
                    IconButton(
                        onClick = {
                            if (inputText.isNotBlank()) {
                                onSendMessage(inputText)
                                inputText = ""
                            }
                        },
                        enabled = inputText.isNotBlank() && !uiState.isLoading,
                        modifier = Modifier.size(48.dp),
                    ) {
                        Icon(
                            Icons.AutoMirrored.Filled.Send,
                            contentDescription = stringResource(R.string.send),
                            tint = if (inputText.isNotBlank() && !uiState.isLoading)
                                MaterialTheme.colorScheme.primary
                            else
                                MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }

    // Settings dialog
    if (showSettings) {
        SettingsDialog(
            gatewayUrl = uiState.gatewayUrl,
            username = uiState.username,
            password = uiState.password,
            isConnected = uiState.isConnected,
            currentLanguage = currentLanguage,
            onDismiss = { showSettings = false },
            onSave = { url, user, pass ->
                onUpdateSettings(url, user, pass)
                onConnect()
                showSettings = false
            },
            onLanguageChange = onLanguageChange,
        )
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun MessageBubble(message: ChatMessage) {
    val isUser = message.isUser
    val clipboardManager = LocalClipboardManager.current
    val haptic = LocalHapticFeedback.current
    var showCopied by remember { mutableStateOf(false) }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        Surface(
            modifier = Modifier
                .widthIn(max = 300.dp)
                .combinedClickable(
                    onClick = {},
                    onLongClick = {
                        clipboardManager.setText(AnnotatedString(message.content))
                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        showCopied = true
                    },
                ),
            shape = RoundedCornerShape(
                topStart = 16.dp,
                topEnd = 16.dp,
                bottomStart = if (isUser) 16.dp else 4.dp,
                bottomEnd = if (isUser) 4.dp else 16.dp,
            ),
            color = if (isUser)
                MaterialTheme.colorScheme.primary
            else
                MaterialTheme.colorScheme.surfaceVariant,
        ) {
            Text(
                text = message.content + if (message.isStreaming) "\u258C" else "",
                modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                color = if (isUser)
                    MaterialTheme.colorScheme.onPrimary
                else
                    MaterialTheme.colorScheme.onSurfaceVariant,
                fontSize = 15.sp,
            )
        }
    }

    if (showCopied) {
        LaunchedEffect(Unit) {
            kotlinx.coroutines.delay(1500)
            showCopied = false
        }
        Box(
            modifier = Modifier.fillMaxWidth(),
            contentAlignment = if (isUser) Alignment.CenterEnd else Alignment.CenterStart,
        ) {
            Text(
                text = "Copied",
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
        }
    }
}

@Composable
fun SettingsDialog(
    gatewayUrl: String,
    username: String,
    password: String,
    isConnected: Boolean,
    currentLanguage: String,
    onDismiss: () -> Unit,
    onSave: (String, String, String) -> Unit,
    onLanguageChange: (String) -> Unit,
) {
    var url by remember { mutableStateOf(gatewayUrl) }
    var user by remember { mutableStateOf(username) }
    var pass by remember { mutableStateOf(password) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.settings)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                // -- Gateway Settings section --
                Text(
                    text = stringResource(R.string.gateway_settings),
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.primary,
                )
                HorizontalDivider()
                OutlinedTextField(
                    value = url,
                    onValueChange = { url = it },
                    label = { Text(stringResource(R.string.gateway_url)) },
                    placeholder = { Text(stringResource(R.string.gateway_url_hint)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = user,
                    onValueChange = { user = it },
                    label = { Text(stringResource(R.string.username)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = pass,
                    onValueChange = { pass = it },
                    label = { Text(stringResource(R.string.password)) },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    modifier = Modifier.fillMaxWidth(),
                )
                // Connection status
                Text(
                    text = if (isConnected) stringResource(R.string.connected)
                    else stringResource(R.string.not_connected),
                    color = if (isConnected) Color(0xFF4CAF50) else Color(0xFF9E9E9E),
                    fontSize = 13.sp,
                )

                Spacer(modifier = Modifier.height(8.dp))

                // -- Language Settings section --
                Text(
                    text = stringResource(R.string.language_settings),
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.primary,
                )
                HorizontalDivider()
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    LanguageChip(
                        label = stringResource(R.string.language_system),
                        selected = currentLanguage == "system",
                        onClick = { onLanguageChange("system") },
                        modifier = Modifier.weight(1f),
                    )
                    LanguageChip(
                        label = stringResource(R.string.language_chinese),
                        selected = currentLanguage == "zh",
                        onClick = { onLanguageChange("zh") },
                        modifier = Modifier.weight(1f),
                    )
                    LanguageChip(
                        label = stringResource(R.string.language_english),
                        selected = currentLanguage == "en",
                        onClick = { onLanguageChange("en") },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onSave(url, user, pass) }) {
                Text(stringResource(R.string.connect))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.cancel))
            }
        },
    )
}

@Composable
fun LanguageChip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = {
            Text(label, fontSize = 13.sp, maxLines = 1)
        },
        modifier = modifier,
    )
}
