"""PVP竞技场 - 6个bug已修复"""
import time
from collections import deque
from dataclasses import dataclass, field

# 匹配以隐藏分(MMR)为主, 段位仅作参考的宽松约束
MMR_MATCH_WINDOW = 200          # 隐藏分匹配窗口
PLACEMENT_MATCH_WINDOW = 400    # 定位赛期间更宽的窗口
RANK_REFERENCE_WINDOW = 5       # 段位参考上限(宽松)
PLACEMENT_MATCHES = 10          # 新号定位赛场次

# 晋级赛: 五局三胜, 失败不掉段, 只消耗晋级机会并有积分保护
PROMOTION_WINS_NEEDED = 3
PROMOTION_LOSES_ALLOWED = 3
PROMOTION_CHANCES = 3           # 每个段位的晋级机会数
POINT_PROTECTION_GAMES = 2      # 晋级失败后保护的场数

# 观战延迟与隐身保护
SPECTATOR_DELAY_SECONDS = 30

# 投降: 超过半数通过, 挂机超时自动算同意
SURRENDER_RATIO = 0.5
AFK_TIMEOUT_SECONDS = 300

# 竞技场独立属性模板: 装备属性归一化上限
ARENA_STAT_TEMPLATE = {
    "attack": 100,
    "defense": 100,
    "hp": 5000,
    "crit": 50,
    "speed": 100,
}


@dataclass
class ArenaPlayer:
    pid: str
    rank: int
    hidden_mmr: int = 1500
    promotion_wins: int = 0
    promotion_losses: int = 0
    best_rank: int = 0
    placement_remaining: int = PLACEMENT_MATCHES
    promotion_chances: int = PROMOTION_CHANCES
    point_protection: int = 0

    def __post_init__(self):
        # 历史最高段位至少为当前段位
        self.best_rank = max(self.best_rank, self.rank)


class ArenaSystem:
    def __init__(self):
        self.players: dict[str, ArenaPlayer] = {}
        self.spectators = {}
        self._match_history: dict[str, deque] = {}
        self._surrender_votes: dict[str, dict] = {}

    # bug1 修复: 匹配以隐藏分为主, 段位为参考; 定位赛期间窗口更宽
    def match(self, p1, p2):
        a = self.players[p1]
        b = self.players[p2]
        in_placement = a.placement_remaining > 0 or b.placement_remaining > 0
        window = PLACEMENT_MATCH_WINDOW if in_placement else MMR_MATCH_WINDOW
        if abs(a.hidden_mmr - b.hidden_mmr) > window:
            return False
        return abs(a.rank - b.rank) <= RANK_REFERENCE_WINDOW

    def record_match_result(self, pid, won):
        """普通排位结算: 更新隐藏分, 定位赛场次递减"""
        p = self.players[pid]
        p.hidden_mmr += 25 if won else -25
        if p.placement_remaining > 0:
            p.placement_remaining -= 1

    # bug2 修复: 晋级赛失败不掉段, 只消耗晋级机会, 并给积分保护
    def promotion_match(self, pid, won):
        p = self.players[pid]
        if won:
            p.promotion_wins += 1
        else:
            p.promotion_losses += 1
        if p.promotion_wins >= PROMOTION_WINS_NEEDED:
            p.rank += 1
            p.best_rank = max(p.best_rank, p.rank)
            self._reset_promotion(p)
            p.promotion_chances = PROMOTION_CHANCES
        elif p.promotion_losses >= PROMOTION_LOSES_ALLOWED:
            # 晋级失败: 段位不变, 消耗一次机会, 获得积分保护
            p.promotion_chances = max(0, p.promotion_chances - 1)
            p.point_protection = POINT_PROTECTION_GAMES
            self._reset_promotion(p)

    def _reset_promotion(self, p):
        p.promotion_wins = 0
        p.promotion_losses = 0

    def lose_ranked_game(self, pid):
        """普通排位失败掉段, 积分保护期间不掉"""
        p = self.players[pid]
        if p.point_protection > 0:
            p.point_protection -= 1
            return
        p.rank = max(0, p.rank - 1)

    # bug3 修复: 赛季奖励按历史最高段位结算
    def season_reward(self, pid):
        p = self.players[pid]
        return max(p.best_rank, p.rank)

    # bug4 修复: 观战有固定延迟, 且隐身单位不可见
    def record_match_state(self, match_id, state, now=None):
        now = time.time() if now is None else now
        history = self._match_history.setdefault(match_id, deque())
        history.append((now, state))
        cutoff = now - SPECTATOR_DELAY_SECONDS * 4
        while history and history[0][0] < cutoff:
            history.popleft()

    def spectator_view(self, match_id, spectator_id, now=None):
        now = time.time() if now is None else now
        history = self._match_history.get(match_id)
        if not history:
            return {"positions": {}, "stealth": []}
        target = now - SPECTATOR_DELAY_SECONDS
        delayed = None
        for ts, state in history:
            if ts <= target:
                delayed = state
            else:
                break
        if delayed is None:
            delayed = history[0][1]
        return self._hide_stealth(delayed)

    def _hide_stealth(self, state):
        view = dict(state)
        stealth = set(view.get("stealth", []))
        positions = view.get("positions", {})
        view["positions"] = {
            pid: pos for pid, pos in positions.items() if pid not in stealth
        }
        view["stealth"] = []
        return view

    def _get_match_state(self, match_id):
        history = self._match_history.get(match_id)
        if history:
            return history[-1][1]
        return {"positions": {}, "stealth": []}

    # bug5 修复: 装备属性按竞技场模板归一化
    def normalize_gear(self, pid, gear):
        normalized = dict(gear)
        for stat, cap in ARENA_STAT_TEMPLATE.items():
            if stat in normalized:
                normalized[stat] = min(normalized[stat], cap)
        return normalized

    # bug6 修复: 投降超过半数即通过, 挂机超时自动算同意
    def surrender_vote(self, match_id, voter, now=None):
        now = time.time() if now is None else now
        vote = self._surrender_votes.setdefault(
            match_id, {"voters": set(), "players": set(), "last_active": {}}
        )
        vote["players"].add(voter)
        vote["voters"].add(voter)
        vote["last_active"][voter] = now
        yes = len(vote["voters"])
        for pid, last in vote["last_active"].items():
            if pid not in vote["voters"] and now - last >= AFK_TIMEOUT_SECONDS:
                yes += 1  # 挂机超时自动算同意
        total = max(len(vote["players"]), 1)
        return yes > total * SURRENDER_RATIO

    def register_match_players(self, match_id, pids, now=None):
        now = time.time() if now is None else now
        vote = self._surrender_votes.setdefault(
            match_id, {"voters": set(), "players": set(), "last_active": {}}
        )
        for pid in pids:
            vote["players"].add(pid)
            vote["last_active"].setdefault(pid, now)
