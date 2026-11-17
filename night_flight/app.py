from __future__ import annotations

import pygame

from .aircraft import Aircraft
from .assets import GameAssets
from .assistant import Assistant, AssistantTask
from .config import FPS, OBSERVATION_RECT, SCREEN_H, SCREEN_W, VIEW_W
from .mess import MessSystem
from .mission import Mission
from .navigation import NavigationSystem
from .renderer import GameRenderer
from .storm import Storm
from .terrain import TerrainMap
from .ui import UIManager
from .utils import bearing_between, compass_name, distance


class GameApp:
    """게임 객체들을 조립하고 입력·업데이트·렌더링 순서를 관리한다."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("야간 비행 — 파비앵의 첫 항로")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.running = True

        self.assets, self.route = GameAssets.load()
        map_w, map_h = self.assets.map_surface.get_size()
        self.terrain = TerrainMap(map_w, map_h)
        self.aircraft = Aircraft()
        self.navigation = NavigationSystem(map_w, map_h)
        self.storm = Storm()
        self.assistant = Assistant()
        self.mess = MessSystem()
        self.mission = Mission()
        self.ui = UIManager()
        self.base_wind = pygame.Vector2(0.20, 0.05)
        self.reset()
        self.renderer = GameRenderer(self)

    def reset(self) -> None:
        self.route.reset()
        heading = bearing_between(self.route.start, self.route.points[1])
        self.aircraft.reset(heading)
        self.navigation.reset(self.route.start)
        self.storm.reset()
        self.assistant.reset()
        self.mess.reset()
        self.mission.reset()
        self.navigation.update_visibility(12)

    def current_clearance(self) -> float:
        return self.terrain.clearance(
            self.navigation.actual_position,
            self.aircraft.altitude,
        )

    def post_message(self, text: str, duration: float = 5.0) -> None:
        self.mission.post_message(text, duration)

    def trigger_mess(self, cause: str) -> None:
        gauge = self.mess.trigger(cause)
        if gauge is not None:
            self.post_message(
                f"엉망! 원인: {cause}. {gauge} 수치를 확인할 수 없습니다.",
                9.0,
            )

    def start_assistant_task(self, command: str) -> None:
        if self.assistant.task is not None:
            error = self.assistant.start(command)
            if error:
                self.post_message(error)
            return
        if command == "organize" and not self.mess.hidden_gauges:
            self.post_message("정리할 문제가 없습니다.")
            return
        error = self.assistant.start(command)
        if error:
            self.post_message(error)

    def finish_assistant_task(self, task: AssistantTask) -> None:
        if task.kind == "terrain" and task.target is not None:
            elevation = int(round(self.terrain.height_at(task.target) / 50) * 50)
            self.post_message(f"보고: 지정 좌표의 지형 고도는 약 {elevation}m입니다.", 8.0)
            return

        if task.kind == "radio":
            position = self.navigation.actual_position
            nearest_index = self.route.nearest_tower_index(position)
            tower = self.route.towers[nearest_index]
            self.navigation.known_towers.add(nearest_index)
            bearing = bearing_between(position, tower)
            tower_distance = int(distance(position, tower))
            bearing_degrees = int(round(bearing)) % 360
            self.navigation.correct_position(0.72)
            self.post_message(
                f"교신 성공: 송신탑은 {compass_name(bearing)}쪽 {bearing_degrees:03d}°, "
                f"약 {tower_distance} 지도단위에 있습니다.",
                9.0,
            )
            return

        if task.kind == "organize":
            restored = self.mess.restore_one() or "계기"
            self.post_message(f"기내 정리 완료: {restored} 계기를 다시 확인할 수 있습니다.", 7.0)
            return

        if task.kind == "weather":
            if self.mission.flight_time < 28:
                self.assistant.weather_report = "전방 40초: 약한 측풍, 시야 양호"
            elif self.mission.flight_time < 55:
                self.assistant.weather_report = "전방 25초: 구름 증가, 돌풍 가능"
            else:
                self.assistant.weather_report = "전방: 비구름, 보고 시각 8분 전"
            self.post_message(f"기상보고: {self.assistant.weather_report}", 9.0)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
                return
            if event.key == pygame.K_RETURN and self.mission.game_state != "playing":
                self.reset()
                return
            if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                self.aircraft.speed_level = event.key - pygame.K_0
            if event.key == pygame.K_x and self.assistant.cancel():
                self.post_message("무선사 작업을 취소했습니다.")

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse = pygame.Vector2(event.pos)
            if mouse.x < VIEW_W:
                world = self.navigation.screen_to_world(
                    mouse,
                    OBSERVATION_RECT,
                    self.storm.rotation,
                    self.storm.intensity,
                    self.storm.visual_scale,
                )
                if world is not None:
                    self.assistant.select(world, mouse)
                    self.post_message(
                        f"좌표 선택: X {int(world.x):04d}, Y {int(world.y):04d}. "
                        "지형 조회를 명령할 수 있습니다.",
                        5.0,
                    )
            else:
                command = self.ui.command_at(event.pos)
                if command is not None:
                    self.start_assistant_task(command)

    def update(self, dt: float) -> None:
        if self.mission.game_state != "playing":
            return

        self.mission.advance(dt)
        keys = pygame.key.get_pressed()
        self.aircraft.update_controls(keys, dt)
        storm_started = self.storm.update(self.mission.flight_time, dt, self.aircraft)
        if storm_started:
            self.post_message(
                "폭풍 진입! 좌측 화면이 흔들립니다. 우측 나침반을 기준으로 방향을 유지하십시오.",
                11.0,
            )

        aircraft_update = self.aircraft.update(
            dt,
            self.mission.flight_time,
            self.storm.intensity,
            bool(keys[pygame.K_a]),
        )
        if aircraft_update.rapid_climb_cause:
            self.trigger_mess(aircraft_update.rapid_climb_cause)
        if aircraft_update.high_altitude_warning:
            self.post_message("고도 안정 구간 초과! 기체 기능이 손상되고 있습니다.", 7.0)

        self.navigation.move(
            self.aircraft.heading,
            self.aircraft.speed_world,
            self.base_wind,
            self.storm.wind,
            self.storm.intensity,
            dt,
        )
        newly_hidden = self.mess.update_stress(
            self.aircraft.stress,
            aircraft_update.dominant_stress_cause,
        )
        for gauge in newly_hidden:
            self.post_message(
                f"엉망! 원인: {aircraft_update.dominant_stress_cause}. "
                f"{gauge} 수치를 확인할 수 없습니다.",
                9.0,
            )

        if self.route.update_progress(self.navigation.actual_position):
            if self.route.index < len(self.route.points):
                self.post_message(
                    "항로 꺾임점 통과. 우측 원본 지도를 확인해 다음 방향으로 선회하십시오.",
                    9.0,
                )

        finished_task = self.assistant.update(dt)
        if finished_task is not None:
            self.finish_assistant_task(finished_task)

        self.mission.update_tutorial(self.aircraft, self.route, dt)
        visible_size = self.storm.visibility_grid_size(self.mission.flight_time)
        self.navigation.update_visibility(visible_size)
        self.mission.check_outcome(self.aircraft, self.navigation, self.terrain, self.route)

    def run(self) -> None:
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.renderer.draw()
        pygame.quit()
