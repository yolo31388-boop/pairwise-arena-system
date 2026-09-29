"""竞技场测试"""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.engine import ArenaSystem, ArenaPlayer

class TestMatch:
    def test_match_uses_mmr(self):
        asys = ArenaSystem()
        asys.players["p1"] = ArenaPlayer("p1", rank=5, hidden_mmr=2000)
        asys.players["p2"] = ArenaPlayer("p2", rank=5, hidden_mmr=800)
        # 同段位但MMR差距大，不应匹配
        assert not asys.match("p1", "p2"), "匹配未使用隐藏分"

class TestPromotion:
    def test_promotion_loss_no_demote(self):
        asys = ArenaSystem()
        asys.players["p1"] = ArenaPlayer("p1", rank=5)
        asys.promotion_match("p1", False)
        assert asys.players["p1"].rank == 5, "晋级赛失败掉段"
