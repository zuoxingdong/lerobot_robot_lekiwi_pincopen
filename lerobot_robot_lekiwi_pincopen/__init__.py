# Copyright 2026 Xingdong Zuo.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""PincOpen LeKiwi — STS3250/PincOpen hardware customizations as a lerobot plugin.

A LeKiwi variant with the arm's four big joints upgraded to STS3250 servos, a
PincOpen gripper with a fixed EPROM calibration, and tuned servo parameters —
packaged out-of-tree, so a stock lerobot install drives the hardware with zero
source edits.

How it plugs in (works on lerobot 0.5.x and 0.6.x):

* Every lerobot CLI calls ``register_third_party_plugins()``, which imports any
  installed distribution named ``lerobot_robot_*``. Importing this package registers
  ``PincOpenLeKiwiConfig`` under ``--robot.type=lekiwi_pincopen``, and lerobot's
  ``make_robot_from_config`` fallback resolves the ``PincOpenLeKiwi`` class from it.
  On the robot's host machine:
  ``lerobot-calibrate --robot.type=lekiwi_pincopen --robot.id=...``
* ``lekiwi_host`` does no plugin discovery and hardcodes the ``LeKiwi`` class, so the
  host is launched through the wrapper module instead (same CLI, same yaml):
  ``python -m lerobot_robot_lekiwi_pincopen.lekiwi_host --config_path=...``

The teleoperating/recording client side is untouched: those CLIs talk to
``lekiwi_client``, which never touches motors.

The package also ships an optional leader-side teleoperator,
``--teleop.type=so101_leader_sprung`` — a stock SO-101 leader whose gripper
trigger springs back to open when released (see ``so101_leader_sprung.py``).
"""

from .config_lekiwi_pincopen import PincOpenLeKiwiConfig
from .config_so101_leader_sprung import SprungSO101LeaderConfig
from .lekiwi_pincopen import PINCOPEN_CALIBRATION, STS3250_JOINTS, PincOpenLeKiwi
from .so101_leader_sprung import SprungSO101Leader

__all__ = [
    "PincOpenLeKiwi",
    "PincOpenLeKiwiConfig",
    "PINCOPEN_CALIBRATION",
    "STS3250_JOINTS",
    "SprungSO101Leader",
    "SprungSO101LeaderConfig",
]
