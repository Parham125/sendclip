#!/usr/bin/env python3.13
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

CONFIG_DIR=Path.home()/".config"/"sendclip"
CONFIG_PATH=CONFIG_DIR/"config.json"


def command_exists(name:str)->bool:
    return shutil.which(name)is not None


def run_command(command:list[str],password:str|None=None)->subprocess.CompletedProcess:
    if password:
        command=["sshpass","-p",password,*command]
    return subprocess.run(command,capture_output=True,text=False)


def ensure_config()->dict:
    CONFIG_DIR.mkdir(parents=True,exist_ok=True)
    os.chmod(CONFIG_DIR,0o700)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps({"aliases":{}},indent=2)+"\n")
        os.chmod(CONFIG_PATH,0o600)
    with open(CONFIG_PATH) as f:
        data=json.load(f)
    if not isinstance(data,dict):
        raise RuntimeError(f"Invalid config file: {CONFIG_PATH}")
    if "aliases" not in data or not isinstance(data["aliases"],dict):
        data["aliases"]={}
        save_config(data)
    return data


def save_config(data:dict)->None:
    CONFIG_DIR.mkdir(parents=True,exist_ok=True)
    os.chmod(CONFIG_DIR,0o700)
    with open(CONFIG_PATH,"w") as f:
        json.dump(data,f,indent=2)
        f.write("\n")
    os.chmod(CONFIG_PATH,0o600)


def write_bytes(temp_dir:Path,data:bytes,extension:str)->Path:
    path=temp_dir/f"clipboard.{extension}"
    path.write_bytes(data)
    return path


def clipboard_from_pillow(temp_dir:Path)->Path|None:
    try:
        from PIL import ImageGrab
    except ImportError:
        return None
    try:
        image=ImageGrab.grabclipboard()
    except Exception:
        return None
    if image is None or not hasattr(image,"save"):
        return None
    path=temp_dir/"clipboard.png"
    image.save(path,"PNG")
    return path


def clipboard_from_wayland(temp_dir:Path)->Path|None:
    if not command_exists("wl-paste"):
        return None
    for mime,extension in (("image/png","png"),("image/jpeg","jpg"),("image/webp","webp")):
        result=run_command(["wl-paste","--no-newline","--type",mime])
        if result.returncode==0 and result.stdout:
            return write_bytes(temp_dir,result.stdout,extension)
    return None


def clipboard_from_xclip(temp_dir:Path)->Path|None:
    if not command_exists("xclip"):
        return None
    for mime,extension in (("image/png","png"),("image/jpeg","jpg"),("image/webp","webp")):
        result=run_command(["xclip","-selection","clipboard","-t",mime,"-o"])
        if result.returncode==0 and result.stdout:
            return write_bytes(temp_dir,result.stdout,extension)
    return None


def clipboard_from_xsel(temp_dir:Path)->Path|None:
    if not command_exists("xsel"):
        return None
    for mime,extension in (("image/png","png"),("image/jpeg","jpg"),("image/webp","webp")):
        result=run_command(["xsel","--clipboard","--output","--mime-type",mime])
        if result.returncode==0 and result.stdout:
            return write_bytes(temp_dir,result.stdout,extension)
    return None


def clipboard_from_pngpaste(temp_dir:Path)->Path|None:
    if not command_exists("pngpaste"):
        return None
    path=temp_dir/"clipboard.png"
    result=run_command(["pngpaste",str(path)])
    if result.returncode==0 and path.exists() and path.stat().st_size>0:
        return path
    return None


def capture_clipboard_image(temp_dir:Path)->Path:
    for loader in (clipboard_from_pillow,clipboard_from_wayland,clipboard_from_xclip,clipboard_from_xsel,clipboard_from_pngpaste):
        path=loader(temp_dir)
        if path:
            return path
    raise RuntimeError("No image found in clipboard. Install Pillow, wl-paste, xclip, xsel, or pngpaste if needed.")


def build_filename(prefix:str,extension:str,name:str|None)->str:
    if name:
        return name if "." in Path(name).name else f"{name}.{extension}"
    timestamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{timestamp}.{extension}"


def user_host(target:str,user:str|None)->str:
    return target if "@" in target or not user else f"{user}@{target}"


def resolve_remote_path(target:str,remote_dir:str,filename:str,user:str|None,password:str|None,port:int)->str:
    host=user_host(target,user)
    remote_command='directory="$1"; filename="$2"; case "$directory" in "~") directory="$HOME" ;; "~/"*) directory="$HOME/${directory#~/}" ;; esac; mkdir -p -- "$directory" && printf "%s/%s\\n" "$directory" "$filename"'
    result=run_command(["ssh","-p",str(port),host,"sh","-lc",remote_command,"sh",remote_dir,filename],password)
    if result.returncode==0:
        return result.stdout.decode().strip()
    message=result.stderr.decode().strip() or result.stdout.decode().strip() or "Unknown ssh error"
    raise RuntimeError(f"Failed to resolve remote path on {host}:{port}: {message}")


def upload_file(target:str,local_path:Path,remote_path:str,user:str|None,password:str|None,port:int)->None:
    host=user_host(target,user)
    result=run_command(["scp","-P",str(port),str(local_path),f"{host}:{remote_path}"],password)
    if result.returncode!=0:
        message=result.stderr.decode().strip() or result.stdout.decode().strip() or "Unknown scp error"
        raise RuntimeError(f"Upload failed: {message}")


def copy_text(text:str)->bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass
    if command_exists("wl-copy"):
        result=subprocess.run(["wl-copy"],input=text.encode(),capture_output=True)
        return result.returncode==0
    if command_exists("xclip"):
        result=subprocess.run(["xclip","-selection","clipboard"],input=text.encode(),capture_output=True)
        return result.returncode==0
    if command_exists("pbcopy"):
        result=subprocess.run(["pbcopy"],input=text.encode(),capture_output=True)
        return result.returncode==0
    if command_exists("clip.exe"):
        result=subprocess.run(["clip.exe"],input=text.encode(),capture_output=True)
        return result.returncode==0
    return False


def apply_alias(args:argparse.Namespace)->argparse.Namespace:
    data=ensure_config()
    alias=data["aliases"].get(args.target)
    if not alias:
        return args
    args.target=alias["host"]
    if args.remote_dir is None:
        args.remote_dir=alias["remote_dir"]
    if args.user is None:
        args.user=alias.get("user")
    if args.password is None:
        args.password=alias.get("password")
    if args.port is None:
        args.port=alias.get("port",22)
    return args


def create_alias(args:argparse.Namespace,replace:bool=False)->int:
    data=ensure_config()
    if args.alias_name in data["aliases"] and not replace:
        raise RuntimeError(f"Alias already exists: {args.alias_name}")
    data["aliases"][args.alias_name]={
        "host":args.alias_host,
        "user":args.alias_user,
        "remote_dir":args.alias_remote_dir,
        "port":args.alias_port,
        "password":args.alias_password,
    }
    save_config(data)
    print(f"Updated alias {args.alias_name}" if replace else f"Created alias {args.alias_name}")
    return 0


def list_aliases()->int:
    data=ensure_config()
    aliases=data["aliases"]
    if not aliases:
        print("No aliases configured.")
        return 0
    for name in sorted(aliases):
        alias=aliases[name]
        remote_dir=alias.get("remote_dir","")
        target=user_host(alias["host"],alias.get("user"))
        port=alias.get("port",22)
        print(f"{name}\t{target}\t{remote_dir}\tport={port}")
    return 0


def remove_alias(name:str)->int:
    data=ensure_config()
    if name not in data["aliases"]:
        raise RuntimeError(f"Alias not found: {name}")
    del data["aliases"][name]
    save_config(data)
    print(f"Removed alias {name}")
    return 0


def build_alias_parser()->argparse.ArgumentParser:
    alias_parser=argparse.ArgumentParser(description="Manage sendclip aliases.")
    alias_subparsers=alias_parser.add_subparsers(dest="alias_command")
    alias_create=alias_subparsers.add_parser("create",help="Create an alias")
    alias_create.add_argument("alias_name")
    alias_create.add_argument("alias_host")
    alias_create.add_argument("alias_user")
    alias_create.add_argument("alias_remote_dir")
    alias_create.add_argument("--port",dest="alias_port",type=int,default=22)
    alias_create.add_argument("--password",dest="alias_password")
    alias_update=alias_subparsers.add_parser("update",help="Update or replace an alias")
    alias_update.add_argument("alias_name")
    alias_update.add_argument("alias_host")
    alias_update.add_argument("alias_user")
    alias_update.add_argument("alias_remote_dir")
    alias_update.add_argument("--port",dest="alias_port",type=int,default=22)
    alias_update.add_argument("--password",dest="alias_password")
    alias_subparsers.add_parser("list",help="List aliases")
    alias_subparsers.add_parser("ls",help="List aliases")
    alias_rm=alias_subparsers.add_parser("rm",help="Remove an alias")
    alias_rm.add_argument("name")
    alias_remove=alias_subparsers.add_parser("remove",help="Remove an alias")
    alias_remove.add_argument("name")
    return alias_parser


def build_upload_parser()->argparse.ArgumentParser:
    parser=argparse.ArgumentParser(description="Upload the current clipboard image to a remote server and copy the remote path.")
    parser.add_argument("target",help="Alias or host to upload to")
    parser.add_argument("remote_dir",nargs="?",help="Remote directory when not using an alias with a stored path")
    parser.add_argument("--user")
    parser.add_argument("--port",type=int)
    parser.add_argument("--password")
    parser.add_argument("--prefix",default="clip")
    parser.add_argument("--name")
    return parser


def parse_args()->argparse.Namespace:
    argv=sys.argv[1:]
    if not argv:
        build_upload_parser().print_help()
        raise SystemExit(1)
    if argv[0]=="alias":
        alias_parser=build_alias_parser()
        if len(argv)==1:
            alias_parser.print_help()
            raise SystemExit(1)
        args=alias_parser.parse_args(argv[1:])
        args.command="alias"
        return args
    args=build_upload_parser().parse_args(argv)
    args.command=None
    return args


def upload(args:argparse.Namespace)->int:
    args=apply_alias(args)
    if args.password and not command_exists("sshpass"):
        raise RuntimeError("sshpass is required when using --password.")
    if args.remote_dir is None:
        raise RuntimeError("remote_dir is required unless the alias already stores one.")
    port=args.port or 22
    with tempfile.TemporaryDirectory(prefix="sendclip-") as temp_dir_name:
        temp_dir=Path(temp_dir_name)
        local_image=capture_clipboard_image(temp_dir)
        extension=local_image.suffix.lstrip(".") or "png"
        filename=build_filename(args.prefix,extension,args.name)
        remote_path=resolve_remote_path(args.target,args.remote_dir,filename,args.user,args.password,port)
        upload_file(args.target,local_image,remote_path,args.user,args.password,port)
        copied=copy_text(remote_path)
        print(remote_path)
        if not copied:
            print("Warning: uploaded successfully but failed to copy the remote path to your clipboard.",file=sys.stderr)
    return 0


def main()->int:
    try:
        args=parse_args()
        if args.command=="alias":
            if args.alias_command in {"list","ls"}:
                return list_aliases()
            if args.alias_command=="create":
                return create_alias(args)
            if args.alias_command=="update":
                return create_alias(args,replace=True)
            if args.alias_command in {"rm","remove"}:
                return remove_alias(args.name)
        return upload(args)
    except RuntimeError as e:
        print(str(e),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
