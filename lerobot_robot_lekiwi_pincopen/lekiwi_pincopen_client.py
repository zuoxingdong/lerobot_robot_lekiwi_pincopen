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

"""Client-side LeKiwi for the recording/teleoperating machine.

Stock lerobot never registers ``lekiwi_client`` in ``lerobot-record`` /
``lerobot-teleoperate`` (the scripts import each robot module explicitly and LeKiwi is
missing), so ``--robot.type=lekiwi_client`` is not a selectable choice there. Registering
this subclass through the plugin makes the client reachable, and fixes the crash below,
without patching lerobot.

Partly addressed upstream by huggingface/lerobot#3741: as of 0.6.1 ``lerobot-record`` has a
multi-teleop branch, but it is gated on ``robot.name == "lekiwi_client"`` (so this subclass
would not match it), and ``LeKiwiClient`` still exposes no ``.cameras``. Both workarounds here
are still required.
"""

from lerobot.cameras import CameraConfig
from lerobot.robots.lekiwi.lekiwi_client import LeKiwiClient

from .config_lekiwi_pincopen_client import PincOpenLeKiwiClientConfig


class PincOpenLeKiwiClient(LeKiwiClient):
    """LeKiwi client that reports its cameras.

    Every robot exposes its cameras on ``.cameras`` and callers rely on it: ``record()``
    sizes the image-writer threads with ``len(robot.cameras)``. LeKiwi's cameras are
    attached to the host and streamed over ZMQ, so the stock client has no local camera
    objects and no such attribute, and recording dies with ``AttributeError``.
    """

    config_class = PincOpenLeKiwiClientConfig
    name = "lekiwi_pincopen_client"

    @property
    def cameras(self) -> dict[str, CameraConfig]:
        """The cameras this robot observes, keyed by name.

        The configured specs are returned rather than live camera objects, since the
        devices live on the host. Callers only need the names and the count.
        """
        return self.config.cameras
