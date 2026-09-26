"""Configuration constants for JY-001 DIY-2 humidifier driver."""

# GPIO Pin assignments
CONTROL_PIN = 17      # GPIO17 - Bidirectional control (LOW output / HIGH-Z input)
STATUS_PIN = 27       # GPIO27 - Input for OFF state detection

# Pulse timing
PULSE_DURATION = 0.5  # seconds - GPIO17 held LOW before releasing to HIGH-Z
PULSE_INTERVAL = 0.1  # seconds - minimum delay between pulses

# Mist levels
MIST_LEVEL_HIGH = 1   # Highest mist output
MIST_LEVEL_MEDIUM = 2 # Medium mist output
MIST_LEVEL_LOW = 3    # Lowest mist output
MIST_LEVEL_OFF = 4    # OFF state

VALID_LEVELS = (MIST_LEVEL_HIGH, MIST_LEVEL_MEDIUM, MIST_LEVEL_LOW, MIST_LEVEL_OFF)

# GPIO27 signal polarity configuration
# True  = GPIO27 reads HIGH when humidifier is OFF
# False = GPIO27 reads LOW when humidifier is OFF
STATUS_PIN_ACTIVE_HIGH = True

# Status detection timeout
STATUS_DETECTION_TIMEOUT = 5.0  # seconds - max time to wait for OFF confirmation

# Startup state assumption (pulses needed to reach known state from power-on)
# This should be calibrated against physical hardware
STARTUP_PULSES_TO_OFF = 3  # pulses to cycle through levels 1->2->3->OFF

# Maximum pulse retries for state synchronization
MAX_SYNC_RETRIES = 3