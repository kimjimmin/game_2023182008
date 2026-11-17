from __future__ import annotations

from dataclasses import dataclass

import pygame


@dataclass
class AssistantTask:
    kind: str
    label: str
    duration: float
    remaining: float
    target: pygame.Vector2 | None = None


class Assistant:
    """조수의 선택 좌표, 작업 대기열과 기상 보고를 관리한다."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.task: AssistantTask | None = None
        self.selected_world: pygame.Vector2 | None = None
        self.selected_screen: pygame.Vector2 | None = None
        self.weather_report = "기상 정보 없음"

    def select(self, world: pygame.Vector2, screen: pygame.Vector2) -> None:
        self.selected_world = world.copy()
        self.selected_screen = screen.copy()

    def start(self, command: str) -> str | None:
        if self.task is not None:
            return "무선사가 다른 작업을 수행 중입니다."
        if command == "terrain":
            if self.selected_world is None:
                return "먼저 왼쪽 화면에서 지형 좌표를 선택하십시오."
            self.task = AssistantTask(
                "terrain",
                "지형표 조회 중",
                5.0,
                5.0,
                self.selected_world.copy(),
            )
        elif command == "radio":
            self.task = AssistantTask("radio", "무전 송신 중", 7.0, 7.0)
        elif command == "organize":
            self.task = AssistantTask("organize", "기내 정리 중", 4.0, 4.0)
        elif command == "weather":
            self.task = AssistantTask("weather", "기상 자료 수신 중", 9.0, 9.0)
        return None

    def cancel(self) -> bool:
        if self.task is None:
            return False
        self.task = None
        return True

    def update(self, dt: float) -> AssistantTask | None:
        if self.task is None:
            return None
        self.task.remaining -= dt
        if self.task.remaining > 0:
            return None
        finished = self.task
        self.task = None
        return finished
