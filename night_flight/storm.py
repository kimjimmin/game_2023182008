from __future__ import annotations

import random

import pygame

from .aircraft import Aircraft
from .utils import clamp, heading_vector


class Storm:
    """폭풍 강도, 바람, 돌풍과 관측 화면 회전을 관리한다."""

    START_TIME = 23.0

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.active = False
        self.announced = False
        self.intensity = 0.0
        self.rotation = 0.0
        self.rotation_direction = 1
        self.rotation_speed = 0.0
        self.rotation_timer = 0.0
        self.gust_timer = 0.0
        self.wind = pygame.Vector2()

    @property
    def visual_scale(self) -> float:
        return 1.0 + self.intensity * 0.14

    def update(self, flight_time: float, dt: float, aircraft: Aircraft) -> bool:
        """이번 프레임에 폭풍이 처음 시작됐으면 True를 반환한다."""
        if flight_time < self.START_TIME:
            self.intensity = 0.0
            self.rotation += (0.0 - self.rotation) * min(1.0, dt * 3.0)
            return False

        started = False
        if not self.active:
            self.active = True
            started = True
            self.rotation_direction = random.choice([-1, 1])
            self.rotation_speed = random.uniform(5.0, 11.0)
            wind_heading = random.uniform(0, 360)
            self.wind = heading_vector(wind_heading) * random.uniform(3.2, 5.2)
            self.rotation_timer = random.uniform(6.0, 15.0)
            self.gust_timer = 0.0

        self.intensity = clamp((flight_time - self.START_TIME) / 4.0, 0.0, 1.0)
        self.rotation_timer -= dt
        if self.rotation_timer <= 0:
            self.rotation_direction *= -1
            self.rotation_speed = random.uniform(5.0, 11.0)
            self.rotation_timer = random.uniform(6.0, 15.0)
        self.rotation += self.rotation_direction * self.rotation_speed * self.intensity * dt
        self.rotation = (self.rotation + 180.0) % 360.0 - 180.0

        self.gust_timer -= dt
        if self.gust_timer <= 0 and self.intensity > 0:
            aircraft.bank += random.uniform(-13.0, 13.0) * self.intensity
            aircraft.pitch += random.uniform(-6.0, 6.0) * self.intensity
            self.gust_timer = random.uniform(0.45, 1.05)
        return started

    def visibility_grid_size(self, flight_time: float) -> int:
        if not self.active:
            return 12
        deterioration_steps = int(max(0.0, flight_time - self.START_TIME) // 2.0)
        return max(6, 12 - deterioration_steps)
