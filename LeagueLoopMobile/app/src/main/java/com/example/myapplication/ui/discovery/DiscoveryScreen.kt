package com.example.myapplication.ui.discovery

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.myapplication.data.discovery.DiscoveredServer
import com.example.myapplication.ui.theme.LeagueBlue
import com.example.myapplication.ui.theme.LeagueGold

@Composable
fun DiscoveryScreen(
    servers: List<DiscoveredServer>,
    onConnect: (DiscoveredServer) -> Unit,
    modifier: Modifier = Modifier
) {
    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = Color.Transparent
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        colors = listOf(
                            Color(0xFF0A0A0C),
                            Color(0xFF1A1A1E)
                        )
                    )
                )
                .padding(innerPadding)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Spacer(modifier = Modifier.height(32.dp))
                
                Text(
                    text = "LeagueLoop",
                    fontSize = 32.sp,
                    fontWeight = FontWeight.Bold,
                    color = LeagueGold,
                    modifier = Modifier.padding(bottom = 8.dp)
                )
                Text(
                    text = "Desktop Client Discovery",
                    fontSize = 18.sp,
                    color = Color.White.copy(alpha = 0.7f),
                    modifier = Modifier.padding(bottom = 32.dp)
                )

                if (servers.isEmpty()) {
                    Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator(color = LeagueBlue)
                            Text(
                                text = "Searching for clients...",
                                color = Color.White.copy(alpha = 0.5f),
                                modifier = Modifier.padding(top = 16.dp)
                            )
                        }
                    }
                } else {
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                        modifier = Modifier.fillMaxWidth().weight(1f)
                    ) {
                        items(servers) { server ->
                            GlassCard(server, onConnect)
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun GlassCard(
    server: DiscoveredServer,
    onConnect: (DiscoveredServer) -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(Color.White.copy(alpha = 0.05f))
            .padding(1.dp)
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        Color.White.copy(alpha = 0.1f),
                        Color.White.copy(alpha = 0.02f)
                    )
                ),
                shape = RoundedCornerShape(16.dp)
            )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp)
        ) {
            Text(
                text = server.name,
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
            Text(
                text = "${server.ipAddress}:${server.port}",
                fontSize = 14.sp,
                color = LeagueBlue
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Button(
                onClick = { onConnect(server) },
                colors = ButtonDefaults.buttonColors(
                    containerColor = LeagueBlue.copy(alpha = 0.8f)
                ),
                modifier = Modifier.align(Alignment.End)
            ) {
                Text("Connect")
            }
        }
    }
}
