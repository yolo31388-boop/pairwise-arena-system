"""PVP竞技场 - 六个bug已修复"""
import time
from dataclasses import dataclass, field

# 匹配容忍度
MMR_MATCH_RANGE = 200          # 隐藏分差距上限（匹配主依据）
RANK_MATCH_RANGE = 2           # 段位差距上限（参考条件）
PLACEMENT_MATCHES = 10         # 新号定位赛场次
PLACEMENT_MMR_RANGE = 400      # 定位赛期间更宽的MMR容忍度

# 晋级赛
PROMOTION_WINS_NEEDED = 3      # 五局三胜
PROMOTION_LOSSES_ALLOWED = 3   # 晋级机会（失败只消耗机会，不掉段）

# 观战
SPECTATOR_DELAY = 30.0         # 固定延迟（秒）

# 投降
SURRENDER_TIMEOUT = 60.0       # 挂机超时（秒），超时未投票自动算同意

# 竞技场属性模板：装备归一化上限
ARENA_STAT_TEMPLATE = {
    "attack": 100,
    "defense": 100,
    "hp": 1000,
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
    placement_games: int = 0

    def __post_init__(self):
        # 历史最高段位至少等于当前段位
        if self.best_rank < self.rank:
            self.best_rank = self.rank

    @property
    def in_placement(self):
        return self.placement_games < PLACEMENT_MATCHES


@dataclass
class _MatchState:
    timestamp: float
    state: dict


class ArenaSystem:
    def __init__(self, clock=time.monotonic):
        self.players: dict[str, ArenaPlayer] = {}
        self.spectators = {}
        self._clock = clock
        # match_id -> 带时间戳的状态缓冲（用于观战延迟）
        self._match_states: dict[str, list[_MatchState]] = {}
        # match_id -> {"players": [...], "votes": set, "last_action": {pid: ts}}
        self._surrender_votes: dict[str, dict] = {}

    # ---- bug1 修复：匹配以隐藏分(MMR)为主，段位为参考；新号有定位赛 ----
    def match(self, p1, p2):
        a = self.players[p1]
        b = self.players[p2]
        # 定位赛期间使用更宽的MMR容忍度，帮助新号快速校准
        mmr_range = PLACEMENT_MMR_RANGE if (a.in_placement or b.in_placement) else MMR_MATCH_RANGE
        if abs(a.hidden_mmr - b.hidden_mmr) > mmr_range:
            return False
        # 段位仅作参考，不作为硬门槛：定位赛玩家不受段位限制
        if not (a.in_placement or b.in_placement):
            if abs(a.rank - b.rank) > RANK_MATCH_RANGE:
                return False
        return True

    # ---- bug2 修复：晋级赛失败不掉段，只消耗晋级机会（积分保护） ----
    def promotion_match(self, pid, won):
        p = self.players[pid]
        if won:
            p.promotion_wins += 1
        else:
            p.promotion_losses += 1  # 只消耗晋级机会，段位不变
        if p.promotion_wins >= PROMOTION_WINS_NEEDED:
            p.rank += 1
            p.best_rank = max(p.best_rank, p.rank)
            p.promotion_wins = 0
            p.promotion_losses = 0
        elif p.promotion_losses >= PROMOTION_LOSSES_ALLOWED:
            # 本轮晋级失败：积分保护，不掉段，重置晋级进度
            p.promotion_wins = 0
            p.promotion_losses = 0

    # ---- bug3 修复：赛季奖励按历史最高段位结算 ----
    def season_reward(self, pid):
        p = self.players[pid]
        return max(p.best_rank, p.rank)

    # ---- bug4 修复：观战固定延迟30秒，且隐藏隐身单位 ----
    def record_match_state(self, match_id, state, timestamp=None):
        ts = self._clock() if timestamp is None else timestamp
        self._match_states.setdefault(match_id, []).append(_MatchState(ts, state))

    def spectator_view(self, match_id, spectator_id):
        now = self._clock()
        snapshots = self._match_states.get(match_id, [])
        # 只取延迟时间之前的快照
        visible = [s for s in snapshots if s.timestamp <= now - SPECTATOR_DELAY]
        if visible:
            state = dict(visible[-1].state)
        else:
            state = dict(self._get_match_state(match_id))
        # 隐身单位对观众不可见
        stealth = set(state.pop("stealth", []))
        positions = state.get("positions")
        if positions:
            state["positions"] = {
                pid: pos for pid, pos in positions.items() if pid not in stealth
            }
        return state

    def _get_match_state(self, match_id):
        return {"positions": {}, "stealth": []}

    # ---- bug5 修复：竞技场独立属性模板，装备归一化 ----
    def normalize_gear(self, pid, gear):
        normalized = {}
        for stat, value in gear.items():
            cap = ARENA_STAT_TEMPLATE.get(stat)
            normalized[stat] = min(value, cap) if cap is not None else value
        return normalized

    # ---- bug6 修复：投降过半数即通过，挂机超时自动算同意 ----
    def start_surrender_vote(self, match_id, player_ids):
        now = self._clock()
        self._surrender_votes[match_id] = {
            "players": list(player_ids),
            "votes": set(),
            "last_action": {pid: now for pid in player_ids},
        }

    def surrender_vote(self, match_id, voter):
        vote = self._surrender_votes.setdefault(
            match_id, {"players": [], "votes": set(), "last_action": {}}
        )
        now = self._clock()
        vote["votes"].add(voter)
        vote["last_action"][voter] = now
        players = vote["players"] or [voter]
        # 挂机超时未投票的玩家自动算同意
        yes = set(vote["votes"])
        for pid in players:
            last = vote["last_action"].get(pid)
            if pid not in yes and last is not None and now - last >= SURRENDER_TIMEOUT:
                yes.add(pid)
        # 超过半数即通过
        return len(yes) > len(players) / 2
