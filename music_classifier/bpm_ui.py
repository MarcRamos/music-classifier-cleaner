# bpm_ui.py
from os import environ

environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
import time
import os


def measure_bpm_ui(mp3_path):
    """
    Launch an interactive UI to measure the BPM of an MP3 track by tapping.

    This function opens a Pygame window that allows the user to play an MP3
    file and estimate its BPM by tapping the space bar in rhythm with the music.
    The BPM is calculated in real time using the average interval between taps.

    Controls
    --------
    Keyboard:
        SPACE : Register a tap to compute BPM
        ENTER : Save and confirm the current BPM value
        ESC   : Cancel and exit without saving

    Mouse (UI buttons):
        [> ]   : Play the track
        [||]   : Stop playback
        [R]    : Restart playback from the beginning and reset BPM calculation
        [>> ]  : Skip the track (exit without saving)

    Parameters
    ----------
    mp3_path : str
        Path to the MP3 file to be played and analyzed.

    Returns
    -------
    bpm : int or None
        The BPM value measured by the user. Returns ``None`` if the user cancels
        or skips the track.
    running : bool
        Indicates whether the application should continue processing more tracks.
        Returns ``False`` only when the user closes the window or presses ESC.

    Notes
    -----
    - BPM is computed as: ``60 / average_interval_between_taps``.
    - Only the most recent taps are used to smooth the BPM estimation.
    - Playback is handled using ``pygame.mixer.music``.
    - The UI runs at ~60 FPS and updates BPM in real time.

    Side Effects
    ------------
    - Initializes and quits Pygame and its mixer module.
    - Opens a graphical window.
    - Plays audio from the provided MP3 file.

    Examples
    --------
    >>> bpm, running = measure_bpm_ui("song.mp3")
    >>> if bpm:
    ...     print(f"Measured BPM: {bpm}")
    """

    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((800, 400))
    pygame.display.set_caption("BPM Tapper")
    font = pygame.font.SysFont("arial", 24)
    bpm_font = pygame.font.SysFont("arial", 64, bold=True)
    clock = pygame.time.Clock()

    taps = []
    bpm = 0
    playing = False

    # Buttons centered
    btn_width = 100
    btn_height = 40
    btn_gap = 20
    total_btns_width = btn_width * 4 + btn_gap * 3
    btn_start_x = (800 - total_btns_width) // 2
    btn_y = 300
    btn_play = pygame.Rect(btn_start_x, btn_y, btn_width, btn_height)
    btn_stop = pygame.Rect(btn_start_x + (btn_width + btn_gap), btn_y, btn_width, btn_height)
    btn_restart = pygame.Rect(btn_start_x + (btn_width + btn_gap) * 2, btn_y, btn_width, btn_height)
    btn_skip = pygame.Rect(btn_start_x + (btn_width + btn_gap) * 3, btn_y, btn_width, btn_height)

    def draw_button(rect, text):
        mouse = pygame.mouse.get_pos()
        color = (120, 120, 120) if rect.collidepoint(mouse) else (70, 70, 70)
        pygame.draw.rect(screen, color, rect, border_radius=6)
        label = font.render(text, True, (220, 220, 220))
        screen.blit(label, label.get_rect(center=rect.center))

    running = True
    while running:
        screen.fill((30, 30, 30))
        center_x = 800 // 2

        # Now Playing label
        now_playing = font.render("Now Playing:", True, (220, 220, 220))
        screen.blit(now_playing, (40, 40))

        # Filename
        filename = font.render(os.path.basename(mp3_path).strip(), True, (220, 220, 220))
        screen.blit(filename, (60, 80))

        # BPM label centered
        bpm_prefix = font.render("BPM:", True, (150, 150, 150))
        screen.blit(bpm_prefix, (center_x - bpm_prefix.get_width() // 2, 130))

        # BPM number centered below label
        bpm_str = str(int(bpm)) if bpm else "--"
        bpm_label = bpm_font.render(bpm_str, True, (180, 220, 180))
        screen.blit(bpm_label, (center_x - bpm_label.get_width() // 2, 155))

        # Keyboard instructions (centered)
        instructions = font.render("SPACE=Tap  |  ENTER=Save  |  ESC=Exit", True, (150, 150, 150))
        screen.blit(instructions, (center_x - instructions.get_width() // 2, 235))

        draw_button(btn_play, "[Play]")
        draw_button(btn_stop, "[Pause]")
        draw_button(btn_restart, "[Restart]")
        draw_button(btn_skip, "[next]")

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.mixer.music.stop()
                pygame.quit()
                return None, False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    now = time.time()
                    taps.append(now)
                    if len(taps) > 1:
                        intervals = [taps[i] - taps[i - 1] for i in range(1, len(taps))]
                        bpm = 60 / (sum(intervals) / len(intervals))
                elif event.key == pygame.K_RETURN and bpm:
                    pygame.mixer.music.stop()
                    pygame.mixer.quit()
                    pygame.quit()
                    return int(bpm), False
                elif event.key == pygame.K_ESCAPE:
                    pygame.mixer.music.stop()
                    pygame.mixer.quit()
                    pygame.quit()
                    return None, False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if btn_play.collidepoint(event.pos):
                    if not playing:
                        pygame.mixer.music.load(mp3_path)
                        pygame.mixer.music.play(start=15)
                        playing = True
                elif btn_stop.collidepoint(event.pos):
                    pygame.mixer.music.stop()
                    playing = False
                elif btn_restart.collidepoint(event.pos):
                    pygame.mixer.music.stop()
                    pygame.mixer.music.load(mp3_path)
                    pygame.mixer.music.play(start=15)
                    playing = True
                    bpm = 0  # restart bpm counting
                elif btn_skip.collidepoint(event.pos):
                    pygame.mixer.music.stop()
                    return None, True

        pygame.display.flip()
        clock.tick(60)
