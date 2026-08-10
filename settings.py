"""All constants and balance for THE LAST REACTOR in one place."""

# --- screen -----------------------------------------------------------------
RES = WIDTH, HEIGHT = 1280, 720
FPS = 60
TITLE = "ПОСЛЕДНИЙ РЕАКТОР"

TILE = 40
FIELD_COLS = 25
FIELD_ROWS = 18
FIELD_W = FIELD_COLS * TILE            # 1000 px of battlefield
PANEL_X = FIELD_W                      # the right-hand control panel
PANEL_W = WIDTH - FIELD_W

# --- campaign ---------------------------------------------------------------
WAVES_TOTAL = 20
START_MONEY = 240
ROCK_COUNT = 16                        # decorative obstacles per map

DIFFICULTIES = (
    {"name": "ЛЁГКИЙ",  "hp": 0.85, "reward": 1.15, "lives": 25},
    {"name": "СРЕДНИЙ", "hp": 1.00, "reward": 1.00, "lives": 20},
    {"name": "КОШМАР",  "hp": 1.30, "reward": 0.85, "lives": 14},
)
HP_GROWTH = 0.07                       # +7% enemy hp per wave

SELL_RATIO = 0.7                       # refund share of everything invested
UPGRADE_RATIO = 0.8                    # upgrade price as share of base cost
MAX_LEVEL = 3

# per-level multipliers (level 1 is the base)
LVL_DMG = 1.45
LVL_RATE = 1.12
LVL_RANGE = 0.30                       # +tiles per level


def wave_bonus(wave):
    """Money paid out for clearing a wave."""
    return 25 + 7 * wave


# --- palette ----------------------------------------------------------------
C_BG = (10, 12, 18)
C_GROUND_A = (26, 30, 40)
C_GROUND_B = (30, 34, 46)
C_GRIDLINE = (38, 44, 58)
C_ROCK = (74, 80, 96)
C_ROCK_EDGE = (108, 116, 136)

C_PANEL = (15, 17, 25)
C_PANEL_EDGE = (66, 76, 106)

C_CORE = (90, 220, 255)
C_CORE_GLOW = (40, 120, 160)
C_PORTAL = (255, 110, 90)

C_MONEY = (240, 200, 90)
C_LIVES = (235, 90, 110)
C_GOOD = (120, 230, 140)
C_BAD = (240, 90, 90)
C_WARN = (255, 170, 60)
C_TEXT = (225, 228, 238)
C_DIM = (120, 126, 142)
C_ARCANE = (150, 150, 255)

# tower accent colors
C_GUN = (205, 215, 235)
C_CANNON = (255, 170, 90)
C_FROST = (120, 200, 255)
C_TESLA = (195, 145, 255)
