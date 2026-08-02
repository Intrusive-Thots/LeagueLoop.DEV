package com.example.myapplication.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.myapplication.data.network.AutoDraftSettings
import com.example.myapplication.data.network.SocketClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class SettingsViewModel(private val socketClient: SocketClient) : ViewModel() {
    private val _settings = MutableStateFlow(AutoDraftSettings())
    val settings: StateFlow<AutoDraftSettings> = _settings.asStateFlow()

    fun updateAutoBan(championId: String?) {
        _settings.value = _settings.value.copy(autoBanChampionId = championId)
        syncSettings()
    }

    fun updateAutoPick(championId: String?) {
        _settings.value = _settings.value.copy(autoPickChampionId = championId)
        syncSettings()
    }

    fun toggleEnabled(enabled: Boolean) {
        _settings.value = _settings.value.copy(enabled = enabled)
        syncSettings()
    }

    private fun syncSettings() {
        // In a real app, this might save to DataStore or send to server
        // For this task, we'll assume the server handles it via ACTION
    }
}
