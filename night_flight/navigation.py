from __future__ import annotations

import math

import pygame

from .config import OBSERVATION_SIZE
from .utils import clamp, heading_vector


class NavigationSystem:
    """실제 위치, 추정 위치, 알려진 송신탑과 현재 시야를 관리한다."""

    def __init__(self, map_w: int, map_h: int) -> None:
        self.map_w = map_w
        self.map_h = map_h
        self.camera_world_w = 620.0
        self.camera_world_h = 620.0
        self.tile_world = 34.0
        self.actual_position = pygame.Vector2()
        self.estimated_position = pygame.Vector2()
        self.current_visible: set[tuple[int, int]] = set()
        self.known_towers: set[int] = set()

    def reset(self, start: pygame.Vector2) -> None:
        self.actual_position = start.copy()
        self.estimated_position = start.copy()
        self.current_visible.clear()
        self.known_towers.clear()

    def move(
        self,
        heading: float,
        speed: float,
        base_wind: pygame.Vector2,
        storm_wind: pygame.Vector2,
        storm_intensity: float,
        dt: float,
    ) -> None:
        ideal_delta = heading_vector(heading) * speed * dt
        wind_delta = (base_wind + storm_wind * storm_intensity) * dt
        self.actual_position += ideal_delta + wind_delta
        self.estimated_position += ideal_delta
        self.actual_position.x = clamp(self.actual_position.x, 0, self.map_w - 1)
        self.actual_position.y = clamp(self.actual_position.y, 0, self.map_h - 1)
        self.estimated_position.x = clamp(self.estimated_position.x, 0, self.map_w - 1)
        self.estimated_position.y = clamp(self.estimated_position.y, 0, self.map_h - 1)

    def correct_position(self, ratio: float = 0.72) -> None:
        self.estimated_position = self.estimated_position.lerp(self.actual_position, ratio)

    def update_visibility(self, grid_size: int) -> None:
        self.current_visible.clear()
        half_view = grid_size * self.tile_world / 2
        start_tx = math.floor((self.estimated_position.x - half_view) / self.tile_world)
        end_tx = math.ceil((self.estimated_position.x + half_view) / self.tile_world)
        start_ty = math.floor((self.estimated_position.y - half_view) / self.tile_world)
        end_ty = math.ceil((self.estimated_position.y + half_view) / self.tile_world)
        max_tx = int((self.map_w - 1) // self.tile_world)
        max_ty = int((self.map_h - 1) // self.tile_world)
        for ty in range(start_ty, end_ty):
            for tx in range(start_tx, end_tx):
                if 0 <= tx <= max_tx and 0 <= ty <= max_ty:
                    self.current_visible.add((tx, ty))

    def chart_geometry(self, rect: pygame.Rect) -> tuple[pygame.Rect, float, pygame.Vector2]:
        inner = rect.inflate(-10, -10)
        scale = min(inner.width / self.camera_world_w, inner.height / self.camera_world_h)
        origin = pygame.Vector2(
            inner.centerx - self.estimated_position.x * scale,
            inner.centery - self.estimated_position.y * scale,
        )
        return inner, scale, origin

    def world_to_screen(self, point: pygame.Vector2, rect: pygame.Rect) -> pygame.Vector2:
        _, scale, origin = self.chart_geometry(rect)
        return pygame.Vector2(origin.x + point.x * scale, origin.y + point.y * scale)

    def screen_to_world(
        self,
        point: pygame.Vector2,
        rect: pygame.Rect,
        storm_rotation: float,
        storm_intensity: float,
        visual_scale: float,
    ) -> pygame.Vector2 | None:
        center = pygame.Vector2(rect.center)
        nx = (point.x - center.x) / (OBSERVATION_SIZE * 0.48)
        ny = (point.y - center.y) / (OBSERVATION_SIZE * 0.44)
        if nx * nx + ny * ny > 1.0:
            return None
        if storm_intensity > 0.01:
            local = point - center
            point = center + local.rotate(-storm_rotation) / visual_scale
        _, scale, origin = self.chart_geometry(rect)
        world_x = (point.x - origin.x) / scale
        world_y = (point.y - origin.y) / scale
        if 0 <= world_x < self.map_w and 0 <= world_y < self.map_h:
            return pygame.Vector2(world_x, world_y)
        return None
