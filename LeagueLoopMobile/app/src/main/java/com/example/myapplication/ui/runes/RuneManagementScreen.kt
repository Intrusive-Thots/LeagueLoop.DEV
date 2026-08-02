package com.example.myapplication.ui.runes

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ArrowBack
import androidx.compose.material.icons.rounded.CheckCircle
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
import com.example.myapplication.data.network.RunePage
import com.example.myapplication.ui.theme.LeagueBlue
import com.example.myapplication.ui.theme.LeagueGold
import com.example.myapplication.ui.theme.SurfaceGlass

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RuneManagementScreen(
    runePages: List<RunePage>,
    selectedPageId: String,
    onSelectPage: (String) -> Unit,
    onBack: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("RUNE MANAGEMENT", fontWeight = FontWeight.Bold) },
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
                .padding(16.dp)
        ) {
            Text(
                text = "Select a Rune Page to sync with desktop",
                color = Color.White.copy(alpha = 0.7f),
                modifier = Modifier.padding(bottom = 24.dp)
            )

            LazyColumn(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                items(runePages) { page ->
                    RunePageCard(
                        page = page,
                        isSelected = page.id == selectedPageId,
                        onClick = { onSelectPage(page.id) }
                    )
                }
            }
        }
    }
}

@Composable
fun RunePageCard(
    page: RunePage,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(if (isSelected) LeagueGold.copy(alpha = 0.1f) else SurfaceGlass)
            .border(
                1.dp,
                if (isSelected) LeagueGold else Color.White.copy(alpha = 0.1f),
                RoundedCornerShape(16.dp)
            )
            .clickable { onClick() }
            .padding(20.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = page.name,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = if (isSelected) LeagueGold else Color.White
                )
                Text(
                    text = "${page.primaryPathId} + ${page.subPathId}",
                    fontSize = 14.sp,
                    color = Color.White.copy(alpha = 0.5f)
                )
            }
            
            if (isSelected) {
                Icon(
                    Icons.Rounded.CheckCircle,
                    contentDescription = "Selected",
                    tint = LeagueGold,
                    modifier = Modifier.size(32.dp)
                )
            }
        }
    }
}
