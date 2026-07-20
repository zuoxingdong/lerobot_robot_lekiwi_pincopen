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

"""Configuration for the sprung SO-101 leader (``--teleop.type=so101_leader_sprung``)."""

from dataclasses import dataclass

from lerobot.teleoperators.config import TeleoperatorConfig
from lerobot.teleoperators.so_leader.config_so_leader import SOLeaderTeleopConfig


@TeleoperatorConfig.register_subclass("so101_leader_sprung")
@dataclass
class SprungSO101LeaderConfig(SOLeaderTeleopConfig):
    """Stock SO-101 leader config; the sprung-gripper servo settings are fixed
    values in :class:`SprungSO101Leader` (they are hardware-specific to the
    STS3215 and mutually coupled, so they are not exposed as knobs)."""
