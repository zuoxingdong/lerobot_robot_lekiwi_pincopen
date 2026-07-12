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

from lerobot.robots import RobotConfig  # noqa: E402
from lerobot.robots.lekiwi.config_lekiwi import LeKiwiConfig  # noqa: E402
from lerobot.robots.utils import make_robot_from_config  # noqa: E402
from lerobot.utils.import_utils import register_third_party_plugins  # noqa: E402

from lerobot_robot_lekiwi_pincopen import (  # noqa: E402
    PINCOPEN_CALIBRATION,
    STS3250_JOINTS,
    PincOpenLeKiwi,
    PincOpenLeKiwiConfig,
)
from lerobot_robot_lekiwi_pincopen.lekiwi_host import PincOpenLeKiwiServerConfig  # noqa: E402
from lerobot.robots.lekiwi.lekiwi_host import LeKiwiServerConfig  # noqa: E402


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
    assert models["arm_wrist_roll"] == "sts3215"
    assert models["arm_gripper"] == "sts3215"
    assert all(models[m] == "sts3215" for m in robot.base_motors)
    # The precomputed lookup tables must reflect the rebuild (why the bus is re-created).
    assert robot.bus._id_to_model_dict[1] == "sts3250"
    assert robot.bus._id_to_model_dict[5] == "sts3215"


def test_plain_lekiwi_config_upgrades_with_tuning_defaults():
    robot = PincOpenLeKiwi(LeKiwiConfig(id="unit-test", port="/dev/null"))
    assert isinstance(robot.config, PincOpenLeKiwiConfig)
    assert robot.config.arm_p_coefficient == 14
    assert robot.config.heavy_p_coefficient == 10
    assert robot.config.gripper_overload_torque == 65


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
