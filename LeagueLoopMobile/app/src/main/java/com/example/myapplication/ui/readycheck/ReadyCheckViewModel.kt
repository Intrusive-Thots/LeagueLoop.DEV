package com.example.myapplication.ui.readycheck

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.data.network.ActionValues
import com.example.myapplication.data.network.MessageTypes
import com.example.myapplication.data.network.SocketClient
import com.example.myapplication.data.network.SocketMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch

sealed class ReadyCheckState {
    object Idle : ReadyCheckState()
    data class MatchFound(val timerSeconds: Int) : ReadyCheckState()
    object Accepted : ReadyCheckState()
    object Declined : ReadyCheckState()
}

class ReadyCheckViewModel(private val socketClient: SocketClient) : ViewModel() {
    
    private val _uiState = MutableStateFlow<ReadyCheckState>(ReadyCheckState.Idle)
    val uiState: StateFlow<ReadyCheckState> = _uiState.asStateFlow()

    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected.asStateFlow()

    init {
        viewModelScope.launch {
            socketClient.connectionState.collect {
                _isConnected.value = it
            }
        }

        viewModelScope.launch {
            socketClient.messages.collect { message ->
                handleMessage(message)
            }
        }
    }

    private fun handleMessage(message: SocketMessage) {
        when (message.type) {
            MessageTypes.MATCH_FOUND -> {
                val timer = (message.payload?.get("timer") as? Double)?.toInt() ?: 10
                _uiState.value = ReadyCheckState.MatchFound(timer)
            }
            // Add other message types if needed
        }
    }

    fun acceptMatch() {
        socketClient.sendAction(ActionValues.ACCEPT)
        _uiState.value = ReadyCheckState.Accepted
    }

    fun declineMatch() {
        socketClient.sendAction(ActionValues.DECLINE)
        _uiState.value = ReadyCheckState.Declined
    }
    
    fun resetState() {
        _uiState.value = ReadyCheckState.Idle
    }
    
    fun connect(ip: String, port: Int) {
        socketClient.connect(ip, port)
    }
}
