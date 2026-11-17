from __future__ import annotations

from .aircraft import Aircraft
from .navigation import NavigationSystem
from .route import Route
from .terrain import TerrainMap


class Mission:
    """비행 시간, 안내 메시지, 튜토리얼과 성공·실패를 관리한다."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.flight_time = 0.0
        self.tutorial_step = 0
        self.level_hold = 0.0
        self.message = "우측 상단 원본 지도와 좌측 관측 지도를 비교해 붉은 항로를 따라가십시오."
        self.message_timer = 8.0
        self.game_state = "playing"

    def post_message(self, text: str, duration: float = 5.0) -> None:
        self.message = text
        self.message_timer = duration

    def advance(self, dt: float) -> None:
        self.flight_time += dt
        if self.message_timer > 0:
            self.message_timer -= dt

    def update_tutorial(self, aircraft: Aircraft, route: Route, dt: float) -> None:
        if self.tutorial_step == 0:
            if abs(aircraft.bank) < 7 and abs(aircraft.pitch) < 6 and aircraft.speed_level == 3:
                self.level_hold += dt
            else:
                self.level_hold = 0
            if self.level_hold >= 2.0:
                self.tutorial_step = 1
                self.post_message("좋습니다. 우측 원본 지도의 붉은 항로를 보고 동쪽으로 출발하십시오.", 9.0)
        elif self.tutorial_step == 1 and self.flight_time >= 10:
            self.tutorial_step = 2
            self.post_message("좌측 관측 지도와 우측 원본 지도를 비교하며 현재 위치를 추정하십시오.", 9.0)
        elif self.tutorial_step == 2 and self.flight_time >= 20:
            self.tutorial_step = 3
            self.post_message("위치가 불확실하면 무전 송신으로 가까운 송신탑을 확인할 수 있습니다.", 9.0)
        elif self.tutorial_step == 3 and route.index >= 2:
            self.tutorial_step = 4
            self.post_message("첫 꺾임점을 통과했습니다. 우측 지도를 보고 다음 구간으로 선회하십시오.", 9.0)

    def check_outcome(
        self,
        aircraft: Aircraft,
        navigation: NavigationSystem,
        terrain: TerrainMap,
        route: Route,
    ) -> None:
        clearance = terrain.clearance(navigation.actual_position, aircraft.altitude)
        if clearance <= 35:
            self.game_state = "failed"
            self.post_message("지형과 충돌했습니다.")
        elif aircraft.fuel <= 0:
            self.game_state = "failed"
            self.post_message("연료가 소진되었습니다.")
        elif aircraft.durability <= 0:
            self.game_state = "failed"
            self.post_message("기체가 더 이상 비행을 버티지 못했습니다.")
        elif route.reached_destination(navigation.actual_position) and clearance > 80:
            self.game_state = "success"
            self.post_message("보라색 도착점에 도달했습니다. 항로 비행 완료.")
