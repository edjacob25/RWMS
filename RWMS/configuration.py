#!/usr/bin/env python3
"""
configuration module for RWMS
"""
import configparser
import os
import sys
from pathlib import Path
from typing import Optional, Union

if sys.platform == "win32":
    import winreg


def configuration_file() -> Path:
    """
    returns the configuration file as a string, empty if not detected.
    :return: str
    """

    # check, if script is compiled with pyinstaller
    if getattr(sys, 'frozen', False):
        mypath = os.path.dirname(sys.executable)
        base_path = Path(".").parent
    elif __file__:
        mypath = os.path.dirname(sys.argv[0])
        base_path = Path.cwd()

    return base_path / "rwms_config.ini"
    # return os.path.join(mypath, "rwms_config.ini")


def load_value(section, entry, is_bool=False) -> Union[str, bool]:
    """
    loads a value from the configurator
    :param section: configuration file section
    :param entry: entry
    :param is_bool: optional, if it is a boolean switch
    :return: value
    """
    configfile = configuration_file()

    if not configfile.is_file():
        return ""

    cfg = configparser.ConfigParser()
    try:
        cfg.read(configfile)
    except:
        print(f"Error parsing configuration file {configfile}.")
        input("Press ENTER to end program.")
        sys.exit(1)

    try:
        if is_bool:
            value = cfg.getboolean(section, entry)
        else:
            value = cfg.get(section, entry, raw=True)
    except:
        print("Error parsing entry '{}', section '{}' from configuration file '{}'".format(entry, section, configfile))
        input("Press ENTER to end program.")
        sys.exit(1)
    return value


def detect_steam() -> Optional[Path]:
    """
    automatic detection of steam
    :return: path to steam base directory
    """
    disablesteam = load_value("rwms", "disablesteam", True)
    if disablesteam:
        return None
    steam_path = load_value("paths", "steamdir")
    if steam_path == "":
        if sys.platform == "win32":
            registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
            key = None
            if registry:
                try:
                    key = winreg.OpenKey(registry, r"SOFTWARE\WoW6432Node\Valve\Steam")
                except:
                    steam_path = None
                if key:
                    res, _ = winreg.QueryValueEx(key, "InstallPath")
                    steam_path = Path(res)
            winreg.CloseKey(registry)
        elif sys.platform == "darwin":
            steam_path = Path.home() / "Library/Application Support/Steam"
        elif sys.platform == "linux":
            steam_path = Path.home() / ".steam/steam"
        return steam_path
    else:
        return Path(steam_path)


def detect_rimworld_steam() -> Optional[Path]:
    rw_steam_path = detect_steam()
    if rw_steam_path is not None:
        if sys.platform == "win32":
            rw_steam_path = rw_steam_path / "steamapps/common/RimWorld"
        elif sys.platform == "darwin":
            rw_steam_path = rw_steam_path / "steamapps/common/RimWorld/RimWorldMac.app"
        elif sys.platform == "linux":
            rw_steam_path = rw_steam_path / "steamapps/common/RimWorld"
    return rw_steam_path


def detect_rimworld_local() -> Path:
    """
    detects local drm free RimWorld installation (has to be configured via configuration file)
    :return: path to RimWorld installation
    """
    drm_freepath = load_value("paths", "drmfreedir")
    return Path(drm_freepath)


def detect_rimworld() -> Path:
    """
    generic detection of RimWorld installation
    :return: path to RimWorld installation
    """
    path = detect_rimworld_steam()
    if path is None:
        path = detect_rimworld_local()
    return path


def detect_rimworld_configdir() -> Path:
    """
    detects RimWorld configuration directory (savegames etc)
    :return: path to RimWorld configuration
    """
    rimworld_config_dir = load_value("paths", "configdir")
    if rimworld_config_dir == "":
        if sys.platform == "win32":
            rimworld_config_dir = Path.home() / "AppData/LocalLow/Ludeon Studios/RimWorld by Ludeon Studios/Config"
        elif sys.platform == "linux":
            rimworld_config_dir = Path.home() / ".config/unity3d/Ludeon Studios/RimWorld by Ludeon Studios/Config"
        elif sys.platform == "darwin":
            rimworld_config_dir = Path.home() / "Library/Application Support/RimWorld/Config"
    else:
        return Path(rimworld_config_dir)
    return rimworld_config_dir


def detect_steamworkshop_dir() -> Optional[Path]:
    """
    detects steamworkshop directory if steam version
    :return: path to workshop directory
    """
    if load_value("rwms", "disablesteam", True):
        return None
    mods_dir = load_value("paths", "workshopdir")
    if mods_dir == "":
        mods_dir = detect_steam() / "steamapps/workshop/content/294100"
    else:
        mods_dir = Path(mods_dir)
    return mods_dir


def detect_localmods_dir() -> Optional[Path]:
    """
    detects local mods directory for RimWorld
    :return: path to localmods directory
    """
    mods_dir = load_value("paths", "localmodsdir")
    if mods_dir == "":
        steam_path = detect_rimworld_steam()
        if steam_path is not None:
            mods_dir = steam_path / "Mods"
        else:
            drm_free_path = detect_rimworld_local()
            if drm_free_path.exists():
                mods_dir = drm_free_path / "Mods"
        return mods_dir
    else:
        return None


def modsconfigfile() -> Path:
    """
    ModsConfig.xml
    :return: returns full path of ModsConfig.xml
    """
    return detect_rimworld_configdir() / "ModsConfig.xml"


def __check_dir(path: Path) -> str:
    if path.is_dir():
        return f"OK {path}"
    else:
        return f"ERR {path}"


def __check_file(file: Path) -> str:
    if file.is_file():
        return f"OK {file}"
    else:
        return f"ERR {file}"


def __dump_configuration():
    """
    dumps complete configuration of RMWS to stdout
    """
    print("pyinstaller configuration")
    frozen = 'not'
    if getattr(sys, 'frozen', False):
        # we are running in a bundle
        frozen = 'ever so'
        bundle_dir = sys._MEIPASS  # pylint: disable=no-member
    else:
        # we are running in a normal Python environment
        bundle_dir = os.path.dirname(os.path.abspath(__file__))
    print('we are', frozen, 'frozen')
    print('bundle dir is', bundle_dir)
    print('sys.argv[0] is', sys.argv[0])
    print('sys.executable is', sys.executable)
    print('os.getcwd is', os.getcwd())
    print('sys.platform is', sys.platform)
    print("")
    print("configuration file is {}\n".format(configuration_file()))
    print("Current OS agnostic configuration")
    if detect_rimworld_steam() is not None:
        print("")
        print("Steam is on .....................: " + __check_dir(detect_steam()))
        print("")
    print("RimWorld folder .................: " + __check_dir(detect_rimworld()))
    print("RimWorld configuration folder ...: " + __check_dir(detect_rimworld_configdir()))
    print("RimWorld local mods folder ......: " + __check_dir(detect_localmods_dir()))
    print("RimWorld steam workshop folder ..: " + __check_dir(detect_steamworkshop_dir()))

    if modsconfigfile() != "":
        print("RimWorld ModsConfig.xml .........: " + __check_file(modsconfigfile()))
        print("")
        print("Updatecheck .....................: {}".format(load_value("rwms", "updatecheck")))
        print("Open Browser ....................: {}".format(load_value("rwms", "openbrowser")))
        print("Wait on Error ...................: {}".format(load_value("rwms", "waitforkeypress_on_error")))
        print("Wait on Exit ....................: {}".format(load_value("rwms", "waitforkeypress_on_exit")))
        print("Enable delays in output .........: {}".format(load_value("rwms", "enabledelaysinoutput")))
        print("Disable Steam Checks ............: {}".format(load_value("rwms", "disablesteam")))
        print("Do not remove unknown mods ......: {}".format(load_value("rwms", "dontremoveunknown")))
        print("Tweaks are disabled .............: {}".format(load_value("rwms", "disabletweaks")))
        print("")
        if load_value("github", "github_username"):
            print("GitHub username .................: is set, not displaying it.")
        if load_value("github", "github_password"):
            print("GitHub password  ................: is set, not displaying it.")
    else:
        print("configuration file not found, using standard values for behaviour.")


# debug
if __name__ == '__main__':
    __dump_configuration()

    print("")
    input("Press ENTER to end program.")
    pass
