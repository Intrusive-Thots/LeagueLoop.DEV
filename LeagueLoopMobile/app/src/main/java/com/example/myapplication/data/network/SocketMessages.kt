package com.example.myapplication.data.network

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class SocketMessage(
    val type: String,
    val payload: Map<String, Any>? = null
)

object MessageTypes {
    const val MATCH_FOUND = "MATCH_FOUND"
    const val DRAFT_UPDATE = "DRAFT_UPDATE"
    const val RUNE_UPDATE = "RUNE_UPDATE"
    const val ACTION = "ACTION"
}

object ActionValues {
    const val ACCEPT = "ACCEPT"
    const val DECLINE = "DECLINE"
    const val PICK = "PICK"
    const val BAN = "BAN"
    const val UPDATE_RUNES = "UPDATE_RUNES"
    const val UPDATE_SETTINGS = "UPDATE_SETTINGS"
}

@JsonClass(generateAdapter = true)
data class DraftState(
    val isMyTurn: Boolean,
    val currentAction: String, // "PICK" or "BAN"
    val teamPicks: List<ChampionAction>,
    val teamBans: List<ChampionAction>,
    val enemyPicks: List<ChampionAction>,
    val enemyBans: List<ChampionAction>,
    val availableChampions: List<Champion>
)

@JsonClass(generateAdapter = true)
data class ChampionAction(
    val championId: String?,
    val playerName: String,
    val isLocked: Boolean
)

@JsonClass(generateAdapter = true)
data class Champion(
    val id: String,
    val name: String,
    val imageUrl: String,
    val tags: List<String>
)

@JsonClass(generateAdapter = true)
data class RunePage(
    val id: String,
    val name: String,
    val primaryPathId: String,
    val subPathId: String,
    val selectedRunes: List<String>
)

@JsonClass(generateAdapter = true)
data class AutoDraftSettings(
    val autoBanChampionId: String? = null,
    val autoPickChampionId: String? = null,
    val enabled: Boolean = false
)
