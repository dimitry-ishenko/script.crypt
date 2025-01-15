import json
import os
import subprocess
import tempfile
import xbmcaddon
import xbmcgui

addon_path = xbmcaddon.Addon().getAddonInfo("path")
res_path = addon_path + "/resources"

def run(args):
    try:
        proc = subprocess.run(args, capture_output=True)
        if not proc.returncode: return True, proc.stdout
        err = proc.stderr
    except Exception as e:
        err = str(e)

    xbmcgui.Dialog().notification("Crypt", err, xbmcgui.NOTIFICATION_ERROR)
    return False, None

def unmount(path):
    success, output = run(["udisksctl", "unmount", "--block-device", path])
    if success:
        xbmcgui.Dialog().notification("Crypt", output)
    return success

def lock(path):
    success, output = run(["udisksctl", "lock", "--block-device", path])
    if success:
        xbmcgui.Dialog().notification("Crypt", output)
    return success

def unlock_and_mount(path):
    with tempfile.NamedTemporaryFile(buffering=0) as file:
        phrase = xbmcgui.Dialog().input("Enter pass phrase", option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if not phrase: return True

        os.chmod(file.name, 0o600)
        file.write(phrase.encode())
        success, output = run(["udisksctl", "unlock", "--key-file", file.name, "--block-device", path])

        phrase = "X" * len(phrase)
        file.seek(0)
        file.write(phrase.encode())

    if success:
        xbmcgui.Dialog().notification("Crypt", output)

        success, output = run(["lsblk", "--json", "--output", "NAME,PATH", path])
        if success:
            data = json.loads(output)
            crypt_path = data["blockdevices"][0]["children"][0]["path"]

            success, output = run(["udisksctl", "mount", "--block-device", crypt_path])
            if success:
                xbmcgui.Dialog().notification("Crypt", output)

    return success

def get_icon(tran):
    if tran == "mmc":
        return res_path + "/mmc.png"
    elif tran == "nvme":
        return res_path + "/ssd.png"
    elif tran == "sata":
        return res_path + "/ssd.png"
    elif tran == "usb" :
        return res_path + "/usb.png"
    else: return res_path + "/hdd.png"

def get_item(node, tran):
    drive_path = node["path"]
    crypt_path = ""
    mount_path = ""
    if "children" in node:
        child = node["children"][0]
        crypt_path = child["path"]
        mount_path = child["mountpoint"]

    label = drive_path
    if node["partlabel"]:
        label += " (" + node["partlabel"] + ")"

    if mount_path:
        label2 = "Unlocked, mounted on " + mount_path
    elif crypt_path:
        label2 = "Unlocked"
    else: label2 = "Locked"

    item = xbmcgui.ListItem(label, label2)
    item.setArt({"icon": get_icon(tran)})
    item.setProperties({
        "drive_path": drive_path,
        "crypt_path": crypt_path,
        "mount_path": mount_path
    })
    return item

if __name__ == "__main__":
    success, output = run(["lsblk", "--json", "--output", "NAME,PATH,FSTYPE,PARTLABEL,TRAN,MOUNTPOINT"])
    if success:
        items = []
        data = json.loads(output)
        for drive in data["blockdevices"]:
            tran = drive["tran"]

            if drive["fstype"] == "crypto_LUKS":
                items.append(get_item(drive, tran))

            elif "children" in drive:
                for part in drive["children"]:
                    if part["fstype"] == "crypto_LUKS":
                        items.append(get_item(part, part["tran"] or tran))

        index = xbmcgui.Dialog().select("Encrypted drives", items, useDetails=True)
        if index >= 0:
            item = items[index]
            label= item.getLabel()

            drive_path = item.getProperty("drive_path")
            crypt_path = item.getProperty("crypt_path")
            mount_path = item.getProperty("mount_path")

            if mount_path:
                if xbmcgui.Dialog().yesno("Crypt", "Unmount & lock " + label + "?", defaultbutton=xbmcgui.DLG_YESNO_YES_BTN):
                    unmount(crypt_path) and lock(drive_path)

            elif crypt_path:
                if xbmcgui.Dialog().yesno("Crypt", "Lock " + label + "?", defaultbutton=xbmcgui.DLG_YESNO_YES_BTN):
                    lock(drive_path)

            else: unlock_and_mount(drive_path)
