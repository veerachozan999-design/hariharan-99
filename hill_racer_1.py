import sys
import math
import random
import pygame

# Initialize pygame
pygame.init()
pygame.mixer.init()

# Window Setup
WIDTH = 1280
HEIGHT = 720
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.DOUBLEBUF)
pygame.display.set_caption("Hill Racer")
clock = pygame.time.Clock()

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
    5: {"name": "Volcanic Ridge", "sky": (15, 5, 5), "horizon": (120, 10, 10), "ground": (45, 30, 30)}
}

# --- SYSTEM FONTS ---
def get_font(size, bold=False):
    return pygame.font.SysFont("Arial", size, bold=bold)

# --- CLASS DEFINITIONS ---

class Particle:
    def __init__(self, x, y, color, vx, vy, size=8, life=30):
        self.x = x
        self.y = y
        self.color = color
        self.vx = vx
        self.vy = vy
        self.size = size
        self.life = life
        self.max_life = life

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        self.size = max(0.5, self.size * 0.95)

    def draw(self, surface, offset_x):
        if self.life > 0:
            alpha = int((self.life / self.max_life) * 255)
            # Create a temporary surface to draw transparent particles
            p_surf = pygame.Surface((int(self.size*2), int(self.size*2)), pygame.SRCALPHA)
            pygame.draw.circle(p_surf, (*self.color, alpha), (int(self.size), int(self.size)), int(self.size))
            surface.blit(p_surf, (self.x - offset_x - self.size, self.y - self.size))


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
        self.show_debug = False

        # Gameplay tracking
        self.current_level = 1
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
        
        # Level configuration parameters
        self.finish_x = 7500
        self.coins_list = []
        self.gas_list = []
        self.generate_collectibles()
        self.particles = []

    def generate_collectibles(self):
        self.coins_list = []
        self.gas_list = []
        # Populate coins along the hills
        for x in range(800, self.finish_x - 300, 150):
            if random.random() < 0.4:
                y = get_terrain_height(x, self.current_level) - 50
                self.coins_list.append({"x": x, "y": y, "collected": False})
        # Populate Gas Canisters
        for x in range(1500, self.finish_x - 500, 1200):
            y = get_terrain_height(x, self.current_level) - 40
            self.gas_list.append({"x": x, "y": y, "collected": False})

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
    else: # Level 5: Volcanic Ridge - Extreme steep climbs and drops
        base = 560
        wave1 = 150 * math.sin(x * 0.002)
        wave2 = 60 * math.sin(x * 0.005)
        gap = 0
        if 4000 < x < 4300: # Deadfall Gap
            gap = 120 * math.sin((x - 4000) / 300.0 * math.pi)
        return base + wave1 + wave2 + gap


# --- DRAWING UTILITIES ---

_gradient_cache = {}

def draw_gradient_sky(surface, top_color, bottom_color):
    """Draws a smooth background gradient representing sunset/neon themes.
    Pre-renders gradient to a 1px-wide surface and scales it up, then caches
    the result per color-pair so we never recompute 720 line draws per frame."""
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

def draw_parallax_mountains(surface, offset_x, theme_idx):
    """Draws layered background silhouettes."""
    if theme_idx == 1: # Sunset Valley Mountains
        colors = [(100, 45, 80), (70, 30, 60), (45, 15, 40)]
    elif theme_idx == 2: # City Skyline
        draw_city_skyline(surface, offset_x)
        return
    elif theme_idx == 3: # Canyon Walls
        colors = [(160, 80, 40), (120, 50, 25), (80, 30, 15)]
    elif theme_idx == 4: # Snowy Mountains
        colors = [(80, 110, 140), (60, 80, 110), (40, 55, 85)]
    else: # Volcanic Rocks
        colors = [(40, 10, 10), (30, 5, 5), (15, 0, 0)]

    if theme_idx != 2:
        for i, color in enumerate(colors):
            factor = 0.15 * (i + 1)
            points = [(0, HEIGHT)]
            for screen_x in range(0, WIDTH + 40, 40):
                world_x = screen_x + offset_x * factor
                # Multi-frequency landscape synthesis
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
    screen.blit(title_lbl, (WIDTH // 2 - title_lbl.get_width() // 2, 50))

    # Grid of Levels
    for lvl in range(1, 6):
        x = 90 + (lvl-1) * 225
        y = 220
        w, h = 200, 260
        
        # Check unlocked
        unlocked = lvl <= state.unlocked_level
        card_color = DARK_GRAY if unlocked else (25, 25, 28)
        border_color = GREEN if (unlocked and state.current_level == lvl) else (GRAY if unlocked else RED)
        
        pygame.draw.rect(screen, card_color, (x, y, w, h), border_radius=15)
        pygame.draw.rect(screen, border_color, (x, y, w, h), width=4, border_radius=15)

        # Level Info
        num_lbl = get_font(32, bold=True).render(f"LEVEL {lvl}", True, WHITE)
        screen.blit(num_lbl, (x + (w - num_lbl.get_width()) // 2, y + 30))

        name_str = LEVEL_THEMES[lvl]["name"]
        name_lbl = get_font(16, bold=True).render(name_str, True, GOLD if unlocked else GRAY)
        screen.blit(name_lbl, (x + (w - name_lbl.get_width()) // 2, y + 90))

        # Difficuly visualizer
        diff_str = "★" * lvl + "☆" * (5 - lvl)
        diff_lbl = get_font(18).render(f"Diff: {diff_str}", True, ORANGE)
        screen.blit(diff_lbl, (x + (w - diff_lbl.get_width()) // 2, y + 140))

        if unlocked:
            draw_glowing_button("SELECT", x + 30, y + 190, 140, 45, BLUE)
        else:
            lock_lbl = get_font(20, bold=True).render("LOCKED", True, RED)
            screen.blit(lock_lbl, (x + (w - lock_lbl.get_width()) // 2, y + 200))

    # Navigation Controls
    draw_glowing_button("CUSTOMIZE VEHICLE", WIDTH // 2 - 150, 560, 300, 60, GREEN)
    draw_glowing_button("BACK", 90, 560, 180, 55, DARK_GRAY)


# --- SETTINGS SCREEN ---

def draw_settings_screen(state):
    draw_gradient_sky(screen, (30, 20, 50), (15, 10, 25))
    
    t_font = get_font(40, bold=True)
    title_lbl = t_font.render("GAME SETTINGS", True, WHITE)
    screen.blit(title_lbl, (WIDTH // 2 - title_lbl.get_width() // 2, 80))

    # Panel
    pygame.draw.rect(screen, DARK_GRAY, (340, 180, 600, 360), border_radius=15)

    # Option: Sound Toggle
    sound_status = "ON" if state.sound_enabled else "OFF"
    lbl_sound = get_font(26, bold=True).render(f"AUDIO FEEDBACK:  {sound_status}", True, WHITE)
    screen.blit(lbl_sound, (400, 240))
    draw_glowing_button("TOGGLE", 740, 230, 140, 45, ORANGE)

    # Option: Reset Progression
    lbl_reset = get_font(26, bold=True).render("RESET SAVED PROGRESS", True, WHITE)
    screen.blit(lbl_reset, (400, 330))
    draw_glowing_button("RESET", 740, 320, 140, 45, RED)

    # Instructions box
    instructions = [
        "CONTROLS:  Hold [D] or [RIGHT] key to Accelerate forward.",
        "                  Hold [A] or [LEFT] to Brake, then Reverse / Balance in Air.",
        "                  Collect coins to upgrade parts in the Garage."
    ]
    for idx, text in enumerate(instructions):
        text_lbl = get_font(16).render(text, True, GRAY)
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

def run_physics_frame(state, keys):
    """Updates custom 2D horizontal-scrolling car dynamics."""
    
    # Check for empty fuel
    if state.gas <= 0:
        state.gas = 0
        # Slowly decay horizontal speed if out of gas
        state.vx *= 0.95
    else:
        state.gas -= 0.04 # Fuel depletion rate

    # Configuration modifiers from Custom Upgrades
    engine_mult = 1.0 + (state.upgrades["engine"] - 1) * 0.18
    tyre_mult = 1.0 + (state.upgrades["tyres"] - 1) * 0.14
    suspension_stiffness = 0.075 + (state.upgrades["suspension"] - 1) * 0.018
    suspension_damping = 0.78 - (state.upgrades["suspension"] - 1) * 0.025

    # Check terrain below wheel locations
    # Set wheel horizontal offsets
    rad = state.angle
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    # Wheel hub attachment offsets. These match draw_car_sprite exactly so
    # ground contact and the visual tyres stay aligned.
    axle_y = max(16, VEHICLE_AXLE_Y - state.upgrades["suspension"] * 1.5)
    back_offset_x = VEHICLE_REAR_AXLE_X * cos_a - axle_y * sin_a
    back_offset_y = VEHICLE_REAR_AXLE_X * sin_a + axle_y * cos_a
    front_offset_x = VEHICLE_FRONT_AXLE_X * cos_a - axle_y * sin_a
    front_offset_y = VEHICLE_FRONT_AXLE_X * sin_a + axle_y * cos_a

    wb_x = state.car_x + back_offset_x
    wb_y = state.car_y + back_offset_y
    wf_x = state.car_x + front_offset_x
    wf_y = state.car_y + front_offset_y

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
        state.vy += back_spring_f
        state.vy *= max(0.66, suspension_damping)
        
    front_spring_f = 0
    if front_grounded:
        front_spring_f = ((terrain_y_front - radius) - wf_y) * suspension_stiffness
        state.vy += front_spring_f
        state.vy *= max(0.66, suspension_damping)

    # Apply torque tilt rotation from suspension variations
    if back_grounded:
        state.omega -= (back_spring_f * 0.012)
    if front_grounded:
        state.omega += (front_spring_f * 0.012)

    # Input Accelerate/Brake & Rotation Forces
    is_accelerating = keys[pygame.K_d] or keys[pygame.K_RIGHT]
    is_braking = keys[pygame.K_a] or keys[pygame.K_LEFT]

    # Ground Traction Movement
    MAX_SPEED = 8.2 * engine_mult  # Top speed scales with engine upgrades, not unbounded
    if back_grounded or front_grounded:
        grounded_wheels = int(back_grounded) + int(front_grounded)
        traction = tyre_mult * (0.72 + grounded_wheels * 0.14)
        if is_accelerating:
            if state.vx < MAX_SPEED:
                state.vx += ACCELERATION_FORCE * engine_mult * traction
                state.vx = min(state.vx, MAX_SPEED)
            # Smooth launch torque: enough character, not a back-flip.
            state.omega += 0.0028 * traction
            # Spawn dust particles
            if len(state.particles) < MAX_PARTICLES and random.random() < 0.3:
                state.particles.append(Particle(wb_x, wb_y + 10, GRAY, -random.random()*4 - 2, -random.random()*2))
        elif is_braking:
            # Brake power scales with tyre grip and stays stable on steep slopes.
            brake_power = BRAKE_FORCE * traction
            if state.vx > 0.12:
                state.vx = max(0.0, state.vx - brake_power)
                state.omega -= 0.0018 * traction
                if len(state.particles) < MAX_PARTICLES and random.random() < 0.42:
                    state.particles.append(Particle(wf_x, wf_y + 10, (60, 60, 60), random.random()*2, -random.random()*1.5, size=6, life=18))
            elif state.vx < -0.08:
                state.vx = max(MAX_REVERSE_SPEED, state.vx - REVERSE_FORCE * traction)
            else:
                # Hold brake at a stop to ease into reverse.
                state.vx = max(MAX_REVERSE_SPEED, state.vx - REVERSE_FORCE * traction)
        else:
            # Natural engine braking / rolling friction when no input
            state.vx *= 0.990
    else:
        # Air Rotation mechanics (Balance your car in mid-air!)
        if is_accelerating: # Pitch down / Clockwise rotation
            state.omega += 0.004
        elif is_braking: # Pitch up / Counter-clockwise rotation
            state.omega -= 0.004

    # Apply Gravity
    gravity = 0.26
    state.vy += gravity

    # Natural Air Resistances / Drags
    state.vx *= 0.985
    state.vy *= 0.99
    state.omega *= 0.94 # Rotational air dampening

    # Position Updates
    state.car_x += state.vx
    state.car_y += state.vy
    state.angle += state.omega
    state.wheel_rotation += state.vx / max(1.0, VEHICLE_WHEEL_RADIUS)

    # Keep angles within standard boundary [-PI, PI]
    if state.angle > math.pi: state.angle -= 2 * math.pi
    elif state.angle < -math.pi: state.angle += 2 * math.pi

    # Check for Ground Collisions (Crashes)
    chassis_terrain_y = get_terrain_height(state.car_x, state.current_level)
    # Crash conditions: Upside down contact OR chassis bottoming out deep
    if state.car_y > chassis_terrain_y - 12:
        deg = abs(math.degrees(state.angle))
        if deg > 92 and deg < 268:
            state.crashed = True
        # Push car up from deep ground clips
        state.car_y = chassis_terrain_y - 12
        state.vy = max(0, state.vy - 1)

    # Restrict backward progression boundary
    if state.car_x < 100:
        state.car_x = 100
        state.vx = max(0, state.vx)

    # Check Level Finish
    if state.car_x >= state.finish_x:
        state.finished = True
        # Unlock the next level
        if state.current_level == state.unlocked_level and state.unlocked_level < 5:
            state.unlocked_level += 1
            state.coins += 250 # Bonus completed reward

    # Process Collectibles overlap
    # Coins
    for coin in state.coins_list:
        if not coin["collected"]:
            dist = math.hypot(state.car_x - coin["x"], state.car_y - coin["y"])
            if dist < 45:
                coin["collected"] = True
                state.coins += 20
                state.coins_collected_this_run += 20
                # Spawn glitter particles
                for _ in range(8):
                    if len(state.particles) < MAX_PARTICLES:
                        state.particles.append(Particle(coin["x"], coin["y"], GOLD, random.uniform(-3,3), random.uniform(-3,3), size=5, life=20))
    # Gas Cans
    for gas in state.gas_list:
        if not gas["collected"]:
            dist = math.hypot(state.car_x - gas["x"], state.car_y - gas["y"])
            if dist < 45:
                gas["collected"] = True
                state.gas = min(100.0, state.gas + 40.0)
                # Spawn gas splash green particles
                for _ in range(8):
                    if len(state.particles) < MAX_PARTICLES:
                        state.particles.append(Particle(gas["x"], gas["y"], GREEN, random.uniform(-3,3), random.uniform(-3,3), size=6, life=25))


# --- DRAWING IN-GAME ENVIRONMENT AND UI ---

def draw_play_screen(state):
    # Retrieve current active level theme
    theme = LEVEL_THEMES[state.current_level]
    draw_gradient_sky(screen, theme["sky"], theme["horizon"])
    
    # Parallax Background
    draw_parallax_mountains(screen, state.car_x, state.current_level)

    # Camera Offset tracking
    offset_x = state.car_x - 300

    # Draw Collectibles (Coins & Gas cans)
    for coin in state.coins_list:
        if not coin["collected"]:
            cx, cy = int(coin["x"] - offset_x), int(coin["y"])
            # Draw rotating/glowing golden coin
            pulse = int(5 * math.sin(pygame.time.get_ticks() * 0.01))
            pygame.draw.circle(screen, GOLD, (cx, cy), 12 + pulse // 2)
            pygame.draw.circle(screen, (255, 240, 150), (cx, cy), 8 + pulse // 2)

    for gas in state.gas_list:
        if not gas["collected"]:
            gx, gy = int(gas["x"] - offset_x), int(gas["y"])
            # Draw Red Canister
            rect = pygame.Rect(gx - 10, gy - 16, 20, 32)
            pygame.draw.rect(screen, RED, rect, border_radius=4)
            pygame.draw.rect(screen, WHITE, (gx - 10, gy - 10, 20, 8)) # Strip
            # Cap
            pygame.draw.rect(screen, DARK_GRAY, (gx - 5, gy - 21, 10, 5))

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

    # Outline edge of hills
    border_points = [(p[0], p[1]) for p in points[:-2]]
    pygame.draw.lines(screen, (min(theme["ground"][0]+30, 255), min(theme["ground"][1]+30, 255), min(theme["ground"][2]+30, 255)), False, border_points, 4)

    # Draw particles
    for p in state.particles:
        p.update()
        p.draw(screen, offset_x)
    # Clear dead particles
    state.particles = [p for p in state.particles if p.life > 0]

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

    while running:
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
                        state.state = "LEVEL_SELECT"
                    elif (WIDTH // 2 - 120) <= mx <= (WIDTH // 2 + 120) and 340 <= my <= 390:
                        state.state = "SETTINGS"
                
                # SETTINGS State triggers
                elif state.state == "SETTINGS":
                    # Toggle Audio button
                    if 740 <= mx <= 880 and 230 <= my <= 275:
                        state.sound_enabled = not state.sound_enabled
                    # Reset game progression button
                    elif 740 <= mx <= 880 and 320 <= my <= 365:
                        state.coins = 500
                        state.unlocked_level = 1
                        state.current_level = 1
                        state.upgrades = {"engine": 1, "suspension": 1, "tyres": 1}
                    # Back button
                    elif (WIDTH // 2 - 100) <= mx <= (WIDTH // 2 + 100) and 580 <= my <= 635:
                        state.state = "LAUNCH"

                # GARAGE State triggers
                elif state.state == "GARAGE":
                    # Paint color changes
                    for idx, name in enumerate(state.car_colors.keys()):
                        if (260 + idx*75) <= mx <= (260 + idx*75 + 65) and 385 <= my <= 420:
                            state.selected_color = name
                    # Performance cards
                    up_x = 640
                    # Engine
                    if (up_x + 380) <= mx <= (up_x + 530) and 140 <= my <= 195:
                        state.upgrade_item("engine")
                    # Suspension
                    elif (up_x + 380) <= mx <= (up_x + 530) and 250 <= my <= 305:
                        state.upgrade_item("suspension")
                    # Tyres
                    elif (up_x + 380) <= mx <= (up_x + 530) and 360 <= my <= 415:
                        state.upgrade_item("tyres")
                    
                    # Back to Main Menu
                    if 80 <= mx <= 280 and 580 <= my <= 635:
                        state.state = "LEVEL_SELECT"
                    # Start Race Game
                    elif (WIDTH // 2 - 150) <= mx <= (WIDTH // 2 + 150) and 580 <= my <= 645:
                        state.reset_game_run()
                        state.state = "PLAY"

                # LEVEL_SELECT State triggers
                elif state.state == "LEVEL_SELECT":
                    # Check selection grid
                    for lvl in range(1, 6):
                        lx = 90 + (lvl-1) * 225
                        ly = 220
                        if lx <= mx <= (lx + 200) and ly <= my <= (ly + 260):
                            if lvl <= state.unlocked_level:
                                state.current_level = lvl
                                # Auto transition to customize/play
                    
                    # Blue dynamic Selection buttons (Inside active items)
                    for lvl in range(1, 6):
                        lx = 90 + (lvl-1) * 225
                        if lx + 30 <= mx <= (lx + 170) and 410 <= my <= 455:
                            if lvl <= state.unlocked_level:
                                state.current_level = lvl
                                state.state = "GARAGE"

                    # Bottom Navigation bar
                    if (WIDTH // 2 - 150) <= mx <= (WIDTH // 2 + 150) and 560 <= my <= 620:
                        state.state = "GARAGE"
                    elif 90 <= mx <= 270 and 560 <= my <= 615:
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
                run_physics_frame(state, keys)
            draw_play_screen(state)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
