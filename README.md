# lerobot_robot_lekiwi_pincopen

My LeKiwi runs STS3250 servos on the four big arm joints and a
[PincOpen](https://github.com/pollen-robotics/PincOpen) gripper.
This plugin lets the **original, unmodified
[LeRobot](https://github.com/huggingface/lerobot) (0.5.x / 0.6.x) drive that
hardware**, zero source edits.

I wrote up the hardware build in
[Mobile Manipulation with LeKiwi + PincOpen](https://huggingface.co/blog/zuoxingdong/mobile-manipulation-lekiwi-pincopen).
This package is that integration as installable code.

[![PincOpen LeKiwi running an autonomous SmolVLA rollout, click to play](https://huggingface.co/datasets/zuoxingdong/lekiwi-blog-assets/resolve/main/readme-poster-eval_smolvla_130ep_40k_rtc.jpg)](https://huggingface.co/datasets/zuoxingdong/lekiwi-blog-assets/resolve/main/eval_smolvla_130ep_40k_rtc.mp4)

*▶ click for the clip: autonomous SmolVLA rollout, pick up the chocolate bar from the basket and place it on the ground*

**vs the original `lekiwi` robot:**

- arm joints 1-4 on **STS3250** (wrist_roll and gripper stay STS3215)
- **PincOpen gripper**: fixed EPROM calibration, skipped during interactive calibration
- **tuned servo params** written on every connect, all exposed as config fields:
  tuning is a yaml/CLI edit (`--robot.heavy_p_coefficient=10`), never a code change

## Install

```bash
pip install -e .
```

## Use

LeRobot auto-discovers the plugin by its package name (the official
[third-party conventions](https://huggingface.co/docs/lerobot/integrate_hardware)):

```bash
# calibrate (gripper is skipped, its EPROM calibration is applied)
lerobot-calibrate --robot.type=lekiwi_pincopen --robot.id=my_lekiwi

# host (the original lekiwi_host skips plugin discovery, hence the wrapper; same CLI, same yaml)
python -m lerobot_robot_lekiwi_pincopen.lekiwi_host --config_path=host.yaml
```

The client side (teleop/record/eval) needs nothing from this package:
`lekiwi_client` never touches motors.

Calibration files live under
`~/.cache/huggingface/lerobot/calibration/robots/lekiwi_pincopen/`.

## Optional: sprung gripper trigger for the SO-101 leader

The package also ships `--teleop.type=so101_leader_sprung`: a stock SO-101
leader whose gripper trigger pushes back progressively when squeezed and
springs back to fully open when released — the SO-arm analogue of the Koch
leader's current-based-position trigger, emulated in the STS3215's position
mode (soft P gain + low torque cap). Works with any SO-101/SO-100 leader, not
just PincOpen setups.

```yaml
teleop:
  type: so101_leader_sprung
  port: /dev/ttyACM0
  id: my_leader
  # calibration files are stored per teleoperator type; reuse an existing
  # so101_leader calibration instead of recalibrating:
  calibration_dir: ~/.cache/huggingface/lerobot/calibration/teleoperators/so101_leader
```

Notes:

* Position reads are unchanged — recorded gripper actions are identical apart
  from a consistent open rest position between grasps.
* The spring's `P_Coefficient` write persists in the servo's EPROM (harmless;
  the servo behaves identically when used as a stock passive leader, since
  torque is off outside this teleoperator).
* Hand-tuned on real hardware; holding the trigger fully squeezed for 8
  continuous minutes raised the servo temperature by 1 °C, and the factory
  overload protection stays armed above the configured torque cap.

## Tuning

| Field | Default |
|---|---|
| `arm_p_coefficient` | 14 |
| `heavy_p_coefficient` | 10 |
| `heavy_acceleration` | 200 |
| `gripper_acceleration` | 200 |
| `gripper_overload_torque` | 65 (percent) |
| `gripper_protective_torque` | 5 (percent) |
| `gripper_protection_time` | 7 (x10 ms) |

**P=10 on the big joints is the load-bearing fix.** The original writes P=16, which gave me
jitter and servo overload shutdowns on this hardware.

## Tests

```bash
pip install -e .[dev]
python -m pytest tests
```

No hardware needed, everything stops short of `bus.connect()`.

## Related

- [Mobile Manipulation with LeKiwi + PincOpen](https://huggingface.co/blog/zuoxingdong/mobile-manipulation-lekiwi-pincopen):
  the hardware story
- [lekiwi-tui](https://github.com/zuoxingdong/lekiwi-tui): my terminal control center,
  ships and drives this plugin automatically

## License

Apache-2.0. `calibrate()`/`configure()` derive from LeRobot (Apache-2.0,
The HuggingFace Inc. team); see the file headers.
