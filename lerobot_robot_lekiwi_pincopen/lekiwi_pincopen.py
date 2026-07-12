# Copyright 2026 Xingdong Zuo.
#
# The calibrate() and configure() bodies are derived from the LeRobot project
# (https://github.com/huggingface/lerobot, src/lerobot/robots/lekiwi/lekiwi.py),
# Copyright 2024 The HuggingFace Inc. team, licensed under the Apache License 2.0.
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

"""The PincOpen LeKiwi robot: STS3250 arm joints, PincOpen gripper, tuned servos."""

import logging
from dataclasses import replace

from lerobot.motors import MotorCalibration
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode
from lerobot.robots.lekiwi.config_lekiwi import LeKiwiConfig
from lerobot.robots.lekiwi.lekiwi import LeKiwi

from .config_lekiwi_pincopen import PincOpenLeKiwiConfig

logger = logging.getLogger(__name__)

# Arm joints 1-4 are upgraded to STS3250 (wrist_roll and gripper remain STS3215).
STS3250_JOINTS = ("arm_shoulder_pan", "arm_shoulder_lift", "arm_elbow_flex", "arm_wrist_flex")

# Hardcoded PincOpen gripper calibration values (from EPROM settings).
# The gripper's travel limits are pre-flashed to the motor's EPROM, so interactive
# gripper calibration is skipped and these fixed values are used instead.
PINCOPEN_CALIBRATION = MotorCalibration(
    id=6,
    drive_mode=1,  # 1 = inverted direction => 0% is closed, 100% is open
    homing_offset=0,
    range_min=512,  # -135 deg (fully open)
    range_max=2048,  # 0 deg (fully closed)
)


class PincOpenLeKiwi(LeKiwi):
    """LeKiwi with STS3250 arm joints, the PincOpen gripper, and tuned servo params."""

    config_class = PincOpenLeKiwiConfig
    name = "lekiwi_pincopen"

    def __init__(self, config: LeKiwiConfig):
        if not isinstance(config, PincOpenLeKiwiConfig):
            # Callers holding a plain LeKiwiConfig (e.g. a stock host yaml block) get
            # the tuning defaults; every LeKiwiConfig field carries over.
            config = PincOpenLeKiwiConfig(**vars(config))
        super().__init__(config)
        # Rebuild the bus with the STS3250 models. MotorsBus.__init__ precomputes
        # id->model lookup tables, so mutating bus.motors after the fact is not enough;
        # deriving from the stock motors dict keeps upstream's ids/norm modes.
        motors = {
            name: replace(motor, model="sts3250") if name in STS3250_JOINTS else motor
            for name, motor in self.bus.motors.items()
        }
        self.bus = FeetechMotorsBus(port=config.port, motors=motors, calibration=self.calibration)

    def calibrate(self) -> None:
        # Stock LeKiwi.calibrate with one change: the gripper is excluded from the
        # interactive procedure and gets the fixed PINCOPEN_CALIBRATION instead.
        if self.calibration:
            user_input = input(
                f"Press ENTER to use provided calibration file associated with the id {self.id}, or type 'c' and press ENTER to run calibration: "
            )
            if user_input.strip().lower() != "c":
                logger.info(f"Writing calibration file associated with the id {self.id} to the motors")
                self.bus.write_calibration(self.calibration)
                return
        logger.info(f"\nRunning calibration of {self}")

        arm_motors = [motor for motor in self.arm_motors if motor != "arm_gripper"]
        motors = arm_motors + self.base_motors

        self.bus.disable_torque(arm_motors)
        for name in arm_motors:
            self.bus.write("Operating_Mode", name, OperatingMode.POSITION.value)

        input("Move robot to the middle of its range of motion and press ENTER....")
        homing_offsets = self.bus.set_half_turn_homings(arm_motors)

        homing_offsets.update(dict.fromkeys(self.base_motors, 0))

        full_turn_motor = [
            motor for motor in motors if any(keyword in motor for keyword in ["wheel", "wrist_roll"])
        ]
        unknown_range_motors = [motor for motor in motors if motor not in full_turn_motor]

        print(
            f"Move all arm joints except '{full_turn_motor}' sequentially through their "
            "entire ranges of motion.\nRecording positions. Press ENTER to stop..."
        )
        range_mins, range_maxes = self.bus.record_ranges_of_motion(unknown_range_motors)
        for name in full_turn_motor:
            range_mins[name] = 0
            range_maxes[name] = 4095

        self.calibration = {}
        for name, motor in self.bus.motors.items():
            if name == "arm_gripper":
                self.calibration[name] = PINCOPEN_CALIBRATION
            else:
                self.calibration[name] = MotorCalibration(
                    id=motor.id,
                    drive_mode=0,
                    homing_offset=homing_offsets[name],
                    range_min=range_mins[name],
                    range_max=range_maxes[name],
                )

        self.bus.write_calibration(self.calibration)
        self._save_calibration()
        print("Calibration saved to", self.calibration_fpath)

    def configure(self):
        # Stock LeKiwi.configure plus the PincOpen tuning, all written while torque is
        # still disabled (P/torque params live in servo EPROM).
        cfg: PincOpenLeKiwiConfig = self.config
        self.bus.disable_torque()
        self.bus.configure_motors()
        for name in self.arm_motors:
            self.bus.write("Operating_Mode", name, OperatingMode.POSITION.value)
            self.bus.write("P_Coefficient", name, cfg.arm_p_coefficient)
            # Set I_Coefficient and D_Coefficient to default value 0 and 32
            self.bus.write("I_Coefficient", name, 0)
            self.bus.write("D_Coefficient", name, 32)

        for name in STS3250_JOINTS:
            self.bus.write("Acceleration", name, cfg.heavy_acceleration)
            self.bus.write("P_Coefficient", name, cfg.heavy_p_coefficient)

        self.bus.write("Acceleration", "arm_gripper", cfg.gripper_acceleration)
        self.bus.write("Overload_Torque", "arm_gripper", cfg.gripper_overload_torque)
        self.bus.write("Protective_Torque", "arm_gripper", cfg.gripper_protective_torque)
        self.bus.write("Protection_Time", "arm_gripper", cfg.gripper_protection_time)

        for name in self.base_motors:
            self.bus.write("Operating_Mode", name, OperatingMode.VELOCITY.value)

        self.bus.enable_torque()
