import json
import sys
import requests
import subprocess
import re
import sys


content_regex = re.compile(r"\('(.+)', '(.*)', '(.*)', '(.+)'\)")
options = {}
cname = {}


def name_func(name: str) -> str:
    if name in cname:
        return cname[name]
    else:
        return name


def iso(iso_orig: list) -> None:
    # modify iso_orig inplace
    for i in iso_orig:
        i["distro"] = name_func(i["distro"])
        if not i.get("category"):
            # now ustcmirror has no category and all iso are OS.
            i["category"] = "os"

def size(bytes: int) -> str:
    mib = bytes / 1024 / 1024
    if mib < 1024:
        return f"{mib:.2f} MiB"
    gib = mib / 1024
    if gib < 1024:
        return f"{gib:.2f} GiB"
    tib = gib / 1024
    return f"{tib:.2f} TiB"


def parse_content_meta(content_txt: str, meta: dict) -> dict:
    content_raw_list = content_txt.strip().split("\n")
    content_list = []
    content_hash = {}
    for i in content_raw_list:
        item = content_regex.match(i)
        if not item:
            print(f"failed to parse content line {i}", file=sys.stderr)
            continue
        _, help_url, _, name = item.groups()
        cname = name_func(name)
        content_hash[cname.lower()] = len(content_list)
        content_list.append({
            "cname": cname,
            "desc": "",  # now we don't have desc yet...
            "url": f"/{name}",
            "status": "U",
            "help": help_url,
            "upstream": ""
        })
    # now we add data to content_list with meta!
    for i in meta:
        name = i["name"]
        if name in options["skip"]:
            continue
        name = name_func(name)
        try:
            try:
                ind = content_hash[name.lower()]
            except KeyError:
                ind = content_hash[name.lower().split(".")[0]]  # fix repo name like "kubernetes.apt"
            next_run = i.get("nextRun")
            last_success = i.get("lastSuccess")
            if i["syncing"]:
                content_list[ind]["status"] = "Y" + str(i.get("prevRun"))
                if last_success:
                    content_list[ind]["status"] += "O" + str(last_success)
            elif i["exitCode"] == 0:
                content_list[ind]["status"] = "S" + str(last_success)
            else:
                content_list[ind]["status"] = "F" + str(i.get("prevRun"))
                if last_success:
                    content_list[ind]["status"] += "O" + str(last_success)
            if next_run:
                content_list[ind]["status"] += "X" + str(next_run)
            content_list[ind]["size"] = size(i["size"])
            content_list[ind]["upstream"] = i["upstream"]
        except KeyError:
            print(f"failed to parse {i['name']}", file=sys.stderr)
    return content_list


def disk_info(site: dict) -> None:
    lug_repo = subprocess.check_output("df -h | grep lug-repo | awk {'print $3, $2'}", shell=True).decode('utf-8')
    site['disk'] = lug_repo.replace(" ", "/")


def main():
    global options
    global cname
    if len(sys.argv) < 7:
        print("help: mirrorz.py site.json meta_url genisolist_prog gencontent_prog options.json cname.json output.json")
        sys.exit(0)
    site = json.loads(open(sys.argv[1]).read())
    meta = requests.get(sys.argv[2]).json()
    isolist = json.loads(subprocess.check_output(
        sys.argv[3], stderr=subprocess.DEVNULL).decode('utf-8'))
    content_txt = subprocess.check_output(
        sys.argv[4], stderr=subprocess.DEVNULL).decode('utf-8')
    # meta = json.loads(open(sys.argv[2]).read())
    # isolist = json.loads(open(sys.argv[3]).read())
    # content_txt = open(sys.argv[4]).read()
    options = json.loads(open(sys.argv[5]).read())
    cname = json.loads(open(sys.argv[6]).read())
    output = sys.argv[7]

    disk_info(site)
    iso(isolist)
    mirrors = parse_content_meta(content_txt, meta)

    mirrorz = {}
    mirrorz["site"] = site
    mirrorz["info"] = isolist
    mirrorz["mirrors"] = mirrors

    with open(output, "w") as f:
        f.write(json.dumps(mirrorz))


if __name__ == '__main__':
    main()
