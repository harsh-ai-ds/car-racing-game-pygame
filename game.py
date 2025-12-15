
import pygame
import random
import os
import sys

pygame.init()
pygame.mixer.init()  # may fail silently on some systems; it's okay

# Window
WIDTH, HEIGHT = 500, 600
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Car Racing Game - Advanced")

# Colors
WHITE = (255, 255, 255)
GRAY = (100, 100, 100)
ROAD = (50, 50, 50)
YELLOW = (255, 220, 0)
BLACK = (0, 0, 0)
RED = (220, 30, 30)

# Assets filenames (put these in same folder as game.py)
PLAYER_IMG = "Player_car.png"   # blue car (player)
ENEMY_IMG = "Enemy_car.png"     # red car (enemy)
EXPLO_IMG = "explosion.png"     # optional
ENGINE_SOUND = "engine.wav"     # optional looping engine sound
CRASH_SOUND = "crash.wav"       # optional crash sound
HIGHSCORE_FILE = "highscore.txt"

# Removes white background
player_img = pygame.image.load("Player_car.png").convert()
player_img.set_colorkey((255, 255, 255))   # Removes white background
enemy_img = pygame.image.load("Enemy_car.png").convert()
enemy_img.set_colorkey((255, 255, 255))    # Removes white background
# Game settings
FPS = 60
CAR_W, CAR_H = 60, 100   # logical size; images will be scaled to this
PLAYER_START_X = WIDTH // 2 - CAR_W // 2
PLAYER_START_Y = HEIGHT - CAR_H - 20
PLAYER_SPEED = 6
ENEMY_BASE_SPEED = 4
NUM_ENEMIES = 3
LIVES = 3

clock = pygame.time.Clock()

# Load images safely with fallback rectangles if missing
def load_and_scale(fname, w, h):
    try:
        img = pygame.image.load(fname).convert_alpha()
        return pygame.transform.smoothscale(img, (w, h))
    except Exception:
        return None

player_img = load_and_scale(PLAYER_IMG, CAR_W, CAR_H)
enemy_img = load_and_scale(ENEMY_IMG, CAR_W, CAR_H)
explosion_img = load_and_scale(EXPLO_IMG, 128, 128)  # used if present

# Sounds: try to load, otherwise None
def load_sound(fname,):
    try:
        return pygame.mixer.Sound(fname,)
    except Exception:
        return None


engine_sound = load_sound(ENGINE_SOUND)
crash_sound = load_sound(CRASH_SOUND)
if crash_sound:
    crash_sound.play()

# If engine sound exists, set loop but we'll start/stop it when playing
if engine_sound:
    engine_sound.set_volume(0.2)
if crash_sound:
    crash_sound.set_volume(0.5)

# High score handling
def load_highscore():
    if not os.path.exists(HIGHSCORE_FILE):
        return 0
    try:
        with open(HIGHSCORE_FILE, "r") as f:
            return int(f.read().strip() or 0)
    except Exception:
        return 0

def save_highscore(val):
    try:
        with open(HIGHSCORE_FILE, "w") as f:
            f.write(str(int(val)))
    except Exception:
        pass

highscore = load_highscore()

# Player and enemies
player_x = PLAYER_START_X
player_y = PLAYER_START_Y
player_speed = PLAYER_SPEED

class Enemy:
    def __init__(self):
        self.reset()

    def reset(self):
        margin = 40
        self.x = random.randint(margin, WIDTH - margin - CAR_W)
        self.y = random.randint(-800, -100)
        self.w = CAR_W
        self.h = CAR_H

    def rect(self):
        return pygame.Rect(self.x, self.y, self.w, self.h)

enemies = [Enemy() for _ in range(NUM_ENEMIES)]
enemy_speed = ENEMY_BASE_SPEED

# Road lines for animation
road_lines = []
for i in range(12):
    road_lines.append([WIDTH // 2 - 5, i * 60])

score = 0
lives = LIVES
game_over = False
running = True
in_menu = True
paused = False

font_small = pygame.font.SysFont(None, 28)
font_med = pygame.font.SysFont(None, 40)
font_big = pygame.font.SysFont(None, 64)

# Explosion fallback animation state
explosions = []  # list of (x,y,frame, max_frames, max_radius)

def start_engine_sound():
    if engine_sound:
        try:
            engine_sound.play(loops=-1)
        except Exception:
            pass

def stop_engine_sound():
    if engine_sound:
        try:
            engine_sound.stop()
        except Exception:
            pass

def play_crash_sound():
    if crash_sound:
        try:
            crash_sound.play()
        except Exception:
            pass

def draw_text_centered(surface, text, font, color, y):
    r = font.render(text, True, color)
    rect= r.get_rect(center=(WIDTH//2, y))
    surface.blit(r, rect)

def reset_game():
    global score, enemy_speed, lives, player_x, player_y, game_over, enemies
    score = 0
    enemy_speed = ENEMY_BASE_SPEED
    lives = LIVES
    player_x = PLAYER_START_X
    player_y = PLAYER_START_Y
    for e in enemies:
        e.reset()
    game_over = False

# Collision checking
def check_collision():
    p_rect = pygame.Rect(player_x, player_y, CAR_W, CAR_H)
    for e in enemies:
        if p_rect.colliderect(e.rect()):
            return e
    return None

# Explosion handling: prefer image; fallback to expanding circle
def spawn_explosion(center_x, center_y):
    if explosion_img:
        explor_w = explosion_img.get_width()
        explor_h = explosion_img.get_height()
        explosions.append({"type":"img","x":center_x - explor_w//2, "y":center_y - explor_h//2, "timer":0, "dur":30})
    else:
        explosions.append({"type":"draw","x":center_x, "y":center_y, "frame":0, "max":25})

def update_draw_explosions(surface):
    to_remove = []
    for i, ex in enumerate(explosions):
        if ex["type"] == "img":
            # simple fade/scale effect
            t = ex["timer"]
            dur = ex["dur"]
            alpha = max(0, 255 - int(255 * (t / dur)))
            s = int(1 + (t / dur) * 2)  # scale
            img = pygame.transform.rotozoom(explosion_img, 0, s)
            img.set_alpha(alpha)
            surface.blit(img, (ex["x"] - (img.get_width()-explosion_img.get_width())//2,
                               ex["y"] - (img.get_height()-explosion_img.get_height())//2))
            ex["timer"] += 1
            if ex["timer"] >= ex["dur"]:
                to_remove.append(i)
        else:
            # draw expanding circle
            frame = ex["frame"]
            maxf = ex["max"]
            radius = int((frame / maxf) * 60) + 10
            alpha = max(0, 200 - int((frame / maxf) * 200))
            s = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 150, 0, alpha), (radius, radius), radius)
            surface.blit(s, (ex["x"]-radius, ex["y"]-radius))
            ex["frame"] += 1
            if ex["frame"] > maxf:
                to_remove.append(i)
    # remove in reverse
    for i in reversed(to_remove):
        explosions.pop(i)

# Touch/mouse control: move player x toward pointer
mouse_target_x = None

# Main draw function
def draw_scene():
    # draw road background
    SCREEN.fill(GRAY)
    road_rect = pygame.Rect(50, 0, WIDTH - 100, HEIGHT)
    pygame.draw.rect(SCREEN, ROAD, road_rect)

    # road edges
    pygame.draw.rect(SCREEN, BLACK, (50, 0, 8, HEIGHT))
    pygame.draw.rect(SCREEN, BLACK, (WIDTH - 58, 0, 8, HEIGHT))

    # draw dashed center line (animated)
    for line in road_lines:
        pygame.draw.rect(SCREEN, YELLOW, (line[0], line[1], 10, 40))

    # draw enemies
    for e in enemies:
        if enemy_img:
            SCREEN.blit(enemy_img, (e.x, e.y))
        else:
            pygame.draw.car(SCREEN, RED, (e.x, e.y, e.w, e.h))
                        #rect
    # draw player
    if player_img:
        SCREEN.blit(player_img, (player_x, player_y))
    else:
        pygame.draw.car(SCREEN, (20,120,255), (player_x, player_y, CAR_W, CAR_H))
                    #rect
    # UI: score, lives, highscore
    score_surf = font_small.render(f"Score: {score}", True, WHITE)
    SCREEN.blit(score_surf, (10, 10))
    lives_surf = font_small.render(f"Lives: {lives}", True, WHITE)
    SCREEN.blit(lives_surf, (10, 36))
    high_surf = font_small.render(f"High: {highscore}", True, WHITE)
    SCREEN.blit(high_surf, (WIDTH - 100, 10))

    # update explosion animations
    update_draw_explosions(SCREEN)

# Game loop
start_engine_sound()  # will play only if engine_sound exists

while running:
    dt = clock.tick(FPS) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # mouse controls / touch
        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = pygame.mouse.get_pos()
            mouse_target_x = mx - CAR_W // 2

        if event.type == pygame.MOUSEMOTION:
            if pygame.mouse.get_pressed()[0]:
                mx, my = pygame.mouse.get_pos()
                mouse_target_x = mx - CAR_W // 2

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_p:
                paused = not paused
                if paused:
                    stop_engine_sound()
                else:
                    start_engine_sound()
            if event.key == pygame.K_SPACE and in_menu:
                in_menu = False
                reset_game()
                start_engine_sound()
            if event.key == pygame.K_r and game_over:
                in_menu = False
                reset_game()
                start_engine_sound()
            if event.key == pygame.K_ESCAPE:
                running = False

    if in_menu:
        SCREEN.fill(GRAY)
        draw_text_centered(SCREEN, "CAR RACING", font_big, WHITE, HEIGHT // 3)
        draw_text_centered(SCREEN, "Press SPACE to Start", font_med, WHITE, HEIGHT // 2)
        draw_text_centered(SCREEN, "Arrows / Mouse to move, P to Pause, R to Restart after Game Over", font_small, WHITE, HEIGHT - 80)
        pygame.display.flip()
        continue

    if paused:
        draw_scene()
        draw_text_centered(SCREEN, "PAUSED", font_big, WHITE, HEIGHT // 2)
        pygame.display.flip()
        continue

    if not game_over:
        # - move player from keys or mouse_target_x
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            player_x -= player_speed
        if keys[pygame.K_RIGHT]:
            player_x += player_speed

        # mouse/touch smoothing toward target
        if mouse_target_x is not None:
            # move smoothly towards target
            if abs(player_x - mouse_target_x) > 4:
                player_x += (mouse_target_x - player_x) * 0.25
            else:
                player_x = mouse_target_x

        # clamp
        player_x = max(60, min(WIDTH - CAR_W - 60, int(player_x)))

        # move road lines
        for line in road_lines:
            line[1] += int(200 * dt)
            if line[1] > HEIGHT:
                line[1] = -60

        # move enemies
        for e in enemies:
            e.y += enemy_speed
            if e.y > HEIGHT + 50:
                e.reset()
                score += 1
                # difficulty bump
                if score % 5 == 0:
                    enemy_speed += 0.7

        # collision
        collided_enemy = check_collision()
        if collided_enemy:
            # spawn explosion at center of collision
            center_x = collided_enemy.x + collided_enemy.w // 2
            center_y = collided_enemy.y + collided_enemy.h // 2
            spawn_explosion(center_x, center_y)
            play_crash_sound()
            # remove/respawn the enemy
            collided_enemy.reset()
            lives -= 1
            stop_engine_sound()
            pygame.time.delay(600)  # brief pause
            if lives <= 0:
                game_over = True
                # check/save highscore
                if score > highscore:
                    highscore = score
                    save_highscore(highscore)
                stop_engine_sound()
            else:
                start_engine_sound()

    # drawing
    draw_scene()

    # Game over overlay
    if game_over:
        draw_text_centered(SCREEN, "GAME OVER", font_big, (255, 30, 30), HEIGHT // 2 - 30)
        draw_text_centered(SCREEN, f"Score: {score}", font_med, WHITE, HEIGHT // 2 + 20)
        draw_text_centered(SCREEN, "Press R to Restart or ESC to Quit", font_small, WHITE, HEIGHT // 2 + 60)

    pygame.display.flip()

# cleanup
stop_engine_sound()
pygame.quit()
sys.exit()
