from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import pygame


SCREEN_W = 1280
SCREEN_H = 720
VIEW_W = 850
PANEL_W = SCREEN_W - VIEW_W
OBSERVATION_SIZE = SCREEN_H
OBSERVATION_X = (VIEW_W - OBSERVATION_SIZE) // 2
OBSERVATION_RECT = pygame.Rect(OBSERVATION_X, 0, OBSERVATION_SIZE, OBSERVATION_SIZE)
FPS = 60

ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / "assets_source"

BG = (31, 33, 38)
VIEW_BG = (87, 90, 95)
PANEL_BG = (20, 23, 31)
PANEL_LINE = (74, 79, 92)
TEXT = (231, 225, 210)
MUTED = (156, 160, 169)
AMBER = (224, 174, 76)
RED = (199, 74, 65)
GREEN = (103, 179, 130)
PURPLE = (139, 93, 174)
CYAN = (104, 172, 190)


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


@dataclass
class Mountain:
    x: float
    y: float
    radius: float
    peak: float


@dataclass
class AssistantTask:
    kind: str
    label: str
    duration: float
    remaining: float
    target: pygame.Vector2 | None = None


@dataclass
class UIButton:
    rect: pygame.Rect
    command: str
    label: str
    subtitle: str


class NightFlightGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("야간 비행 — 파비앵의 첫 항로")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()

        self.font_xs = load_font(14)
        self.font_sm = load_font(17)
        self.font_md = load_font(21)
        self.font_lg = load_font(28, bold=True)
        self.font_xl = load_font(38, bold=True)
        self.globe_mask, self.globe_vignette = self.make_globe_effects()

        self.map_surface = pygame.image.load(str(ASSET_DIR / "map.png")).convert()
        self.map_w, self.map_h = self.map_surface.get_size()
        self.player_base = make_player_surface(ASSET_DIR / "Player.jpg")
        assistant = pygame.image.load(str(ASSET_DIR / "assistant.png")).convert()
        self.assistant_surface = pygame.transform.smoothscale(assistant, (PANEL_W, 260))

        # map.png의 실제 크기에 대한 정규화 좌표다.
        self.start = pygame.Vector2(self.map_w * 0.066, self.map_h * 0.843)
        self.destination = pygame.Vector2(self.map_w * 0.908, self.map_h * 0.096)
        self.villages = [
            pygame.Vector2(self.map_w * 0.187, self.map_h * 0.641),
            pygame.Vector2(self.map_w * 0.189, self.map_h * 0.273),
            pygame.Vector2(self.map_w * 0.912, self.map_h * 0.145),
        ]
        self.towers = [
            pygame.Vector2(self.map_w * 0.315, self.map_h * 0.724),
            pygame.Vector2(self.map_w * 0.349, self.map_h * 0.443),
            pygame.Vector2(self.map_w * 0.615, self.map_h * 0.445),
        ]
        # 붉은 점선 항로의 꺾임점. 항로 진행 상태 판정에 사용한다.
        self.route_points = [
            self.start.copy(),
            pygame.Vector2(self.map_w * 0.340, self.map_h * 0.836),
            pygame.Vector2(self.map_w * 0.340, self.map_h * 0.514),
            pygame.Vector2(self.map_w * 0.606, self.map_h * 0.514),
            pygame.Vector2(self.map_w * 0.710, self.map_h * 0.360),
            pygame.Vector2(self.map_w * 0.780, self.map_h * 0.215),
            self.destination.copy(),
        ]
        # 비행 시야에는 종이 지도에 그려진 붉은 점선을 노출하지 않는다.
        # 항로 원본은 우측 상단 지도와 진행 상태 판정에만 사용한다.
        self.world_surface = self.map_surface.copy()
        for start, end in zip(self.route_points, self.route_points[1:]):
            segment = end - start
            if segment.length_squared() == 0:
                continue
            normal = pygame.Vector2(-segment.y, segment.x).normalize() * 22
            segment_length_sq = segment.length_squared()
            left = max(0, int(min(start.x, end.x) - 18))
            right = min(self.map_w - 1, int(max(start.x, end.x) + 18))
            top = max(0, int(min(start.y, end.y) - 18))
            bottom = min(self.map_h - 1, int(max(start.y, end.y) + 18))
            for py in range(top, bottom + 1):
                for px in range(left, right + 1):
                    point = pygame.Vector2(px, py)
                    projection = clamp((point - start).dot(segment) / segment_length_sq, 0.0, 1.0)
                    nearest = start + segment * projection
                    if distance(point, nearest) > 15:
                        continue
                    sample = pygame.Vector2(px, py) + normal
                    sx = int(clamp(sample.x, 0, self.map_w - 1))
                    sy = int(clamp(sample.y, 0, self.map_h - 1))
                    replacement = self.map_surface.get_at((sx, sy))
                    self.world_surface.set_at((px, py), replacement)
        self.mountains = self.build_mountains()

        self.camera_world_w = 510.0
        self.camera_world_h = self.camera_world_w * SCREEN_H / VIEW_W
        self.tile_world = 34.0
        self.current_visible: set[tuple[int, int]] = set()
        self.remembered: set[tuple[int, int]] = set()
        self.known_towers: set[int] = set()

        self.buttons = self.build_buttons()
        self.reset()

    def build_mountains(self) -> list[Mountain]:
        # map.png의 산 그림을 따라 배치한 충돌용 고도 데이터다.
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

    def build_buttons(self) -> list[UIButton]:
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
        return [
            UIButton(pygame.Rect(x, start_y + i * (height + gap), width, height), key, title, sub)
            for i, (key, title, sub) in enumerate(data)
        ]

    def reset(self) -> None:
        self.actual_pos = self.start.copy()
        self.estimated_pos = self.start.copy()
        self.heading = bearing_between(self.start, self.route_points[1])
        self.bank = 0.0
        self.pitch = 0.0
        self.altitude = 720.0
        self.vertical_speed = 0.0
        self.speed_level = 0
        self.fuel = 100.0
        self.stress = 0.0
        self.durability = 100.0
        self.flight_time = 0.0
        self.tutorial_step = 0
        self.level_hold = 0.0
        self.stress_peak_band = 0
        self.task: AssistantTask | None = None
        self.selected_world: pygame.Vector2 | None = None
        self.selected_screen: pygame.Vector2 | None = None
        self.hidden_gauges: list[str] = []
        self.last_mess_cause = "없음"
        self.weather_report = "기상 정보 없음"
        self.route_index = 1
        self.message = "우측 상단 원본 지도와 좌측 관측 지도를 비교해 붉은 항로를 따라가십시오."
        self.message_timer = 8.0
        self.game_state = "playing"
        self.turbulence = 0.0
        self.wind = pygame.Vector2(0.20, 0.05)
        self.storm_active = False
        self.storm_announced = False
        self.storm_intensity = 0.0
        self.storm_rotation = 0.0
        self.storm_rotation_direction = 1
        self.storm_rotation_speed = 0.0
        self.storm_rotation_timer = 0.0
        self.storm_gust_timer = 0.0
        self.storm_wind = pygame.Vector2()
        self.current_visible.clear()
        self.remembered.clear()
        self.known_towers.clear()

    def terrain_height(self, point: pygame.Vector2) -> float:
        base = 180.0
        for mountain in self.mountains:
            d = distance(point, pygame.Vector2(mountain.x, mountain.y))
            if d < mountain.radius:
                contribution = mountain.peak * (1.0 - d / mountain.radius) ** 1.35
                base = max(base, 180.0 + contribution)
        return base

    def speed_world(self) -> float:
        speeds = [0.0, 3.7, 5.5, 14.0, 17.6, 21.0]
        return speeds[self.speed_level]

    def current_clearance(self) -> float:
        return self.altitude - self.terrain_height(self.actual_pos)

    def storm_visual_scale(self) -> float:
        return 1.0 + self.storm_intensity * 0.14

    @staticmethod
    def make_globe_effects() -> tuple[pygame.Surface, pygame.Surface]:
        """관측 화면을 타원형 구처럼 보이게 하는 부드러운 마스크와 가장자리 음영."""
        sample_size = 180
        mask_small = pygame.Surface((sample_size, sample_size), pygame.SRCALPHA)
        vignette_small = pygame.Surface((sample_size, sample_size), pygame.SRCALPHA)
        center = (sample_size - 1) / 2

        for y in range(sample_size):
            for x in range(sample_size):
                nx = (x - center) / (sample_size * 0.48)
                ny = (y - center) / (sample_size * 0.44)
                radius = math.sqrt(nx * nx + ny * ny)
                edge_alpha = int(255 * clamp((1.0 - radius) / 0.10, 0.0, 1.0))
                mask_small.set_at((x, y), (255, 255, 255, edge_alpha))

                limb = clamp((radius - 0.62) / 0.38, 0.0, 1.0)
                shade_alpha = int(145 * limb * edge_alpha / 255)
                vignette_small.set_at((x, y), (7, 12, 21, shade_alpha))

        size = (OBSERVATION_SIZE, OBSERVATION_SIZE)
        return (
            pygame.transform.smoothscale(mask_small, size),
            pygame.transform.smoothscale(vignette_small, size),
        )

    def update_storm(self, dt: float) -> None:
        if self.flight_time < 23.0:
            self.storm_intensity = 0.0
            self.storm_rotation += (0.0 - self.storm_rotation) * min(1.0, dt * 3.0)
            return

        if not self.storm_active:
            self.storm_active = True
            self.storm_rotation_direction = random.choice([-1, 1])
            self.storm_rotation_speed = random.uniform(5.0, 11.0)
            wind_heading = random.uniform(0, 360)
            self.storm_wind = heading_vector(wind_heading) * random.uniform(3.2, 5.2)
            self.storm_rotation_timer = random.uniform(6.0, 15.0)
            self.storm_gust_timer = 0.0

        if not self.storm_announced:
            self.storm_announced = True
            self.post_message("폭풍 진입! 좌측 화면이 흔들립니다. 우측 나침반을 기준으로 방향을 유지하십시오.", 11.0)

        self.storm_intensity = clamp((self.flight_time - 23.0) / 4.0, 0.0, 1.0)
        self.storm_rotation_timer -= dt
        if self.storm_rotation_timer <= 0:
            self.storm_rotation_direction *= -1
            self.storm_rotation_speed = random.uniform(5.0, 11.0)
            self.storm_rotation_timer = random.uniform(6.0, 15.0)
        self.storm_rotation += (
            self.storm_rotation_direction
            * self.storm_rotation_speed
            * self.storm_intensity
            * dt
        )
        self.storm_rotation = (self.storm_rotation + 180.0) % 360.0 - 180.0

        self.storm_gust_timer -= dt
        if self.storm_gust_timer <= 0 and self.storm_intensity > 0:
            self.bank += random.uniform(-13.0, 13.0) * self.storm_intensity
            self.pitch += random.uniform(-6.0, 6.0) * self.storm_intensity
            self.storm_gust_timer = random.uniform(0.45, 1.05)

    def post_message(self, text: str, duration: float = 5.0) -> None:
        self.message = text
        self.message_timer = duration

    def trigger_mess(self, cause: str) -> None:
        candidates = [
            name for name in ["고도", "나침반", "연료", "속도", "기체 부담", "기체 상태"]
            if name not in self.hidden_gauges
        ]
        if not candidates:
            return
        gauge = random.choice(candidates)
        self.hidden_gauges.append(gauge)
        self.last_mess_cause = cause
        self.post_message(f"엉망! 원인: {cause}. {gauge} 수치를 확인할 수 없습니다.", 9.0)

    def start_task(self, command: str) -> None:
        if self.task is not None:
            self.post_message("무선사가 다른 작업을 수행 중입니다.")
            return

        if command == "terrain":
            if self.selected_world is None:
                self.post_message("먼저 왼쪽 화면에서 지형 좌표를 선택하십시오.")
                return
            self.task = AssistantTask("terrain", "지형표 조회 중", 5.0, 5.0, self.selected_world.copy())
        elif command == "radio":
            self.task = AssistantTask("radio", "무전 송신 중", 7.0, 7.0)
        elif command == "organize":
            if not self.hidden_gauges:
                self.post_message("정리할 문제가 없습니다.")
                return
            self.task = AssistantTask("organize", "기내 정리 중", 4.0, 4.0)
        elif command == "weather":
            self.task = AssistantTask("weather", "기상 자료 수신 중", 9.0, 9.0)

    def finish_task(self) -> None:
        if self.task is None:
            return
        task = self.task
        if task.kind == "terrain" and task.target is not None:
            elevation = int(round(self.terrain_height(task.target) / 50) * 50)
            self.post_message(f"보고: 지정 좌표의 지형 고도는 약 {elevation}m입니다.", 8.0)
        elif task.kind == "radio":
            nearest_index = min(range(len(self.towers)), key=lambda i: distance(self.actual_pos, self.towers[i]))
            tower = self.towers[nearest_index]
            self.known_towers.add(nearest_index)
            bearing = bearing_between(self.actual_pos, tower)
            dist = int(distance(self.actual_pos, tower))
            # 위치 보고를 받으면 추정 위치가 실제 위치 쪽으로 보정된다.
            self.estimated_pos = self.estimated_pos.lerp(self.actual_pos, 0.72)
            self.post_message(
                f"교신 성공: {compass_name(bearing)}쪽 약 {dist} 지도단위에 송신탑이 있습니다.", 9.0
            )
        elif task.kind == "organize":
            restored = self.hidden_gauges.pop(0) if self.hidden_gauges else "계기"
            self.post_message(f"기내 정리 완료: {restored} 계기를 다시 확인할 수 있습니다.", 7.0)
        elif task.kind == "weather":
            if self.flight_time < 28:
                self.weather_report = "전방 40초: 약한 측풍, 시야 양호"
            elif self.flight_time < 55:
                self.weather_report = "전방 25초: 구름 증가, 돌풍 가능"
            else:
                self.weather_report = "전방: 비구름, 보고 시각 8분 전"
            self.post_message(f"기상보고: {self.weather_report}", 9.0)
        self.task = None

    def cancel_task(self) -> None:
        if self.task is not None:
            self.task = None
            self.post_message("무선사 작업을 취소했습니다.")

    def screen_to_world(self, point: pygame.Vector2) -> pygame.Vector2 | None:
        center = pygame.Vector2(OBSERVATION_RECT.center)
        nx = (point.x - center.x) / (OBSERVATION_SIZE * 0.48)
        ny = (point.y - center.y) / (OBSERVATION_SIZE * 0.44)
        if nx * nx + ny * ny > 1.0:
            return None
        if self.storm_intensity > 0.01:
            local = point - center
            point = center + local.rotate(-self.storm_rotation) / self.storm_visual_scale()
        _, scale, origin = self.chart_geometry(OBSERVATION_RECT)
        world_x = (point.x - origin.x) / scale
        world_y = (point.y - origin.y) / scale
        if 0 <= world_x < self.map_w and 0 <= world_y < self.map_h:
            return pygame.Vector2(world_x, world_y)
        return None

    def world_to_screen(self, point: pygame.Vector2) -> pygame.Vector2:
        left = self.actual_pos.x - self.camera_world_w / 2
        top = self.actual_pos.y - self.camera_world_h / 2
        return pygame.Vector2(
            OBSERVATION_RECT.left + (point.x - left) / self.camera_world_w * OBSERVATION_SIZE,
            OBSERVATION_RECT.top + (point.y - top) / self.camera_world_h * OBSERVATION_SIZE,
        )

    def chart_geometry(self, rect: pygame.Rect) -> tuple[pygame.Rect, float, pygame.Vector2]:
        inner = rect.inflate(-10, -10)
        scale = min(inner.width / self.map_w, inner.height / self.map_h)
        origin = pygame.Vector2(
            inner.centerx - self.map_w * scale / 2,
            inner.centery - self.map_h * scale / 2,
        )
        return inner, scale, origin

    def tile_is_visible(self, world_center: pygame.Vector2) -> bool:
        delta = world_center - self.actual_pos
        dist = delta.length()
        immediate_vision = max(24.0, 46.0 * (1.0 - self.storm_intensity * 0.45))
        if dist < immediate_vision:
            return True
        vision = max(48.0, 190.0 * (1.0 - self.storm_intensity * 0.75))
        if dist > vision:
            return False
        if dist == 0:
            return True
        forward = heading_vector(self.heading)
        dot = forward.dot(delta.normalize())
        minimum_dot = -0.12 + self.storm_intensity * 0.47
        return dot > minimum_dot

    def update_visibility(self) -> None:
        self.current_visible.clear()
        min_x = max(0, int((self.actual_pos.x - 220) // self.tile_world))
        max_x = min(int(self.map_w // self.tile_world), int((self.actual_pos.x + 220) // self.tile_world) + 1)
        min_y = max(0, int((self.actual_pos.y - 220) // self.tile_world))
        max_y = min(int(self.map_h // self.tile_world), int((self.actual_pos.y + 220) // self.tile_world) + 1)
        for ty in range(min_y, max_y + 1):
            for tx in range(min_x, max_x + 1):
                center = pygame.Vector2((tx + 0.5) * self.tile_world, (ty + 0.5) * self.tile_world)
                if self.tile_is_visible(center):
                    self.current_visible.add((tx, ty))
        self.remembered.update(self.current_visible)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            if event.key == pygame.K_RETURN and self.game_state != "playing":
                self.reset()
                return
            if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                self.speed_level = event.key - pygame.K_0
            if event.key == pygame.K_x:
                self.cancel_task()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse = pygame.Vector2(event.pos)
            if mouse.x < VIEW_W:
                world = self.screen_to_world(mouse)
                if world is not None:
                    self.selected_world = world
                    self.selected_screen = mouse
                    self.post_message(
                        f"좌표 선택: X {int(world.x):04d}, Y {int(world.y):04d}. 지형 조회를 명령할 수 있습니다.",
                        5.0,
                    )
            else:
                for button in self.buttons:
                    if button.rect.collidepoint(event.pos):
                        self.start_task(button.command)
                        break

    def update_controls(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
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

    def update_flight(self, dt: float) -> None:
        if self.game_state != "playing":
            return

        self.flight_time += dt
        if self.message_timer > 0:
            self.message_timer -= dt

        self.update_controls(dt)
        self.update_storm(dt)

        self.turbulence = self.storm_intensity
        gust = math.sin(self.flight_time * 1.7) * self.turbulence
        self.bank += gust * dt * 9.0
        self.pitch += math.sin(self.flight_time * 2.4) * self.turbulence * dt * 4.0

        turn_multiplier = 1.75 if pygame.key.get_pressed()[pygame.K_a] else 1.0
        self.heading = (self.heading + self.bank * 0.34 * turn_multiplier * dt) % 360

        climb_power = 15.0 if self.speed_level > 0 else 5.0
        self.vertical_speed += (self.pitch * climb_power - self.vertical_speed) * min(1.0, dt * 1.8)
        self.vertical_speed += math.sin(self.flight_time * 2.1) * self.turbulence * 7.5
        self.altitude += self.vertical_speed * dt
        self.altitude = clamp(self.altitude, 0, 3000)

        speed = self.speed_world()
        forward = heading_vector(self.heading)
        ideal_delta = forward * speed * dt
        wind_delta = (self.wind + self.storm_wind * self.storm_intensity) * dt
        self.actual_pos += ideal_delta + wind_delta
        self.estimated_pos += ideal_delta
        self.actual_pos.x = clamp(self.actual_pos.x, 0, self.map_w - 1)
        self.actual_pos.y = clamp(self.actual_pos.y, 0, self.map_h - 1)
        self.estimated_pos.x = clamp(self.estimated_pos.x, 0, self.map_w - 1)
        self.estimated_pos.y = clamp(self.estimated_pos.y, 0, self.map_h - 1)

        self.fuel -= dt * (0.018 + self.speed_level * 0.009 + abs(self.pitch) * 0.0008)
        self.fuel = max(0, self.fuel)

        stress_causes: list[tuple[float, str]] = []
        if self.speed_level == 5:
            stress_causes.append((16.0, "5단계 과속"))
        if abs(self.bank) > 38:
            stress_causes.append(((abs(self.bank) - 38) * 1.6, f"기체 과도 기울기 {abs(self.bank):.0f}°"))
        if abs(self.pitch) > 18:
            stress_causes.append(((abs(self.pitch) - 18) * 1.2, f"과도한 기수 각도 {abs(self.pitch):.0f}°"))
        turbulence_stress = self.turbulence * max(0, self.speed_level - 3) * 5
        if turbulence_stress > 0:
            stress_causes.append((turbulence_stress, "난기류 속 고속 비행"))
        dangerous = sum(amount for amount, _ in stress_causes)
        dominant_cause = max(stress_causes, default=(0.0, "원인 없음"), key=lambda item: item[0])[1]
        if dangerous > 0:
            self.stress += dangerous * dt
        else:
            self.stress -= 24 * dt
        self.stress = clamp(self.stress, 0, 100)
        if self.stress >= 100:
            self.durability -= 9 * dt

        # 기체 부담이 10% 단계를 새로 넘을 때마다 엉망 이벤트가 한 번 발생한다.
        # 부담이 거의 0까지 회복되면 다음 과부하 구간에서 다시 10%부터 계산한다.
        stress_band = int(self.stress // 10)
        while stress_band > self.stress_peak_band:
            self.stress_peak_band += 1
            self.trigger_mess(dominant_cause)
        if self.stress <= 2:
            self.stress_peak_band = 0

        # 붉은 항로의 다음 꺾임점에 도달하면 진행 구간을 갱신한다.
        if self.route_index < len(self.route_points) and distance(self.actual_pos, self.route_points[self.route_index]) < 36:
            self.route_index += 1
            if self.route_index < len(self.route_points):
                self.post_message("항로 꺾임점 통과. 우측 원본 지도를 확인해 다음 방향으로 선회하십시오.", 9.0)

        if self.task is not None:
            self.task.remaining -= dt
            if self.task.remaining <= 0:
                self.finish_task()

        self.update_tutorial(dt)
        self.update_visibility()
        self.check_outcome()

    def update_tutorial(self, dt: float) -> None:
        if self.tutorial_step == 0:
            if abs(self.bank) < 7 and abs(self.pitch) < 6 and self.speed_level == 3:
                self.level_hold += dt
            else:
                self.level_hold = 0
            if self.level_hold >= 2.0:
                self.tutorial_step = 1
                self.post_message("좋습니다. 우측 원본 지도의 붉은 항로를 보고 동쪽으로 출발하십시오.", 9.0)
        elif self.tutorial_step == 1:
            if self.flight_time >= 10:
                self.tutorial_step = 2
                self.post_message("좌측 관측 지도와 우측 원본 지도를 비교하며 현재 위치를 추정하십시오.", 9.0)
        elif self.tutorial_step == 2:
            if self.flight_time >= 20:
                self.tutorial_step = 3
                self.post_message("위치가 불확실하면 무전 송신으로 가까운 송신탑을 확인할 수 있습니다.", 9.0)
        elif self.tutorial_step == 3:
            if self.route_index >= 2:
                self.tutorial_step = 4
                self.post_message("첫 꺾임점을 통과했습니다. 우측 지도를 보고 다음 구간으로 선회하십시오.", 9.0)

    def check_outcome(self) -> None:
        clearance = self.current_clearance()
        if clearance <= 35:
            self.game_state = "failed"
            self.post_message("지형과 충돌했습니다.")
        elif self.fuel <= 0:
            self.game_state = "failed"
            self.post_message("연료가 소진되었습니다.")
        elif self.durability <= 0:
            self.game_state = "failed"
            self.post_message("기체가 더 이상 비행을 버티지 못했습니다.")
        elif distance(self.actual_pos, self.destination) < 48 and self.altitude > self.terrain_height(self.actual_pos) + 80:
            self.game_state = "success"
            self.post_message("보라색 도착점에 도달했습니다. 항로 비행 완료.")

    def draw_text(self, text: str, pos: tuple[int, int], font: pygame.font.Font | None = None,
                  color: tuple[int, int, int] = TEXT, anchor: str = "topleft") -> pygame.Rect:
        font = font or self.font_sm
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        setattr(rect, anchor, pos)
        self.screen.blit(surface, rect)
        return rect

    def draw_world_tile(self, tx: int, ty: int, alpha: int) -> None:
        wx = tx * self.tile_world
        wy = ty * self.tile_world
        world_rect = pygame.Rect(int(wx), int(wy), int(self.tile_world + 1), int(self.tile_world + 1))
        world_rect = world_rect.clip(self.map_surface.get_rect())
        if world_rect.width <= 0 or world_rect.height <= 0:
            return
        screen_a = self.world_to_screen(pygame.Vector2(world_rect.left, world_rect.top))
        screen_b = self.world_to_screen(pygame.Vector2(world_rect.right, world_rect.bottom))
        dst = pygame.Rect(
            int(screen_a.x), int(screen_a.y),
            max(1, int(screen_b.x - screen_a.x + 1)), max(1, int(screen_b.y - screen_a.y + 1)),
        )
        tile = self.world_surface.subsurface(world_rect)
        tile = pygame.transform.smoothscale(tile, dst.size)
        if alpha < 255:
            tile = tile.copy()
            tile.set_alpha(alpha)
        self.screen.blit(tile, dst)

    def draw_left_view(self) -> None:
        chart_rect = OBSERVATION_RECT
        self.draw_discovered_chart(chart_rect, show_estimate=False)
        _, scale, origin = self.chart_geometry(chart_rect)

        def chart_point(point: pygame.Vector2) -> pygame.Vector2:
            return pygame.Vector2(origin.x + point.x * scale, origin.y + point.y * scale)

        # 좌측 주 화면의 항공기는 조종사가 추정하는 위치에 표시한다.
        plane_position = chart_point(self.estimated_pos)
        plane = pygame.transform.rotozoom(self.player_base, -self.heading, 0.30)
        plane_rect = plane.get_rect(center=plane_position)
        self.screen.blit(plane, plane_rect)

        if self.selected_world is not None:
            p = chart_point(self.selected_world)
            pygame.draw.circle(self.screen, CYAN, p, 11, 2)
            pygame.draw.line(self.screen, CYAN, (p.x - 15, p.y), (p.x + 15, p.y), 1)
            pygame.draw.line(self.screen, CYAN, (p.x, p.y - 15), (p.x, p.y + 15), 1)

        # 수평계는 지도 상단에 독립 계기로 유지한다.
        center = pygame.Vector2(chart_rect.centerx, chart_rect.top + 80)
        length = 160
        angle = math.radians(-self.bank)
        line = pygame.Vector2(math.cos(angle), math.sin(angle)) * length / 2
        pygame.draw.line(self.screen, (83, 74, 54), center - line, center + line, 4)
        pygame.draw.circle(self.screen, (83, 74, 54), center, 7, 2)
        pygame.draw.line(self.screen, (83, 74, 54), (center.x, center.y - 18), (center.x, center.y + 18), 2)

        text_x = chart_rect.left + 16
        self.draw_text("관측 지도 / 미확인 영역은 흰색", (text_x, 14), self.font_sm, (52, 55, 61))
        self.draw_text("클릭: 좌표 지정", (text_x, 38), self.font_xs, (92, 96, 103))
        legend = [
            ((218, 224, 214), "평지"),
            ((225, 201, 183), "낮은 지형"),
            ((185, 103, 96), "높은 산"),
            ((74, 25, 36), "산 정상"),
        ]
        for index, (color, label) in enumerate(legend):
            ly = 72 + index * 20
            pygame.draw.rect(self.screen, color, (text_x, ly, 16, 14))
            pygame.draw.rect(self.screen, (80, 82, 86), (text_x, ly, 16, 14), 1)
            self.draw_text(label, (text_x + 22, ly - 2), self.font_xs, (74, 77, 82))

        if self.last_mess_cause != "없음":
            cause_rect = pygame.Rect(chart_rect.left + 190, 12, chart_rect.width - 206, 42)
            cause_surface = pygame.Surface(cause_rect.size, pygame.SRCALPHA)
            cause_surface.fill((28, 5, 8, 226))
            self.screen.blit(cause_surface, cause_rect)
            pygame.draw.rect(self.screen, RED, cause_rect, 1, border_radius=5)
            self.draw_text(f"최근 엉망 원인: {self.last_mess_cause}",
                           cause_rect.center, self.font_sm, (255, 78, 78), "center")

        clearance = int(self.current_clearance())
        terrain = int(self.terrain_height(self.actual_pos))
        if clearance <= 150:
            warning_rect = pygame.Rect(chart_rect.centerx - 175, 155, 350, 42)
            pygame.draw.rect(self.screen, (42, 4, 7), warning_rect, border_radius=5)
            pygame.draw.rect(self.screen, (242, 35, 35), warning_rect, 2, border_radius=5)
            self.draw_text(f"지형 접근 경고 · 여유 고도 {clearance}m",
                           warning_rect.center, self.font_md, (255, 74, 74), "center")
        self.draw_text(f"추정 지상 여유 {clearance}m", (text_x, SCREEN_H - 54), self.font_sm,
                       GREEN if clearance > 250 else AMBER if clearance > 100 else RED)
        self.draw_text(f"현재 지형 추정 {terrain}m", (text_x, SCREEN_H - 30), self.font_xs, (92, 96, 103))

    def draw_gauge(self, rect: pygame.Rect, title: str, value: str, ratio: float,
                   color: tuple[int, int, int], hidden: bool = False) -> None:
        pygame.draw.rect(self.screen, (28, 31, 41), rect, border_radius=6)
        pygame.draw.rect(self.screen, PANEL_LINE, rect, 1, border_radius=6)
        self.draw_text(title, (rect.x + 10, rect.y + 7), self.font_xs, MUTED)
        if hidden:
            pygame.draw.rect(self.screen, (0, 0, 0), rect.inflate(-4, -4), border_radius=4)
            self.draw_text("엉망!", rect.center, self.font_md, (238, 47, 47), "center")
            return
        self.draw_text(value, (rect.right - 10, rect.y + 5), self.font_md, color, "topright")
        bar = pygame.Rect(rect.x + 10, rect.bottom - 12, rect.width - 20, 5)
        pygame.draw.rect(self.screen, (52, 56, 68), bar, border_radius=3)
        fill = bar.copy()
        fill.width = int(bar.width * clamp(ratio, 0, 1))
        pygame.draw.rect(self.screen, color, fill, border_radius=3)

    def draw_discovered_chart(self, rect: pygame.Rect, show_estimate: bool = True) -> None:
        """실제 map.png와 붉은 항로를 노출하지 않는 관측 기록 지도."""
        pygame.draw.rect(self.screen, (247, 247, 243), rect)
        pygame.draw.rect(self.screen, (72, 75, 82), rect, 2)
        _, scale, origin = self.chart_geometry(rect)

        for tx, ty in self.remembered:
            center = pygame.Vector2((tx + 0.5) * self.tile_world, (ty + 0.5) * self.tile_world)
            elevation = self.terrain_height(center)
            if elevation < 250:
                color = (218, 224, 214)
                contour = (190, 200, 188)
                contour_width = 0
            elif elevation < 500:
                color = (225, 201, 183)
                contour = (194, 155, 137)
                contour_width = 1
            elif elevation < 850:
                color = (213, 157, 139)
                contour = (173, 100, 91)
                contour_width = 2
            elif elevation < 1250:
                color = (185, 103, 96)
                contour = (126, 57, 59)
                contour_width = 3
            elif elevation < 1750:
                color = (135, 60, 66)
                contour = (76, 29, 38)
                contour_width = 4
            else:
                color = (74, 25, 36)
                contour = (31, 10, 18)
                contour_width = 5
            tile_rect = pygame.Rect(
                int(origin.x + tx * self.tile_world * scale),
                int(origin.y + ty * self.tile_world * scale),
                max(1, int(self.tile_world * scale + 1)),
                max(1, int(self.tile_world * scale + 1)),
            )
            pygame.draw.rect(self.screen, color, tile_rect)
            if contour_width > 0:
                pygame.draw.rect(
                    self.screen,
                    contour,
                    tile_rect,
                    max(1, min(contour_width, tile_rect.width // 3, tile_rect.height // 3)),
                )

            # 현재 시야에서 충돌 여유가 150m 이하인 지형은 붉게 경고한다.
            if (tx, ty) in self.current_visible and self.altitude - elevation <= 150:
                pygame.draw.rect(self.screen, (242, 35, 35), tile_rect, max(1, min(3, tile_rect.width // 2)))

        def chart_point(point: pygame.Vector2) -> pygame.Vector2:
            return pygame.Vector2(origin.x + point.x * scale, origin.y + point.y * scale)

        for village in self.villages:
            key = (int(village.x // self.tile_world), int(village.y // self.tile_world))
            if key in self.remembered:
                pygame.draw.circle(self.screen, (200, 83, 134), chart_point(village), max(3, int(6 * scale + 2)))
        for index in self.known_towers:
            pygame.draw.circle(self.screen, (232, 188, 42), chart_point(self.towers[index]), max(3, int(6 * scale + 2)))

        start_key = (int(self.start.x // self.tile_world), int(self.start.y // self.tile_world))
        if start_key in self.remembered:
            pygame.draw.circle(self.screen, (25, 25, 25), chart_point(self.start), 3)
        destination_key = (int(self.destination.x // self.tile_world), int(self.destination.y // self.tile_world))
        if destination_key in self.remembered:
            pygame.draw.circle(self.screen, PURPLE, chart_point(self.destination), 4)

        if show_estimate:
            estimate = chart_point(self.estimated_pos)
            error = max(4, int((distance(self.actual_pos, self.estimated_pos) + 12) * scale))
            pygame.draw.circle(self.screen, (50, 88, 107), estimate, error, 1)
            pygame.draw.circle(self.screen, (38, 113, 151), estimate, 3)

    def draw_right_panel(self) -> None:
        panel = pygame.Rect(VIEW_W, 0, PANEL_W, SCREEN_H)
        pygame.draw.rect(self.screen, PANEL_BG, panel)
        pygame.draw.line(self.screen, PANEL_LINE, (VIEW_W, 0), (VIEW_W, SCREEN_H), 2)

        self.draw_text("야간 비행", (VIEW_W + 14, 14), self.font_lg, TEXT)
        self.draw_text("파비앵", (VIEW_W + 14, 47), self.font_sm, MUTED)
        self.draw_text("원본 항로 지도", (VIEW_W + 14, 78), self.font_xs, MUTED)
        self.draw_text("붉은 선: 예정 항로", (VIEW_W + 14, 99), self.font_xs, MUTED)
        self.draw_text("M: 원본 지도 확대", (VIEW_W + 14, 120), self.font_xs, CYAN)
        map_thumb_rect = pygame.Rect(VIEW_W + 176, 10, PANEL_W - 190, 145)
        pygame.draw.rect(self.screen, (235, 226, 207), map_thumb_rect)
        thumb_scale = min(map_thumb_rect.width / self.map_w, map_thumb_rect.height / self.map_h)
        thumb_size = (int(self.map_w * thumb_scale), int(self.map_h * thumb_scale))
        map_thumb = pygame.transform.smoothscale(self.map_surface, thumb_size)
        map_thumb_pos = map_thumb.get_rect(center=map_thumb_rect.center)
        self.screen.blit(map_thumb, map_thumb_pos)
        pygame.draw.rect(self.screen, (72, 75, 82), map_thumb_rect, 2)

        x = VIEW_W + 18
        width = (PANEL_W - 43) // 2
        h = 52
        col2 = x + width + 7
        alt_color = GREEN if self.current_clearance() > 250 else AMBER if self.current_clearance() > 100 else RED
        self.draw_gauge(pygame.Rect(x, 163, width, h), "고도", f"{int(self.altitude)}m", self.altitude / 2000,
                        alt_color, "고도" in self.hidden_gauges)
        self.draw_gauge(pygame.Rect(col2, 163, width, h), "나침반", f"{int(self.heading):03d}°",
                        self.heading / 360, CYAN, "나침반" in self.hidden_gauges)
        self.draw_gauge(pygame.Rect(x, 220, width, h), "연료", f"{int(self.fuel)}%", self.fuel / 100,
                        GREEN if self.fuel > 25 else RED, "연료" in self.hidden_gauges)
        self.draw_gauge(pygame.Rect(col2, 220, width, h), "속도", f"{self.speed_level}단계",
                        self.speed_level / 5, AMBER if self.speed_level >= 4 else GREEN,
                        "속도" in self.hidden_gauges)
        self.draw_gauge(pygame.Rect(x, 277, width, h), "기체 부담", f"{int(self.stress)}%",
                        self.stress / 100, RED if self.stress > 70 else AMBER,
                        "기체 부담" in self.hidden_gauges)
        self.draw_gauge(pygame.Rect(col2, 277, width, h), "기체 상태", f"{int(self.durability)}%",
                        self.durability / 100, GREEN if self.durability > 40 else RED,
                        "기체 상태" in self.hidden_gauges)

        weather_rect = pygame.Rect(x, 334, PANEL_W - 36, 63)
        pygame.draw.rect(self.screen, (28, 31, 41), weather_rect, border_radius=6)
        self.draw_text("운항 상태", (weather_rect.x + 10, weather_rect.y + 6), self.font_xs, AMBER)
        self.draw_text(f"항로 구간 {min(self.route_index, len(self.route_points) - 1)}/{len(self.route_points) - 1}",
                       (weather_rect.x + 10, weather_rect.y + 23), self.font_xs, TEXT)
        self.draw_text(f"기상: {self.weather_report}", (weather_rect.x + 10, weather_rect.y + 43), self.font_xs, MUTED)

        portrait_rect = pygame.Rect(VIEW_W, 403, PANEL_W, 111)
        crop = self.assistant_surface.subsurface((0, 0, PANEL_W, 220))
        self.screen.blit(crop, portrait_rect, area=pygame.Rect(0, 18, PANEL_W, 111))
        shade = pygame.Surface(portrait_rect.size, pygame.SRCALPHA)
        shade.fill((12, 15, 24, 105))
        self.screen.blit(shade, portrait_rect)
        self.draw_text("무선사", (x, 410), self.font_md, TEXT)
        if self.task:
            progress = 1 - self.task.remaining / self.task.duration
            self.draw_text(self.task.label, (x + 88, 414), self.font_sm, AMBER)
            task_bar = pygame.Rect(x + 88, 446, PANEL_W - 124, 7)
            pygame.draw.rect(self.screen, (48, 51, 61), task_bar, border_radius=4)
            filled = task_bar.copy()
            filled.width = int(task_bar.width * progress)
            pygame.draw.rect(self.screen, AMBER, filled, border_radius=4)
            self.draw_text("X 취소", (x, 442), self.font_xs, MUTED)
        else:
            self.draw_text("명령 대기 중", (x + 88, 414), self.font_sm, GREEN)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            hover = button.rect.collidepoint(mouse_pos)
            base = (48, 52, 64) if hover else (34, 37, 47)
            pygame.draw.rect(self.screen, base, button.rect, border_radius=5)
            pygame.draw.rect(self.screen, AMBER if hover else PANEL_LINE, button.rect, 1, border_radius=5)
            self.draw_text(button.label, (button.rect.x + 10, button.rect.y + 2), self.font_sm, TEXT)
            self.draw_text(button.subtitle, (button.rect.x + 205, button.rect.y + 9), self.font_xs, MUTED)

    def draw_message(self) -> None:
        if self.message_timer <= 0 and self.game_state == "playing":
            return
        rect = pygame.Rect(64, SCREEN_H - 102, VIEW_W - 128, 68)
        surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        surface.fill((12, 14, 18, 220))
        self.screen.blit(surface, rect)
        pygame.draw.rect(self.screen, (158, 142, 103), rect, 1, border_radius=6)
        self.draw_text("운항 지시", (rect.x + 14, rect.y + 9), self.font_xs, AMBER)
        self.draw_text(self.message, (rect.x + 14, rect.y + 31), self.font_sm, TEXT)

    def apply_observation_globe(self) -> None:
        source = self.screen.subsurface(OBSERVATION_RECT).copy()
        angle = self.storm_rotation if self.storm_intensity > 0.01 else 0.0
        scale = self.storm_visual_scale() if self.storm_intensity > 0.01 else 1.0
        rotated = pygame.transform.rotozoom(source, angle, scale)

        globe = pygame.Surface((OBSERVATION_SIZE, OBSERVATION_SIZE), pygame.SRCALPHA)
        globe.blit(rotated, rotated.get_rect(center=globe.get_rect().center))

        if self.storm_intensity > 0.01:
            darkness = pygame.Surface(globe.get_size(), pygame.SRCALPHA)
            darkness.fill((16, 22, 35, int(38 + 65 * self.storm_intensity)))
            globe.blit(darkness, (0, 0))

            rain_count = int(20 + 45 * self.storm_intensity)
            for _ in range(rain_count):
                x = random.randrange(0, OBSERVATION_SIZE)
                y = random.randrange(0, OBSERVATION_SIZE)
                length = random.randrange(8, 25)
                pygame.draw.line(
                    globe,
                    (155, 176, 196),
                    (x, y),
                    (x - int(length * 0.45), y + length),
                    1,
                )

        globe.blit(self.globe_vignette, (0, 0))
        globe.blit(self.globe_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        pygame.draw.rect(self.screen, (9, 12, 18), (0, 0, VIEW_W, SCREEN_H))
        shadow = pygame.Surface((OBSERVATION_SIZE, OBSERVATION_SIZE), pygame.SRCALPHA)
        shadow_rect = pygame.Rect(16, 51, OBSERVATION_SIZE - 32, OBSERVATION_SIZE - 82)
        pygame.draw.ellipse(shadow, (0, 0, 0, 155), shadow_rect)
        self.screen.blit(shadow, (OBSERVATION_RECT.left + 7, OBSERVATION_RECT.top + 9))
        self.screen.blit(globe, OBSERVATION_RECT)

        rim = pygame.Rect(
            OBSERVATION_RECT.left + 14,
            OBSERVATION_RECT.top + 43,
            OBSERVATION_SIZE - 28,
            OBSERVATION_SIZE - 86,
        )
        pygame.draw.ellipse(self.screen, (91, 111, 130), rim, 2)

        if self.storm_intensity > 0.01:
            storm_label = pygame.Rect(OBSERVATION_RECT.left + 14, 14, 215, 48)
            label_surface = pygame.Surface(storm_label.size, pygame.SRCALPHA)
            label_surface.fill((20, 5, 9, 215))
            self.screen.blit(label_surface, storm_label)
            pygame.draw.rect(self.screen, RED, storm_label, 1, border_radius=5)
            self.draw_text("폭풍", (storm_label.x + 10, storm_label.y + 5), self.font_sm, (255, 88, 88))
            self.draw_text("나침반을 기준으로 방향 유지", (storm_label.x + 10, storm_label.y + 25), self.font_xs, TEXT)

    def draw_map_overlay(self) -> None:
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((8, 10, 14, 230))
        self.screen.blit(overlay, (0, 0))
        map_rect = pygame.Rect(74, 62, SCREEN_W - 148, SCREEN_H - 124)
        pygame.draw.rect(self.screen, (235, 226, 207), map_rect)
        map_scale = min(map_rect.width / self.map_w, map_rect.height / self.map_h)
        map_size = (int(self.map_w * map_scale), int(self.map_h * map_scale))
        map_large = pygame.transform.smoothscale(self.map_surface, map_size)
        map_large_rect = map_large.get_rect(center=map_rect.center)
        self.screen.blit(map_large, map_large_rect)
        pygame.draw.rect(self.screen, (184, 167, 137), map_rect, 2)
        self.draw_text("원본 항로 지도", (map_rect.x, 20), self.font_lg, TEXT)
        self.draw_text("M을 놓으면 닫힙니다", (map_rect.right, 29),
                       self.font_sm, MUTED, "topright")

    def draw_end_overlay(self) -> None:
        if self.game_state == "playing":
            return
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((8, 10, 14, 215))
        self.screen.blit(overlay, (0, 0))
        title = "항로 비행 완료" if self.game_state == "success" else "비행 실패"
        color = GREEN if self.game_state == "success" else RED
        self.draw_text(title, (SCREEN_W // 2, 270), self.font_xl, color, "center")
        sub = "파비앵은 붉은 항로를 따라 보라색 도착점에 도달했습니다." if self.game_state == "success" else self.message
        self.draw_text(sub, (SCREEN_W // 2, 330), self.font_md, TEXT, "center")
        self.draw_text("ENTER: 다시 시작   ESC: 종료", (SCREEN_W // 2, 380), self.font_sm, MUTED, "center")

    def draw(self) -> None:
        self.screen.fill(BG)
        self.draw_left_view()
        self.apply_observation_globe()
        self.draw_right_panel()
        self.draw_message()
        if pygame.key.get_pressed()[pygame.K_m]:
            self.draw_map_overlay()
        self.draw_end_overlay()
        pygame.display.flip()

    def run(self) -> None:
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for event in pygame.event.get():
                self.handle_event(event)
            self.update_flight(dt)
            self.draw()


if __name__ == "__main__":
    NightFlightGame().run()

