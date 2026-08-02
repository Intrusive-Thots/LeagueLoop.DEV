package com.example.myapplication.data.network

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class SocketMessage(
    val type: String,
    val payload: Map<String, Any>? = null
)

object MessageTypes {
    const val MATCH_FOUND = "MATCH_FOUND"
    const val ACTION = "ACTION"
}

object ActionValues {
    const val ACCEPT = "ACCEPT"
    const val DECLINE = "DECLINE"
}
