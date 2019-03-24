#!/usr/bin/python3
# RimWorld Module Sorter

import json
import os
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from operator import itemgetter

from colorama import Fore as Color
from colorama import init as coloramainit

coloramainit(autoreset=True)

modsconfigfile = "C:/Users/pulaski/AppData/LocalLow/Ludeon Studios/RimWorld by Ludeon Studios/Config/ModsConfig.xml"

mod_unknown = list()
scoring_table = dict()


def load_mod_data(basedir, modsource):
    mod_details = dict()
    folderlist = os.listdir(basedir)
    for moddirs in folderlist:
        aboutxml = basedir + '/' + moddirs + "/About/About.xml"
        if os.path.isfile(aboutxml):
            xml = ET.parse(aboutxml)
            name = xml.find('name').text

            try:
                mod_entry = [moddirs, float(scoring_table[name]), name, modsource]

            except KeyError:
                mod_unknown.append(name)
                mod_entry = list()
                # print("unknown mod "+str(name))

            if mod_entry:
                mod_details[moddirs] = mod_entry
        else:
            print("could not find metadata for item " + moddirs + " (skipping)!")
            name = ""
    return mod_details


# Lists
# fixme: proper loading mechanism
# load scoring table
score_db = "testdata/db_modscoring.json"
if not os.path.isfile(score_db):
    print("could not load db scoring table.")
    sys.exit(1)
with open(score_db, 'r', encoding='UTF-8') as scoringfile:
    scoring_table = json.loads(scoringfile.read())
scoringfile.close()
print('Number of Mods registered in DB : ' + Color.LIGHTCYAN_EX + '{}'.format(len(scoring_table)))
print('Last DB updated date : ' + Color.LIGHTGREEN_EX + '{}'.format(scoring_table['time']))
print("")

# fixme: proper reading and parsing of ModsConfig
print("Loading and parsing ModConfig.xml")
if not os.path.isfile(modsconfigfile):
    print("could not find " + modsconfigfile)
    sys.exit(1)
xml = ET.parse(modsconfigfile)
xml = xml.find('activeMods')
mods_enabled_list = [t.text for t in xml.findall('li')]
if not "Core" in mods_enabled_list:
    mods_enabled_list.append("Core")

# check auf unknown mods
print("loading mod data.")
mod_data_workshop = load_mod_data('D:/Spiele/Steam/steamapps/workshop/content/294100', "W")
mod_data_local = load_mod_data("D:/Spiele/Steam/steamapps/common/RimWorld/Mods", "L")
mod_data_full = {**mod_data_local, **mod_data_workshop}

mods_data_active = list()
for mods in mods_enabled_list:
    try:
        mods_data_active.append([mods, mod_data_full[mods][1]])

    except KeyError:
        pass
        # print("Unknown mod ID {}, deactivating it from mod list.".format(mods))

print("sorting mods.")
newlist = sorted(mods_data_active, key=itemgetter(1))
print("")
print("{} subscribed mods, {} ({} known, {} unknown) enabled mods".format(len(mod_data_full), len(mods_enabled_list),
                                                                          len(mods_data_active), len(mod_unknown)))
# do backup
now_time = time.strftime('%Y%m%d-%H%M', time.localtime(time.time()))
shutil.copy(modsconfigfile, modsconfigfile + '.backup-{}'.format(now_time))
# write configuration
print("writing ModConfig.xml.")
if not os.path.isfile(modsconfigfile):
    print("error accessing " + modsconfigfile)
    sys.exit(1)
doc = ET.parse(modsconfigfile)
xml = doc.getroot()
xml = xml.find('activeMods')
for li in xml.findall('li'):
    xml.remove(li)

# ET.dump(doc)

xml_sorted = ET.SubElement(xml, 'li')
for mods in newlist:
    # print(mods)
    if mods[0] == "":
        print("skipping, empty?")
    else:
        xml_sorted = ET.SubElement(xml, 'li')
        xml_sorted.text = str(mods[0])
    # ET.dump(doc)

### create


### finish
# enable it to write ModConfig, actually.
# doc.write(modsconfigfile, encoding='UTF-8', xml_declaration='False')