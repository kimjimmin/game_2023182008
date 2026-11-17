from __future__ import annotations

from dataclasses import dataclass
import math

import pygame

from .config import (
    ALTITUDE_LIMIT,
    ALTITUDE_SAFE_MAX,
    BASE_ALTITUDE_SINK,
    RAPID_CLIMB_RESET,
    RAPID_CLIMB_THRESHOLD,
)
from .utils import clamp


@dataclass(frozen=True)
class AircraftUpdate:
    rapid_climb_cause: str | None
    high_altitude_warning: bool
    dominant_stress_cause: str


class Aircraft:
    """조종, 고도, 연료, 부하와 내구도를 관리한다."""

    SPEEDS = (0.0, 3.7, 5.5, 14.0, 17.6, 21.0)

    def __init__(self) -> None:
        self.reset(0.0)

    def reset(self, heading: float) -> None:
        self.heading = heading
        self.bank = 0.0
        self.pitch = 0.0
        self.altitude = 720.0
        self.vertical_speed = 0.0
        self.speed_level = 0
        self.fuel = 100.0
        self.stress = 0.0
        self.durability = 100.0
        self.rapid_climb_latched = False
        self.high_altitude_failure_announced = False

    @property
    def speed_world(self) -> float:
        return self.SPEEDS[self.speed_level]

    def update_controls(self, keys: pygame.key.ScancodeWrapper, dt: float) -> None:
        deliberate_turn = keys[pygame.K_a]
        bank_rate = 34 if deliberate_turn else 22
        pitch_rate = 20

        if keys[pygame.K_LEFT]:
            self.bank -= bank_rate * dt
        elif keys[pygame.K_RIGHT]:
            self.bank += bank_rate * dt
        else:
            self.bank *= max(0.0, 1.0 - 1.7 * dt)

        if keys[pygame.K_UP]:
            self.pitch += pitch_rate * dt
        elif keys[pygame.K_DOWN]:
            self.pitch -= pitch_rate * dt
        else:
            self.pitch *= max(0.0, 1.0 - 1.4 * dt)

        self.bank = clamp(self.bank, -58, 58)
        self.pitch = clamp(self.pitch, -24, 24)

    def update(
        self,
        dt: float,
        flight_time: float,
        turbulence: float,
        deliberate_turn: bool,
    ) -> AircraftUpdate:
        self.bank += math.sin(flight_time * 1.7) * turbulence * dt * 9.0
        self.pitch += math.sin(flight_time * 2.4) * turbulence * dt * 4.0

        turn_multiplier = 1.75 if deliberate_turn else 1.0
        self.heading = (self.heading + self.bank * 0.34 * turn_multiplier * dt) % 360

        climb_power = 15.0 if self.speed_level > 0 else 5.0
        target_vertical_speed = self.pitch * climb_power - BASE_ALTITUDE_SINK
        smoothing = min(1.0, dt * 1.8)
        self.vertical_speed += (target_vertical_speed - self.vertical_speed) * smoothing
        self.vertical_speed += math.sin(flight_time * 2.1) * turbulence * 7.5
        self.altitude = clamp(self.altitude + self.vertical_speed * dt, 0, ALTITUDE_LIMIT)

        rapid_climb_cause = None
        if self.vertical_speed >= RAPID_CLIMB_THRESHOLD and not self.rapid_climb_latched:
            rapid_climb_cause = f"급격한 상승 {self.vertical_speed:.0f}m/s"
            self.rapid_climb_latched = True
        elif self.vertical_speed < RAPID_CLIMB_RESET:
            self.rapid_climb_latched = False

        high_altitude_warning = False
        if self.altitude > ALTITUDE_SAFE_MAX:
            overload_ratio = (self.altitude - ALTITUDE_SAFE_MAX) / (
                ALTITUDE_LIMIT - ALTITUDE_SAFE_MAX
            )
            failure_rate = 2.0 + 6.0 * overload_ratio
            self.durability = max(0.0, self.durability - failure_rate * dt)
            if not self.high_altitude_failure_announced:
                high_altitude_warning = True
                self.high_altitude_failure_announced = True
        elif self.altitude < ALTITUDE_SAFE_MAX - 100:
            self.high_altitude_failure_announced = False

        self.fuel = max(
            0.0,
            self.fuel - dt * (0.018 + self.speed_level * 0.009 + abs(self.pitch) * 0.0008),
        )

        stress_causes: list[tuple[float, str]] = []
        if self.speed_level == 5:
            stress_causes.append((16.0, "5단계 과속"))
        if abs(self.bank) > 38:
            stress_causes.append(
                ((abs(self.bank) - 38) * 1.6, f"기체 과도 기울기 {abs(self.bank):.0f}°")
            )
        if abs(self.pitch) > 18:
            stress_causes.append(
                ((abs(self.pitch) - 18) * 1.2, f"과도한 기수 각도 {abs(self.pitch):.0f}°")
            )
        turbulence_stress = turbulence * max(0, self.speed_level - 3) * 5
        if turbulence_stress > 0:
            stress_causes.append((turbulence_stress, "난기류 속 고속 비행"))

        dangerous = sum(amount for amount, _ in stress_causes)
        dominant_cause = max(
            stress_causes,
            default=(0.0, "원인 없음"),
            key=lambda item: item[0],
        )[1]
        self.stress += (dangerous if dangerous > 0 else -24) * dt
        self.stress = clamp(self.stress, 0, 100)
        if self.stress >= 100:
            self.durability = max(0.0, self.durability - 9 * dt)

        return AircraftUpdate(rapid_climb_cause, high_altitude_warning, dominant_cause)
