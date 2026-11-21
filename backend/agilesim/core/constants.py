"""Named constants, so that no magic strings or numbers are repeated in the code."""

API_PREFIX = "/v1"

# Roles carried by access tokens.
ROLE_FACILITATOR = "facilitator"
ROLE_PARTICIPANT = "participant"

# HTTP headers.
HEADER_REQUEST_ID = "X-Request-ID"

# Codes of the stages of the Startup Flow scenario (rows of ``scenario_stages``).
STAGE_BACKLOG = "backlog"
STAGE_ANALYSIS = "analysis"
STAGE_DEVELOPMENT = "development"
STAGE_TESTING = "testing"
STAGE_DONE = "done"
WORK_STAGES = (STAGE_ANALYSIS, STAGE_DEVELOPMENT, STAGE_TESTING)

# Game rules of Startup Flow.
DICE_MIN = 1
DICE_MAX = 6
GAME_DAYS = 8
FIRST_ROUND_LAST_DAY = 4  # days 1-4 are played without WIP limits
DAY_ONE_PULL = 5  # the five most valuable cards are pulled on day 1
BLOCK_RELEASE_POINTS = 3  # full Development points that remove a BLOCKED marker
HELP_DIVISOR = 2  # help from another stage counts half, rounded down

# Limits of input fields.
MIN_PASSWORD_LENGTH = 10
MAX_NAME_LENGTH = 60
JOIN_CODE_LENGTH = 6
