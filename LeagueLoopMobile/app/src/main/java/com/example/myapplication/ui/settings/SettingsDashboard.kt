package com.example.myapplication.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.myapplication.data.network.AutoDraftSettings
import com.example.myapplication.ui.theme.LeagueBlue
import com.example.myapplication.ui.theme.LeagueGold
import com.example.myapplication.ui.theme.SurfaceGlass

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsDashboard(
    settings: AutoDraftSettings,
    onToggleAutoDraft: (Boolean) -> Unit,
    onUpdateAutoBan: (String) -> Unit,
    onUpdateAutoPick: (String) -> Unit,
    onBack: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("SETTINGS DASHBOARD", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Rounded.ArrowBack, contentDescription = "Back", color = Color.White)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Transparent,
                    titleContentColor = Color.White
                )
            )
        },
        containerColor = Color.Transparent
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .background(
                    Brush.verticalGradient(
                        colors = listOf(Color(0xFF0A0A0C), Color(0xFF1A1A1E))
                    )
                )
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            SettingsSection(title = "Auto-Drafting") {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text("Enable Auto-Draft", color = Color.White, fontSize = 16.sp)
                        Text("Automatically ban/pick your favorites", color = Color.White.copy(alpha = 0.5f), fontSize = 12.sp)
                    }
                    Switch(
                        checked = settings.enabled,
                        onCheckedChange = onToggleAutoDraft,
                        colors = SwitchDefaults.colors(
                            checkedThumbColor = LeagueGold,
                            checkedTrackColor = LeagueGold.copy(alpha = 0.5f)
                        )
                    )
                }
            }

            SettingsSection(title = "Preferences") {
                PreferenceItem(
                    label = "Auto-Ban Champion",
                    value = settings.autoBanChampionId ?: "None",
                    onClick = { /* Open selection dialog */ }
                )
                Spacer(modifier = Modifier.height(16.dp))
                PreferenceItem(
                    label = "Auto-Pick Champion",
                    value = settings.autoPickChampionId ?: "None",
                    onClick = { /* Open selection dialog */ }
                )
            }
        }
    }
}

@Composable
fun SettingsSection(title: String, content: @Composable () -> Unit) {
    Column {
        Text(
            text = title.uppercase(),
            color = LeagueGold,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 8.dp)
        )
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(SurfaceGlass)
                .border(1.dp, Color.White.copy(alpha = 0.1f), RoundedCornerShape(16.dp))
                .padding(16.dp)
        ) {
            content()
        }
    }
}

@Composable
fun PreferenceItem(label: String, value: String, onClick: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, color = Color.White, fontSize = 16.sp)
        Text(
            text = value,
            color = LeagueBlue,
            fontSize = 16.sp,
            modifier = Modifier.clickable { onClick() }
        )
    }
}
