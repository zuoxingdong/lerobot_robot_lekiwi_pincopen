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

"""Configuration for the PincOpen LeKiwi (``--robot.type=lekiwi_pincopen``)."""

from dataclasses import dataclass

from lerobot.robots import RobotConfig
from lerobot.robots.lekiwi.config_lekiwi import LeKiwiConfig


@RobotConfig.register_subclass("lekiwi_pincopen")
@dataclass
class PincOpenLeKiwiConfig(LeKiwiConfig):
    # Servo tuning, applied by configure() on every connect. Lowering the P-gain on
    # the four big joints is the critical fix against jitter and servo overload
    # shutdowns; stock lerobot writes P=16 arm-wide.
    arm_p_coefficient: int = 14  # all arm joints (14: smooth, 16: jittery)
    heavy_p_coefficient: int = 10  # the four STS3250 joints (10: smooth, 12: jittery)
    heavy_acceleration: int = 200  # acceleration limit on the STS3250 joints
    # PincOpen gripper safety params (move fast through air, back off on contact)
    gripper_acceleration: int = 200
    # NOTE: keep percent signs out of these comments; draccus feeds them to argparse
    # help, which treats a bare percent as a format character and crashes --help.
    gripper_overload_torque: int = 65  # unit: percent
    gripper_protective_torque: int = 5  # unit: percent
    gripper_protection_time: int = 7  # unit: 10 ms
