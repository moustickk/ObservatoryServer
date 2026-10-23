import time

import pythoncom
import win32com.client

from backend.mount.config import (
    TELESCOPE_DRIVER,
    PARK_TIMEOUT
)

from backend.mount.logging import (
    mount_log
)


class MountService:

    def ensure_parked(self):

        pythoncom.CoInitialize()

        try:

            mount_log(
                f"Driver={TELESCOPE_DRIVER}"
            )

            try:

                telescope = (
                    win32com.client
                    .GetActiveObject(
                        TELESCOPE_DRIVER
                    )
                )

                mount_log(
                    "Using existing ASCOM instance"
                )

            except Exception:

                mount_log(
                    "No active ASCOM instance found"
                )

                telescope = (
                    win32com.client
                    .Dispatch(
                        TELESCOPE_DRIVER
                    )
                )

                mount_log(
                    "Created new ASCOM instance"
                )

            telescope.Connected = True

            mount_log(
                f"Connected={telescope.Connected}"
            )

            mount_log(
                f"AtPark={telescope.AtPark}"
            )

            if telescope.AtPark:

                mount_log(
                    "Mount already parked"
                )

                return True

            mount_log(
                "Mount not parked"
            )

            mount_log(
                "Sending PARK command"
            )

            telescope.Park()

            timeout = (
                time.time()
                + PARK_TIMEOUT
            )

            while time.time() < timeout:

                mount_log(
                    "Waiting for park..."
                )

                if telescope.AtPark:

                    mount_log(
                        "Mount parked"
                    )

                    return True

                time.sleep(2)

            mount_log(
                "Parking timeout"
            )

            return False

        except Exception as ex:

            mount_log(
                f"EQMOD error: {ex}"
            )

            return False

        finally:

            pythoncom.CoUninitialize()