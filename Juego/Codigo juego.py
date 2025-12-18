from PyQt6.QtWidgets import QApplication, QWidget, QLabel
from PyQt6.QtCore import Qt, QTimer, QUrl, QTime
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QPixmap
from pathlib import Path
from gpiozero import Button
import json
import sys
import vlc

LANES = 5
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 800
HIT_LINE_Y = 550
NOTE_SPEED = 4
FRAME_MS = 16
SPAWN_Y = -60
BUTTON_PINS = [17,27,22,23,24]


class Note:
    def __init__(self, lane, y):
        self.lane = lane
        self.y = y
        self.hit = False
        
class HitEffect:
    def __init__(self, lane, frames):
        self.lane = lane
        self.frames = frames


def load_song(folder: Path):
    config_path = folder / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    audio_path = folder / config["audio"]
    background_path = folder / config["background"]
    chart_path = folder / config["chart"]
    chart_raw = json.loads(chart_path.read_text(encoding="utf-8"))
    chart = [(int(t), int(l)) for t, l in chart_raw]
    offset = int(config.get("offset_ms", 0))
    return {
        "name": config["name"],
        "audio": str(audio_path),
        "background": str(background_path),
        "chart": chart,
        "offset": offset,
    }


class GameWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setWindowTitle("Guitar Raspi")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.mode = "menu"
        self.songs = []
        self.selected_song = 0
        self.current_song = None

        songs_root = Path(__file__).parent / "songs"
        if songs_root.exists():
            for sub in songs_root.iterdir():
                if sub.is_dir() and (sub / "config.json").exists():
                    self.songs.append(load_song(sub))

        self.background_image = QPixmap()
        self.notes = []
        self.score = 0

        self.score_label = QLabel("Puntaje: 0", self)
        self.score_label.setFont(QFont("Arial", 16))
        self.score_label.setStyleSheet("color: white;")
        self.score_label.move(10, 10)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.game_loop)
        self.timer.start(FRAME_MS)

        self.keys_for_lane = {
            Qt.Key.Key_A: 0,
            Qt.Key.Key_S: 1,
            Qt.Key.Key_D: 2,
            Qt.Key.Key_K: 3,
            Qt.Key.Key_L: 4,
        }
        
        self.buttons = [Button(pin) for pin in BUTTON_PINS]
        
        self.button_prev_state = [False] * LANES

        self.lane_colors = [
            QColor(255, 60, 60),
            QColor(60, 180, 255),
            QColor(255, 200, 0),
            QColor(120, 255, 120),
            QColor(200, 120, 255),
        ]

        self.hit_effects = []
        self.effect_frames = 12

        self.feedback_text = ""
        self.feedback_color = QColor(255, 255, 255)
        self.feedback_frames = 0
        self.max_feedback_frames = 30

        self.chart = []
        self.chart_index = 0
        self.offset_ms = 0
        self.travel_time_ms = 0

        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()
        self.player.audio_set_volume(80)
        self.start_time_ms = 0
        self._position = 0

    def start_song(self, idx: int):
        if not self.songs:
            return
        self.current_song = self.songs[idx]
        self.background_image = QPixmap(self.current_song["background"])
        self.chart = self.current_song["chart"]
        self.offset_ms = self.current_song["offset"]
        self.chart_index = 0
        self.notes = []
        self.hit_effects = []
        self.feedback_text = ""
        self.feedback_frames = 0
        self.score = 0
        self.score_label.setText("Puntaje: 0")

        dist_pixels = HIT_LINE_Y - SPAWN_Y
        px_per_ms = NOTE_SPEED / FRAME_MS
        self.travel_time_ms = dist_pixels / px_per_ms

        self.player.stop()
        media = self.vlc_instance.media_new(self.current_song["audio"])
        self.player.set_media(media)
        self.player.play()
        
        self.start_time_ms= QTime.currentTime().msecsSinceStartOfDay()
        self._position = 0
        
        self.mode = "game"

    def back_to_menu(self):
        self.player.stop()
        self.mode = "menu"
        self._position = 0
        self.notes = []
        self.hit_effects = []
        self.feedback_text = ""
        self.chart_index = 0

    def spawn_note_for_lane(self, lane):
        self.notes.append(Note(lane, SPAWN_Y))

    def game_loop(self):
    
        for lane, button in enumerate(self.buttons):
            pressed = button.is_pressed
            if pressed and not self.button_prev_state[lane]:
            
                self.check_hit(lane)
            self.button_prev_state[lane] = pressed
    
    
        if self.mode == "game":
            current_time_ms = QTime.currentTime().msecsSinceStartOfDay()
            current_ms = current_time_ms - self.start_time_ms
            
            lead_ms = self.travel_time_ms
            while (
                self.chart_index < len(self.chart)
                and current_ms
                >= self.chart[self.chart_index][0] - lead_ms + self.offset_ms
            ):
                _, lane = self.chart[self.chart_index]
                if 0 <= lane < LANES:
                    self.spawn_note_for_lane(lane)
                self.chart_index += 1

            for note in self.notes:
                note.y += NOTE_SPEED

            self.notes = [
                n for n in self.notes if n.y < WINDOW_HEIGHT + 80 and not n.hit
            ]

            for eff in self.hit_effects:
                eff.frames -= 1
            self.hit_effects = [e for e in self.hit_effects if e.frames > 0]

            if self.feedback_frames > 0:
                self.feedback_frames -= 1
                if self.feedback_frames == 0:
                    self.feedback_text = ""
        self.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)

        if self.mode == "menu":
            painter.fillRect(self.rect(), QColor(10, 10, 20))
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 26, QFont.Weight.Bold))
            painter.drawText(
                0,
                40,
                self.width(),
                40,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                "Seleccionar CanciÃ³n",
            )
            painter.setFont(QFont("Arial", 16))
            y0 = 120
            line_h = 32
            if not self.songs:
                painter.drawText(
                    0,
                    y0,
                    self.width(),
                    40,
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                    "No hay canciones en /songs",
                )
            else:
                for i, song in enumerate(self.songs):
                    color = QColor(255, 255, 0) if i == self.selected_song else QColor(
                        220, 220, 220
                    )
                    painter.setPen(color)
                    painter.drawText(
                        60,
                        y0 + i * line_h,
                        self.width() - 120,
                        line_h,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        song["name"],
                    )
            painter.setPen(QColor(180, 180, 180))
            painter.setFont(QFont("Arial", 12))
            painter.drawText(
                0,
                self.height() - 60,
                self.width(),
                20,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                "Arriba/Abajo o W/S para elegir, Enter para jugar, Esc para salir",
            )
            return

        if not self.background_image.isNull():
            painter.drawPixmap(self.rect(), self.background_image)
        else:
            painter.fillRect(self.rect(), QColor(20, 20, 20))

        lane_width = self.width() / LANES

        for lane in range(LANES):
            x = lane * lane_width
            painter.fillRect(int(x), 0, int(lane_width), self.height(), QColor(0, 0, 0, 150))
            painter.setPen(QColor(180, 180, 180, 200))
            painter.drawLine(int(x), 0, int(x), self.height())

        painter.setPen(QColor(255, 255, 255))
        painter.drawLine(0, HIT_LINE_Y, self.width(), HIT_LINE_Y)

        circle_size = 55
        for note in self.notes:
            color = self.lane_colors[note.lane]
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            center_x = note.lane * lane_width + lane_width / 2
            center_y = note.y
            painter.drawEllipse(
                int(center_x - circle_size / 2),
                int(center_y - circle_size / 2),
                circle_size,
                circle_size,
            )

        for eff in self.hit_effects:
            t = eff.frames / self.effect_frames
            base_size = 70
            size = base_size + 15 * (1 - t)
            color = self.lane_colors[eff.lane]
            pen_color = QColor(color.red(), color.green(), color.blue(), int(80 + 175 * t))
            pen = QPen(pen_color)
            pen.setWidth(4)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            center_x = eff.lane * lane_width + lane_width / 2
            center_y = HIT_LINE_Y
            painter.drawEllipse(
                int(center_x - size / 2),
                int(center_y - size / 2),
                int(size),
                int(size),
            )

        if self.feedback_frames > 0 and self.feedback_text:
            painter.setFont(QFont("Arial", 24, QFont.Weight.Bold))
            painter.setPen(self.feedback_color)
            painter.drawText(
                0,
                HIT_LINE_Y - 80,
                self.width(),
                40,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                self.feedback_text,
            )

    def keyPressEvent(self, event):
        key = event.key()

        if self.mode == "menu":
            if key in (Qt.Key.Key_Up, Qt.Key.Key_W):
                if self.songs:
                    self.selected_song = (self.selected_song - 1) % len(self.songs)
            elif key in (Qt.Key.Key_Down, Qt.Key.Key_S):
                if self.songs:
                    self.selected_song = (self.selected_song + 1) % len(self.songs)
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                self.start_song(self.selected_song)
            elif key == Qt.Key.Key_Escape:
                QApplication.quit()
            return

        if self.mode == "game":
            if key == Qt.Key.Key_Escape:
                self.back_to_menu()
                return
            if key in self.keys_for_lane:
                lane = self.keys_for_lane[key]
                self.check_hit(lane)

    def show_feedback(self, text, color):
        self.feedback_text = text
        self.feedback_color = color
        self.feedback_frames = self.max_feedback_frames

    def check_hit(self, lane):
        hit_window = 35
        best_note = None
        best_dist = hit_window

        for note in self.notes:
            if note.lane != lane or note.hit:
                continue
            dist = abs(note.y - HIT_LINE_Y)
            if dist <= best_dist:
                best_dist = dist
                best_note = note

        if best_note:
            best_note.hit = True
            self.score += 100
            self.score_label.setText(f"Puntaje: {self.score}")
            self.hit_effects.append(HitEffect(lane, self.effect_frames))
            if best_dist <= 10:
                self.show_feedback("PERFECTO", QColor(0, 255, 0))
            else:
                self.show_feedback("BIEN", QColor(255, 215, 0))
        else:
            self.show_feedback("FALLASTE", QColor(255, 80, 80))


def main():
    app = QApplication(sys.argv)
    game = GameWidget()
    game.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
