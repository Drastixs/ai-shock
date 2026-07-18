"""All loop tunables in one place (loop-design.md §7).

Every magic number the demo might want to tweak live lives here so logic modules
stay clean. Import as `from config import CFG` or override fields on the command
line in loop.py.
"""

import os
from dataclasses import dataclass


@dataclass
class Config:
    # --- capture -----------------------------------------------------------
    display: str = ":1"                 # X display the game renders on

    # --- vision detection --------------------------------------------------
    engine_path: str = "~/models/yolo26n_fp16.engine"
    img_size: int = 640
    conf_thres: float = 0.40            # decode floor (drop boxes below this)

    # --- telemetry detection ----------------------------------------------
    telemetry_host: str = "127.0.0.1"
    telemetry_port: int = 28786
    stale_ms: int = 100                 # ignore telemetry packets older than this

    # --- select / decide ---------------------------------------------------
    min_box_px: int = 8                 # ignore boxes narrower than this
    fire_conf: float = 0.40             # confidence needed to pull the trigger
    nudge: bool = False                 # enable L/R aim-assist (stretch)
    nudge_deadzone_px: int = 40

    # --- stim output (Genesis Mini SoftAP) --------------------------------
    stim_host: str = "192.168.4.1"
    stim_port: int = 4210
    trigger_channel: int = 1
    left_channel: int = 2
    right_channel: int = 3
    fire_burst_ms: int = 120            # trigger pulse length
    nudge_burst_ms: int = 80            # L/R nudge pulse length
    max_burst_ms: int = 300             # hard clamp (mirrors firmware)
    cooldown_ms: int = 300              # min gap between fires on a channel

    def engine(self):
        return os.path.expanduser(self.engine_path)


CFG = Config()
