from __future__ import annotations

import random


class MessSystem:
    """부하 구간에 따른 계기 가림과 복구를 관리한다."""

    GAUGES = ("고도", "나침반", "연료", "속도", "기체 부담", "기체 상태")

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.hidden_gauges: list[str] = []
        self.last_cause = "없음"
        self.peak_stress_band = 0

    def trigger(self, cause: str) -> str | None:
        candidates = [name for name in self.GAUGES if name not in self.hidden_gauges]
        if not candidates:
            return None
        gauge = random.choice(candidates)
        self.hidden_gauges.append(gauge)
        self.last_cause = cause
        return gauge

    def update_stress(self, stress: float, cause: str) -> list[str]:
        hidden: list[str] = []
        stress_band = int(stress // 10)
        while stress_band > self.peak_stress_band:
            self.peak_stress_band += 1
            gauge = self.trigger(cause)
            if gauge is not None:
                hidden.append(gauge)
        if stress <= 2:
            self.peak_stress_band = 0
        return hidden

    def restore_one(self) -> str | None:
        return self.hidden_gauges.pop(0) if self.hidden_gauges else None
