from backend.mount.service import (
    MountService
)


_mount = MountService()


def ensure_mount_parked():

    return _mount.ensure_parked()