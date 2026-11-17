from __future__ import annotations

from dataclasses import dataclass

import pygame

from .utils import distance


@dataclass(frozen=True)
class Mountain:
    x: float
    y: float
    radius: float
    peak: float


class TerrainMap:
    """산 데이터와 좌표별 지형 고도를 제공한다."""

    BASE_HEIGHT = 180.0

    def __init__(self, map_w: int, map_h: int) -> None:
        self.map_w = map_w
        self.map_h = map_h
        self.mountains = self._build_mountains()

    def _build_mountains(self) -> list[Mountain]:
        specs = [
            (0.083, 0.305, 0.075, 1250),
            (0.145, 0.360, 0.070, 1050),
            (0.310, 0.230, 0.075, 1450),
            (0.350, 0.388, 0.105, 1700),
            (0.290, 0.742, 0.065, 1100),
            (0.435, 0.780, 0.080, 1350),
            (0.650, 0.250, 0.120, 2050),
            (0.735, 0.155, 0.125, 2350),
            (0.620, 0.420, 0.090, 1550),
        ]
        scale = min(self.map_w, self.map_h)
        return [
            Mountain(self.map_w * x, self.map_h * y, scale * radius, peak)
            for x, y, radius, peak in specs
        ]

    def height_at(self, point: pygame.Vector2) -> float:
        height = self.BASE_HEIGHT
        for mountain in self.mountains:
            center = pygame.Vector2(mountain.x, mountain.y)
            offset = distance(point, center)
            if offset < mountain.radius:
                contribution = mountain.peak * (1.0 - offset / mountain.radius) ** 1.35
                height = max(height, self.BASE_HEIGHT + contribution)
        return height

    def clearance(self, point: pygame.Vector2, altitude: float) -> float:
        return altitude - self.height_at(point)
