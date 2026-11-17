from __future__ import annotations

import math
from pathlib import Path

import pygame


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def distance(a: pygame.Vector2, b: pygame.Vector2) -> float:
    return (a - b).length()


def heading_vector(degrees: float) -> pygame.Vector2:
    radians = math.radians(degrees)
    return pygame.Vector2(math.sin(radians), -math.cos(radians))


def bearing_between(origin: pygame.Vector2, target: pygame.Vector2) -> float:
    delta = target - origin
    return math.degrees(math.atan2(delta.x, -delta.y)) % 360


def compass_name(degrees: float) -> str:
    names = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"]
    return names[int((degrees + 22.5) // 45) % 8]


def load_font(size: int, bold: bool = False) -> pygame.font.Font:
    preferred = ["malgungothic", "맑은 고딕", "nanumgothic", "arial"]
    for name in preferred:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def make_player_surface(path: Path) -> pygame.Surface:
    source = pygame.image.load(str(path)).convert()
    source = pygame.transform.smoothscale(source, (154, 160))
    result = pygame.Surface(source.get_size(), pygame.SRCALPHA)
    for y in range(source.get_height()):
        for x in range(source.get_width()):
            color = source.get_at((x, y))
            brightness = (color.r + color.g + color.b) / 3
            alpha = int(clamp((245 - brightness) * 8, 0, 255))
            if alpha > 0:
                result.set_at((x, y), (24, 26, 31, alpha))
    return result
