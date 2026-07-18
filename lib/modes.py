# lib/modes.py — AS8016 program catalogue (P01..P24)
#
# The AUVON AS8016 has 24 sub-modes: P01-P16 are TENS (pain relief) and
# P17-P24 are EMS (muscle performance), per the manual (6 massage modes,
# 24 sub-mode choices). The "feel" strings are short human descriptions for
# the API's GET /modes catalogue; they are descriptive, not a device readout.
#
# master_mode is DERIVED from the program number, so it can never disagree
# with `mode`.

NUM_MODES = 24          # P01..P24
MAX_LEVEL = 20          # 20 discrete intensity levels (0 = off)

# index 0 -> "P01" ... index 23 -> "P24"
_FEEL = [
    "Continuous comfortable tingling.",                 # P01
    "Steady pressure-like pulsing.",                    # P02
    "Comfortable rhythmic tingling.",                   # P03
    "Slow wave that swells and fades.",                 # P04
    "Gentle kneading sensation.",                       # P05
    "Alternating push-pull massage.",                   # P06
    "Light tapping across the pad.",                    # P07
    "Deep rhythmic thumping.",                          # P08
    "Rolling, cupping-like draw.",                      # P09
    "Quick fluttering pulses.",                         # P10
    "Broad, warming continuous stimulation.",           # P11
    "Scraping/guasha-style sweep.",                     # P12
    "Combined tingle and knead cycle.",                 # P13
    "Long soothing pulse trains.",                      # P14
    "Randomized comfortable massage.",                  # P15
    "Full-body relaxation blend.",                      # P16
    "EMS: slow muscle contraction and release.",        # P17
    "EMS: steady hold-and-relax contractions.",         # P18
    "EMS: rhythmic strengthening pulses.",              # P19
    "Muscle twitches at a very low frequency, like a tapping massage.",  # P20
    "EMS: endurance-style repeated contractions.",      # P21
    "EMS: power contractions with rest intervals.",     # P22
    "Fast-twitch pulse frequency; builds maximum muscle strength.",      # P23
    "EMS: peak-strength maximal contraction.",          # P24
]


def mode_str(index):
    """0-based index -> 'P01'.. 'P24'."""
    return "P%02d" % (index + 1)


def mode_index(mode):
    """'P01'..'P24' -> 0-based index. Raises ValueError if invalid."""
    m = str(mode).upper().strip()
    if len(m) != 3 or m[0] != "P" or not m[1:].isdigit():
        raise ValueError("mode must be 'P01'..'P24', got %r" % (mode,))
    n = int(m[1:])
    if not (1 <= n <= NUM_MODES):
        raise ValueError("mode out of range 'P01'..'P24', got %r" % (mode,))
    return n - 1


def master_mode(mode):
    """'TENS' for P01-P16, 'EMS' for P17-P24 (derived from the number)."""
    return "TENS" if mode_index(mode) < 16 else "EMS"


def feel(mode):
    return _FEEL[mode_index(mode)]


def describe(mode):
    """Full record for one program."""
    return {"mode": mode_str(mode_index(mode)),
            "master_mode": master_mode(mode),
            "feel": feel(mode)}


def catalogue():
    """{'count': 24, 'modes': [ {mode, master_mode, feel}, ... ]}"""
    return {"count": NUM_MODES,
            "modes": [describe(mode_str(i)) for i in range(NUM_MODES)]}
