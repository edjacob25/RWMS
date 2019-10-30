# RimWorld database handling stuff
import json
import sys
from typing import Dict
from urllib.request import urlopen

import RWMS.configuration
import RWMS.error

wait_on_error = RWMS.configuration.load_value("rwms", "waitforkeypress_on_error", True)


# download most recent DB
def download_database(url: str) -> Dict:
    print("loading database.")
    if url == "":
        RWMS.error.fatal_error("no database URL defined.", wait_on_error)
        sys.exit(1)

    try:
        with urlopen(url) as json_url:
            json_data = json_url.read()
    except:
        RWMS.error.fatal_error(f"could not open {url}", wait_on_error)
        sys.exit(1)

    db = dict()
    if json_data:
        try:
            db = json.loads(json_data.decode("utf-8"))
            # python 3.6 and above can decode bytes objects automatically, python 3.5 and below cannot.
        except:
            RWMS.error.fatal_error("Could not load data from RWMSDB repository.", wait_on_error)
            sys.exit(1)

    return db
