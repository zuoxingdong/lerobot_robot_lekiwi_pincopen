"""Hardware-free checks for the lerobot_robot_lekiwi_pincopen plugin.

Run from the repo root (or anywhere OUTSIDE the repo's parent dir — from there this
folder would shadow the installed package as an empty namespace package) with an env
that carries lerobot:

    python -m pytest tests -q

Everything here stops short of bus.connect(), so no Pi, no motors, no cameras.
"""

import dataclasses
import sys

import pytest

pytest.importorskip("lerobot")

from lerobot.common.control_utils import teleop_supports_feedback
from lerobot.robots import RobotConfig
from lerobot.robots.lekiwi.config_lekiwi import LeKiwiConfig
from lerobot.robots.lekiwi.lekiwi_host import LeKiwiServerConfig
from lerobot.robots.utils import make_robot_from_config
from lerobot.teleoperators.so_leader.config_so_leader import SOLeaderConfig
from lerobot.utils.import_utils import register_third_party_plugins

from lerobot_robot_lekiwi_pincopen import (
    HEAVY_JOINTS,
    PINCOPEN_CALIBRATION,
    PINCOPEN_MAX_RELATIVE_TARGET,
    STS3250_JOINTS,
    PincOpenLeKiwi,
    PincOpenLeKiwiConfig,
    PincOpenLeKiwiLeader,
    PincOpenLeKiwiLeaderConfig,
    SprungSO101Leader,
    SprungSO101LeaderConfig,
)
from lerobot_robot_lekiwi_pincopen.lekiwi_host import PincOpenLeKiwiServerConfig


def test_distribution_name_matches_discovery_contract():
    # register_third_party_plugins() imports the DISTRIBUTION name as a module, so the
    # dist must keep the underscore name (a backend that normalizes it breaks discovery).
    import importlib.metadata

    assert importlib.metadata.metadata("lerobot_robot_lekiwi_pincopen")["Name"] == "lerobot_robot_lekiwi_pincopen"


def test_discovery_registers_choice():
    register_third_party_plugins()
    assert sys.modules.get("lerobot_robot_lekiwi_pincopen") is not None
    assert "lekiwi_pincopen" in RobotConfig.get_known_choices()


def test_make_robot_from_config_resolves_plugin_class():
    robot = make_robot_from_config(PincOpenLeKiwiConfig(id="unit-test", port="/dev/null"))
    assert type(robot) is PincOpenLeKiwi


def test_bus_rebuilt_with_sts3250_models():
    robot = PincOpenLeKiwi(PincOpenLeKiwiConfig(id="unit-test", port="/dev/null"))
    models = {name: motor.model for name, motor in robot.bus.motors.items()}
    for joint in STS3250_JOINTS:
        assert models[joint] == "sts3250"
    # 2026-08-14: shoulder_pan carries an STS3250 again, so the default inventory
    # covers all four load-bearing joints; it stays in HEAVY_JOINTS as well.
    assert models["arm_shoulder_pan"] == "sts3250"
    assert "arm_shoulder_pan" in HEAVY_JOINTS
    assert models["arm_wrist_roll"] == "sts3215"
    assert models["arm_gripper"] == "sts3215"
    assert all(models[m] == "sts3215" for m in robot.base_motors)
    # The precomputed lookup tables must reflect the rebuild (why the bus is re-created).
    assert robot.bus._id_to_model_dict[1] == "sts3250"
    assert robot.bus._id_to_model_dict[2] == "sts3250"
    assert robot.bus._id_to_model_dict[5] == "sts3215"


def test_plain_lekiwi_config_upgrades_with_tuning_defaults():
    robot = PincOpenLeKiwi(LeKiwiConfig(id="unit-test", port="/dev/null"))
    assert isinstance(robot.config, PincOpenLeKiwiConfig)
    assert robot.config.arm_p_coefficient == 14
    assert robot.config.heavy_p_coefficient == 10
    assert robot.config.gripper_overload_torque == 65


def test_joint_sets_are_yaml_overridable():
    # A servo swap must never need a code edit: both sets are plain config fields.
    cfg = PincOpenLeKiwiConfig(id="unit-test", port="/dev/null", sts3250_joints=("arm_elbow_flex",))
    robot = PincOpenLeKiwi(cfg)
    models = {name: motor.model for name, motor in robot.bus.motors.items()}
    assert models["arm_elbow_flex"] == "sts3250"
    assert models["arm_shoulder_lift"] == "sts3215"


def test_pincopen_gripper_calibration_constants():
    assert PINCOPEN_CALIBRATION.id == 6
    assert PINCOPEN_CALIBRATION.drive_mode == 1
    assert (PINCOPEN_CALIBRATION.range_min, PINCOPEN_CALIBRATION.range_max) == (512, 2048)


def test_host_server_config_roundtrip(tmp_path):
    # The wrapper parses PincOpenLeKiwiServerConfig from the SAME yaml the stock host
    # takes, then must hand main() an exact LeKiwiServerConfig (draccus.wrap skips
    # re-parsing only on `type(...) is` equality) carrying the PincOpen robot block.
    import draccus

    yaml = tmp_path / "host.yaml"
    yaml.write_text(
        "robot:\n"
        "  use_degrees: true\n"
        "  heavy_p_coefficient: 12\n"
        "host:\n"
        "  max_loop_freq_hz: 25\n"
    )
    cfg = draccus.parse(
        config_class=PincOpenLeKiwiServerConfig, args=[f"--config_path={yaml}", "--robot.id=pincopen"]
    )
    assert isinstance(cfg.robot, PincOpenLeKiwiConfig)
    assert cfg.robot.heavy_p_coefficient == 12  # yaml can now drive the tuning
    assert cfg.host.max_loop_freq_hz == 25

    stock = LeKiwiServerConfig(
        **{f.name: getattr(cfg, f.name) for f in dataclasses.fields(LeKiwiServerConfig)}
    )
    assert type(stock) is LeKiwiServerConfig  # exact type: the wrapped main won't re-parse
    assert stock.robot is cfg.robot


def test_max_relative_target_constant_matches_the_arm_action_keys():
    robot = PincOpenLeKiwi(PincOpenLeKiwiConfig(id="unit-test", port="/dev/null"))
    # ensure_safe_goal_position compares the two key sets exactly, so a missing or stale
    # joint turns the safety cap into a ValueError on the first send_action rather than
    # into a looser clamp. Keys carry the `.pos` suffix here, unlike SOFollower's.
    assert set(PINCOPEN_MAX_RELATIVE_TARGET) == {k for k in robot.action_features if k.endswith(".pos")}
    # Shipped opt-in: enabling it costs a Present_Position read per tick.
    assert PincOpenLeKiwiConfig().max_relative_target is None


def _build_leader() -> PincOpenLeKiwiLeader:
    return PincOpenLeKiwiLeader(
        PincOpenLeKiwiLeaderConfig(id="unit-test", arm_config=SOLeaderConfig(port="/dev/null"))
    )


def test_leader_is_actuated_with_arm_prefixed_feedback():
    leader = _build_leader()
    # DAgger's smooth leader<-follower handover only engages for actuated teleops.
    assert teleop_supports_feedback(leader)
    # Feedback keys must live in the same `arm_`-prefixed space as action_features
    # (= LeKiwi's robot action key space), or teleop_smooth_move_to silently no-ops.
    assert leader.feedback_features == {
        f"arm_{key}": value for key, value in leader.arm.feedback_features.items()
    }
    assert set(leader.feedback_features) < set(leader.action_features)  # base keys are action-only


def test_leader_delegates_feedback_and_torque_to_arm():
    class ArmStub:
        is_connected = True  # the leader's is_connected reads through to the arm

        def __init__(self):
            self.feedback = None
            self.torque_calls = []

        def send_feedback(self, feedback):
            self.feedback = feedback

        def enable_torque(self):
            self.torque_calls.append("on")

        def disable_torque(self):
            self.torque_calls.append("off")

    leader = _build_leader()
    leader.arm = ArmStub()

    # Interpolated targets arrive in robot action key space; the base `*.vel`
    # keys have no actuator and must be dropped, the arm keys unprefixed.
    leader.send_feedback({"arm_shoulder_pan.pos": 1.0, "arm_gripper.pos": 50.0, "x.vel": 0.1})
    assert leader.arm.feedback == {"shoulder_pan.pos": 1.0, "gripper.pos": 50.0}

    leader.disable_torque()
    leader.enable_torque()
    assert leader.arm.torque_calls == ["off", "on"]


def test_sprung_disable_torque_keeps_gripper_spring():
    arm = SprungSO101Leader(SprungSO101LeaderConfig(id="unit-test", port="/dev/null"))

    calls = []

    class BusStub:
        is_connected = True  # SOLeader.is_connected reads through to the bus

        def disable_torque(self, *args):
            calls.append(("disable", args))

        def enable_torque(self, *args):
            calls.append(("enable", args))

        def write(self, register, motor, value, **kwargs):
            calls.append(("write", register, motor, value))

    arm.bus = BusStub()
    arm.disable_torque()

    # Bus-wide release first, then the spring is immediately re-armed so the
    # trigger keeps resisting and springing back while the human teleoperates.
    assert calls[0] == ("disable", ())
    assert calls[1] == ("enable", ("gripper",))
    assert calls[2] == ("write", "Goal_Position", "gripper", 100.0)

    # Disconnected, the re-arm is skipped: its goal write is normalized, so it
    # needs a calibrated bus. The bus-wide release still goes through.
    calls.clear()
    arm.bus.is_connected = False
    arm.disable_torque()
    assert calls == [("disable", ())]
