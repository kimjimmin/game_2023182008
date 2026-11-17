from __future__ import annotations

import pygame

from .utils import distance


class Route:
    """지도 표식과 항로 진행 상태를 관리한다."""

    def __init__(self, map_w: int, map_h: int) -> None:
        self.start = pygame.Vector2(map_w * 0.066, map_h * 0.843)
        self.destination = pygame.Vector2(map_w * 0.908, map_h * 0.096)
        self.villages = [
            pygame.Vector2(map_w * 0.187, map_h * 0.641),
            pygame.Vector2(map_w * 0.189, map_h * 0.273),
            pygame.Vector2(map_w * 0.912, map_h * 0.145),
        ]
        self.towers = [
            pygame.Vector2(map_w * 0.315, map_h * 0.724),
            pygame.Vector2(map_w * 0.349, map_h * 0.443),
            pygame.Vector2(map_w * 0.615, map_h * 0.445),
        ]
        self.points = [
            self.start.copy(),
            pygame.Vector2(map_w * 0.340, map_h * 0.836),
            pygame.Vector2(map_w * 0.340, map_h * 0.514),
            pygame.Vector2(map_w * 0.606, map_h * 0.514),
            pygame.Vector2(map_w * 0.710, map_h * 0.360),
            pygame.Vector2(map_w * 0.780, map_h * 0.215),
            self.destination.copy(),
        ]
        self.index = 1

    def reset(self) -> None:
        self.index = 1

    def update_progress(self, actual_position: pygame.Vector2) -> bool:
        """새 꺾임점을 통과했으면 True를 반환한다."""
        if self.index >= len(self.points):
            return False
        if distance(actual_position, self.points[self.index]) >= 36:
            return False
        self.index += 1
        return True

    def reached_destination(self, actual_position: pygame.Vector2) -> bool:
        return distance(actual_position, self.destination) < 48

    def nearest_tower_index(self, position: pygame.Vector2) -> int:
        return min(range(len(self.towers)), key=lambda index: distance(position, self.towers[index]))
