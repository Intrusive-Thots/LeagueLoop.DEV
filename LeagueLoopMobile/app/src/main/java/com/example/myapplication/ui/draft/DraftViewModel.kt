package com.example.myapplication.ui.draft

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.data.network.*
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed class DraftUiState {
    object Idle : DraftUiState()
    data class Active(val state: DraftState) : DraftUiState()
}

class DraftViewModel(private val socketClient: SocketClient) : ViewModel() {
    private val _uiState = MutableStateFlow<DraftUiState>(DraftUiState.Idle)
    val uiState: StateFlow<DraftUiState> = _uiState.asStateFlow()

    private val moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()
    
    private val draftStateAdapter = moshi.adapter(DraftState::class.java)

    init {
        viewModelScope.launch {
            socketClient.messages.collect { message ->
                when (message.type) {
                    MessageTypes.DRAFT_UPDATE -> {
                        message.payload?.let { payload ->
                            try {
                                val json = moshi.adapter(Map::class.java).toJson(payload)
                                val state = draftStateAdapter.fromJson(json)
                                if (state != null) {
                                    _uiState.value = DraftUiState.Active(state)
                                }
                            } catch (e: Exception) {
                                // Log error
                            }
                        }
                    }
                }
            }
        }
    }

    fun pickChampion(championId: String) {
        socketClient.sendAction(ActionValues.PICK + ":" + championId)
    }

    fun banChampion(championId: String) {
        socketClient.sendAction(ActionValues.BAN + ":" + championId)
    }
}
