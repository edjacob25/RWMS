## RimWorld ModSorter update module
##
## checks repo for newly commited versions and (in some point in the future) an inplace upgrade

import sys
from urllib.request import urlopen

import RWMS.configuration
import RWMS.error

version_url = "https://paste.gg/p/anonymous/0758ce1d65e74262bd503ba9d58d4d64/files/57108e161a5543a4ba524c26679eb290/raw"

wait_on_error = RWMS.configuration.load_value("rwms", "waitforkeypress_on_error", True)

def __load_version_from_repo():
    try:
        data = urlopen(version_url)

    except:
        RWMS.error.fatal_error("** updatecheck: could not load update URL.", wait_on_error)
        sys.exit(1)

    version = data.read().decode('utf-8').strip()
    return version


def is_update_available(currentversion):
    if currentversion == "":
        return False

    if __load_version_from_repo() == currentversion:
        return False
    else:
        return True


# debug
if __name__ == '__main__':
    print(__load_version_from_repo())
