#!/usr/bin/env python2.7

import sys
import getopt
import argparse
import re
import subprocess
from os.path import expanduser
from math import ceil

home = expanduser("~")
host_re = re.compile(r"host\s+(\S+)", re.IGNORECASE)
hostname_re = re.compile(r"hostname\s+(\S+)", re.IGNORECASE)
# this regexp will extract a integer suffix, if ones exists, then use 
# the prefix as first sorting field and the suffix and the second one
host_split = re.compile(r"(\D+(?:\d+\D+)*)(\d+)")

hostname_by_host = {}

parser = argparse.ArgumentParser(
    description="Tool to automatically open several ssh connections in iTerm2 by querying ~/.ssh/config")
parser.add_argument("-r", "--run", dest="should_actually_run", action="store_true", default=False, 
    help="Must pass this to actually run, otherwise will just list matching hosts")
parser.add_argument("pattern", help="A regular expression used to select hosts by name")
parser.add_argument("-d", "--debug", action="store_true", default=False, 
    help="Just dump Applescript, do not execute")
arguments = parser.parse_args()


def load_hosts():
    with open(home + "/.ssh/config") as f:
        current_host = None
        for line in f.readlines():
            result = host_re.search(line);
            if result:
                current_host = result.group(1)
            elif current_host is not None:
                result = hostname_re.search(line)
                if result:
                    hostname_by_host[current_host] = result.group(1)
                    current_host = None


def check_if_iterm_version_is_supported():
    osa = subprocess.Popen(['osascript', '-'],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)

    version_script = 'set iterm_version to (get version of application "iTerm")'
    version = osa.communicate(version_script)[0].strip()

    match = re.search(r"^(\d+)\.(\d+)", version)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2))
        return (major > 2) or (major == 2 and minor > 9)  # support only if greater than 2.9
    return False


def prompt_for_confirmation(hosts_count):
    print("\nNumber of panes to open: %d" % hosts_count)
    sys.stdout.write("Press 'y' to continue or anything else to abort: ")
    choice = raw_input().strip().lower()
    return choice == "y"


def create_pane(parent, child, orientation):
    return """
        tell pane_{parent}
            set pane_{child} to (split {orientation}ly with same profile)
        end tell
        """.format(parent=parent, child=child, orientation=orientation)


def init_pane(number, host):
    return """
        tell pane_{number}
            write text "ssh {host}"
            set name to "this is me testing"
        end tell
        """.format(number=number, host=host)


def prepare_and_run_applescript(selected_hosts):
    num_panes = len(selected_hosts)
    vertical_splits = int(ceil((num_panes / 2.0))) - 1
    second_columns = num_panes / 2
    pane_creation = ""

    for p in range(0, vertical_splits):
        parent = (p * 2) + 1
        child = parent + 2
        pane_creation += create_pane(parent, child, "horizontal")

    for p in range(0, second_columns):
        parent = (p * 2) + 1
        child = parent + 1
        pane_creation += create_pane(parent, child, "vertical")

    pane_initialization = ""

    for i in range(0, num_panes):
        pane_initialization += init_pane(i + 1, selected_hosts[i])

    script = """
        tell application "iTerm"
            activate
            tell current window
                create tab with default profile
            end tell

            set pane_1 to (current session of current window)

            {pane_creation}
            {pane_initialization}
        end tell
        """.format(pane_creation=pane_creation, pane_initialization=pane_initialization)

    if arguments.debug:
        print(script)
        exit(0)

    osa = subprocess.Popen(['osascript', '-'],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    output = osa.communicate(script)[0]
    print(output)


def split_host_by_prefix_and_suffix(host):
    result = host_split.match(host)
    if result:
        prefix = result.group(1)
        suffix = result.group(2) if result.group(2) else 0
    else:
        prefix = host
        suffix = 0
    return (prefix, suffix)


def sort_hosts(selected_hosts):
    return sorted(selected_hosts, key=lambda host: split_host_by_prefix_and_suffix(host))


def main():
    if not check_if_iterm_version_is_supported():
        print("iTerm2 version not supported or iTerm2 is not installed")
        exit(1)

    pat = re.compile(arguments.pattern, re.IGNORECASE)
    load_hosts()

    # get filtered list of hosts, each a tuple (name, address)
    selected_hosts = list(host for host in hostname_by_host.keys() if pat.search(host))

    if len(selected_hosts) == 0:
        print("There are no hosts that match the given filter.")
        exit(0)

    selected_hosts = sort_hosts(selected_hosts)

    print("Will open the following terminal panes:\n")
    for host in selected_hosts:
        print("- %s" % host)
    
    if arguments.debug or prompt_for_confirmation(len(selected_hosts)):
        prepare_and_run_applescript(selected_hosts)


main()
