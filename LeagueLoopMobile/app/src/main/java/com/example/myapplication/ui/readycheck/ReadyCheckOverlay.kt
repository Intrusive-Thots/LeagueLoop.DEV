package com.example.myapplication.ui.readycheck

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.myapplication.ui.theme.LeagueGold
import com.example.myapplication.ui.theme.SurfaceGlass
import kotlinx.coroutines.delay

@Composable
fun ReadyCheckOverlay(
    state: ReadyCheckState,
    onAccept: () -> Unit,
    onDecline: () -> Unit
) {
    AnimatedVisibility(
        visible = state is ReadyCheckState.MatchFound,
        enter = fadeIn() + scaleIn(),
        exit = fadeOut() + scaleOut()
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.5f)),
            contentAlignment = Alignment.Center
        ) {
            if (state is ReadyCheckState.MatchFound) {
                GlassCard(
                    timerSeconds = state.timerSeconds,
                    onAccept = onAccept,
                    onDecline = onDecline
                )
            }
        }
    }
}

@Composable
fun GlassCard(
    timerSeconds: Int,
    onAccept: () -> Unit,
    onDecline: () -> Unit
) {
    var timeLeft by remember(timerSeconds) { mutableIntStateOf(timerSeconds) }

    LaunchedEffect(timeLeft) {
        if (timeLeft > 0) {
            delay(1000L)
            timeLeft -= 1
        }
    }

    Box(
        modifier = Modifier
            .padding(24.dp)
            .width(300.dp)
            .clip(RoundedCornerShape(24.dp))
            .background(SurfaceGlass)
            .border(
                width = 1.dp,
                brush = Brush.verticalGradient(
                    colors = listOf(
                        Color.White.copy(alpha = 0.2f),
                        Color.Transparent
                    )
                ),
                shape = RoundedCornerShape(24.dp)
            )
            .padding(24.dp)
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text(
                text = "MATCH FOUND",
                style = MaterialTheme.typography.headlineMedium,
                color = Color.White,
                fontWeight = FontWeight.Bold,
                letterSpacing = 2.sp
            )
            
            val progress = if (timerSeconds > 0) timeLeft.toFloat() / timerSeconds.toFloat() else 0f
            
            CircularProgressIndicator(
                progress = progress,
                modifier = Modifier.size(100.dp),
                color = LeagueGold,
                strokeWidth = 8.dp,
                trackColor = Color.White.copy(alpha = 0.1f)
            )
            
            Text(
                text = "$timeLeft",
                style = MaterialTheme.typography.displaySmall,
                color = Color.White,
                fontWeight = FontWeight.Light
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Button(
                    onClick = onAccept,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = LeagueGold,
                        contentColor = Color.Black
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text("ACCEPT", fontWeight = FontWeight.Bold)
                }
                
                OutlinedButton(
                    onClick = onDecline,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = Color.White
                    ),
                    shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.dp, Color.White.copy(alpha = 0.3f))
                ) {
                    Text("DECLINE")
                }
            }
        }
    }
}
