# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from pathlib import Path
from typing import Any, Optional

from lisa import features


class StartStop(features.StartStop):
    def _stop(
        self,
        wait: bool = True,
        state: features.StopState = features.StopState.Shutdown,
    ) -> None:
        pass

    def _start(self, wait: bool = True) -> None:
        pass

    def _restart(self, wait: bool = True) -> None:
        pass

    def _initialize(self, *args: Any, **kwargs: Any) -> None:
        super()._initialize(*args, **kwargs)


class SerialConsole(features.SerialConsole):
    def _initialize(self, *args: Any, **kwargs: Any) -> None:
        super()._initialize(*args, **kwargs)

    def _get_console_log(self, saved_path: Optional[Path]) -> bytes:
        return b""
