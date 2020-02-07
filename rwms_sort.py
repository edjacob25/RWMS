#!/usr/bin/env python3
# RimWorld Module Sorter
import collections
import json
import os
import re
import shutil
import sys
import textwrap
import time
import webbrowser
import xml.etree.ElementTree as ElementTree
from argparse import ArgumentParser, Namespace
from operator import itemgetter
from pathlib import Path
from typing import Dict, Tuple
from urllib.request import urlopen

from bs4 import BeautifulSoup

import RWMS.configuration
import RWMS.database
import RWMS.error
import RWMS.issue_mgmt
import RWMS.update

VERSION = "0.95.1.4"

# ##################################################################################
# helper functions
def be_sleepy(how_long: float, ed=True):
    if ed:
        time.sleep(how_long)


def wait_for_exit(exit_code, wfo=True):
    if wfo:
        input("\nPress ENTER to end program.")
    sys.exit(exit_code)


def check_directory(directory: str):
    if not os.path.exists(directory):
        print(f"** Directory '{directory}' does not exist or is not accessible.")
        return False
    return True


def print_dry_run(config_file, final_doc, mod_data):
    print("This is a dry run, nothing will be changed\n")
    initial = [x.text for x in ElementTree.parse(config_file).getroot().find("activeMods").findall("li")]
    final = [x.text for x in final_doc.getroot().find("activeMods").findall("li")]
    for i, mod in enumerate(initial):
        initial_pos = i + 1
        name = mod_data[mod][2]
        try:
            final_pos = final.index(mod) + 1

            if initial_pos == final_pos:
                print(f"{name} retained the same position at {initial_pos}")
            else:
                print(f"{name} moved from position {initial_pos} to position {final_pos}")
        except ValueError:
            print(f"{name} was eliminated from the resulting active mods")

    print("\n\nResultant order is: ")
    for i, mod in enumerate(final):
        name = mod_data[mod][2]
        print(f"{i + 1} - {name} - {mod}")


#####################################################################################################################
def get_args() -> Namespace:
    parser = ArgumentParser()

    # configuration overrides
    parser.add_argument("--disable-steam", action="store_true", help="(override) disable steam detection")
    parser.add_argument("--dont-remove-unknown-mods", action="store_true", help="(override) do not remove unknown mods")
    parser.add_argument(
        "--openbrowser",
        action="store_true",
        help="(override) opens browser if new version available, " "implies force updatecheck ",
    )
    parser.add_argument("--disable-tweaks", action="store_true", help="(override) disable user tweaks")

    # misc options
    parser.add_argument(
        "-d", "--dry-run", action="store_true", help="shows what would change, does not actually " "overrides any file"
    )
    parser.add_argument("--contributors", action="store_true", help="display contributors for RWMS(DB)")

    parser.add_argument(
        "--dump-configuration", action="store_true", help="displays the current configuration RWMS is thinking of"
    )
    parser.add_argument(
        "--dump-configuration-nowait",
        action="store_true",
        help="displays the current configuration RWMS is thinking of, forces no waiting (for scripts)",
    )

    parser.add_argument("--reset-to-core", action="store_true", help="reset mod list to Core only")

    # delay options
    parser.add_argument("--wait-error", action="store_true", help="(override) wait on errors")
    parser.add_argument("--wait", action="store_true", help="(override) wait on exit")
    parser.add_argument("--enable-delays", action="store_true", help="(override) enable some delays")

    # directory options
    parser.add_argument("--steamdir", action="store", help="(override) Steam installation directory")
    parser.add_argument("--drmfreedir", action="store", help="(override) DRM free directory of RimWorld")
    parser.add_argument(
        "--configdir", action="store", help="(override) location of game configuration / save directory"
    )
    parser.add_argument("--workshopdir", action="store", help="(override) location of Steam Workshop mod directory")
    parser.add_argument("--localmodsdir", action="store", help="(override) location of local mod directory")

    return parser.parse_args()


# functions - cleanup_garbage_name(garbage_name)
def cleanup_garbage_name(garbage_name: str) -> str:
    clean = garbage_name
    regex = re.compile(
        r"(v|V|)\d+\.\d+(\.\d+|)([a-z]|)|\[(1.0|(A|B)\d+)\]|\((1.0|(A|B)\d+)\)|(for |R|)(1.0|(A|B)\d+)|\.1(8|9)"
    )
    clean = re.sub(regex, "", clean)
    clean = re.sub(regex, "", clean)
    clean = clean.replace(" - ", ": ").replace(" : ", ": ")
    #
    clean = clean.replace("  ", " ")
    clean = " ".join(clean.split()).strip()

    # cleanup ruined names
    clean = clean.replace("()", "")
    clean = clean.replace("[]", "")

    # special cases
    clean = clean.replace("(v. )", "")  # Sora's RimFantasy: Brutal Start (v. )
    if clean.endswith(" Ver"):
        clean = clean.replace(" Ver", "")  # Starship Troopers Arachnids Ver
    if clean.endswith(" %"):
        clean = clean.replace(" %", "")  # Tilled Soil (Rebalanced): %
    if clean.find("[ "):
        clean = clean.replace("[ ", "[")  # Additional Traits [ Update]
    if clean.find("( & b19)"):
        clean = clean.replace("( & b19)", "")  # Barky's Caravan Dogs ( & b19)
    if clean.find("[19]"):
        clean = clean.replace("[19]", "")  # Sailor Scouts Hair [19]
    if clean.find("[/] Version"):
        clean = clean.replace("[/] Version", "")  # Fueled Smelter [/] Version

    if clean.endswith(":"):
        clean = clean[:-1]
    if clean.startswith(": "):
        clean = clean[2:]  # : ACP: More Floors Wool Patch
    if clean.startswith("-"):
        clean = clean[1:]  # -FuelBurning

    clean = clean.strip()

    return clean


######################################################################################################################
# functions - read in mod data
#
# cats       = categories
# db         = FULL db dict
# basedir    = mod base directory
# mod_source  = type of mod installation
#
def load_mod_data(categories: Dict, db: Dict, basedir: Path, mod_source: str, wait_on_error: bool) -> Dict[str, Tuple]:
    mod_details = {}
    folder_list = [x for x in basedir.iterdir()]
    for mod_folder in folder_list:
        about_xml = mod_folder / "About" / "About.xml"
        mod_id = mod_folder.name
        if about_xml.exists():
            try:
                xml = ElementTree.parse(about_xml)
                name = xml.find("name").text
            except ElementTree.ParseError:
                print(f"Mod ID is '{mod_id}'")
                print(f"** error: malformed XML in {about_xml}\n")
                print("Please contact mod author for clarification.")
                if RWMS.configuration.detect_rimworld_steam():
                    workshop_url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"
                    print(f"(trying to workaround by loading steam workshop page {workshop_url})")
                    try:
                        name = str(BeautifulSoup(urlopen(workshop_url), "html.parser").title.string)
                        if "Steam Community :: Error" in name:
                            RWMS.error.fatal_error("Could not find a matching mod on the workshop.", wait_on_error)
                            sys.exit(1)
                    except:
                        print("Could not open workshop page. sorry.")
                        continue
                    name = name.replace("Steam Workshop :: ", "")
                    print(f"Matching mod ID '{mod_folder}' with '{name}'\n")
                else:
                    RWMS.error.fatal_error("(cannot do a workaround, no steam installation)", wait_on_error)
                    sys.exit(1)

            # cleanup name stuff for version garbage
            name = cleanup_garbage_name(name)

            if name in db["db"]:
                try:
                    score = categories[db["db"][name]][0]
                except:
                    print(f"FIXME: mod '{name}' has an unknown category '{db['db'][name]}'. Stop.")
                    RWMS.error.fatal_error("please report this error to the database maintainer.", wait_on_error)
                    sys.exit(1)

                try:
                    mod_info = (mod_id, float(score), name, mod_source)

                except KeyError:
                    RWMS.error.fatal_error(
                        f"could not construct dictionary entry for mod {name}, score {score}", wait_on_error
                    )
                    sys.exit(1)
            else:
                # note: need the mod source later for distinguishing local vs workshop mod in unknown mod report
                mod_info = (mod_id, None, name, mod_source)

            mod_details[mod_id] = mod_info
        else:
            print(f"could not find metadata for item {mod_id} (skipping, is probably a scenario)!")
    return mod_details


def save_results(mods_config_file: Path, doc):
    now = time.strftime("%Y%m%d-%H%M", time.localtime(time.time()))
    backup_file = mods_config_file.with_suffix(f".backup-{now}.xml")
    shutil.copy(str(mods_config_file), str(backup_file))
    print(f"Backed up ModsConfig.xml to {backup_file}.")

    print("Writing new ModsConfig.xml.")
    mods_config_str = ElementTree.tostring(doc.getroot(), encoding="unicode")
    with open(str(mods_config_file), "w", encoding="utf-8-sig", newline="\n") as f:
        # poor man's pretty print
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        mods_config_str = mods_config_str.replace("</li><li>", "</li>\n    <li>").replace(
            "</li></activeMods>", "</li>\n  </activeMods>"
        )
        f.write(mods_config_str)


def print_contributors(database: Dict):
    print(f"{'Contributor':<30} {'# Mods':<6}")
    d = sorted(database["contributor"].items(), key=itemgetter(1), reverse=True)
    for contributors in d:
        if contributors[1] >= 20:
            print(f"{contributors[0]:<30} {contributors[1]:>5}")
    print("\nfor a full list of contributors visit:")
    print("https://bitbucket.org/shakeyourbunny/rwmsdb/src/master/CONTRIBUTING.md")


def main():
    # ##################################################################################
    # some basic initialization and default output
    twx, twy = shutil.get_terminal_size()

    banner = f"** RWMS {VERSION} by shakeyourbunny"
    print(f"{banner:*<{twx}}")
    print("bugs: https://bitbucket.org/shakeyourbunny/rwms/issues")
    print("database updates: visit https://bitbucket.org/shakeyourbunny/rwmsdb/issues\n")

    args = get_args()

    update_check = RWMS.configuration.load_value("rwms", "updatecheck", True)
    open_browser = RWMS.configuration.load_value("rwms", "openbrowser", True)
    wait_on_error = RWMS.configuration.load_value("rwms", "waitforkeypress_on_error", True)
    wait_on_exit = RWMS.configuration.load_value("rwms", "waitforkeypress_on_exit", True)
    disable_steam = RWMS.configuration.load_value("rwms", "disablesteam", True)
    dont_remove_unknown = RWMS.configuration.load_value("rwms", "dontremoveunknown", False)
    enable_delays = RWMS.configuration.load_value("rwms", "enabledelaysinoutput", True)
    disable_tweaks = RWMS.configuration.load_value("rwms", "disabletweaks", True)

    # process command line switches
    # configuration file overrides
    if args.disable_steam:
        disable_steam = True

    if args.dont_remove_unknown_mods:
        dont_remove_unknown = True

    if args.openbrowser:
        update_check = True
        open_browser = True

    if args.wait_error:
        wait_on_error = True

    if args.wait:
        wait_on_exit = True

    if args.enable_delays:
        enable_delays = True

    if args.disable_tweaks:
        disable_tweaks = True

    # directory overrides
    if args.steamdir:
        disable_steam = False
        if not check_directory(args.steamdir):
            wait_for_exit(1, wait_on_error)

    if args.drmfreedir:
        if not check_directory(args.drmfreedir):
            wait_for_exit(1, wait_on_error)

    if args.configdir:
        if not check_directory(args.configdir):
            wait_for_exit(1, wait_on_error)

    if args.workshopdir:
        disable_steam = False
        if not check_directory(args.workshopdir):
            wait_for_exit(1, wait_on_error)

    if args.localmodsdir:
        if not check_directory(args.localmodsdir):
            wait_for_exit(1, wait_on_error)

    # configuration dump
    if args.dump_configuration:
        RWMS.configuration.__dump_configuration()
        wait_for_exit(0, wait_on_exit)

    if args.dump_configuration_nowait:
        RWMS.configuration.__dump_configuration()
        sys.exit(0)

    # start script
    if update_check:
        if RWMS.update.is_update_available(VERSION):
            print(f"*** Update available, new version is {RWMS.update.__load_version_from_repo()} ***\n")
            print("Release: https://bitbucket.org/shakeyourbunny/rwms/downloads/")
            if open_browser:
                webbrowser.open_new("https://bitbucket.org/shakeyourbunny/rwms/downloads/")

    if RWMS.configuration.detect_rimworld() == "":
        RWMS.error.fatal_error("no valid RimWorld installation detected!", wait_on_error)
        wait_for_exit(0, wait_on_error)

    categories_url = (
        "https://api.bitbucket.org/2.0/repositories/shakeyourbunny/rwmsdb/src/master/rwms_db_categories.json"
    )
    database_url = "https://api.bitbucket.org/2.0/repositories/shakeyourbunny/rwmsdb/src/master/rwmsdb.json"

    ####################################################################################################################
    # real start of the script

    # load scoring mapping dict
    categories = RWMS.database.download_database(categories_url)
    if not categories:
        RWMS.error.fatal_error("Could not load properly categories.", wait_on_error)
        wait_for_exit(1, wait_on_error)

    # preload all needed data
    # categories
    database = RWMS.database.download_database(database_url)
    if not database:
        RWMS.error.fatal_error(f"Error loading scoring database {database_url}.", wait_on_error)
        wait_for_exit(1, wait_on_error)
    else:
        print(f"\nDatabase (v{database['version']}, date: {database['timestamp']}) successfully loaded.")
        print(f'{len(database["db"])} known mods, {len(database["contributor"])} contributors.')

    if args.contributors:
        print_contributors(database)
        wait_for_exit(0, wait_on_exit)
    else:
        contributors = collections.Counter(database["contributor"])
        most_common = [f"{c[0]} ({c[1]})" for c in contributors.most_common(5)]
        print(f"Top contributors: {', '.join(most_common)}\n")

    mods_config_file = RWMS.configuration.modsconfigfile()
    print("Loading and parsing ModsConfig.xml")
    if not mods_config_file.exists():
        RWMS.error.fatal_error(f"could not find ModsConfig.xml; detected: '{mods_config_file}'", wait_on_error)
        wait_for_exit(1, wait_on_error)

    try:
        xml = ElementTree.parse(mods_config_file)
    except:
        RWMS.error.fatal_error("could not parse XML from ModsConfig.xml.", wait_on_error)
        wait_for_exit(1, wait_on_error)

    xml = xml.find("activeMods")
    mods_enabled_list = [t.text for t in xml.findall("li")]
    if "Core" not in mods_enabled_list:
        mods_enabled_list.append("Core")

    # check auf unknown mods
    print("Loading mod data.")
    mod_data_workshop = dict()

    if not disable_steam:
        steam_workshop_dir = RWMS.configuration.detect_steamworkshop_dir()
        if steam_workshop_dir is not None:
            if not steam_workshop_dir.is_dir():
                RWMS.error.fatal_error(
                    f"steam workshop directory '{steam_workshop_dir}' could not be found. please "
                    f"check your installation and / or configuration file.",
                    wait_on_error,
                )
                wait_for_exit(1, wait_on_error)
            mod_data_workshop = load_mod_data(categories, database, steam_workshop_dir, "W", wait_on_error)

    local_mod_dir = RWMS.configuration.detect_localmods_dir()
    if not local_mod_dir.is_dir():
        RWMS.error.fatal_error(
            f"local mod directory '{local_mod_dir}' could not be found. please check your installation "
            f"and / or configuration file.",
            wait_on_error,
        )
        wait_for_exit(1, wait_on_error)
    mod_data_local = load_mod_data(categories, database, local_mod_dir, "L", wait_on_error)

    mod_data_full = {**mod_data_local, **mod_data_workshop}
    mod_data_known = {}  # all found known mods, regardless of their active status
    mod_data_unknown = {}  # all found unknown mods, regardless of their active status
    for mods, mod_entry in mod_data_full.items():
        if mod_entry[1] is not None:
            mod_data_known[mods] = mod_entry
        else:
            mod_data_unknown[mods] = mod_entry

    mods_data_active = list()
    mods_unknown_active = list()
    for mods in mods_enabled_list:
        try:
            mods_data_active.append((mods, mod_data_known[mods][1]))

        except KeyError:
            # print("Unknown mod ID {}, deactivating it from mod list.".format(mods))
            print(f"Unknown ACTIVE mod ID {mods} found..")
            mods_unknown_active.append(mods)

    print("Sorting mods.\n")
    be_sleepy(1.0, enable_delays)
    new_list = sorted(mods_data_active, key=itemgetter(1))
    print(
        f"{len(mod_data_full)} subscribed mods, {len(mods_enabled_list)} ({len(mods_data_active) + 1} known,"
        f" {len(mods_unknown_active)} unknown) enabled mods"
    )
    be_sleepy(2.0, enable_delays)

    doc = ElementTree.parse(mods_config_file)
    xml = doc.getroot()

    try:
        rimworld_version = xml.find("version").text
    except:
        try:
            rimworld_version = xml.find("buildNumber").text
        except:
            rimworld_version = "unknown"

    xml = xml.find("activeMods")
    for li in xml.findall("li"):
        xml.remove(li)

    now_time = time.strftime("%Y%m%d-%H%M", time.localtime(time.time()))

    write_mods_config = False

    if args.reset_to_core:
        while True:
            data = input("Do you want to reset your mod list to Core only (y/n)? ")
            if data.lower() in ("y", "n"):
                break
        if data.lower() == "y":
            print("Resetting your ModsConfig.xml to Core only!")
            xml_sorted = ElementTree.SubElement(xml, "li")
            xml_sorted.text = "Core"
            write_mods_config = True
    else:
        # handle known active mods
        for mods in new_list:
            if mods[0] == "":
                print("skipping, empty?")
            else:
                xml_sorted = ElementTree.SubElement(xml, "li")
                xml_sorted.text = str(mods[0])

        # handle unknown active mods if dont-remove-unknown-mods enabled
        if dont_remove_unknown and mods_unknown_active:
            print("Adding in unknown mods in the load order (at the bottom).")
            for mods in mods_unknown_active:
                if mods == "":
                    print("skipping, empty?")
                else:
                    xml_sorted = ElementTree.SubElement(xml, "li")
                    xml_sorted.text = str(mods)

        # generate unknown mod report for all found unknown mods, regardless of their active status
        if mod_data_unknown:
            print("\nGenerating unknown mods report.")
            DB = dict()
            DB["version"] = 2

            unknown_meta = dict()
            unknown_meta["contributor"] = RWMS.issue_mgmt.get_github_user().split("@")[0]
            unknown_meta["mods_unknown"] = len(mod_data_unknown)
            unknown_meta["mods_known"] = len(mods_data_active) + 1
            unknown_meta["rimworld_version"] = rimworld_version
            unknown_meta["rwms_version"] = VERSION
            unknown_meta["os"] = sys.platform
            unknown_meta["time"] = str(time.ctime())
            DB["meta"] = unknown_meta

            unknown_diff = dict()
            for mod_entry in mod_data_unknown.values():
                if mod_entry[3] == "L":
                    # not printing actual path for security/privacy
                    mod_loc = os.path.join("<RimWorld install directory>", "Mods", mod_entry[0])
                elif not disable_steam:
                    mod_loc = f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_entry[0]}"
                else:
                    mod_loc = ""
                unknown_diff[mod_entry[2]] = ("not_categorized", mod_loc)
            DB["unknown"] = unknown_diff

            unknownfile = f"rwms_unknown_mods_{now_time}.json.txt"
            print("Writing unknown mods report.\n")
            with open(unknownfile, "w", encoding="UTF-8", newline="\n") as f:
                json.dump(DB, f, indent=True, sort_keys=True)

            if RWMS.issue_mgmt.is_github_configured():
                print("For now, due to GitHub issues by itself, disabled. IGNORED.\n")
                print("Please visit https://bitbucket.org/shakeyourbunny/rwmsdb/issues")
                # print("Creating a new issue on the RWMSDB issue tracker.")
                # with open(unknownfile, 'r', encoding="UTF-8") as f:
                #     issuebody = f.read()
                # RWMS.issue_mgmt.create_issue('unknown mods found by ' + RWMS.issue_mgmt.get_github_user(), issuebody)
            else:
                print(
                    textwrap.fill(
                        "For the full list of unknown mods see the written data file in the current "
                        "directory. You can either submit the data file manually on the RWMSDB issue tracker "
                        "or on Steam / Ludeon forum thread. Thank you!",
                        78,
                    )
                )
                print(f"\nData file name is {unknownfile}\n")

                while True:
                    data = input("Do you want to open the RWMSDB issues web page in your default browser (y/n): ")
                    if data.lower() in ("y", "n"):
                        break
                if data.lower() == "y":
                    print("Trying to open the default webbrowser for RWMSDB issues page.\n")
                    webbrowser.open_new("https://bitbucket.org/shakeyourbunny/rwmsdb/issues")

            if dont_remove_unknown:
                print("Unknown, ACTIVE mods will be written at the end of the mod list.")
            else:
                print("Unknown, ACTIVE mods will be removed.")
        else:
            print("lucky, no unknown mods detected!")

        if args.dry_run:
            print_dry_run(mods_config_file, doc, mod_data_full)
            write_mods_config = False

        # ask for confirmation to write the ModsConfig.xml anyway
        while True and not args.dry_run:
            data = input("Do you REALLY want to write ModsConfig.xml (y/n): ")
            if data.lower() in ("y", "n"):
                break
        if data.lower() == "y":
            write_mods_config = True

    if write_mods_config:
        # do backup
        save_results(mods_config_file, doc)
        print("Writing done.")
    else:
        print("ModsConfig.xml was NOT modified.")

    wait_for_exit(0, wait_on_exit)


if __name__ == "__main__":
    main()
