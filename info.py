
__package_name__ = "CAN to UDP converter"

__version_info__ = (0, 1, 0)

__version__ = ".".join(map(str, __version_info__))
__version_major__ = __version_info__[0]
__version_minor__ = __version_info__[1]
__version_patch__ = __version_info__[2]
__version_id__ = ((__version_major__ << 24) |
                  (__version_minor__ << 16) |
                  (__version_patch__ << 0))