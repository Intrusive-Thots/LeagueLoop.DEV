import time
import random
import threading

def handle_ready_check(engine, phase):
    if phase != "ReadyCheck":
        if engine._accept_timer:
            engine._accept_timer.cancel()
            engine._accept_timer = None
        engine.ready_check_start = None
        engine.ready_check_delay = None
        engine.ready_check_accepted = False
        engine._last_countdown_log = None
        return

    if not engine.config.get("auto_accept"): return
    if engine._accept_timer or engine.ready_check_accepted: return

    engine.ready_check_start = time.time()
    base_delay = engine.config.get("accept_delay", 2.0)
    delay = base_delay + random.uniform(0.0, 1.5) if base_delay > 0 else 0.0
    engine.ready_check_delay = delay
    
    def _do_accept():
        engine.lcu.request("POST", "/lol-matchmaking/v1/ready-check/accept")
        engine.ready_check_accepted = True
        engine._log("Ready Check Accepted!")
        
    engine._accept_timer = threading.Timer(delay, _do_accept)
    engine._accept_timer.daemon = True
    engine._accept_timer.start()
