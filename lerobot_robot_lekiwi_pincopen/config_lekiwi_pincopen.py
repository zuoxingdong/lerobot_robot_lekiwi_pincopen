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

from dataclasses import dataclass, field, replace

from lerobot.cameras import CameraConfig
from lerobot.robots import RobotConfig
from lerobot.robots.lekiwi.config_lekiwi import LeKiwiConfig, lekiwi_cameras_config


def pincopen_cameras_config() -> dict[str, CameraConfig]:
    """The inherited LeKiwi camera defaults, with MJPG pinned on every entry.

    Without a fourcc, OpenCV takes the camera's first-advertised format — uncompressed
    YUYV at ~147 Mbps each, enough for three cameras to saturate the Pi's shared USB2 bus.
    That fails as silently dropped frames rather than an error, so it stays pinned here
    even though lerobot has set MJPG in ``lekiwi_cameras_config`` since 0.6.1.

    This guards the defaults only: a ``cameras:`` block in yaml replaces this factory
    wholesale and has to pin ``fourcc`` itself. The WiFi link is unaffected either way,
    since ``lekiwi_host`` JPEG-encodes every frame before publishing it over ZMQ.
    """
    return {name: replace(cfg, fourcc="MJPG") for name, cfg in lekiwi_cameras_config().items()}


# Which arm joints carry an STS3250 instead of the stock STS3215. Hardware
# inventory only: this drives the motor model declared on the bus, nothing else.
# 2026-08-14: shoulder_pan carries an STS3250 again (the interim STS3215 that made
# the two sets diverge is retired), so the four load-bearing joints are uniform.
STS3250_JOINTS = ("arm_shoulder_pan", "arm_shoulder_lift", "arm_elbow_flex", "arm_wrist_flex")

# Which arm joints get the heavy tuning (lower P-gain, capped acceleration).
# Kept as a separate set from the inventory above: the heavy tuning tracks the
# servo model fitted to a slot (low P tames the STS3250's authority), so if a
# slot ever runs a weaker STS3215 again it should leave this set but keep its
# place in the arm.
HEAVY_JOINTS = ("arm_shoulder_pan", "arm_shoulder_lift", "arm_elbow_flex", "arm_wrist_flex")

# A vetted per-joint ceiling on |goal - present| for the inherited `max_relative_target`,
# which bounds how far one tick may command a joint from where it currently is. Left opt-in
# (the field defaults to None) because enabling it adds a Present_Position read to every
# send_action, on a bus that already needs `num_read_retries` when several joints move at
# once. Turn it on from the HOST yaml, where LeKiwi.send_action runs:
#   robot:
#     max_relative_target: {arm_shoulder_pan.pos: 40.0, ...}
#
# Units follow each joint's norm mode: degrees for the five body joints (use_degrees=True),
# percent of travel for the gripper. One value across the body joints on purpose: this is a
# backstop against a command no human or policy should issue, not a per-joint tuning, and it
# sits above every per-tick delta seen in ordinary teleoperation and leader takeovers so it
# should never fire in normal use. Load-dependent protection belongs in `joint_torque_limits`,
# which caps how hard a joint pulls rather than how far it is asked to jump. Raise this if the
# host starts logging "Relative goal position magnitude had to be clamped" during normal work.
PINCOPEN_MAX_RELATIVE_TARGET = {
    "arm_shoulder_pan.pos": 40.0,
    "arm_shoulder_lift.pos": 40.0,
    "arm_elbow_flex.pos": 40.0,
    "arm_wrist_flex.pos": 40.0,
    "arm_wrist_roll.pos": 40.0,
    # Full travel, i.e. no effective cap: the sprung trigger's release is a one-tick
    # full-range move by design, and clamping it would soften the spring.
    "arm_gripper.pos": 100.0,
}


@RobotConfig.register_subclass("lekiwi_pincopen")
@dataclass
class PincOpenLeKiwiConfig(LeKiwiConfig):
    cameras: dict[str, CameraConfig] = field(default_factory=pincopen_cameras_config)

    # Servo inventory and load profile. Both are config fields so a servo swap is a
    # yaml edit, not a code change.
    sts3250_joints: tuple[str, ...] = STS3250_JOINTS  # joints fitted with an STS3250
    heavy_joints: tuple[str, ...] = HEAVY_JOINTS  # joints given the heavy P-gain and acceleration

    # Extra attempts for the torque-enable at the end of configure(). That write is the
    # first thing every joint must acknowledge, and stock lerobot retries it zero times, so
    # one dropped Feetech status packet aborts the whole launch. (disconnect already retries
    # its disable_torque 5x, so the connect path was the odd one out.)
    num_write_retries: int = 2

    # Servo tuning, applied by configure() on every connect. Lowering the P-gain on
    # the four big joints is the critical fix against jitter and servo overload
    # shutdowns; stock lerobot writes P=16 arm-wide.
    arm_p_coefficient: int = 14  # all arm joints (14: smooth, 16: jittery)
    heavy_p_coefficient: int = 10  # the heavy joints (10: smooth, 12: jittery)
    heavy_acceleration: int = 200  # acceleration limit on the heavy joints
    # Derivative gain, mirroring the P structure above. Damping opposes velocity, so it
    # suppresses the hunting that a loaded joint falls into at high gain; raising D and P
    # together keeps the damping ratio while buying back stiffness. Too much D amplifies
    # encoder quantisation into an audible buzz, which is the signal you have overshot.
    # I is deliberately left at 0 and not exposed: on a joint that saturates under gravity
    # the integral term winds up and holds maximum current, which is the condition that
    # disturbs the servo bus.
    arm_d_coefficient: int = 32  # all arm joints
    heavy_d_coefficient: int = 32  # the heavy joints, overrides the arm-wide value
    # Per-joint last word on the two knobs above, applied after the arm-wide and heavy
    # passes so they win. Use when one joint needs a value that neither set describes,
    # e.g. a joint that carries a heavy load but no longer carries the bigger servo.
    #   joint_p_overrides: {arm_shoulder_pan: 12}
    #   joint_acceleration_overrides: {arm_shoulder_pan: 200}
    # NOTE: Acceleration (reg 41) is a RAM register, so it resets to 0 on power cycle and
    # is only in effect while the robot has been configured since it last powered up.
    joint_p_overrides: dict[str, int] = field(default_factory=dict)
    joint_d_overrides: dict[str, int] = field(default_factory=dict)
    joint_acceleration_overrides: dict[str, int] = field(default_factory=dict)
    # Hard ceiling on commanded torque, 0-1000 = 0-100 percent of Max_Torque_Limit. The
    # servos ship at 1000, i.e. uncapped, so a joint that saturates holding a load out at
    # full reach pulls whatever current it can, and that spike is what disturbs the bus.
    # Capping trades holding force for a bounded draw: the arm sags sooner instead of the
    # session dying. Torque_Limit is a RAM register, so configure() rewrites it each connect.
    joint_torque_limits: dict[str, int] = field(default_factory=dict)

    # PincOpen gripper safety params (move fast through air, back off on contact)
    gripper_acceleration: int = 200
    # NOTE: keep percent signs out of these comments; draccus feeds them to argparse
    # help, which treats a bare percent as a format character and crashes --help.
    gripper_overload_torque: int = 65  # unit: percent
    gripper_protective_torque: int = 5  # unit: percent
    gripper_protection_time: int = 7  # unit: 10 ms
