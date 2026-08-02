package com.example.myapplication.data.network

import android.util.Log
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

class SocketClient(private val okHttpClient: OkHttpClient) {
    private val TAG = "SocketClient"
    private var webSocket: WebSocket? = null
    
    private val moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()
    private val adapter = moshi.adapter(SocketMessage::class.java)

    private val _messages = MutableSharedFlow<SocketMessage>(
        extraBufferCapacity = 10,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    val messages: SharedFlow<SocketMessage> = _messages.asSharedFlow()

    private val _connectionState = MutableSharedFlow<Boolean>(
        replay = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    val connectionState: SharedFlow<Boolean> = _connectionState.asSharedFlow()

    fun connect(ip: String, port: Int) {
        val url = "ws://$ip:$port/ws" // Assuming /ws endpoint
        Log.d(TAG, "Connecting to $url")
        
        val request = Request.Builder()
            .url(url)
            .build()
            
        webSocket = okHttpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "WebSocket Opened")
                _connectionState.tryEmit(true)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d(TAG, "Received message: $text")
                try {
                    adapter.fromJson(text)?.let {
                        _messages.tryEmit(it)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to parse message", e)
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket Closing: $code / $reason")
                _connectionState.tryEmit(false)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket Failure", t)
                _connectionState.tryEmit(false)
            }
            
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket Closed")
                _connectionState.tryEmit(false)
            }
        })
    }

    fun sendAction(action: String) {
        val message = SocketMessage(
            type = MessageTypes.ACTION,
            payload = mapOf("action" to action)
        )
        val json = adapter.toJson(message)
        Log.d(TAG, "Sending action: $json")
        webSocket?.send(json)
    }

    fun disconnect() {
        webSocket?.close(1000, "User disconnected")
        webSocket = null
    }
}
