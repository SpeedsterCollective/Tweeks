import threading
import time

try:
    from pypresence import Presence
except ImportError:
    Presence = None


class DiscordRPC:
    def __init__(self, client_id: str = "1416567503030718555"):
        self.client_id = client_id
        self._rpc = None
        self._connected = False
        self._lock = threading.Lock()
        self._update_thread = None
        self._running = False
        self._state = {}
        self._games = []
        self._game_idx = 0
        self._available = Presence is not None

    def _ensure_connected(self):
        if not self._available:
            print("[DiscordRPC] pypresence not installed.")
            return False
        with self._lock:
            if self._connected:
                return True
            try:
                self._rpc = Presence(self.client_id)
                self._rpc.connect()
                self._connected = True
                print("[DiscordRPC] Connected to Discord RPC.")
                return True
            except Exception as e:
                print(f"[DiscordRPC] Failed to connect: {e}")
                self._connected = False
                self._rpc = None
                return False

    def _compose_state_for_game(self, game_name: str, overrides=None):
        base = {
            "details": f"Playing {game_name}",
            "state": "In-game",
            "large_image": "default",
            "large_text": game_name,
        }
        if overrides:
            base.update({k: v for k, v in overrides.items() if v is not None})
        return base

    def start_for_games(self, game_names):
        if not self._available:
            return False
        if not game_names:
            return False

        if not self._ensure_connected():
            return False

        with self._lock:
            normalized = []
            seen = set()

            if isinstance(game_names, dict):
                for name, state in game_names.items():
                    if name and name not in seen:
                        seen.add(name)
                        normalized.append({"name": name, "state": state or None})
            else:
                for item in game_names:
                    if isinstance(item, str):
                        name, state = item, None
                    elif isinstance(item, dict):
                        if "name" in item:
                            name, state = item["name"], item.get("state")
                        else:
                            pairs = list(item.items())
                            if not pairs:
                                continue
                            name, state = pairs[0]
                    else:
                        continue
                    if name and name not in seen:
                        seen.add(name)
                        normalized.append({"name": name, "state": state or None})

            if not normalized:
                return False

            self._games = normalized
            self._game_idx = 0
            current = self._games[self._game_idx]
            self._state = self._compose_state_for_game(current["name"], current.get("state"))

            try:
                self._rpc.update(**self._state)
                print(f"[DiscordRPC] Initial presence set: {self._state}")
            except Exception as e:
                print(f"[DiscordRPC] Failed to update presence: {e}")
                return False

            if not self._running:
                self._running = True
                self._update_thread = threading.Thread(target=self._refresh_loop, daemon=True)
                self._update_thread.start()
        return True

    def _refresh_loop(self):
        while True:
            time.sleep(15)
            with self._lock:
                if not self._running or not self._connected or not self._rpc:
                    break
                if self._games:
                    item = self._games[self._game_idx % len(self._games)]
                    name = item.get("name")
                    overrides = item.get("state")
                    self._state = self._compose_state_for_game(name, overrides)
                    self._game_idx = (self._game_idx + 1) % len(self._games)
                try:
                    self._rpc.update(**self._state)
                    print(f"[DiscordRPC] Updated presence: {self._state}")
                except Exception as e:
                    print(f"[DiscordRPC] Lost connection: {e}")
                    self._connected = False
                    break


rpc = DiscordRPC()
rpc.start_for_games([
    {"name": "Speedster Tweaks", "state": {
        "details": "Corporate Clash • Playground",
        "state": "Picking a map",
        "large_image": "sst",
        "large_text": "Speedster Tweaks v0.0.1",
        "small_image": "clash",
        "small_text": "ToonTown:Corporate Clash",
        "buttons": [{"label": "Join", "url": "https://..."}]
    }},
    {"name": "Speedster Tweaks", "state": {
        "details": "In the Playground",
        "large_image": "sst",
        "small_image": "ttrnew",
    }},
])
