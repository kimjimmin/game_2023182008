from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

from .config import (
    ALTITUDE_LIMIT,
    ALTITUDE_SAFE_MAX,
    ALTITUDE_SAFE_MIN,
    AMBER,
    BG,
    CYAN,
    GREEN,
    HORIZON_BLUE,
    MUTED,
    OBSERVATION_RECT,
    OBSERVATION_SIZE,
    PANEL_BG,
    PANEL_LINE,
    PANEL_W,
    PURPLE,
    RED,
    SCREEN_H,
    SCREEN_W,
    TEXT,
    VIEW_W,
)
from .utils import bearing_between, clamp, distance, load_font

if TYPE_CHECKING:
    from .app import GameApp


class GameRenderer:
    """게임 상태를 변경하지 않고 화면에 표현한다."""

    def __init__(self, game: GameApp) -> None:
        self.game = game
        self.screen = game.screen
        self.map_surface = game.assets.map_surface
        self.world_surface = game.assets.world_surface
        self.player_base = game.assets.player_surface
        self.assistant_surface = game.assets.assistant_surface
        self.map_w, self.map_h = self.map_surface.get_size()

        self.font_xs = load_font(14)
        self.font_sm = load_font(17)
        self.font_md = load_font(21)
        self.font_lg = load_font(28, bold=True)
        self.font_xl = load_font(38, bold=True)
        self.globe_mask, self.globe_vignette = self._make_globe_effects()

    @staticmethod
    def _make_globe_effects() -> tuple[pygame.Surface, pygame.Surface]:
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

    def draw_text(
        self,
        text: str,
        pos: tuple[int, int] | pygame.Vector2,
        font: pygame.font.Font | None = None,
        color: tuple[int, int, int] = TEXT,
        anchor: str = "topleft",
    ) -> pygame.Rect:
        font = font or self.font_sm
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        setattr(rect, anchor, pos)
        self.screen.blit(surface, rect)
        return rect

    def draw_left_view(self) -> None:
        chart_rect = OBSERVATION_RECT
        self.draw_observation_chart(chart_rect, show_estimate=False)
        _, scale, origin = self.game.navigation.chart_geometry(chart_rect)

        def chart_point(point: pygame.Vector2) -> pygame.Vector2:
            return pygame.Vector2(origin.x + point.x * scale, origin.y + point.y * scale)

        plane_position = pygame.Vector2(chart_rect.center)
        plane = pygame.transform.rotozoom(
            self.player_base,
            -self.game.aircraft.heading,
            0.30,
        )
        self.screen.blit(plane, plane.get_rect(center=plane_position))

        selected_world = self.game.assistant.selected_world
        if selected_world is not None:
            point = chart_point(selected_world)
            pygame.draw.circle(self.screen, CYAN, point, 11, 2)
            pygame.draw.line(self.screen, CYAN, (point.x - 15, point.y), (point.x + 15, point.y), 1)
            pygame.draw.line(self.screen, CYAN, (point.x, point.y - 15), (point.x, point.y + 15), 1)

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
            legend_y = 72 + index * 20
            pygame.draw.rect(self.screen, color, (text_x, legend_y, 16, 14))
            pygame.draw.rect(self.screen, (80, 82, 86), (text_x, legend_y, 16, 14), 1)
            self.draw_text(label, (text_x + 22, legend_y - 2), self.font_xs, (74, 77, 82))

        clearance = int(self.game.current_clearance())
        terrain = int(self.game.terrain.height_at(self.game.navigation.actual_position))
        self.draw_text(
            f"추정 지상 여유 {clearance}m",
            (text_x, SCREEN_H - 54),
            self.font_sm,
            GREEN if clearance > 250 else AMBER if clearance > 100 else RED,
        )
        self.draw_text(
            f"현재 지형 추정 {terrain}m",
            (text_x, SCREEN_H - 30),
            self.font_xs,
            (92, 96, 103),
        )

    def draw_gauge(
        self,
        rect: pygame.Rect,
        title: str,
        value: str,
        ratio: float,
        color: tuple[int, int, int],
        hidden: bool = False,
    ) -> None:
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

    def draw_altitude_gauge(self, rect: pygame.Rect, hidden: bool = False) -> None:
        aircraft = self.game.aircraft
        pygame.draw.rect(self.screen, (28, 31, 41), rect, border_radius=6)
        pygame.draw.rect(self.screen, PANEL_LINE, rect, 1, border_radius=6)
        if hidden:
            pygame.draw.rect(self.screen, (0, 0, 0), rect.inflate(-4, -4), border_radius=4)
            self.draw_text("엉망!", rect.center, self.font_md, (238, 47, 47), "center")
            return

        if aircraft.altitude > ALTITUDE_SAFE_MAX:
            title, value_color = "고도 · 기능 손상", RED
        elif aircraft.altitude < ALTITUDE_SAFE_MIN:
            title, value_color = "고도 · 상승 필요", AMBER
        else:
            title, value_color = "고도 · 안정 구간", GREEN
        self.draw_text(title, (rect.x + 10, rect.y + 7), self.font_xs, MUTED)
        self.draw_text(
            f"{int(aircraft.altitude)}m",
            (rect.right - 10, rect.y + 5),
            self.font_md,
            value_color,
            "topright",
        )

        bar = pygame.Rect(rect.x + 10, rect.bottom - 13, rect.width - 20, 7)
        safe_start = int(bar.width * ALTITUDE_SAFE_MIN / ALTITUDE_LIMIT)
        safe_end = int(bar.width * ALTITUDE_SAFE_MAX / ALTITUDE_LIMIT)
        pygame.draw.rect(
            self.screen,
            (116, 85, 33),
            pygame.Rect(bar.x, bar.y, safe_start, bar.height),
            border_radius=3,
        )
        pygame.draw.rect(
            self.screen,
            (70, 157, 105),
            pygame.Rect(bar.x + safe_start, bar.y, safe_end - safe_start, bar.height),
        )
        pygame.draw.rect(
            self.screen,
            (145, 50, 48),
            pygame.Rect(bar.x + safe_end, bar.y, bar.width - safe_end, bar.height),
            border_radius=3,
        )
        marker_x = bar.x + int(bar.width * clamp(aircraft.altitude / ALTITUDE_LIMIT, 0.0, 1.0))
        pygame.draw.line(
            self.screen,
            (246, 243, 232),
            (marker_x, bar.y - 3),
            (marker_x, bar.bottom + 3),
            2,
        )

    def draw_observation_chart(self, rect: pygame.Rect, show_estimate: bool = True) -> None:
        pygame.draw.rect(self.screen, (247, 247, 243), rect)
        pygame.draw.rect(self.screen, (72, 75, 82), rect, 2)
        navigation = self.game.navigation
        aircraft = self.game.aircraft
        route = self.game.route
        _, scale, origin = navigation.chart_geometry(rect)
        displayed_tiles = navigation.current_visible
        grid_size = self.game.storm.visibility_grid_size(self.game.mission.flight_time)
        visible_size = grid_size * navigation.tile_world * scale
        visibility_rect = pygame.Rect(0, 0, math.ceil(visible_size), math.ceil(visible_size))
        visibility_rect.center = rect.center
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(previous_clip.clip(visibility_rect).clip(rect))

        for tx, ty in displayed_tiles:
            center = pygame.Vector2(
                (tx + 0.5) * navigation.tile_world,
                (ty + 0.5) * navigation.tile_world,
            )
            elevation = self.game.terrain.height_at(center)
            if elevation < 250:
                color, contour, contour_width = (218, 224, 214), (190, 200, 188), 0
            elif elevation < 500:
                color, contour, contour_width = (225, 201, 183), (194, 155, 137), 1
            elif elevation < 850:
                color, contour, contour_width = (213, 157, 139), (173, 100, 91), 2
            elif elevation < 1250:
                color, contour, contour_width = (185, 103, 96), (126, 57, 59), 3
            elif elevation < 1750:
                color, contour, contour_width = (135, 60, 66), (76, 29, 38), 4
            else:
                color, contour, contour_width = (74, 25, 36), (31, 10, 18), 5
            tile_rect = pygame.Rect(
                int(origin.x + tx * navigation.tile_world * scale),
                int(origin.y + ty * navigation.tile_world * scale),
                max(1, int(navigation.tile_world * scale + 1)),
                max(1, int(navigation.tile_world * scale + 1)),
            )
            if not tile_rect.colliderect(rect):
                continue
            pygame.draw.rect(self.screen, color, tile_rect)
            if contour_width > 0:
                pygame.draw.rect(
                    self.screen,
                    contour,
                    tile_rect,
                    max(1, min(contour_width, tile_rect.width // 3, tile_rect.height // 3)),
                )
            if aircraft.altitude - elevation <= 150:
                pygame.draw.rect(
                    self.screen,
                    (242, 35, 35),
                    tile_rect,
                    max(1, min(3, tile_rect.width // 2)),
                )

        def chart_point(point: pygame.Vector2) -> pygame.Vector2:
            return pygame.Vector2(origin.x + point.x * scale, origin.y + point.y * scale)

        for village in route.villages:
            key = (int(village.x // navigation.tile_world), int(village.y // navigation.tile_world))
            point = chart_point(village)
            if key in displayed_tiles and rect.collidepoint(point):
                pygame.draw.circle(self.screen, (200, 83, 134), point, max(3, int(6 * scale + 2)))
        start_key = (
            int(route.start.x // navigation.tile_world),
            int(route.start.y // navigation.tile_world),
        )
        start_point = chart_point(route.start)
        if start_key in displayed_tiles and rect.collidepoint(start_point):
            pygame.draw.circle(self.screen, (25, 25, 25), start_point, 3)
        destination_key = (
            int(route.destination.x // navigation.tile_world),
            int(route.destination.y // navigation.tile_world),
        )
        destination_point = chart_point(route.destination)
        if destination_key in displayed_tiles and rect.collidepoint(destination_point):
            pygame.draw.circle(self.screen, PURPLE, destination_point, 4)
        self.screen.set_clip(previous_clip)

        if show_estimate:
            estimate = chart_point(navigation.estimated_position)
            error = max(
                4,
                int((distance(navigation.actual_position, navigation.estimated_position) + 12) * scale),
            )
            pygame.draw.circle(self.screen, (50, 88, 107), estimate, error, 1)
            pygame.draw.circle(self.screen, (38, 113, 151), estimate, 3)

    def draw_right_panel(self) -> None:
        aircraft = self.game.aircraft
        route = self.game.route
        assistant = self.game.assistant
        hidden = self.game.mess.hidden_gauges
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
        self.screen.blit(map_thumb, map_thumb.get_rect(center=map_thumb_rect.center))
        pygame.draw.rect(self.screen, (72, 75, 82), map_thumb_rect, 2)

        x = VIEW_W + 18
        width = (PANEL_W - 43) // 2
        height = 52
        col2 = x + width + 7
        self.draw_altitude_gauge(pygame.Rect(x, 163, width, height), "고도" in hidden)
        self.draw_gauge(
            pygame.Rect(col2, 163, width, height),
            "나침반",
            f"{int(aircraft.heading):03d}°",
            aircraft.heading / 360,
            CYAN,
            "나침반" in hidden,
        )
        self.draw_gauge(
            pygame.Rect(x, 220, width, height),
            "연료",
            f"{int(aircraft.fuel)}%",
            aircraft.fuel / 100,
            GREEN if aircraft.fuel > 25 else RED,
            "연료" in hidden,
        )
        self.draw_gauge(
            pygame.Rect(col2, 220, width, height),
            "속도",
            f"{aircraft.speed_level}단계",
            aircraft.speed_level / 5,
            AMBER if aircraft.speed_level >= 4 else GREEN,
            "속도" in hidden,
        )
        self.draw_gauge(
            pygame.Rect(x, 277, width, height),
            "기체 부담",
            f"{int(aircraft.stress)}%",
            aircraft.stress / 100,
            RED if aircraft.stress > 70 else AMBER,
            "기체 부담" in hidden,
        )
        self.draw_gauge(
            pygame.Rect(col2, 277, width, height),
            "기체 상태",
            f"{int(aircraft.durability)}%",
            aircraft.durability / 100,
            GREEN if aircraft.durability > 40 else RED,
            "기체 상태" in hidden,
        )

        weather_rect = pygame.Rect(x, 334, PANEL_W - 36, 63)
        pygame.draw.rect(self.screen, (28, 31, 41), weather_rect, border_radius=6)
        self.draw_text("운항 상태", (weather_rect.x + 10, weather_rect.y + 6), self.font_xs, AMBER)
        self.draw_text(
            f"항로 구간 {min(route.index, len(route.points) - 1)}/{len(route.points) - 1}",
            (weather_rect.x + 10, weather_rect.y + 23),
            self.font_xs,
            TEXT,
        )
        self.draw_text(
            f"기상: {assistant.weather_report}",
            (weather_rect.x + 10, weather_rect.y + 43),
            self.font_xs,
            MUTED,
        )

        portrait_rect = pygame.Rect(VIEW_W, 403, PANEL_W, 111)
        crop = self.assistant_surface.subsurface((0, 0, PANEL_W, 220))
        self.screen.blit(crop, portrait_rect, area=pygame.Rect(0, 18, PANEL_W, 111))
        shade = pygame.Surface(portrait_rect.size, pygame.SRCALPHA)
        shade.fill((12, 15, 24, 105))
        self.screen.blit(shade, portrait_rect)
        self.draw_text("무선사", (x, 410), self.font_md, TEXT)
        if assistant.task:
            progress = 1 - assistant.task.remaining / assistant.task.duration
            self.draw_text(assistant.task.label, (x + 88, 414), self.font_sm, AMBER)
            task_bar = pygame.Rect(x + 88, 446, PANEL_W - 124, 7)
            pygame.draw.rect(self.screen, (48, 51, 61), task_bar, border_radius=4)
            filled = task_bar.copy()
            filled.width = int(task_bar.width * progress)
            pygame.draw.rect(self.screen, AMBER, filled, border_radius=4)
            self.draw_text("X 취소", (x, 442), self.font_xs, MUTED)
        else:
            self.draw_text("명령 대기 중", (x + 88, 414), self.font_sm, GREEN)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.game.ui.buttons:
            hover = button.rect.collidepoint(mouse_pos)
            base = (48, 52, 64) if hover else (34, 37, 47)
            pygame.draw.rect(self.screen, base, button.rect, border_radius=5)
            pygame.draw.rect(
                self.screen,
                AMBER if hover else PANEL_LINE,
                button.rect,
                1,
                border_radius=5,
            )
            self.draw_text(button.label, (button.rect.x + 10, button.rect.y + 2), self.font_sm, TEXT)
            self.draw_text(
                button.subtitle,
                (button.rect.x + 205, button.rect.y + 9),
                self.font_xs,
                MUTED,
            )

    def draw_message(self) -> None:
        mission = self.game.mission
        if mission.message_timer <= 0 and mission.game_state == "playing":
            return
        rect = pygame.Rect(64, SCREEN_H - 102, VIEW_W - 128, 68)
        surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        surface.fill((12, 14, 18, 220))
        self.screen.blit(surface, rect)
        pygame.draw.rect(self.screen, (158, 142, 103), rect, 1, border_radius=6)
        self.draw_text("운항 지시", (rect.x + 14, rect.y + 9), self.font_xs, AMBER)
        self.draw_text(mission.message, (rect.x + 14, rect.y + 31), self.font_sm, TEXT)

    def apply_observation_globe(self) -> None:
        storm = self.game.storm
        source = self.screen.subsurface(OBSERVATION_RECT).copy()
        angle = storm.rotation if storm.intensity > 0.01 else 0.0
        scale = storm.visual_scale if storm.intensity > 0.01 else 1.0
        rotated = pygame.transform.rotozoom(source, angle, scale)
        globe = pygame.Surface((OBSERVATION_SIZE, OBSERVATION_SIZE), pygame.SRCALPHA)
        globe.blit(rotated, rotated.get_rect(center=globe.get_rect().center))

        if storm.intensity > 0.01:
            darkness = pygame.Surface(globe.get_size(), pygame.SRCALPHA)
            darkness.fill((16, 22, 35, int(38 + 65 * storm.intensity)))
            globe.blit(darkness, (0, 0))
            rain_count = int(20 + 45 * storm.intensity)
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
        if storm.intensity > 0.01:
            storm_label = pygame.Rect(OBSERVATION_RECT.left + 14, 14, 215, 48)
            label_surface = pygame.Surface(storm_label.size, pygame.SRCALPHA)
            label_surface.fill((20, 5, 9, 215))
            self.screen.blit(label_surface, storm_label)
            pygame.draw.rect(self.screen, RED, storm_label, 1, border_radius=5)
            self.draw_text("폭풍", (storm_label.x + 10, storm_label.y + 5), self.font_sm, (255, 88, 88))
            self.draw_text(
                "나침반을 기준으로 방향 유지",
                (storm_label.x + 10, storm_label.y + 25),
                self.font_xs,
                TEXT,
            )

    def draw_known_tower_markers(self) -> None:
        navigation = self.game.navigation
        storm = self.game.storm
        route = self.game.route
        _, scale, origin = navigation.chart_geometry(OBSERVATION_RECT)
        globe_center = pygame.Vector2(OBSERVATION_RECT.center)
        angle = storm.rotation if storm.intensity > 0.01 else 0.0
        visual_scale = storm.visual_scale if storm.intensity > 0.01 else 1.0

        for index in navigation.known_towers:
            source_point = origin + route.towers[index] * scale
            point = globe_center + (source_point - globe_center).rotate(-angle) * visual_scale
            nx = (point.x - globe_center.x) / (OBSERVATION_SIZE * 0.48)
            ny = (point.y - globe_center.y) / (OBSERVATION_SIZE * 0.44)
            ellipse_distance = math.sqrt(nx * nx + ny * ny)
            if ellipse_distance > 0.92:
                point = globe_center + (point - globe_center) * (0.92 / ellipse_distance)
            pygame.draw.circle(self.screen, (255, 220, 48), point, 9)
            pygame.draw.circle(self.screen, (104, 78, 8), point, 9, 2)
            pygame.draw.circle(self.screen, (255, 248, 176), point, 3)

            bearing = bearing_between(navigation.actual_position, route.towers[index])
            bearing_text = f"{int(round(bearing)) % 360:03d}°"
            label_surface = self.font_xs.render(bearing_text, True, (255, 232, 91))
            label_rect = label_surface.get_rect()
            if point.x < globe_center.x:
                label_rect.midleft = (int(point.x + 13), int(point.y))
            else:
                label_rect.midright = (int(point.x - 13), int(point.y))
            label_back = label_rect.inflate(8, 5)
            pygame.draw.rect(self.screen, (30, 24, 7), label_back, border_radius=4)
            pygame.draw.rect(self.screen, (162, 128, 19), label_back, 1, border_radius=4)
            self.screen.blit(label_surface, label_rect)

    def draw_horizon_indicator(self) -> None:
        center = pygame.Vector2(OBSERVATION_RECT.centerx, OBSERVATION_RECT.top + 80)
        backing = pygame.Rect(0, 0, 210, 54)
        backing.center = center
        backing_surface = pygame.Surface(backing.size, pygame.SRCALPHA)
        backing_surface.fill((5, 19, 31, 180))
        self.screen.blit(backing_surface, backing)
        pygame.draw.rect(self.screen, (36, 116, 168), backing, 2, border_radius=8)

        length = 168
        angle = math.radians(-self.game.aircraft.bank)
        line = pygame.Vector2(math.cos(angle), math.sin(angle)) * length / 2
        pygame.draw.line(self.screen, (9, 42, 67), center - line, center + line, 9)
        pygame.draw.line(self.screen, HORIZON_BLUE, center - line, center + line, 5)
        pygame.draw.circle(self.screen, (9, 42, 67), center, 10)
        pygame.draw.circle(self.screen, HORIZON_BLUE, center, 8, 3)
        pygame.draw.line(
            self.screen,
            HORIZON_BLUE,
            (center.x, center.y - 20),
            (center.x, center.y + 20),
            3,
        )

    def draw_fixed_view_alerts(self) -> None:
        if self.game.mess.last_cause != "없음":
            cause_rect = pygame.Rect(OBSERVATION_RECT.left + 245, 12, 455, 42)
            cause_surface = pygame.Surface(cause_rect.size, pygame.SRCALPHA)
            cause_surface.fill((28, 5, 8, 226))
            self.screen.blit(cause_surface, cause_rect)
            pygame.draw.rect(self.screen, RED, cause_rect, 1, border_radius=5)
            self.draw_text(
                f"최근 엉망 원인: {self.game.mess.last_cause}",
                cause_rect.center,
                self.font_sm,
                (255, 78, 78),
                "center",
            )

        clearance = int(self.game.current_clearance())
        if clearance <= 150:
            warning_rect = pygame.Rect(OBSERVATION_RECT.centerx - 175, 155, 350, 42)
            pygame.draw.rect(self.screen, (42, 4, 7), warning_rect, border_radius=5)
            pygame.draw.rect(self.screen, (242, 35, 35), warning_rect, 2, border_radius=5)
            self.draw_text(
                f"지형 접근 경고 · 여유 고도 {clearance}m",
                warning_rect.center,
                self.font_md,
                (255, 74, 74),
                "center",
            )

    def draw_map_overlay(self) -> None:
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((8, 10, 14, 230))
        self.screen.blit(overlay, (0, 0))
        map_rect = pygame.Rect(74, 62, SCREEN_W - 148, SCREEN_H - 124)
        pygame.draw.rect(self.screen, (235, 226, 207), map_rect)
        map_scale = min(map_rect.width / self.map_w, map_rect.height / self.map_h)
        map_size = (int(self.map_w * map_scale), int(self.map_h * map_scale))
        map_large = pygame.transform.smoothscale(self.map_surface, map_size)
        self.screen.blit(map_large, map_large.get_rect(center=map_rect.center))
        pygame.draw.rect(self.screen, (184, 167, 137), map_rect, 2)
        self.draw_text("원본 항로 지도", (map_rect.x, 20), self.font_lg, TEXT)
        self.draw_text(
            "M을 놓으면 닫힙니다",
            (map_rect.right, 29),
            self.font_sm,
            MUTED,
            "topright",
        )

    def draw_end_overlay(self) -> None:
        mission = self.game.mission
        if mission.game_state == "playing":
            return
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((8, 10, 14, 215))
        self.screen.blit(overlay, (0, 0))
        title = "항로 비행 완료" if mission.game_state == "success" else "비행 실패"
        color = GREEN if mission.game_state == "success" else RED
        self.draw_text(title, (SCREEN_W // 2, 270), self.font_xl, color, "center")
        subtitle = (
            "파비앵은 붉은 항로를 따라 보라색 도착점에 도달했습니다."
            if mission.game_state == "success"
            else mission.message
        )
        self.draw_text(subtitle, (SCREEN_W // 2, 330), self.font_md, TEXT, "center")
        self.draw_text(
            "ENTER: 다시 시작   ESC: 종료",
            (SCREEN_W // 2, 380),
            self.font_sm,
            MUTED,
            "center",
        )

    def draw(self) -> None:
        self.screen.fill(BG)
        self.draw_left_view()
        self.apply_observation_globe()
        self.draw_known_tower_markers()
        self.draw_horizon_indicator()
        self.draw_fixed_view_alerts()
        self.draw_right_panel()
        self.draw_message()
        if pygame.key.get_pressed()[pygame.K_m]:
            self.draw_map_overlay()
        self.draw_end_overlay()
        pygame.display.flip()
