# RimWorld ModSorter update module
#
# checks repo for newly committed versions and (in some point in the future) an inplace upgrade

import sys
from urllib.request import urlopen

import RWMS.configuration
import RWMS.error

version_url = "https://api.bitbucket.org/2.0/repositories/shakeyourbunny/rwms/src/master/VERSION"

wait_on_error = RWMS.configuration.load_value("rwms", "waitforkeypress_on_error", True)


def __load_version_from_repo() -> str:
    try:
        data = urlopen(version_url)

    except:
        RWMS.error.fatal_error("** updatecheck: could not load update URL.", wait_on_error)
        sys.exit(1)

    version = data.read().decode('utf-8').strip()
    return version


def is_update_available(current_version) -> bool:
    if current_version == "":
        return False

    if __load_version_from_repo() == current_version:
        return False
    else:
        return True


# debug
if __name__ == '__main__':
    print(__load_version_from_repo())
