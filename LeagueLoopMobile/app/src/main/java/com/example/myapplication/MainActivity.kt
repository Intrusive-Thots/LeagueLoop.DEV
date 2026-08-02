package com.example.myapplication

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.material3.adaptive.ExperimentalMaterial3AdaptiveApi
import androidx.compose.material3.adaptive.currentWindowAdaptiveInfo
import androidx.compose.material3.adaptive.layout.calculatePaneScaffoldDirective
import androidx.compose.material3.adaptive.navigation3.ListDetailSceneStrategy
import androidx.compose.material3.adaptive.navigation3.rememberListDetailSceneStrategy
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation3.runtime.NavKey
import androidx.navigation3.runtime.entryProvider
import androidx.navigation3.runtime.rememberNavBackStack
import androidx.navigation3.ui.NavDisplay
import com.example.myapplication.data.discovery.DiscoveredServer
import com.example.myapplication.data.discovery.ServerDiscovery
import com.example.myapplication.data.network.SocketClient
import com.example.myapplication.ui.discovery.DiscoveryScreen
import com.example.myapplication.ui.draft.ChampionSelectScreen
import com.example.myapplication.ui.draft.DraftUiState
import com.example.myapplication.ui.draft.DraftViewModel
import com.example.myapplication.ui.navigation.*
import com.example.myapplication.ui.readycheck.ReadyCheckOverlay
import com.example.myapplication.ui.readycheck.ReadyCheckState
import com.example.myapplication.ui.readycheck.ReadyCheckViewModel
import com.example.myapplication.ui.runes.RuneManagementScreen
import com.example.myapplication.ui.settings.SettingsDashboard
import com.example.myapplication.ui.settings.SettingsViewModel
import com.example.myapplication.ui.theme.LeagueLoopTheme
import kotlinx.coroutines.flow.collect
import okhttp3.OkHttpClient

class MainActivity : ComponentActivity() {
    private val serverDiscovery = ServerDiscovery()
    private val okHttpClient = OkHttpClient()
    private val socketClient = SocketClient(okHttpClient)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            LeagueLoopTheme {
                MainApp(socketClient, serverDiscovery)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3AdaptiveApi::class)
@Composable
fun MainApp(socketClient: SocketClient, serverDiscovery: ServerDiscovery) {
    val readyCheckViewModel = remember { ReadyCheckViewModel(socketClient) }
    val draftViewModel = remember { DraftViewModel(socketClient) }
    val settingsViewModel = remember { SettingsViewModel(socketClient) }
    
    val backStack = rememberNavBackStack(Discovery)
    val readyCheckState by readyCheckViewModel.uiState.collectAsState()
    val draftState by draftViewModel.uiState.collectAsState()
    val settings by settingsViewModel.settings.collectAsState()
    
    val servers = remember { mutableStateListOf<DiscoveredServer>() }

    val windowAdaptiveInfo = currentWindowAdaptiveInfo()
    val directive = remember(windowAdaptiveInfo) {
        calculatePaneScaffoldDirective(windowAdaptiveInfo)
            .copy(horizontalPartitionSpacerSize = 0.dp)
    }
    val listDetailStrategy = rememberListDetailSceneStrategy<NavKey>(directive = directive)

    LaunchedEffect(Unit) {
        serverDiscovery.discover().collect { server ->
            if (servers.none { it.ipAddress == server.ipAddress }) {
                servers.add(server)
            }
        }
    }

    // Navigation logic: Switch to ChampionSelect when draft is active
    LaunchedEffect(draftState) {
        if (draftState is DraftUiState.Active && backStack.lastOrNull() !is ChampionSelect) {
            backStack.add(ChampionSelect)
            readyCheckViewModel.resetState()
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        val isMatchFound = readyCheckState is ReadyCheckState.MatchFound
        
        NavDisplay(
            backStack = backStack,
            onBack = { backStack.removeLastOrNull() },
            modifier = Modifier.blur(if (isMatchFound) 12.dp else 0.dp),
            sceneStrategies = listOf(listDetailStrategy),
            entryProvider = entryProvider {
                entry<Discovery>(
                    metadata = ListDetailSceneStrategy.listPane()
                ) {
                    DiscoveryScreen(
                        servers = servers,
                        onConnect = { server ->
                            readyCheckViewModel.connect(server.ipAddress, server.port)
                        }
                    )
                }
                entry<ChampionSelect>(
                    metadata = ListDetailSceneStrategy.detailPane()
                ) {
                    val activeState = (draftState as? DraftUiState.Active)?.state
                    if (activeState != null) {
                        ChampionSelectScreen(
                            state = activeState,
                            onPick = { draftViewModel.pickChampion(it) },
                            onBan = { draftViewModel.banChampion(it) },
                            onOpenSettings = { backStack.add(Settings) },
                            onOpenRunes = { backStack.add(Runes) }
                        )
                    } else {
                        // Fallback or loading
                        Box(modifier = Modifier.fillMaxSize().background(Color.Black))
                    }
                }
                entry<Runes>(
                    metadata = ListDetailSceneStrategy.extraPane()
                ) {
                    RuneManagementScreen(
                        runePages = emptyList(), // Mock or from VM
                        selectedPageId = "",
                        onSelectPage = { /* Sync */ },
                        onBack = { backStack.removeLastOrNull() }
                    )
                }
                entry<Settings>(
                    metadata = ListDetailSceneStrategy.extraPane()
                ) {
                    SettingsDashboard(
                        settings = settings,
                        onToggleAutoDraft = { settingsViewModel.toggleEnabled(it) },
                        onUpdateAutoBan = { settingsViewModel.updateAutoBan(it) },
                        onUpdateAutoPick = { settingsViewModel.updateAutoPick(it) },
                        onBack = { backStack.removeLastOrNull() }
                    )
                }
            }
        )

        ReadyCheckOverlay(
            state = readyCheckState,
            onAccept = { readyCheckViewModel.acceptMatch() },
            onDecline = { readyCheckViewModel.declineMatch() }
        )
    }
}
