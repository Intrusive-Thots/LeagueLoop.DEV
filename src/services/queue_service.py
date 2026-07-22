"""
Queue Service
Manages queue searches, game lobbies, matchmaking queue timers, and queue control actions (join, cancel, dodge, play again).
"""
import threading
import time
from core.events import EventBus
from utils.logger import Logger

class QueueService:
    def __init__(self, settings_service=None, league_service=None):
        self._settings = settings_service
        self._league = league_service
        
        self.current_phase = "None"
        self._current_queue_time = 0
        self._estimated_queue_time = 120
        self.is_searching = False
        
        self._timer_thread = None
        self._timer_stop_event = threading.Event()
        
        # Subscribe to LCU connection / state / phase events
        EventBus.on("game_phase_changed", self._on_phase_changed)
        EventBus.on("lcu_connected", self._on_lcu_connected)
        EventBus.on("queue_event", self._on_queue_event)

    def _on_lcu_connected(self, connected: bool):
        if not connected:
            self._stop_timer()
            self.current_phase = "None"
            self._current_queue_time = 0
            self.is_searching = False
            EventBus.emit("queue_state_changed")

    def _on_phase_changed(self, phase: str):
        self.current_phase = phase
        if phase != "Matchmaking":
            self._stop_timer()
        EventBus.emit("queue_state_changed")

    def _on_queue_event(self, search_state):
        if not search_state:
            self._stop_timer()
            return
        
        search_status = search_state.get("searchState")
        if search_status == "Searching":
            time_in_queue = search_state.get("timeInQueue", 0)
            estimated_time = search_state.get("estimatedQueueTime", 0)
            self._start_timer(time_in_queue, estimated_time)
        else:
            self._stop_timer()
        EventBus.emit("queue_state_changed")

    def _start_timer(self, start_time, estimated_time):
        self._estimated_queue_time = estimated_time if estimated_time > 0 else 120
        self._current_queue_time = start_time
        
        # Avoid duplicating timer threads
        if not self.is_searching:
            self.is_searching = True
            self._timer_stop_event.clear()
            self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
            self._timer_thread.start()

    def _stop_timer(self):
        if self.is_searching:
            self.is_searching = False
            self._timer_stop_event.set()

    def _timer_loop(self):
        while self.is_searching and not self._timer_stop_event.is_set():
            time.sleep(1.0)
            if self._timer_stop_event.is_set():
                break
            self._current_queue_time += 1
            EventBus.emit("queue_timer_tick", self._current_queue_time, self._estimated_queue_time)

    def get_queue_time(self) -> int:
        return self._current_queue_time if self.is_searching else 0

    def get_estimated_time(self) -> int:
        return self._estimated_queue_time

    def _get_queue_id_for_mode(self, mode: str) -> int:
        mode_map = {
            "ARAM": 450,
            "ARAM Mayhem": 2400,
            "Ranked Solo/Duo": 420,
            "Ranked Flex": 440,
            "Draft Pick": 400,
            "Quickplay": 490,
            "Arena": 1700,
            "TFT Normal": 1090,
            "TFT Ranked": 1100,
            "TFT Hyper Roll": 1130,
            "TFT Double Up": 1160,
            "Co-op vs. AI": 850,
        }
        return mode_map.get(mode, 450)

    def find_match(self) -> bool:
        """Triggers matchmaking search based on the configured aram/game mode."""
        if not self._league or not self._league.is_connected:
            return False
        
        mode = self._settings.get("aram_mode", "ARAM") if self._settings else "ARAM"
        Logger.info("QueueService", f"Initiating {mode} matchmaking search...")
        
        try:
            # Check search state first
            state_req = self._league.request("GET", "/lol-lobby/v2/lobby/matchmaking/search-state")
            state_data = state_req.json() if state_req and state_req.status_code == 200 else {}
            
            if state_data.get("searchState") == "Searching":
                # Toggle search state: cancel it
                self.cancel_matchmaking()
                return True

            target_q_id = self._get_queue_id_for_mode(mode)
            lobby_req = self._league.request("GET", "/lol-lobby/v2/lobby")
            in_lobby = lobby_req and lobby_req.status_code == 200
            should_create = True

            if in_lobby:
                try:
                    data = lobby_req.json()
                    current_q = data.get("gameConfig", {}).get("queueId")
                    if current_q == target_q_id:
                        should_create = False
                    else:
                        self._league.request("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")
                        time.sleep(0.5)
                        self._league.request("DELETE", "/lol-lobby/v2/lobby")
                        time.sleep(0.5)
                except Exception:
                    should_create = True

            if should_create:
                self._league.request("POST", "/lol-lobby/v2/lobby", {"queueId": target_q_id})
                time.sleep(1.0)

            res = self._league.request("POST", "/lol-lobby/v2/lobby/matchmaking/search")
            if res and res.status_code in [200, 204]:
                Logger.info("QueueService", f"Successfully started search for: {mode}")
                return True
            else:
                Logger.error("QueueService", f"Failed starting search: status {res.status_code if res else 'No response'}")
                return False
        except Exception as e:
            Logger.error("QueueService", f"Error initiating matchmaking: {e}")
            return False

    def cancel_matchmaking(self) -> bool:
        """Cancels any active matchmaking search."""
        if not self._league or not self._league.is_connected:
            return False
        try:
            res = self._league.request("DELETE", "/lol-lobby/v2/lobby/matchmaking/search")
            if res and res.status_code in [200, 204]:
                Logger.info("QueueService", "Matchmaking cancelled.")
                return True
            return False
        except Exception as e:
            Logger.error("QueueService", f"Error cancelling matchmaking: {e}")
            return False

    def force_dodge(self):
        """Dodges queue by quitting LCU process control."""
        if not self._league or not self._league.is_connected:
            return False, "League Client disconnected."
        try:
            res = self._league.request("POST", "/process-control/v1/process/quit")
            if res and res.status_code in [200, 204]:
                Logger.info("QueueService", "Force quit sent to LCU.")
                return True, "Dodged Lobby cleanly."
            return False, f"LCU returned status {res.status_code if res else 'No response'}"
        except Exception as e:
            Logger.error("QueueService", f"Error force dodging: {e}")
            return False, str(e)

    def play_again(self) -> bool:
        """Requests play again lobby recreation."""
        if not self._league or not self._league.is_connected:
            return False
        try:
            res = self._league.request("POST", "/lol-lobby/v2/play-again")
            if res and res.status_code in [200, 204]:
                Logger.info("QueueService", "Play again request sent.")
                return True
            return False
        except Exception as e:
            Logger.error("QueueService", f"Error on play again: {e}")
            return False

    def requeue(self):
        """Triggers play again and restarts matchmaking search."""
        if not self._league or not self._league.is_connected:
            return False, "League Client disconnected."
        try:
            self.play_again()
            time.sleep(0.5)
            success = self.find_match()
            if success:
                return True, "Requeued match successfully."
            return False, "Failed to start matchmaking search."
        except Exception as e:
            Logger.error("QueueService", f"Error on requeue: {e}")
            return False, str(e)

    def create_lobby(self, mode: str) -> bool:
        """Creates a lobby with the specified mode/queue ID."""
        if not self._league or not self._league.is_connected:
            return False
        try:
            target_q_id = self._get_queue_id_for_mode(mode)
            res = self._league.request("POST", "/lol-lobby/v2/lobby", {"queueId": target_q_id})
            return res is not None and res.status_code in [200, 204]
        except Exception as e:
            Logger.error("QueueService", f"Error creating lobby: {e}")
            return False

    def leave_lobby(self) -> bool:
        """Deletes/leaves the current lobby."""
        if not self._league or not self._league.is_connected:
            return False
        try:
            res = self._league.request("DELETE", "/lol-lobby/v2/lobby")
            return res is not None and res.status_code in [200, 204]
        except Exception as e:
            Logger.error("QueueService", f"Error leaving lobby: {e}")
            return False

# Global singleton
_instance = None

def get_queue_service(settings_service=None, league_service=None) -> QueueService:
    global _instance
    if _instance is None:
        _instance = QueueService(settings_service, league_service)
    return _instance
