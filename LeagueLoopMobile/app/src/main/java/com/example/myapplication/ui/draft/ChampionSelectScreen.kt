package com.example.myapplication.ui.draft

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.example.myapplication.data.network.Champion
import com.example.myapplication.data.network.ChampionAction
import com.example.myapplication.data.network.DraftState
import com.example.myapplication.ui.theme.LeagueBlue
import com.example.myapplication.ui.theme.LeagueGold
import com.example.myapplication.ui.theme.SurfaceGlass

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChampionSelectScreen(
    state: DraftState,
    onPick: (String) -> Unit,
    onBan: (String) -> Unit,
    onOpenSettings: () -> Unit,
    onOpenRunes: () -> Unit
) {
    var searchQuery by remember { mutableStateOf("") }
    
    val filteredChampions = remember(searchQuery, state.availableChampions) {
        state.availableChampions.filter { it.name.contains(searchQuery, ignoreCase = true) }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("CHAMPION SELECT", fontWeight = FontWeight.Bold, letterSpacing = 2.sp) },
                actions = {
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Rounded.Settings, contentDescription = "Settings", color = Color.White)
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
        ) {
            // Bans Section
            BansSection(state.teamBans, state.enemyBans)
            
            Spacer(modifier = Modifier.height(16.dp))
            
            // Drafting Layout
            Row(modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
                // Team Picks (Left)
                Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    state.teamPicks.forEach { action ->
                        PickItem(action, isTeam = true)
                    }
                }
                
                Spacer(modifier = Modifier.width(16.dp))
                
                // Champion Grid (Center)
                Column(modifier = Modifier.weight(3f)) {
                    OutlinedTextField(
                        value = searchQuery,
                        onValueChange = { searchQuery = it },
                        modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp),
                        placeholder = { Text("Search Champions...", color = Color.White.copy(alpha = 0.5f)) },
                        leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, color = Color.White) },
                        shape = RoundedCornerShape(12.dp),
                        colors = TextFieldDefaults.outlinedTextFieldColors(
                            focusedBorderColor = LeagueGold,
                            unfocusedBorderColor = Color.White.copy(alpha = 0.2f),
                            textColor = Color.White
                        )
                    )
                    
                    LazyVerticalGrid(
                        columns = GridCells.Adaptive(80.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.weight(1f)
                    ) {
                        items(filteredChampions) { champion ->
                            ChampionGridItem(champion, onClick = {
                                if (state.isMyTurn) {
                                    if (state.currentAction == "BAN") onBan(champion.id)
                                    else onPick(champion.id)
                                }
                            })
                        }
                    }
                    
                    Button(
                        onClick = onOpenRunes,
                        modifier = Modifier.fillMaxWidth().padding(vertical = 16.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = SurfaceGlass),
                        shape = RoundedCornerShape(12.dp),
                        border = BorderStroke(1.dp, Color.White.copy(alpha = 0.1f))
                    ) {
                        Text("ADJUST RUNES", color = LeagueGold, fontWeight = FontWeight.Bold)
                    }
                }

                Spacer(modifier = Modifier.width(16.dp))

                // Enemy Picks (Right)
                Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    state.enemyPicks.forEach { action ->
                        PickItem(action, isTeam = false)
                    }
                }
            }
        }
    }
}

@Composable
fun BansSection(teamBans: List<ChampionAction>, enemyBans: List<ChampionAction>) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            teamBans.forEach { BanItem(it) }
        }
        Text("BANS", color = Color.White.copy(alpha = 0.5f), fontSize = 12.sp, fontWeight = FontWeight.Bold)
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            enemyBans.forEach { BanItem(it) }
        }
    }
}

@Composable
fun BanItem(action: ChampionAction) {
    Box(
        modifier = Modifier
            .size(32.dp)
            .clip(CircleShape)
            .background(Color.Red.copy(alpha = 0.2f))
            .border(1.dp, Color.Red.copy(alpha = 0.5f), CircleShape)
    ) {
        // Champion Icon would go here
    }
}

@Composable
fun PickItem(action: ChampionAction, isTeam: Boolean) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(80.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(SurfaceGlass)
            .border(
                1.dp,
                if (action.isLocked) LeagueGold.copy(alpha = 0.5f) else Color.White.copy(alpha = 0.1f),
                RoundedCornerShape(12.dp)
            )
    ) {
        Column(modifier = Modifier.padding(8.dp)) {
            Text(
                text = action.playerName,
                color = if (isTeam) LeagueBlue else Color.Red.copy(alpha = 0.7f),
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.weight(1f))
            Text(
                text = action.championId ?: "Selecting...",
                color = Color.White,
                fontSize = 14.sp
            )
        }
    }
}

@Composable
fun ChampionGridItem(champion: Champion, onClick: () -> Unit) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.clickable { onClick() }
    ) {
        Box(
            modifier = Modifier
                .size(64.dp)
                .clip(RoundedCornerShape(8.dp))
                .background(Color.White.copy(alpha = 0.05f))
                .border(1.dp, Color.White.copy(alpha = 0.1f), RoundedCornerShape(8.dp))
        ) {
            AsyncImage(
                model = champion.imageUrl,
                contentDescription = champion.name,
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop
            )
        }
        Text(
            text = champion.name,
            color = Color.White.copy(alpha = 0.7f),
            fontSize = 10.sp,
            modifier = Modifier.padding(top = 4.dp)
        )
    }
}
