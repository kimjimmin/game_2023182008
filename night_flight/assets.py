from __future__ import annotations

from dataclasses import dataclass

import pygame

from .config import ASSET_DIR, PANEL_W
from .route import Route
from .utils import clamp, distance, make_player_surface


@dataclass
class GameAssets:
    map_surface: pygame.Surface
    world_surface: pygame.Surface
    player_surface: pygame.Surface
    assistant_surface: pygame.Surface

    @classmethod
    def load(cls) -> tuple[GameAssets, Route]:
        map_surface = pygame.image.load(str(ASSET_DIR / "map.png")).convert()
        map_w, map_h = map_surface.get_size()
        route = Route(map_w, map_h)
        world_surface = _remove_route_line(map_surface, route.points)
        player_surface = make_player_surface(ASSET_DIR / "Player.jpg")
        assistant = pygame.image.load(str(ASSET_DIR / "assistant.png")).convert()
        assistant_surface = pygame.transform.smoothscale(assistant, (PANEL_W, 260))
        return cls(map_surface, world_surface, player_surface, assistant_surface), route


def _remove_route_line(
    map_surface: pygame.Surface,
    route_points: list[pygame.Vector2],
) -> pygame.Surface:
    """관측 지도에서 종이 지도의 붉은 항로를 지운 복사본을 만든다."""
    world_surface = map_surface.copy()
    map_w, map_h = map_surface.get_size()
    for start, end in zip(route_points, route_points[1:]):
        segment = end - start
        if segment.length_squared() == 0:
            continue
        normal = pygame.Vector2(-segment.y, segment.x).normalize() * 22
        segment_length_sq = segment.length_squared()
        left = max(0, int(min(start.x, end.x) - 18))
        right = min(map_w - 1, int(max(start.x, end.x) + 18))
        top = max(0, int(min(start.y, end.y) - 18))
        bottom = min(map_h - 1, int(max(start.y, end.y) + 18))
        for py in range(top, bottom + 1):
            for px in range(left, right + 1):
                point = pygame.Vector2(px, py)
                projection = clamp((point - start).dot(segment) / segment_length_sq, 0.0, 1.0)
                nearest = start + segment * projection
                if distance(point, nearest) > 15:
                    continue
                sample = point + normal
                sx = int(clamp(sample.x, 0, map_w - 1))
                sy = int(clamp(sample.y, 0, map_h - 1))
                world_surface.set_at((px, py), map_surface.get_at((sx, sy)))
    return world_surface
