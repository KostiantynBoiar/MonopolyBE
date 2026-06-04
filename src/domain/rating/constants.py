"""ELO rating constants. See domain/rating/elo.py for how they're applied."""

INITIAL_RATING = 800

# A player's first CALIBRATION_GAMES games are provisional: bigger K + cap so the rating
# converges quickly (chess-style). After that, the steady-state values apply.
CALIBRATION_GAMES = 3

CALIBRATION_K = 120
CALIBRATION_CAP = 75  # max |Δ| per provisional game

REGULAR_K = 48
REGULAR_CAP = 25  # max |Δ| per steady-state game

RATING_FLOOR = 100  # rating never drops below this
