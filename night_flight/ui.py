from __future__ import annotations

from dataclasses import dataclass

import pygame

from .config import PANEL_W, VIEW_W


@dataclass(frozen=True)
class UIButton:
    rect: pygame.Rect
    command: str
    label: str
    subtitle: str


class UIManager:
    """오른쪽 조수 명령 버튼과 클릭 판정을 관리한다."""

    def __init__(self) -> None:
        x = VIEW_W + 18
        width = PANEL_W - 36
        height = 37
        start_y = 520
        gap = 4
        data = [
            ("terrain", "좌표 지형 조회", "선택한 지점의 고도"),
            ("radio", "무전 송신", "가까운 송신탑 확인"),
            ("organize", "기내 정리", "가려진 계기 복구"),
            ("weather", "기상보고 요청", "전방 기상 확인"),
        ]
        self.buttons = [
            UIButton(
                pygame.Rect(x, start_y + index * (height + gap), width, height),
                key,
                title,
                subtitle,
            )
            for index, (key, title, subtitle) in enumerate(data)
        ]

    def command_at(self, position: tuple[int, int]) -> str | None:
        for button in self.buttons:
            if button.rect.collidepoint(position):
                return button.command
        return None
