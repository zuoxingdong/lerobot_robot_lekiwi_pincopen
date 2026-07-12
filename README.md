# lerobot_robot_lekiwi_pincopen

A [LeRobot](https://github.com/huggingface/lerobot) third-party robot plugin: the
**PincOpen LeKiwi**, a LeKiwi variant with STS3250 servos on the four big arm joints,
a PincOpen gripper with a fixed EPROM calibration, and tuned servo parameters.
Identical hardware behavior to a patched lerobot tree, with zero lerobot source
edits — a stock lerobot install (0.5.x or 0.6.x) drives the robot out of the box.

The hardware itself — mounting a PincOpen gripper on a LeKiwi and what it took to
make the combination reliable — is covered in the blog post
[Mobile Manipulation with LeKiwi + PincOpen](https://huggingface.co/blog/zuoxingdong/mobile-manipulation-lekiwi-pincopen);
this package is that integration distilled into an installable plugin.

What it changes vs the stock `lekiwi` robot:

- arm joints 1-4 run STS3250 motors (wrist_roll and gripper stay STS3215)
- the PincOpen gripper uses a fixed EPROM calibration (`drive_mode=1`, range
  512-2048) and is skipped during interactive calibration
- `configure()` writes tuned servo params on every connect: P=14 arm-wide, P=10 +
  acceleration 200 on the four big joints, and gripper overload/protective torque.
  Every tuning value is a config field, settable from the host yaml or the CLI
  (`--robot.heavy_p_coefficient=10`, ...) with no code changes.

## Install

```bash
pip install -e .        # into the environment that runs the robot host
```

## Use

The plugin follows lerobot's
[third-party device conventions](https://huggingface.co/docs/lerobot/integrate_hardware),
so every lerobot CLI discovers it automatically by its package name:

```bash
# calibration (the gripper is skipped; its EPROM calibration is applied)
lerobot-calibrate --robot.type=lekiwi_pincopen --robot.id=my_lekiwi

# the ZMQ host (stock lekiwi_host does no plugin discovery, so launch through the
# wrapper; same CLI and yaml as python -m lerobot.robots.lekiwi.lekiwi_host)
python -m lerobot_robot_lekiwi_pincopen.lekiwi_host --config_path=host.yaml
```

The teleoperation/recording client side needs nothing from this package: those CLIs
talk to lerobot's `lekiwi_client`, which never touches motors.

Note: the robot is named `lekiwi_pincopen`, so calibration files live under
`~/.cache/huggingface/lerobot/calibration/robots/lekiwi_pincopen/`. Migrating from a
stock `lekiwi` calibration is a one-time copy of that folder.

## Tuning fields

| Field | Default | Meaning |
|---|---|---|
| `arm_p_coefficient` | 14 | P-gain for all arm joints (stock lerobot writes 16) |
| `heavy_p_coefficient` | 10 | P-gain for the four STS3250 joints |
| `heavy_acceleration` | 200 | acceleration limit on the STS3250 joints |
| `gripper_acceleration` | 200 | gripper acceleration limit |
| `gripper_overload_torque` | 65 | percent; move fast through air |
| `gripper_protective_torque` | 5 | percent; back off on contact |
| `gripper_protection_time` | 7 | unit: 10 ms |

Lowering the P-gain on the big joints is the critical fix against jitter and servo
overload shutdowns on this hardware.

## Tests (hardware-free)

```bash
pip install -e .[dev]
python -m ruff check .
python -m pytest tests
```

Everything stops short of `bus.connect()`: no robot, no motors, no cameras needed.

## Related

- [Mobile Manipulation with LeKiwi + PincOpen](https://huggingface.co/blog/zuoxingdong/mobile-manipulation-lekiwi-pincopen)
  — the hardware integration story behind this plugin
- [lekiwi-tui](https://github.com/zuoxingdong/lekiwi-tui) — a terminal control center
  for the LeKiwi workflow that ships and drives this plugin automatically

## License

Apache-2.0. The `calibrate()`/`configure()` bodies are derived from the LeRobot
project (Apache-2.0, © The HuggingFace Inc. team); see the file headers.
