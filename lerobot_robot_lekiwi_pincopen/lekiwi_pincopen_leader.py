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

"""Single teleoperator driving LeKiwi's arm and mobile base.

LeKiwi needs two devices at once: a leader arm for the follower arm, and a keyboard for the
holonomic base. Stock ``lerobot-teleoperate`` has no way to express that, and while
``record_loop`` carries a ``list[Teleoperator]`` branch for it, nothing ever builds that list,
so it is unreachable. Composing both devices behind one teleoperator (the way
``bi_so_leader`` composes two arms) means the CLIs see one ordinary ``Teleoperator``.

Proposed upstream in huggingface/lerobot#3741. As of 0.6.1 ``lerobot-teleoperate`` still carries
the "if more robots require multiple teleoperators (like lekiwi)" TODO rather than a composite,
so this remains the way to drive both devices from one CLI — here with the sprung SO-101 leader
instead of the stock one.
"""

import logging
from dataclasses import fields
from functools import cached_property
from typing import Any

from lerobot.processor import RobotAction
from lerobot.teleoperators.keyboard import KeyboardTeleop, KeyboardTeleopConfig
from lerobot.teleoperators.teleoperator import Teleoperator
from lerobot.utils.decorators import check_if_not_connected

from .config_lekiwi_pincopen_leader import PincOpenLeKiwiLeaderConfig
from .config_so101_leader_sprung import SprungSO101LeaderConfig
from .so101_leader_sprung import SprungSO101Leader

logger = logging.getLogger(__name__)

BASE_FEATURES = ("x.vel", "y.vel", "theta.vel")


class PincOpenLeKiwiLeader(Teleoperator):
    """Sprung SO-101 leader for the arm, keyboard for the base, behind one teleoperator."""

    config_class = PincOpenLeKiwiLeaderConfig
    name = "lekiwi_pincopen_leader"

    def __init__(self, config: PincOpenLeKiwiLeaderConfig):
        super().__init__(config)
        self.config = config

        # The arm keeps this teleoperator's own id, unsuffixed. `BiSOLeader` appends
        # `_left`/`_right` because it has two arms whose calibration files must not collide;
        # LeKiwi has one, so a suffix would only orphan the leader's existing calibration
        # (``<calibration_dir>/<id>.json``) and force a pointless recalibration.
        #
        # Copy whatever the installed lerobot's SOLeaderConfig carries rather than naming
        # each field: the set grows between releases (`num_read_retries` postdates 0.6.x),
        # and naming them here would silently drop a field the user had set.
        arm_config = SprungSO101LeaderConfig(
            id=config.id,
            calibration_dir=config.calibration_dir,
            **{f.name: getattr(config.arm_config, f.name) for f in fields(config.arm_config)},
        )

        self.arm = SprungSO101Leader(arm_config)
        # No calibration_dir for the keyboard: it needs no calibration, and sharing the arm's
        # directory would make it read the arm's calibration file as its own.
        self.keyboard = KeyboardTeleop(KeyboardTeleopConfig(id=config.id))
        self.speed_index = 0  # Start at slow

    @cached_property
    def action_features(self) -> dict[str, type]:
        return {
            **{f"arm_{key}": value for key, value in self.arm.action_features.items()},
            **dict.fromkeys(BASE_FEATURES, float),
        }

    @cached_property
    def feedback_features(self) -> dict[str, type]:
        """Arm joints the leader can be driven to, in LeKiwi's robot action key space.

        Non-empty features plus the torque toggles below mark this teleop as actuated,
        which is what makes DAgger's handover drive the leader to the follower rather
        than the follower to the leader. The ``arm_`` prefix has to match
        ``action_features`` or that handover silently no-ops.
        """
        return {f"arm_{key}": value for key, value in self.arm.feedback_features.items()}

    @property
    def is_connected(self) -> bool:
        # The keyboard is best-effort: pynput cannot capture keys on Wayland or on a headless
        # machine, and there the arm should still be teleoperable on its own.
        return self.arm.is_connected

    @property
    def is_calibrated(self) -> bool:
        return self.arm.is_calibrated

    def connect(self, calibrate: bool = True) -> None:
        self.arm.connect(calibrate)
        self.keyboard.connect()
        if not self.keyboard.is_connected:
            logger.warning(
                "LeKiwi's base keyboard is unavailable, so the base will not move. The arm "
                "remains teleoperable. See the KeyboardTeleop warning above for the cause."
            )

    def calibrate(self) -> None:
        self.arm.calibrate()

    def configure(self) -> None:
        self.arm.configure()

    def setup_motors(self) -> None:
        self.arm.setup_motors()

    def _base_action(self) -> RobotAction:
        """Turn the currently held keys into base velocities."""
        if not self.keyboard.is_connected:
            # Keep the action space complete so the base is commanded to hold still.
            return dict.fromkeys(BASE_FEATURES, 0.0)

        pressed_keys = self.keyboard.get_action()
        keys = self.config.teleop_keys

        if keys["speed_up"] in pressed_keys:
            self.speed_index = min(self.speed_index + 1, len(self.config.speed_levels) - 1)
        if keys["speed_down"] in pressed_keys:
            self.speed_index = max(self.speed_index - 1, 0)

        speed_setting = self.config.speed_levels[self.speed_index]
        xy_speed = speed_setting["xy"]  # m/s
        theta_speed = speed_setting["theta"]  # deg/s

        x_cmd = 0.0  # m/s forward/backward
        y_cmd = 0.0  # m/s lateral
        theta_cmd = 0.0  # deg/s rotation

        if keys["forward"] in pressed_keys:
            x_cmd += xy_speed
        if keys["backward"] in pressed_keys:
            x_cmd -= xy_speed
        if keys["left"] in pressed_keys:
            y_cmd += xy_speed
        if keys["right"] in pressed_keys:
            y_cmd -= xy_speed
        if keys["rotate_left"] in pressed_keys:
            theta_cmd += theta_speed
        if keys["rotate_right"] in pressed_keys:
            theta_cmd -= theta_speed

        return {"x.vel": x_cmd, "y.vel": y_cmd, "theta.vel": theta_cmd}

    @check_if_not_connected
    def get_action(self) -> RobotAction:
        # The follower arm's joints are prefixed on LeKiwi, the base velocities are not.
        action = {f"arm_{key}": value for key, value in self.arm.get_action().items()}
        action.update(self._base_action())
        return action

    @check_if_not_connected
    def send_feedback(self, feedback: dict[str, Any]) -> None:
        # Base `*.vel` keys fall through unactuated; only arm joints can be driven.
        self.arm.send_feedback(
            {key.removeprefix("arm_"): value for key, value in feedback.items() if key.startswith("arm_")}
        )

    def enable_torque(self) -> None:
        self.arm.enable_torque()

    def disable_torque(self) -> None:
        self.arm.disable_torque()

    def disconnect(self) -> None:
        self.arm.disconnect()
        if self.keyboard.is_connected:
            self.keyboard.disconnect()
