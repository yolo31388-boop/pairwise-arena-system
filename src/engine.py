"""PVP竞技场 - 带6个bug"""
from dataclasses import dataclass, field

@dataclass
class ArenaPlayer:
    pid: str
    rank: int
    hidden_mmr: int = 1500
    promotion_wins: int = 0
    promotion_losses: int = 0
    best_rank: int = 0

class ArenaSystem:
    def __init__(self):
        self.players: dict[str, ArenaPlayer] = {}
        self.spectators = {}

    def match(self, p1, p2):
        # bug1: 只看段位
        a = self.players[p1]
        b = self.players[p2]
        return abs(a.rank - b.rank) <= 2

    def promotion_match(self, pid, won):
        p = self.players[pid]
        if won:
            p.promotion_wins += 1
        else:
            p.promotion_losses += 1
            p.rank -= 1  # bug2: 晋级赛失败掉段
        if p.promotion_wins >= 3:
            p.rank += 1
            p.promotion_wins = 0
            p.promotion_losses = 0

    def season_reward(self, pid):
        p = self.players[pid]
        # bug3: 按最终段位
        return p.rank

    def spectator_view(self, match_id, spectator_id):
        # bug4: 无延迟
        return self._get_match_state(match_id)

    def _get_match_state(self, match_id):
        return {"positions": {}, "stealth": []}

    def normalize_gear(self, pid, gear):
        # bug5: 不归一化
        return gear

    def surrender_vote(self, match_id, voter):
        # bug6: 需要全员
        return False
