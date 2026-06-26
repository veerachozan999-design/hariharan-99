import sys
import math
import random
import pygame
import array

# Initialize pygame
pygame.init()
pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)

# Window Setup
WIDTH = 1280
HEIGHT = 720
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.DOUBLEBUF)
pygame.display.set_caption("Hill Racer")
clock = pygame.time.Clock()

# --- OPTIMIZATION CACHES & PROCEDURAL TEMPLATES ---
PARTICLE_CACHE = {}
CLOUD_SURFACES = []
for size in [60, 95, 130]:
    surf = pygame.Surface((size * 2, size), pygame.SRCALPHA)
    pygame.draw.circle(surf, (255, 255, 255, 85), (size, size // 2), size // 2)
    pygame.draw.circle(surf, (255, 255, 255, 60), (size - size // 3, size // 2 + size // 10), size // 3)
    pygame.draw.circle(surf, (255, 255, 255, 60), (size + size // 3, size // 2 + size // 10), size // 3)
    pygame.draw.circle(surf, (255, 255, 255, 110), (size, size // 2 - size // 10), size // 2.5)
    CLOUD_SURFACES.append(surf)

# --- COLORS ---
WHITE = (255, 255, 255)
BLACK = (20, 20, 25)
GRAY = (100, 100, 100)
DARK_GRAY = (40, 40, 45)
ORANGE = (255, 126, 0)
GOLD = (255, 215, 0)
RED = (220, 50, 50)
GREEN = (46, 204, 113)
BLUE = (41, 128, 185)
PURPLE = (142, 68, 173)

# Vehicle geometry shared by rendering and physics. Keeping these values in one
# place prevents the rear tyre from drifting behind the visual body.
VEHICLE_REAR_AXLE_X = -34
VEHICLE_FRONT_AXLE_X = 42
VEHICLE_AXLE_Y = 23
VEHICLE_WHEEL_RADIUS = 20
MAX_PARTICLES = 140
ACCELERATION_FORCE = 0.35
BRAKE_FORCE = 0.25
REVERSE_FORCE = 0.055
MAX_REVERSE_SPEED = -2.2

# Theme Colors for levels
LEVEL_THEMES = {
    1: {"name": "Sunset Valley", "sky": (50, 20, 70), "horizon": (255, 110, 40), "ground": (34, 112, 63)},
    2: {"name": "Neon Metropolis", "sky": (10, 10, 30), "horizon": (40, 20, 80), "ground": (24, 28, 40)},
    3: {"name": "Desert Canyon", "sky": (214, 115, 55), "horizon": (243, 198, 119), "ground": (196, 117, 43)},
    4: {"name": "Snowy Alpine", "sky": (20, 40, 65), "horizon": (140, 180, 210), "ground": (220, 235, 245)},
    5: {"name": "Volcanic Ridge", "sky": (15, 5, 5), "horizon": (120, 10, 10), "ground": (45, 30, 30)},
    6: {"name": "Emerald Jungle", "sky": (10, 50, 25), "horizon": (50, 160, 80), "ground": (20, 90, 45)},
    7: {"name": "Cyber Grid", "sky": (10, 15, 20), "horizon": (0, 180, 255), "ground": (20, 30, 40)},
    8: {"name": "Lunar Outpost", "sky": (5, 5, 10), "horizon": (30, 30, 40), "ground": (70, 70, 75)},
    9: {"name": "Ocean Trench", "sky": (5, 10, 40), "horizon": (10, 60, 120), "ground": (5, 30, 60)},
    10: {"name": "Apex Mountain", "sky": (30, 15, 45), "horizon": (120, 60, 150), "ground": (80, 70, 90)}
}

# --- SOUND GENERATION SYSTEM (NO EXTERNAL FILES) ---
def generate_beep(frequency=440, duration_ms=100, volume=0.3):
    """Generates a simple synthesized sound wave in memory."""
    sample_rate = 22050
    n_samples = int(sample_rate * (duration_ms / 1000.0))
    buf = array.array('h', [0] * n_samples)
    max_sample = 2**(16 - 1) - 1
    for i in range(n_samples):
        t = float(i) / sample_rate
        # Sine wave with fade out to prevent clicking sounds
        fade_out = max(0.0, 1.0 - (i / n_samples))
        buf[i] = int(max_sample * volume * math.sin(2.0 * math.pi * frequency * t) * fade_out)
    sound = pygame.mixer.Sound(buffer=buf)
    return sound

# Pre-generate our sound effects at boot (Takes barely any memory)
SFX_COIN = generate_beep(880, 80, 0.2)       # High pitch ting
SFX_GAS = generate_beep(440, 150, 0.25)       # Lower thud
SFX_CRASH = generate_beep(100, 400, 0.5)      # Heavy low boom
SFX_ENGINE_HUM = generate_beep(120, 200, 0.15) # Rumbling loop

# --- SYSTEM FONTS ---
def get_font(size, bold=False):
    return pygame.font.SysFont("Arial", size, bold=bold)

# --- CLASS DEFINITIONS ---

class Particle:
    def __init__(self, x, y, color, vx, vy, size=8, life=30, p_type="smoke"):
        self.x = x
        self.y = y
        self.color = color
        self.vx = vx
        self.vy = vy
        self.size = size
        self.life = life
        self.max_life = life
        self.p_type = p_type

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        
        if self.p_type == "smoke":
            # Smoke expands and floats upwards
            self.size = min(36, self.size * 1.045)
            self.vy -= 0.04
            self.vx *= 0.95
        elif self.p_type == "spark":
            # Spark/dirt falls and shrinks
            self.size = max(0.5, self.size * 0.91)
            self.vy += 0.16
            self.vx *= 0.93
        else: # "glitter"
            self.size = max(0.5, self.size * 0.96)
            self.vy *= 0.95
            self.vx *= 0.95

    def draw(self, surface, offset_x):
        if self.life > 0:
            alpha = int((self.life / self.max_life) * 255)
            # Optimize: Round alpha and size to keep cache clean
            alpha_cached = (alpha // 15) * 15
            size_cached = max(1, int(self.size))
            
            # Cache key
            key = (size_cached, self.color, alpha_cached)
            p_surf = PARTICLE_CACHE.get(key)
            if p_surf is None:
                p_surf = pygame.Surface((size_cached * 2, size_cached * 2), pygame.SRCALPHA)
                pygame.draw.circle(p_surf, (*self.color, alpha_cached), (size_cached, size_cached), size_cached)
                PARTICLE_CACHE[key] = p_surf
            
            surface.blit(p_surf, (self.x - offset_x - size_cached, self.y - size_cached))


class GameState:
    def __init__(self):
        self.state = "LAUNCH"
        self.coins = 500  # Starting balance for testing customization instantly
        self.unlocked_level = 1
        
        # Vehicle Configs
        self.car_colors = {"Orange": ORANGE, "Crimson": (180, 0, 30), "Cobalt": BLUE, "Emerald": (30, 150, 80)}
        self.selected_color = "Orange"
        
        # Upgrades (Level 1 to 5)
        self.upgrades = {
            "engine": 1,
            "suspension": 1,
            "tyres": 1
        }
        
        # Settings
        self.sound_enabled = True
        self.volume = 70
        self.target_fps = 60
        self.show_debug = False

        # Gameplay tracking
        self.current_level = 1
        self.engine_sound_cooldown = 0 # Prevents engine sound from overlapping too fast
        self.reset_game_run()

    def reset_game_run(self):
        self.car_x = 200
        self.car_y = 300
        self.vx = 0
        self.vy = 0
        self.angle = 0  # in radians
        self.omega = 0  # angular velocity
        self.wheel_rotation = 0
        self.gas = 100.0
        self.finished = False
        self.crashed = False
        self.coins_collected_this_run = 0
        
        # AI Opponent state variables
        self.ai_x = 150
        self.ai_y = 300
        self.ai_vx = 0
        self.ai_vy = 0
        self.ai_angle = 0
        self.ai_omega = 0
        self.ai_wheel_rotation = 0
        self.ai_crashed = False
        self.ai_finished = False
        self.ai_grounded = True
        # AI upgrades scale with level difficulty (from level 1 to 5)
        ai_up_lvl = min(5, 1 + (self.current_level - 1) // 2)
        self.ai_upgrades = {
            "engine": ai_up_lvl,
            "suspension": ai_up_lvl,
            "tyres": ai_up_lvl
        }
        
        # Level configuration parameters - dynamic length per level
        self.finish_x = 8000 + (self.current_level - 1) * 1500
        self.coins_list = []
        self.gas_list = []
        self.generate_collectibles()
        self.particles = []
        self.popups = []

        # Generate cloud details for sky visual animation
        self.clouds = []
        for _ in range(18):
            self.clouds.append({
                "x": random.randint(0, self.finish_x + WIDTH),
                "y": random.randint(20, 200),
                "speed": random.uniform(0.12, 0.38),
                "type": random.randint(0, 2)
            })

        # Precompute mountain heights for 3 parallax layers to optimize rendering (removes math.sin/cos inside draw loop)
        self.mountain_layers = []
        for i in range(3):
            layer_heights = []
            factor = 0.15 * (i + 1)
            max_x = int(self.finish_x + WIDTH + 1000)
            for x in range(0, max_x, 40):
                # Calculate heights using coordinates directly
                y = HEIGHT - 200 - (i * 60) + 80 * math.sin(x * 0.001) + 30 * math.cos(x * 0.003)
                layer_heights.append(y)
            self.mountain_layers.append(layer_heights)

    def generate_collectibles(self):
        self.coins_list = []
        self.gas_list = []
        # Populate coins along the hills
        for x in range(800, self.finish_x - 300, 150):
            if random.random() < 0.4:
                y = get_terrain_height(x, self.current_level) - 50
                # Choose random coin values: 25, 50, 100, 500
                val = random.choices([25, 50, 100, 500], weights=[70, 20, 8, 2])[0]
                self.coins_list.append({"x": x, "y": y, "collected": False, "value": val})
        # Populate Gas Canisters
        for x in range(1500, self.finish_x - 500, 1200):
            y = get_terrain_height(x, self.current_level) - 40
            self.gas_list.append({"x": x, "y": y, "collected": False})

    def play_sfx(self, sfx):
        """Helper to play sounds only if enabled"""
        if self.sound_enabled:
            vol_mult = self.volume / 100.0
            if sfx == SFX_COIN: sfx.set_volume(0.2 * vol_mult)
            elif sfx == SFX_GAS: sfx.set_volume(0.25 * vol_mult)
            elif sfx == SFX_CRASH: sfx.set_volume(0.5 * vol_mult)
            elif sfx == SFX_ENGINE_HUM: sfx.set_volume(0.15 * vol_mult)
            sfx.play()

    def upgrade_item(self, item_name):
        current_lvl = self.upgrades[item_name]
        if current_lvl < 5:
            cost = current_lvl * 150
            if self.coins >= cost:
                self.coins -= cost
                self.upgrades[item_name] += 1
                return True
        return False


# --- PROCEDURAL TERRAIN GENERATOR ---
def get_terrain_height(x, level):
    """Generates continuous hill terrain slopes depending on level parameters."""
    if x < 0:
        x = 0
    if level == 1: # Sunset Valley - Smooth & Flowy
        base = 520
        wave1 = 80 * math.sin(x * 0.003)
        wave2 = 25 * math.sin(x * 0.008)
        return base + wave1 + wave2
    elif level == 2: # Neon Metropolis - Moderate steps and ramps
        base = 540
        wave1 = 60 * math.sin(x * 0.002)
        wave2 = 40 * math.sin(x * 0.006)
        # Structural platform ramp simulation
        ramp = 0
        if 2000 < x < 2400:
            ramp = -80 * ((x - 2000) / 400)
        elif 2400 <= x < 2800:
            ramp = -80
        elif 2800 <= x < 3200:
            ramp = -80 * (1.0 - (x - 2800) / 400)
        return base + wave1 + wave2 + ramp
    elif level == 3: # Desert Canyon - Large Steep Sand Dunes
        base = 550
        wave1 = 120 * math.sin(x * 0.0025)
        wave2 = 30 * math.cos(x * 0.01)
        return base + wave1 + wave2
    elif level == 4: # Snowy Alpine - Bumpy and dynamic
        base = 500
        wave1 = 90 * math.sin(x * 0.004)
        wave2 = 15 * math.sin(x * 0.015)  # Fine bumps
        return base + wave1 + wave2
    elif level == 5: # Level 5: Volcanic Ridge - Extreme steep climbs and drops
        base = 560
        wave1 = 150 * math.sin(x * 0.002)
        wave2 = 60 * math.sin(x * 0.005)
        gap = 0
        if 4000 < x < 4300: # Deadfall Gap
            gap = 120 * math.sin((x - 4000) / 300.0 * math.pi)
        return base + wave1 + wave2 + gap
    elif level == 6: # Emerald Jungle - Swooping rollercoaster waves
        base = 500
        wave1 = 100 * math.sin(x * 0.0035)
        wave2 = 40 * math.sin(x * 0.007)
        return base + wave1 + wave2
    elif level == 7: # Cyber Grid - Sharp geometric plateaus
        base = 530
        wave1 = 50 * math.sin(x * 0.002)
        # Create stair step effect
        stair = 40 * math.floor(math.sin(x * 0.005) * 2)
        return base + wave1 + stair
    elif level == 8: # Lunar Outpost - Smooth craters and wide jumps
        base = 480
        wave1 = 70 * math.sin(x * 0.0015)
        wave2 = 20 * math.sin(x * 0.01)
        # Crater dips
        crater = 0
        if 2500 < (x % 3000) < 3100:
            crater = 80 * math.sin(((x % 3000) - 2500) / 600.0 * math.pi)
        return base + wave1 + wave2 + crater
    elif level == 9: # Ocean Trench - Massively long tidal swells
        base = 540
        wave1 = 160 * math.sin(x * 0.0018)
        wave2 = 30 * math.cos(x * 0.008)
        return base + wave1 + wave2
    else: # Level 10: Apex Mountain - Extreme climbs and huge drop-offs
        base = 560
        wave1 = 200 * math.sin(x * 0.0015) # Massively long vertical elevation changes
        wave2 = 40 * math.sin(x * 0.006)
        # Giant ramp at 4800m
        ramp = 0
        if 4800 < x < 5300:
            ramp = -180 * math.sin((x - 4800) / 500.0 * math.pi / 2)
        return base + wave1 + wave2 + ramp


# --- DRAWING UTILITIES ---

_gradient_cache = {}

def draw_gradient_sky(surface, top_color, bottom_color):
    """Draws a smooth background gradient representing sunset/neon themes."""
    key = (top_color, bottom_color)
    cached = _gradient_cache.get(key)
    if cached is None:
        strip = pygame.Surface((1, HEIGHT))
        for y in range(HEIGHT):
            ratio = y / HEIGHT
            r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
            g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
            b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
            strip.set_at((0, y), (r, g, b))
        cached = pygame.transform.scale(strip, (WIDTH, HEIGHT))
        _gradient_cache[key] = cached
    surface.blit(cached, (0, 0))

def draw_parallax_mountains(surface, offset_x, state_or_theme):
    """Draws layered background silhouettes."""
    if isinstance(state_or_theme, int):
        theme_idx = state_or_theme
        has_cache = False
    else:
        theme_idx = state_or_theme.current_level
        has_cache = True

    if theme_idx == 1: # Sunset Valley Mountains
        colors = [(100, 45, 80), (70, 30, 60), (45, 15, 40)]
    elif theme_idx == 2: # City Skyline
        draw_city_skyline(surface, offset_x)
        return
    elif theme_idx == 3: # Canyon Walls
        colors = [(160, 80, 40), (120, 50, 25), (80, 30, 15)]
    elif theme_idx == 4: # Snowy Mountains
        colors = [(80, 110, 140), (60, 80, 110), (40, 55, 85)]
    elif theme_idx == 5: # Volcanic Rocks
        colors = [(40, 10, 10), (30, 5, 5), (15, 0, 0)]
    elif theme_idx == 6: # Emerald Jungle Canopy
        colors = [(30, 70, 40), (20, 50, 30), (10, 30, 15)]
    elif theme_idx == 7: # Cyber Grid Towers
        colors = [(20, 25, 35), (15, 20, 28), (10, 12, 18)]
    elif theme_idx == 8: # Lunar Craters
        colors = [(80, 80, 85), (60, 60, 65), (40, 40, 45)]
    elif theme_idx == 9: # Deep Trench Reefs
        colors = [(15, 45, 90), (10, 30, 70), (5, 15, 45)]
    else: # Apex Peaks
        colors = [(90, 70, 100), (60, 45, 75), (40, 25, 55)]

    if theme_idx != 2:
        for i, color in enumerate(colors):
            factor = 0.15 * (i + 1)
            points = [(0, HEIGHT)]
            for screen_x in range(0, WIDTH + 40, 40):
                world_x = screen_x + offset_x * factor
                if has_cache and hasattr(state_or_theme, "mountain_layers"):
                    layer_heights = state_or_theme.mountain_layers[i]
                    idx = int(world_x // 40)
                    idx = max(0, min(idx, len(layer_heights) - 1))
                    y = layer_heights[idx]
                else:
                    y = HEIGHT - 200 - (i * 60) + 80 * math.sin(world_x * 0.001) + 30 * math.cos(world_x * 0.003)
                points.append((screen_x, y))
            points.append((WIDTH, HEIGHT))
            pygame.draw.polygon(surface, color, points)

def draw_city_skyline(surface, offset_x):
    """Procedurally render a neon cityscape for Level 2."""
    for i, color in enumerate([(25, 20, 45), (15, 12, 30)]):
        factor = 0.1 * (i + 1)
        step = 60 - i * 15
        for sx in range(-100, WIDTH + 100, step):
            wx = sx + offset_x * factor
            random.seed(int(wx // step)) # Static seed based on coordinates
            b_h = 200 + random.randint(50, 250) + i * 40
            b_w = step - 5
            rect = pygame.Rect(sx, HEIGHT - b_h, b_w, b_h)
            pygame.draw.rect(surface, color, rect)
            # Simple windows
            if i == 1:
                pygame.draw.rect(surface, (50, 40, 75), rect, 1)
                for wx_off in range(10, b_w - 10, 12):
                    for wy_off in range(15, b_h - 20, 25):
                        if random.random() > 0.4:
                            pygame.draw.rect(surface, (230, 230, 150), (sx + wx_off, HEIGHT - b_h + wy_off, 5, 8))


# --- GAME LAUNCH SCREEN (Styled after user reference) ---

def draw_launch_screen(state):
    # Base sunset gradient
    draw_gradient_sky(screen, (40, 10, 55), (245, 105, 30))
    
    # Parallax distant mountains
    draw_parallax_mountains(screen, 300, 1)
    
    # Draw a shining sun
    pygame.draw.circle(screen, (255, 230, 180), (WIDTH - 300, 400), 80)
    pygame.draw.circle(screen, (255, 255, 220), (WIDTH - 300, 400), 65)

    # Drawing a stylized terrain base at the bottom
    points = [(0, HEIGHT)]
    for x in range(0, WIDTH + 50, 50):
        y = 600 + 30 * math.sin(x * 0.004)
        points.append((x, y))
    points.append((WIDTH, HEIGHT))
    pygame.draw.polygon(screen, (35, 15, 30), points)

    # Stylized title "HILL RACER"
    # Secondary shadow title text
    title_font = get_font(100, bold=True)
    title_text_sub = title_font.render("HILL RACER", True, BLACK)
    screen.blit(title_text_sub, (WIDTH // 2 - 295, 125))

    title_text = title_font.render("HILL RACER", True, WHITE)
    screen.blit(title_text, (WIDTH // 2 - 300, 120))

    # Decorative checkered flag outline next to title
    flag_x, flag_y = WIDTH // 2 + 280, 110
    pygame.draw.rect(screen, WHITE, (flag_x, flag_y, 80, 45))
    for r in range(3):
        for c in range(4):
            if (r + c) % 2 == 1:
                pygame.draw.rect(screen, BLACK, (flag_x + c*20, flag_y + r*15, 20, 15))

    # Render Jeep-style vehicle artwork in launch screen
    car_x, car_y = WIDTH // 2, 530
    draw_car_sprite(screen, car_x, car_y, 0, ORANGE, suspension_lvl=3)

    # Draw Buttons
    draw_glowing_button("PRESS START", WIDTH // 2 - 150, 260, 300, 60, ORANGE)
    draw_glowing_button("SETTINGS", WIDTH // 2 - 120, 340, 240, 50, DARK_GRAY)


def draw_glowing_button(text, x, y, w, h, base_color):
    mouse_x, mouse_y = pygame.mouse.get_pos()
    rect = pygame.Rect(x, y, w, h)
    hovered = rect.collidepoint(mouse_x, mouse_y)
    
    # Border glow
    glow_color = GOLD if hovered else (base_color[0]//2, base_color[1]//2, base_color[2]//2)
    pygame.draw.rect(screen, glow_color, (x-4, y-4, w+8, h+8), border_radius=12)
    
    # Main button
    btn_color = (min(base_color[0] + 30, 255), min(base_color[1] + 30, 255), min(base_color[2] + 30, 255)) if hovered else base_color
    pygame.draw.rect(screen, btn_color, rect, border_radius=10)
    
    # Text
    btn_font = get_font(24, bold=True)
    txt_surf = btn_font.render(text, True, WHITE)
    screen.blit(txt_surf, (x + (w - txt_surf.get_width())//2, y + (h - txt_surf.get_height())//2))


# --- GARAGE CUSTOMIZATION SCREEN ---

def draw_garage_screen(state):
    draw_gradient_sky(screen, (30, 50, 80), (10, 15, 30))
    
    # Title
    t_font = get_font(40, bold=True)
    title_lbl = t_font.render("VEHICLE CUSTOMIZATION & TUNING", True, WHITE)
    screen.blit(title_lbl, (50, 40))

    # Coin balance indicator
    coin_lbl = get_font(28, bold=True).render(f"COINS: {state.coins} $", True, GOLD)
    screen.blit(coin_lbl, (WIDTH - 250, 40))

    # Draw Vehicle visualizer bay
    pygame.draw.rect(screen, DARK_GRAY, (80, 120, 500, 340), border_radius=15)
    pygame.draw.rect(screen, BLACK, (90, 130, 480, 240), border_radius=10)
    
    # Render customized preview car
    car_color = state.car_colors[state.selected_color]
    draw_car_sprite(screen, 330, 290, 0, car_color, suspension_lvl=state.upgrades["suspension"])

    # Paint Shop Selection
    lbl = get_font(22, bold=True).render("SELECT COLOR:", True, WHITE)
    screen.blit(lbl, (100, 390))
    for idx, (name, col) in enumerate(state.car_colors.items()):
        rect = pygame.Rect(260 + idx*75, 385, 65, 35)
        border_col = GOLD if state.selected_color == name else WHITE
        pygame.draw.rect(screen, col, rect, border_radius=5)
        pygame.draw.rect(screen, border_col, rect, width=3, border_radius=5)
        # Small check label
        name_lbl = get_font(12, bold=True).render(name, True, WHITE)
        screen.blit(name_lbl, (260 + idx*75 + 5, 425))

    # Render Performance Upgrades Section
    up_x = 640
    up_y = 120
    draw_upgrade_card("Engine Power", "engine", state.upgrades["engine"], up_x, up_y, state)
    draw_upgrade_card("Suspension Springiness", "suspension", state.upgrades["suspension"], up_x, up_y + 110, state)
    draw_upgrade_card("Tire Friction Grip", "tyres", state.upgrades["tyres"], up_x, up_y + 220, state)

    # Navigation buttons
    draw_glowing_button("START RACE", WIDTH // 2 - 150, 580, 300, 65, GREEN)
    draw_glowing_button("MAIN MENU", 80, 580, 200, 55, DARK_GRAY)


def draw_upgrade_card(title, config_name, current_lvl, x, y, state):
    pygame.draw.rect(screen, DARK_GRAY, (x, y, 550, 95), border_radius=12)
    # Card Text Info
    lbl_title = get_font(20, bold=True).render(title, True, WHITE)
    screen.blit(lbl_title, (x + 20, y + 15))
    
    # Current Level indicators (5 Bars)
    for i in range(5):
        bar_color = GREEN if i < current_lvl else GRAY
        pygame.draw.rect(screen, bar_color, (x + 20 + i*45, y + 45, 35, 12), border_radius=3)

    # Price / Status information
    if current_lvl >= 5:
        lbl_status = get_font(18, bold=True).render("MAX LEVEL", True, GOLD)
        screen.blit(lbl_status, (x + 380, y + 35))
    else:
        cost = current_lvl * 150
        lbl_cost = get_font(18, bold=True).render(f"Cost: {cost} $", True, GOLD)
        screen.blit(lbl_cost, (x + 270, y + 35))
        draw_glowing_button("UPGRADE", x + 380, y + 20, 150, 55, ORANGE)


# --- LEVEL SELECTION SCREEN ---

def draw_level_select_screen(state):
    draw_gradient_sky(screen, (20, 20, 40), (40, 20, 60))
    
    t_font = get_font(40, bold=True)
    title_lbl = t_font.render("SELECT RACING LEVEL", True, WHITE)
    screen.blit(title_lbl, (WIDTH // 2 - title_lbl.get_width() // 2, 35))

    # Grid of Levels (2 rows of 5)
    w, h = 180, 185
    x_start = 120
    dx = 210
    
    for lvl in range(1, 11):
        # Calculate row and column
        row = (lvl - 1) // 5  # 0 or 1
        col = (lvl - 1) % 5   # 0 to 4
        
        x = x_start + col * dx
        y = 110 + row * 220
        
        # Check unlocked
        unlocked = lvl <= state.unlocked_level
        card_color = DARK_GRAY if unlocked else (25, 25, 28)
        border_color = GREEN if (unlocked and state.current_level == lvl) else (GRAY if unlocked else RED)
        
        pygame.draw.rect(screen, card_color, (x, y, w, h), border_radius=12)
        pygame.draw.rect(screen, border_color, (x, y, w, h), width=3, border_radius=12)

        # Level Info
        num_lbl = get_font(24, bold=True).render(f"LEVEL {lvl}", True, WHITE)
        screen.blit(num_lbl, (x + (w - num_lbl.get_width()) // 2, y + 15))

        name_str = LEVEL_THEMES[lvl]["name"]
        name_lbl = get_font(14, bold=True).render(name_str, True, GOLD if unlocked else GRAY)
        screen.blit(name_lbl, (x + (w - name_lbl.get_width()) // 2, y + 55))

        # Difficulty visualizer
        diff_str = "★" * (1 + (lvl-1)//2) + "☆" * (5 - (1 + (lvl-1)//2))
        diff_lbl = get_font(16).render(f"Diff: {diff_str}", True, ORANGE)
        screen.blit(diff_lbl, (x + (w - diff_lbl.get_width()) // 2, y + 95))

        if unlocked:
            draw_glowing_button("SELECT", x + 25, y + 130, 130, 38, BLUE)
        else:
            lock_lbl = get_font(18, bold=True).render("LOCKED", True, RED)
            screen.blit(lock_lbl, (x + (w - lock_lbl.get_width()) // 2, y + 140))

    # Navigation Controls
    draw_glowing_button("CUSTOMIZE VEHICLE", WIDTH // 2 - 150, 570, 300, 60, GREEN)
    draw_glowing_button("BACK", 120, 570, 180, 55, DARK_GRAY)


# --- SETTINGS SCREEN ---

def draw_settings_screen(state):
    draw_gradient_sky(screen, (30, 20, 50), (15, 10, 25))
    
    t_font = get_font(40, bold=True)
    title_lbl = t_font.render("GAME SETTINGS", True, WHITE)
    screen.blit(title_lbl, (WIDTH // 2 - title_lbl.get_width() // 2, 60))

    # Panel
    pygame.draw.rect(screen, DARK_GRAY, (340, 140, 600, 410), border_radius=15)

    # Option: Sound Toggle (Row 1)
    sound_status = "ON" if state.sound_enabled else "OFF"
    lbl_sound = get_font(22, bold=True).render(f"AUDIO FEEDBACK:  {sound_status}", True, WHITE)
    screen.blit(lbl_sound, (380, 170))
    draw_glowing_button("TOGGLE", 740, 160, 140, 42, ORANGE)

    # Option: Sound Volume (Row 2)
    lbl_volume = get_font(22, bold=True).render(f"VOLUME LEVEL:  {state.volume}%", True, WHITE)
    screen.blit(lbl_volume, (380, 230))
    draw_glowing_button("-", 740, 220, 55, 42, BLUE)
    draw_glowing_button("+", 825, 220, 55, 42, BLUE)

    # Option: Target FPS (Row 3)
    lbl_fps = get_font(22, bold=True).render(f"TARGET FPS:  {state.target_fps}", True, WHITE)
    screen.blit(lbl_fps, (380, 290))
    draw_glowing_button("-", 740, 280, 55, 42, BLUE)
    draw_glowing_button("+", 825, 280, 55, 42, BLUE)

    # Option: Reset Progression (Row 4)
    lbl_reset = get_font(22, bold=True).render("RESET SAVED PROGRESS", True, WHITE)
    screen.blit(lbl_reset, (380, 350))
    draw_glowing_button("RESET", 740, 340, 140, 42, RED)

    # Instructions box
    instructions = [
        "CONTROLS:  Hold [D] or [RIGHT] key to Accelerate forward.",
        "                  Hold [A] or [LEFT] to Brake, then Reverse / Balance in Air.",
        "                  Collect coins to upgrade parts in the Garage."
    ]
    for idx, text in enumerate(instructions):
        text_lbl = get_font(15).render(text, True, GRAY)
        screen.blit(text_lbl, (380, 410 + idx * 25))

    # Return button
    draw_glowing_button("BACK", WIDTH // 2 - 100, 580, 200, 55, BLUE)


# --- DYNAMIC VEHICLE RENDERING ---

def draw_car_sprite(surface, x, y, angle_rad, body_color, suspension_lvl=1, braking=False, wheel_rotation=0.0):
    """Draws a polished side-profile rally car with stable axle placement."""
    # Scale variables
    car_width = 118
    
    # Calculate transform coordinates based on vector angle
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    def rot(dx, dy):
        # Rotate offsets from car center
        rx = dx * cos_a - dy * sin_a
        ry = dx * sin_a + dy * cos_a
        return x + rx, y + ry

    # Draw suspension spring lines. Higher suspension upgrades shorten visual
    # compression while preserving the same axle x positions as physics.
    susp_length = max(16, VEHICLE_AXLE_Y - suspension_lvl * 1.5)
    back_hub = rot(VEHICLE_REAR_AXLE_X, susp_length)
    front_hub = rot(VEHICLE_FRONT_AXLE_X, susp_length)

    back_mount = rot(VEHICLE_REAR_AXLE_X, 2)
    front_mount = rot(VEHICLE_FRONT_AXLE_X, 2)

    pygame.draw.line(surface, (35, 35, 38), back_mount, back_hub, 5)
    pygame.draw.line(surface, (35, 35, 38), front_mount, front_hub, 5)

    # Soft ground shadow beneath the car for visual depth
    shadow_surf = pygame.Surface((car_width + 20, 40), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow_surf, (0, 0, 0, 90), (0, 10, car_width + 20, 22))
    surface.blit(shadow_surf, (x - (car_width + 20) // 2, y + 14))

    # Main car chassis, shaped so the rear tyre sits inside the arch instead of
    # hanging behind the vehicle.
    raw_points = [
        (-55, -1), (-43, -17), (-18, -22), (0, -38), (32, -35),
        (48, -15), (57, -8), (54, 10), (-50, 12)
    ]
    rot_points = [rot(px, py) for px, py in raw_points]
    pygame.draw.polygon(surface, body_color, rot_points)
    pygame.draw.polygon(surface, BLACK, rot_points, 3) # Outline

    # Bonnet and lower highlight panels add depth without expensive assets.
    highlight = tuple(min(255, int(c * 1.22 + 18)) for c in body_color)
    lower_shadow = tuple(max(0, int(c * 0.62)) for c in body_color)
    pygame.draw.polygon(surface, highlight, [rot(-48, -3), rot(-36, -14), rot(-9, -18), rot(-18, -5)])
    pygame.draw.polygon(surface, lower_shadow, [rot(-49, 5), rot(53, 4), rot(54, 10), rot(-50, 12)])

    # Tinted glass and roll cage.
    glass = (125, 205, 230)
    windshield = [rot(-7, -21), rot(2, -34), rot(18, -33), rot(13, -20)]
    side_window = [rot(17, -32), rot(31, -30), rot(41, -16), rot(17, -19)]
    pygame.draw.polygon(surface, glass, windshield)
    pygame.draw.polygon(surface, glass, side_window)
    pygame.draw.polygon(surface, BLACK, windshield, 2)
    pygame.draw.polygon(surface, BLACK, side_window, 2)

    # Wheel arches keep the tyres visually tucked into the body.
    for hub in (back_hub, front_hub):
        pygame.draw.circle(surface, BLACK, (int(hub[0]), int(hub[1])), VEHICLE_WHEEL_RADIUS + 6, 5)

    # Wheels rendering (Outer Tire + Inner Rims)
    draw_wheel(surface, back_hub, VEHICLE_WHEEL_RADIUS, wheel_rotation)
    draw_wheel(surface, front_hub, VEHICLE_WHEEL_RADIUS, wheel_rotation)

    # Glowing Headlight (front)
    light_pos = rot(53, 2)
    pygame.draw.circle(surface, GOLD, (int(light_pos[0]), int(light_pos[1])), 6)

    # Brake Light (rear) - lights up bright red when braking, dim otherwise
    brake_pos = rot(-48, 2)
    if braking:
        glow_surf = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (255, 40, 40, 110), (15, 15), 15)
        surface.blit(glow_surf, (int(brake_pos[0]) - 15, int(brake_pos[1]) - 15))
        pygame.draw.circle(surface, (255, 60, 60), (int(brake_pos[0]), int(brake_pos[1])), 7)
    else:
        pygame.draw.circle(surface, (120, 20, 20), (int(brake_pos[0]), int(brake_pos[1])), 5)

def draw_wheel(surface, center, radius, rot_angle):
    """Draws a high-quality wheel with hub spokes to show rotation clearly."""
    cx, cy = int(center[0]), int(center[1])
    # Outer rubber tire
    pygame.draw.circle(surface, BLACK, (cx, cy), radius)
    pygame.draw.circle(surface, (70, 70, 75), (cx, cy), radius, 7) # Thicker tread ring, easier to read
    pygame.draw.circle(surface, (15, 15, 15), (cx, cy), radius, 2) # Crisp tire edge

    # Inner alloy hub
    rim_r = radius - 8
    pygame.draw.circle(surface, (195, 198, 205), (cx, cy), rim_r)
    pygame.draw.circle(surface, (140, 142, 150), (cx, cy), rim_r, 2)

    # Spokes to show rotation visually
    for i in range(4):
        spoke_angle = rot_angle + (i * math.pi / 2)
        sx = cx + rim_r * math.cos(spoke_angle)
        sy = cy + rim_r * math.sin(spoke_angle)
        pygame.draw.line(surface, DARK_GRAY, (cx, cy), (int(sx), int(sy)), 3)

    # Center Hub Cap
    pygame.draw.circle(surface, BLACK, (cx, cy), 5)
    pygame.draw.circle(surface, (90, 90, 95), (cx, cy), 5, 1)


# --- ACTIVE GAMEPLAY LOOP & LOGIC ---

def run_car_physics(state, is_ai, is_accelerating, is_braking):
    """Generalized function to update custom 2D car dynamics for player or AI."""
    # Retrieve active state references based on agent type
    if is_ai:
        x, y = state.ai_x, state.ai_y
        vx, vy = state.ai_vx, state.ai_vy
        angle, omega = state.ai_angle, state.ai_omega
        wheel_rotation = state.ai_wheel_rotation
        upgrades = state.ai_upgrades
        crashed = state.ai_crashed
        finished = state.ai_finished
    else:
        x, y = state.car_x, state.car_y
        vx, vy = state.vx, state.vy
        angle, omega = state.angle, state.omega
        wheel_rotation = state.wheel_rotation
        upgrades = state.upgrades
        crashed = state.crashed
        finished = state.finished

    if crashed or finished:
        return # Skip processing if already finished or crashed

    # Level gravity modifier (Lunar Outpost has low gravity)
    gravity = 0.14 if state.current_level == 8 else 0.26

    # Configuration modifiers from Upgrades
    engine_mult = 1.0 + (upgrades["engine"] - 1) * 0.18
    tyre_mult = 1.0 + (upgrades["tyres"] - 1) * 0.14
    suspension_stiffness = 0.075 + (upgrades["suspension"] - 1) * 0.018
    suspension_damping = 0.78 - (upgrades["suspension"] - 1) * 0.025

    # Check terrain below wheel locations
    rad = angle
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    # Wheel hub attachment offsets
    axle_y = max(16, VEHICLE_AXLE_Y - upgrades["suspension"] * 1.5)
    back_offset_x = VEHICLE_REAR_AXLE_X * cos_a - axle_y * sin_a
    back_offset_y = VEHICLE_REAR_AXLE_X * sin_a + axle_y * cos_a
    front_offset_x = VEHICLE_FRONT_AXLE_X * cos_a - axle_y * sin_a
    front_offset_y = VEHICLE_FRONT_AXLE_X * sin_a + axle_y * cos_a

    wb_x = x + back_offset_x
    wb_y = y + back_offset_y
    wf_x = x + front_offset_x
    wf_y = y + front_offset_y

    terrain_y_back = get_terrain_height(wb_x, state.current_level)
    terrain_y_front = get_terrain_height(wf_x, state.current_level)

    # Suspension springs modeling (Raycast style)
    radius = VEHICLE_WHEEL_RADIUS
    back_grounded = wb_y >= terrain_y_back - radius
    front_grounded = wf_y >= terrain_y_front - radius

    # Vertical Normal spring forces
    back_spring_f = 0
    if back_grounded:
        back_spring_f = ((terrain_y_back - radius) - wb_y) * suspension_stiffness
        vy += back_spring_f
        vy *= max(0.66, suspension_damping)
        
    front_spring_f = 0
    if front_grounded:
        front_spring_f = ((terrain_y_front - radius) - wf_y) * suspension_stiffness
        vy += front_spring_f
        vy *= max(0.66, suspension_damping)

    # Apply torque tilt rotation from suspension variations
    if back_grounded:
        omega -= (back_spring_f * 0.012)
    if front_grounded:
        omega += (front_spring_f * 0.012)

    # Ground Traction Movement
    MAX_SPEED = 8.2 * engine_mult
    if back_grounded or front_grounded:
        grounded_wheels = int(back_grounded) + int(front_grounded)
        traction = tyre_mult * (0.72 + grounded_wheels * 0.14)
        if is_accelerating:
            if vx < MAX_SPEED:
                vx += ACCELERATION_FORCE * engine_mult * traction
                vx = min(vx, MAX_SPEED)
            # Smooth launch torque
            omega -= 0.0022 * traction
            # Spawn dust particles (Player only)
            if not is_ai and len(state.particles) < MAX_PARTICLES:
                # Spawn expanding smoke
                if random.random() < 0.4:
                    state.particles.append(Particle(wb_x, wb_y + 10, (140, 140, 145), -vx*0.5 - random.uniform(1,3), -random.uniform(0.5, 1.5), size=6, life=35, p_type="smoke"))
                # Spawn flying dirt sparks
                if random.random() < 0.25:
                    state.particles.append(Particle(wb_x, wb_y + 10, (90, 60, 30), -vx*0.7 - random.uniform(2,5), -random.uniform(1, 4), size=4, life=20, p_type="spark"))
            
            # Sound loop (Player only)
            if not is_ai and state.engine_sound_cooldown <= 0:
                state.play_sfx(SFX_ENGINE_HUM)
                state.engine_sound_cooldown = 15 # Play every 15 frames
                
        elif is_braking:
            brake_power = BRAKE_FORCE * traction
            if vx > 0.12:
                vx = max(0.0, vx - brake_power)
                omega += 0.0020 * traction
                if not is_ai and len(state.particles) < MAX_PARTICLES:
                    # Brake smoke/sparks
                    if random.random() < 0.5:
                        state.particles.append(Particle(wf_x, wf_y + 10, (80, 80, 80), random.uniform(-1, 1), -random.uniform(1, 2.5), size=5, life=18, p_type="smoke"))
                    if random.random() < 0.3:
                        state.particles.append(Particle(wf_x, wf_y + 10, (100, 100, 100), random.uniform(-2, 2), -random.uniform(0.5, 1.5), size=3, life=15, p_type="spark"))
            elif vx < -0.08:
                vx = max(MAX_REVERSE_SPEED, vx - REVERSE_FORCE * traction)
            else:
                vx = max(MAX_REVERSE_SPEED, vx - REVERSE_FORCE * traction)
        else:
            vx *= 0.990
    else:
        # Air Rotation mechanics (Balance car in mid-air!)
        if is_accelerating: # Pitch down / Clockwise rotation
            omega += 0.004
        elif is_braking: # Pitch up / Counter-clockwise rotation
            omega -= 0.004

    # Apply Gravity
    vy += gravity

    # Natural Air Resistances
    vx *= 0.985
    vy *= 0.99
    omega *= 0.94

    # Position Updates
    x += vx
    y += vy
    angle += omega
    wheel_rotation += vx / max(1.0, VEHICLE_WHEEL_RADIUS)

    # Keep angles within boundary [-PI, PI]
    if angle > math.pi: angle -= 2 * math.pi
    elif angle < -math.pi: angle += 2 * math.pi

    # Check for Ground Collisions (Crashes)
    chassis_terrain_y = get_terrain_height(x, state.current_level)
    if y > chassis_terrain_y - 12:
        deg = abs(math.degrees(angle))
        if deg > 92 and deg < 268:
            crashed = True
            if not is_ai:
                state.play_sfx(SFX_CRASH)
        y = chassis_terrain_y - 12
        vy = max(0, vy - 1)

    # Restrict backward boundary
    if x < 100:
        x = 100
        vx = max(0, vx)

    # Check Level Finish
    if x >= state.finish_x:
        finished = True
        if not is_ai:
            # Unlock the next level
            if state.current_level == state.unlocked_level and state.unlocked_level < 10:
                state.unlocked_level += 1
                state.coins += 250

    # Save local variables back to state
    if is_ai:
        state.ai_x, state.ai_y = x, y
        state.ai_vx, state.ai_vy = vx, vy
        state.ai_angle, state.ai_omega = angle, omega
        state.ai_wheel_rotation = wheel_rotation
        state.ai_crashed = crashed
        state.ai_finished = finished
        state.ai_grounded = back_grounded or front_grounded
    else:
        state.car_x, state.car_y = x, y
        state.vx, state.vy = vx, vy
        state.angle, state.omega = angle, omega
        state.wheel_rotation = wheel_rotation
        state.crashed = crashed
        state.finished = finished


def run_physics_frame(state, keys):
    """Updates game physics for both player and AI car."""
    # Player inputs
    is_accelerating = keys[pygame.K_d] or keys[pygame.K_RIGHT]
    is_braking = keys[pygame.K_a] or keys[pygame.K_LEFT]

    # Check for empty fuel (Player only)
    if state.gas <= 0:
        state.gas = 0
        is_accelerating = False # Out of fuel prevents gas pedal
        state.vx *= 0.95
    else:
        state.gas -= 0.04 # Fuel depletion rate

    # Run physics for Player
    run_car_physics(state, is_ai=False, is_accelerating=is_accelerating, is_braking=is_braking)

    # AI opponent behavior logic
    ai_accel = False
    ai_brake = False
    
    if not state.ai_crashed and not state.ai_finished:
        if state.ai_grounded:
            # Accelerate forward
            ai_accel = True
            ai_brake = False
        else:
            # Air control balancing
            if state.ai_angle > 0.05: # Tilted forward -> brake to nose-up
                ai_brake = True
                ai_accel = False
            elif state.ai_angle < -0.05: # Tilted backward -> accel to nose-down
                ai_accel = True
                ai_brake = False

    # Run physics for AI
    run_car_physics(state, is_ai=True, is_accelerating=ai_accel, is_braking=ai_brake)

    # Process Collectibles overlap
    # Coins (Player only)
    for coin in state.coins_list:
        if not coin["collected"]:
            dist = math.hypot(state.car_x - coin["x"], state.car_y - coin["y"])
            if dist < 45:
                coin["collected"] = True
                val = coin.get("value", 25)
                state.coins += val
                state.coins_collected_this_run += val
                state.play_sfx(SFX_COIN) # --- SOUND: Coin pickup ---
                
                # Determine popup color based on value
                if val == 25:
                    p_color = GOLD
                elif val == 50:
                    p_color = (200, 210, 220) # Silver-ish
                elif val == 100:
                    p_color = (255, 80, 80) # Red
                else: # 500
                    p_color = (180, 100, 255) # Amethyst Purple
                
                # Spawn floating text popup
                state.popups.append({"x": coin["x"], "y": coin["y"] - 20, "text": f"+{val}", "color": p_color, "life": 45})
                
                # Spawn glitter particles
                for _ in range(12): # Increased count for better visual impact
                    if len(state.particles) < MAX_PARTICLES:
                        state.particles.append(Particle(coin["x"], coin["y"], p_color, random.uniform(-3,3), random.uniform(-3,3), size=5, life=20, p_type="glitter"))
    # Gas Cans (Player only)
    for gas in state.gas_list:
        if not gas["collected"]:
            dist = math.hypot(state.car_x - gas["x"], state.car_y - gas["y"])
            if dist < 45:
                gas["collected"] = True
                state.gas = min(100.0, state.gas + 40.0)
                state.play_sfx(SFX_GAS) # --- SOUND: Gas pickup ---
                
                # Spawn a floating "FUEL!" popup
                state.popups.append({"x": gas["x"], "y": gas["y"] - 20, "text": "FUEL +40%", "color": GREEN, "life": 45})
                
                # Spawn gas splash green particles
                for _ in range(12): # Increased count
                    if len(state.particles) < MAX_PARTICLES:
                        state.particles.append(Particle(gas["x"], gas["y"], GREEN, random.uniform(-3,3), random.uniform(-3,3), size=6, life=25, p_type="glitter"))
    
    # Update active floating popups (float up and fade out)
    for popup in state.popups:
        popup["y"] -= 1.2
        popup["life"] -= 1
    state.popups = [p for p in state.popups if p["life"] > 0]
    
    # Reduce engine cooldown timer
    if state.engine_sound_cooldown > 0:
        state.engine_sound_cooldown -= 1

    # Update particles
    for p in state.particles:
        p.update()
    # Clear dead particles
    state.particles = [p for p in state.particles if p.life > 0]


# --- DRAWING IN-GAME ENVIRONMENT AND UI ---

def draw_play_screen(state):
    # Retrieve current active level theme
    theme = LEVEL_THEMES[state.current_level]
    draw_gradient_sky(screen, theme["sky"], theme["horizon"])
    
    # Camera Offset tracking
    offset_x = state.car_x - 300

    # Draw cloud visual animation layer
    for cloud in state.clouds:
        cx = int((cloud["x"] - offset_x * cloud["speed"]) % (WIDTH + 300)) - 150
        cy = cloud["y"]
        screen.blit(CLOUD_SURFACES[cloud["type"]], (cx, cy))
    
    # Parallax Background
    draw_parallax_mountains(screen, state.car_x, state)

    # Draw Collectibles (Coins & Gas cans)
    for coin in state.coins_list:
        if not coin["collected"]:
            cx, cy = int(coin["x"] - offset_x), int(coin["y"])
            val = coin.get("value", 25)
            
            # Select color and size based on coin value
            if val == 25:
                outer_color = GOLD
                inner_color = (255, 240, 150)
                text_color = (120, 80, 0)
                radius = 16
            elif val == 50:
                outer_color = (180, 190, 200) # Silver
                inner_color = (230, 240, 250)
                text_color = (50, 70, 90)
                radius = 19
            elif val == 100:
                outer_color = (220, 50, 50) # Ruby Red
                inner_color = (255, 120, 120)
                text_color = WHITE
                radius = 21
            else: # 500
                outer_color = (155, 89, 182) # Amethyst Purple
                inner_color = (220, 180, 255)
                text_color = GOLD
                radius = 24

            pulse = int(3 * math.sin(pygame.time.get_ticks() * 0.01))
            r = radius + pulse
            
            # Draw coin shadow & base circles
            pygame.draw.circle(screen, (30, 30, 30), (cx + 2, cy + 2), r) # Shadow
            pygame.draw.circle(screen, outer_color, (cx, cy), r)
            pygame.draw.circle(screen, inner_color, (cx, cy), r - 3)
            
            # Draw number inside the coin
            c_font = get_font(int(r * 0.8), bold=True)
            txt_surf = c_font.render(str(val), True, text_color)
            screen.blit(txt_surf, (cx - txt_surf.get_width()//2, cy - txt_surf.get_height()//2))

    for gas in state.gas_list:
        if not gas["collected"]:
            gx, gy = int(gas["x"] - offset_x), int(gas["y"])
            
            # --- IMPROVED FUEL CANISTER DESIGN ---
            # Pulse animation (float up and down slightly)
            float_y = int(4 * math.sin(pygame.time.get_ticks() * 0.005))
            gy_anim = gy + float_y
            
            # Soft shadow
            pygame.draw.ellipse(screen, (0, 0, 0, 80), (gx - 16, gy + 22, 32, 10))
            
            # 1. Main body (Red jerrycan)
            body_rect = pygame.Rect(gx - 16, gy_anim - 18, 32, 38)
            pygame.draw.rect(screen, (180, 20, 20), body_rect, border_radius=6) # Darker red base
            pygame.draw.rect(screen, (230, 40, 40), (gx - 14, gy_anim - 16, 28, 34), border_radius=4) # Light red interior
            
            # Shine highlight (3D effect)
            pygame.draw.rect(screen, (255, 120, 120), (gx - 12, gy_anim - 14, 4, 30), border_radius=2)
            
            # 2. Triple Handle on top
            pygame.draw.rect(screen, (120, 10, 10), (gx - 12, gy_anim - 24, 24, 7), border_radius=2)
            pygame.draw.rect(screen, (200, 20, 20), (gx - 10, gy_anim - 23, 20, 5), border_radius=2)
            
            # 3. Cap/Spout (Angled/offset cap)
            pygame.draw.rect(screen, (60, 60, 65), (gx + 4, gy_anim - 25, 8, 8), border_radius=2) # Neck
            pygame.draw.rect(screen, (241, 196, 15), (gx + 2, gy_anim - 28, 12, 4), border_radius=1) # Yellow cap
            
            # 4. Central Label ("F" with a fuel icon look)
            pygame.draw.rect(screen, WHITE, (gx - 8, gy_anim - 4, 16, 16), border_radius=3)
            # Draw a black letter "F" (for Fuel)
            f_font = get_font(14, bold=True)
            f_txt = f_font.render("F", True, BLACK)
            screen.blit(f_txt, (gx - f_txt.get_width()//2, gy_anim - 4 + (16 - f_txt.get_height())//2))
            
            # 5. Outer border outline for contrast
            pygame.draw.rect(screen, BLACK, (gx - 16, gy_anim - 18, 32, 38), width=2, border_radius=6)

    # Draw Finish Line Flag
    flag_x = state.finish_x - offset_x
    flag_y = get_terrain_height(state.finish_x, state.current_level)
    pygame.draw.line(screen, WHITE, (flag_x, flag_y), (flag_x, flag_y - 120), 4)
    # Checkered banner
    for r in range(4):
        for c in range(5):
            f_col = BLACK if (r + c) % 2 == 1 else WHITE
            pygame.draw.rect(screen, f_col, (flag_x + c * 12, flag_y - 120 + r * 10, 12, 10))

    # Render Terrain Solid Ground Polygon
    points = []
    # Collect screen vertices
    start_scr_x = -50
    end_scr_x = WIDTH + 50
    for screen_x in range(start_scr_x, end_scr_x, 10):
        world_x = screen_x + offset_x
        y = get_terrain_height(world_x, state.current_level)
        points.append((screen_x, y))
    
    # Close polygon shape to bottom screen corners
    points.append((WIDTH, HEIGHT))
    points.append((0, HEIGHT))
    pygame.draw.polygon(screen, theme["ground"], points)

    # Outline edge of hills (Multi-layered grass/dirt details)
    border_points = [(p[0], p[1]) for p in points[:-2]]
    border_color = (min(theme["ground"][0]+30, 255), min(theme["ground"][1]+30, 255), min(theme["ground"][2]+30, 255))
    
    # 1. Sub-surface dirt outline (offset slightly downwards)
    sub_points = [(p[0], p[1] + 8) for p in border_points]
    pygame.draw.lines(screen, (max(0, theme["ground"][0]-20), max(0, theme["ground"][1]-20), max(0, theme["ground"][2]-20)), False, sub_points, 5)
    
    # 2. Main top grass border
    pygame.draw.lines(screen, border_color, False, border_points, 6)
    
    # 3. Procedural vertical foliage/grass accents along the hill outline
    for idx, p in enumerate(border_points):
        if idx % 4 == 0:
            gx, gy = p[0], p[1]
            pygame.draw.line(screen, border_color, (gx, gy), (gx - 1, gy - 6), 2)

    # Draw particles
    for p in state.particles:
        p.draw(screen, offset_x)

    # Draw our primary vehicle (Jeep)
    car_color = state.car_colors[state.selected_color]
    keys = pygame.key.get_pressed()
    is_braking_now = (keys[pygame.K_a] or keys[pygame.K_LEFT]) and not state.crashed and not state.finished
    draw_car_sprite(
        screen,
        state.car_x - offset_x,
        state.car_y,
        state.angle,
        car_color,
        suspension_lvl=state.upgrades["suspension"],
        braking=is_braking_now,
        wheel_rotation=state.wheel_rotation,
    )

    # Draw AI opponent vehicle
    if not state.ai_crashed:
        ai_col_name = "Cobalt" if state.selected_color == "Crimson" else "Crimson"
        ai_color = state.car_colors[ai_col_name]
        draw_car_sprite(
            screen,
            state.ai_x - offset_x,
            state.ai_y,
            state.ai_angle,
            ai_color,
            suspension_lvl=state.ai_upgrades["suspension"],
            braking=False,
            wheel_rotation=state.ai_wheel_rotation,
        )
        # Draw "COM" text badge above AI car
        ax, ay = int(state.ai_x - offset_x), int(state.ai_y - 60)
        pygame.draw.rect(screen, BLACK, (ax - 22, ay - 12, 44, 20), border_radius=4)
        pygame.draw.rect(screen, RED, (ax - 22, ay - 12, 44, 20), width=1, border_radius=4)
        com_lbl = get_font(12, bold=True).render("COM", True, WHITE)
        screen.blit(com_lbl, (ax - com_lbl.get_width()//2, ay - 10))

    # Draw active floating popups (text animations) on top of everything
    for p in state.popups:
        alpha = int((p["life"] / 45) * 255)
        p_font = get_font(20, bold=True)
        txt_surf = p_font.render(p["text"], True, p["color"])
        txt_surf.set_alpha(alpha)
        screen.blit(txt_surf, (p["x"] - offset_x - txt_surf.get_width() // 2, p["y"]))

    # Draw UI HUD elements
    draw_hud(state)

    # Draw overlay overlays (Game Over or Level Cleared)
    if state.crashed:
        draw_status_overlay("VEHICLE CRASHED!", "PRESS [ENTER] TO RETRY", RED)
    elif state.finished:
        draw_status_overlay("LEVEL COMPLETED!", "PRESS [ENTER] FOR GARAGE", GREEN)


def draw_hud(state):
    # Top HUD Bar
    pygame.draw.rect(screen, (15, 15, 20, 180), (10, 10, WIDTH - 20, 65), border_radius=10)
    
    # Progress gauge bar (visual slider)
    p_len = 300
    start_px, py = 40, 42
    pygame.draw.rect(screen, GRAY, (start_px, py, p_len, 10), border_radius=5)
    progress = max(0.0, min(1.0, state.car_x / state.finish_x))
    pygame.draw.rect(screen, GREEN, (start_px, py, int(p_len * progress), 10), border_radius=5)
    
    # Distance marker
    dist_txt = get_font(13, bold=True).render(f"DISTANCE: {int(state.car_x)}m / {state.finish_x}m", True, WHITE)
    screen.blit(dist_txt, (start_px, py - 20))

    # Gas / Fuel Indicator
    g_x, g_y = 400, py
    pygame.draw.rect(screen, GRAY, (g_x, g_y, 180, 10), border_radius=5)
    gas_col = RED if state.gas < 25 else ORANGE
    pygame.draw.rect(screen, gas_col, (g_x, g_y, int(180 * (state.gas / 100)), 10), border_radius=5)
    gas_lbl = get_font(13, bold=True).render(f"FUEL: {int(state.gas)}%", True, WHITE)
    screen.blit(gas_lbl, (g_x, g_y - 20))

    # Speedometer display
    speed_kph = abs(int(state.vx * 12))
    speed_lbl = get_font(26, bold=True).render(f"{speed_kph} KPH", True, WHITE)
    screen.blit(speed_lbl, (650, 22))

    # Coin Counter
    coins_lbl = get_font(22, bold=True).render(f"COINS: {state.coins} $", True, GOLD)
    screen.blit(coins_lbl, (840, 25))

    # Back to Garage Quick button
    draw_glowing_button("GARAGE", WIDTH - 180, 18, 150, 48, DARK_GRAY)


def draw_status_overlay(title_text, subtitle_text, color_theme):
    """Semi-transparent modal window for pause, victory, or game over states."""
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    pygame.draw.rect(screen, DARK_GRAY, (WIDTH // 2 - 250, HEIGHT // 2 - 120, 500, 240), border_radius=15)
    pygame.draw.rect(screen, color_theme, (WIDTH // 2 - 250, HEIGHT // 2 - 120, 500, 240), width=4, border_radius=15)

    title_lbl = get_font(36, bold=True).render(title_text, True, color_theme)
    screen.blit(title_lbl, (WIDTH // 2 - title_lbl.get_width() // 2, HEIGHT // 2 - 60))

    sub_lbl = get_font(20).render(subtitle_text, True, WHITE)
    screen.blit(sub_lbl, (WIDTH // 2 - sub_lbl.get_width() // 2, HEIGHT // 2 + 10))


# --- CENTRAL CONTROL CONTROLLER ---

def main():
    state = GameState()
    running = True
    physics_accumulator = 0.0

    while running:
        dt = clock.tick(state.target_fps)
        if dt > 100:
            dt = 100
        keys = pygame.key.get_pressed()
        
        # --- EVENT HANDLING ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                
                # LAUNCH State triggers
                if state.state == "LAUNCH":
                    if (WIDTH // 2 - 150) <= mx <= (WIDTH // 2 + 150) and 260 <= my <= 320:
                        state.play_sfx(SFX_COIN) # Click sound
                        state.state = "LEVEL_SELECT"
                    elif (WIDTH // 2 - 120) <= mx <= (WIDTH // 2 + 120) and 340 <= my <= 390:
                        state.play_sfx(SFX_COIN) # Click sound
                        state.state = "SETTINGS"
                
                # SETTINGS State triggers
                elif state.state == "SETTINGS":
                    # Toggle Audio button (Row 1)
                    if 740 <= mx <= 880 and 160 <= my <= 202:
                        state.sound_enabled = not state.sound_enabled
                        state.play_sfx(SFX_COIN)
                    # Volume Level Adjust (Row 2)
                    elif 740 <= mx <= 795 and 220 <= my <= 262: # Volume [-]
                        state.volume = max(0, state.volume - 10)
                        state.play_sfx(SFX_COIN)
                    elif 825 <= mx <= 880 and 220 <= my <= 262: # Volume [+]
                        state.volume = min(100, state.volume + 10)
                        state.play_sfx(SFX_COIN)
                    # Target FPS Adjust (Row 3)
                    elif 740 <= mx <= 795 and 280 <= my <= 322: # FPS [-]
                        state.target_fps = max(30, state.target_fps - 30)
                        state.play_sfx(SFX_COIN)
                    elif 825 <= mx <= 880 and 280 <= my <= 322: # FPS [+]
                        state.target_fps = min(300, state.target_fps + 30)
                        state.play_sfx(SFX_COIN)
                    # Reset game progression button (Row 4)
                    elif 740 <= mx <= 880 and 340 <= my <= 382:
                        state.coins = 500
                        state.unlocked_level = 1
                        state.current_level = 1
                        state.upgrades = {"engine": 1, "suspension": 1, "tyres": 1}
                        state.play_sfx(SFX_CRASH)
                    # Back button
                    elif (WIDTH // 2 - 100) <= mx <= (WIDTH // 2 + 100) and 580 <= my <= 635:
                        state.play_sfx(SFX_COIN)
                        state.state = "LAUNCH"

                # GARAGE State triggers
                elif state.state == "GARAGE":
                    # Paint color changes
                    for idx, name in enumerate(state.car_colors.keys()):
                        if (260 + idx*75) <= mx <= (260 + idx*75 + 65) and 385 <= my <= 420:
                            state.selected_color = name
                            state.play_sfx(SFX_GAS)
                    # Performance cards
                    up_x = 640
                    # Engine
                    if (up_x + 380) <= mx <= (up_x + 530) and 140 <= my <= 195:
                        if state.upgrade_item("engine"):
                            state.play_sfx(SFX_COIN) # Success
                        else:
                            state.play_sfx(SFX_CRASH) # Fail (Not enough coins)
                    # Suspension
                    elif (up_x + 380) <= mx <= (up_x + 530) and 250 <= my <= 305:
                        if state.upgrade_item("suspension"):
                            state.play_sfx(SFX_COIN)
                        else:
                            state.play_sfx(SFX_CRASH)
                    # Tyres
                    elif (up_x + 380) <= mx <= (up_x + 530) and 360 <= my <= 415:
                        if state.upgrade_item("tyres"):
                            state.play_sfx(SFX_COIN)
                        else:
                            state.play_sfx(SFX_CRASH)
                    
                    # Back to Main Menu
                    if 80 <= mx <= 280 and 580 <= my <= 635:
                        state.play_sfx(SFX_COIN)
                        state.state = "LEVEL_SELECT"
                    # Start Race Game
                    elif (WIDTH // 2 - 150) <= mx <= (WIDTH // 2 + 150) and 580 <= my <= 645:
                        state.reset_game_run()
                        state.play_sfx(SFX_ENGINE_HUM) # Rev sound on start
                        state.state = "PLAY"

                # LEVEL_SELECT State triggers
                elif state.state == "LEVEL_SELECT":
                    # Check selection grid (10 levels in 2x5 grid)
                    w, h = 180, 185
                    x_start = 120
                    dx = 210
                    
                    clicked_level = None
                    clicked_select_btn = False
                    
                    for lvl in range(1, 11):
                        row = (lvl - 1) // 5
                        col = (lvl - 1) % 5
                        lx = x_start + col * dx
                        ly = 110 + row * 220
                        
                        # Check click inside the level card
                        if lx <= mx <= (lx + w) and ly <= my <= (ly + h):
                            if lvl <= state.unlocked_level:
                                clicked_level = lvl
                                # Check if click was inside the "SELECT" button on that card
                                if lx + 25 <= mx <= lx + 155 and ly + 130 <= my <= ly + 168:
                                    clicked_select_btn = True
                                break
                    
                    if clicked_level is not None:
                        state.current_level = clicked_level
                        if clicked_select_btn:
                            state.play_sfx(SFX_COIN)
                            state.state = "GARAGE"
                    
                    # Bottom Navigation bar
                    if (WIDTH // 2 - 150) <= mx <= (WIDTH // 2 + 150) and 570 <= my <= 630:
                        state.play_sfx(SFX_COIN)
                        state.state = "GARAGE"
                    elif 120 <= mx <= 300 and 570 <= my <= 625:
                        state.play_sfx(SFX_COIN)
                        state.state = "LAUNCH"

                # PLAY State HUD Triggers
                elif state.state == "PLAY":
                    # Exit to garage menu mid-run
                    if (WIDTH - 180) <= mx <= (WIDTH - 30) and 18 <= my <= 66:
                        state.state = "GARAGE"

            # Keypress reactions inside menus
            elif event.type == pygame.KEYDOWN:
                if state.state == "PLAY":
                    if event.key == pygame.K_ESCAPE:
                        state.state = "GARAGE"
                    elif event.key == pygame.K_RETURN:
                        if state.crashed:
                            state.reset_game_run()
                        elif state.finished:
                            state.state = "GARAGE"

        # --- UPDATE & RENDER ---
        if state.state == "LAUNCH":
            draw_launch_screen(state)
        elif state.state == "SETTINGS":
            draw_settings_screen(state)
        elif state.state == "GARAGE":
            draw_garage_screen(state)
        elif state.state == "LEVEL_SELECT":
            draw_level_select_screen(state)
        elif state.state == "PLAY":
            if not state.finished and not state.crashed:
                physics_accumulator += dt
                while physics_accumulator >= 16.667:
                    run_physics_frame(state, keys)
                    physics_accumulator -= 16.667
            draw_play_screen(state)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()