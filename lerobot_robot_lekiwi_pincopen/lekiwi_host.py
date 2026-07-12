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

"""Launch lerobot's stock lekiwi_host with the PincOpen LeKiwi.

    python -m lerobot_robot_lekiwi_pincopen.lekiwi_host --config_path=/tmp/lekiwi_host.yaml ...

Drop-in replacement for ``python -m lerobot.robots.lekiwi.lekiwi_host``: same CLI, same
yaml. Needed because the stock host does no plugin discovery and hardcodes
``robot = LeKiwi(cfg.robot)``.

Three moving parts:

1. parse the CLI into a server config whose ``robot`` block is a
   ``PincOpenLeKiwiConfig``, so the tuning fields are settable from the host yaml;
2. swap the host module's ``LeKiwi`` global for ``PincOpenLeKiwi`` (a
   monkeypatch shim — lerobot itself is never modified);
3. hand ``lekiwi_host.main`` a genuine ``LeKiwiServerConfig`` instance — its
   ``@draccus.wrap()`` skips re-parsing only on an exact ``type(...) is`` match, so a
   subclass instance would trigger a second argv parse.

This module is deliberately also named ``lekiwi_host`` so process-management
tooling that pgreps for ``python.*lekiwi_host`` keeps matching the host process.
"""

import dataclasses
from dataclasses import dataclass, field

import draccus

from lerobot.robots.lekiwi import lekiwi_host
from lerobot.robots.lekiwi.lekiwi_host import LeKiwiServerConfig

from . import PincOpenLeKiwi, PincOpenLeKiwiConfig


@dataclass
class PincOpenLeKiwiServerConfig(LeKiwiServerConfig):
    robot: PincOpenLeKiwiConfig = field(default_factory=PincOpenLeKiwiConfig)


def main() -> None:
    cfg = draccus.parse(config_class=PincOpenLeKiwiServerConfig)
    lekiwi_host.LeKiwi = PincOpenLeKiwi
    stock_cfg = LeKiwiServerConfig(
        **{f.name: getattr(cfg, f.name) for f in dataclasses.fields(LeKiwiServerConfig)}
    )
    lekiwi_host.main(stock_cfg)


if __name__ == "__main__":
    main()
