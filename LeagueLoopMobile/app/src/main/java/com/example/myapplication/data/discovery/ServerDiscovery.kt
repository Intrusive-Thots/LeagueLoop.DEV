package com.example.myapplication.data.discovery

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import android.util.Log

data class DiscoveredServer(
    val name: String,
    val ipAddress: String,
    val port: Int
)

class ServerDiscovery(private val discoveryPort: Int = 8888) {
    private val TAG = "ServerDiscovery"

    fun discover(): Flow<DiscoveredServer> = flow {
        Log.d(TAG, "Starting discovery on port $discoveryPort")
        val socket = try {
            DatagramSocket(discoveryPort).apply {
                broadcast = true
                soTimeout = 5000 // 5 seconds timeout to allow checking for cancellation
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to open socket", e)
            return@flow
        }

        val buffer = ByteArray(1024)

        try {
            while (true) {
                val packet = DatagramPacket(buffer, buffer.size)
                try {
                    socket.receive(packet)
                    val message = String(packet.data, 0, packet.length)
                    Log.d(TAG, "Received packet from ${packet.address.hostAddress}: $message")
                    
                    // Expecting a format like "LeagueLoopClient:ServerName:Port"
                    if (message.startsWith("LeagueLoopClient")) {
                        val parts = message.split(":")
                        if (parts.size >= 3) {
                            emit(
                                DiscoveredServer(
                                    name = parts[1],
                                    ipAddress = packet.address.hostAddress,
                                    port = parts[2].toIntOrNull() ?: 8080
                                )
                            )
                        }
                    }
                } catch (e: java.net.SocketTimeoutException) {
                    // Timeout is fine, just loop and check if coroutine is still active
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Discovery error", e)
        } finally {
            socket.close()
            Log.d(TAG, "Discovery socket closed")
        }
    }.flowOn(Dispatchers.IO)
}
