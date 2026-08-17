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

"""SO-101 leader whose gripper trigger springs back to open when released."""

import logging

from lerobot.teleoperators.so_leader.so_leader import SOLeader

from .config_so101_leader_sprung import SprungSO101LeaderConfig

logger = logging.getLogger(__name__)


class SprungSO101Leader(SOLeader):
    """SO-101 leader with a sprung gripper trigger.

    The gripper servo holds its calibrated open position with a soft,
    torque-capped P controller: the trigger resists progressively when
    squeezed and springs back to open when released — the SO-arm analogue of
    the Koch leader's current-based-position gripper trigger, emulated in
    position mode since the STS3215 has no current control mode. Position
    reads are unaffected, so recorded gripper actions are unchanged apart
    from a consistent open rest position between grasps.

    Calibration files are stored per teleoperator type: to reuse a
    calibration made with the stock ``so101_leader`` type, point
    ``calibration_dir`` at that directory (or copy the ``<id>.json`` file).
    """

    config_class = SprungSO101LeaderConfig
    name = "so101_leader_sprung"

    def configure(self) -> None:
        super().configure()  # torque off everywhere, POSITION mode everywhere
        # A low P gain makes resistance grow gradually with squeeze depth. The
        # torque cap sets both the maximum squeeze resistance and the return
        # force — they cannot be tuned independently. The P write persists in
        # the servo's EPROM.
        self.bus.write("P_Coefficient", "gripper", 8, normalize=False)
        self.bus.write("Acceleration", "gripper", 0, normalize=False)  # 0 = fastest ramp
        self.bus.write("Torque_Limit", "gripper", 75, normalize=False)
        self._arm_gripper_spring()

    def _arm_gripper_spring(self) -> None:
        """(Re-)arm the sprung trigger: gripper torque on, goal = fully open.

        RAM-only writes, so safe to repeat on every torque toggle; the P gain,
        acceleration and torque cap from configure() survive a torque-off. Skipped
        when disconnected, since the goal write is normalized and so needs a
        calibrated bus.
        """
        if not self.is_connected:
            return
        self.bus.enable_torque("gripper")
        self.bus.write("Goal_Position", "gripper", 100.0)  # normalized: fully open
        logger.info("%s sprung gripper armed", self)

    def disable_torque(self) -> None:
        """Release the arm joints but keep the gripper spring armed.

        DAgger calls this to hand the leader over, and the stock bus-wide torque-off
        would leave the trigger floppy for exactly the phase the human teleoperates.
        Re-arming targets fully open, so take over mid-grasp with the trigger already
        squeezed or the follower gripper will ease open.
        """
        super().disable_torque()
        self._arm_gripper_spring()
