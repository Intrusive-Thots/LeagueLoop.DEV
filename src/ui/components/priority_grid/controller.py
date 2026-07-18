from core.constants import SPACING_SM

ICON_SIZE = 40
ICONS_PER_ROW = 4
GRID_GAP = SPACING_SM

_CLEAN_TRANS = str.maketrans("", "", " '.")

class PriorityGridController:
    def __init__(self, config, assets):
        self.config = config
        self.assets = assets
        self.undo_stack = []
        self.known_champions = self._scan_known_champions()
        self.parsed_import = None

    def _scan_known_champions(self):
        known = {}
        if self.assets:
            known = self.assets.get_known_champions()
        self.search_cache = sorted([(v.lower(), v) for v in known.values()], key=lambda x: x[1])
        return known

    def resolve_champion_name(self, raw):
        res = self.known_champions.get(raw)
        if res:
            return res
        normalized = raw.translate(_CLEAN_TRANS).lower()
        return self.known_champions.get(normalized)

    @staticmethod
    def dedup(seq):
        return list(dict.fromkeys(seq))

    def get_priority_list(self):
        raw = self.config.get("priority_picker", {}).get("list", [])
        return self.dedup(raw)

    def save_priority_list(self, lst, record_history=True, on_change=None):
        if record_history:
            current = self.get_priority_list()
            if current != lst:
                self.undo_stack.append(current)
                if len(self.undo_stack) > 10:
                    self.undo_stack.pop(0)

        cfg = self.config.get("priority_picker", {})
        cfg["list"] = self.dedup(lst)
        self.config.set("priority_picker", cfg)

        if on_change:
            on_change()

    def undo_action(self, on_change=None):
        if not self.undo_stack:
            return False
        previous_state = self.undo_stack.pop()
        self.save_priority_list(previous_state, record_history=False, on_change=on_change)
        return True

    def perform_add_search(self, query):
        query = query.strip().lower()
        if not query:
            return []
        matches = []
        for champ_lower, champ in self.search_cache:
            if champ_lower.startswith(query):
                matches.append(champ)
            elif query in champ_lower:
                matches.append(champ)
        unique_matches = list(dict.fromkeys(matches))
        return unique_matches[:3]

    def delete_active(self, selected_indices, on_change=None):
        if not selected_indices:
            return
        names = self.get_priority_list()
        for idx in sorted(list(selected_indices), reverse=True):
            if idx < len(names):
                names.pop(idx)
        self.save_priority_list(names, on_change=on_change)
        selected_indices.clear()
