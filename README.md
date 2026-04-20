# sendclip

`sendclip` grabs an image from your local clipboard, uploads it to a remote server, prints the final remote file path, and copies that remote path back to your local clipboard.

This is useful when you develop on a remote SSH server and want to pass image file paths directly into tools that run remotely, such as an image MCP.

## Features

- Reads an image from your local clipboard
- Uploads it to a remote server with `scp`
- Creates the remote target directory if needed
- Prints the full remote file path
- Copies the remote file path to your local clipboard
- Stores reusable sendclip aliases in its own config file
- Supports password-based upload through `sshpass`

## Requirements

- Python 3.11+
- `ssh`, `scp`, and `sshpass` if you want password-based auth
- A working SSH connection to the target host
- One clipboard image source that works on your machine:
  - `Pillow` for `ImageGrab`
  - `wl-paste` on Wayland
  - `xclip` or `xsel` on X11/Linux
  - `pngpaste` on macOS

## Install

```bash
./install.sh
```

This installs a `sendclip` launcher into `~/.local/bin` so you can run it from anywhere.
The installer also creates a local virtualenv in the project and installs the required Python packages there.

## Create A Sendclip Alias

If you want to use short names like `dev`, create a sendclip alias:

```bash
sendclip alias create dev 203.0.113.10 user ~/images
```

With a custom port:

```bash
sendclip alias create dev 203.0.113.10 user ~/images --port 2222
```

With a password for `sshpass`:

```bash
sendclip alias create dev 203.0.113.10 user ~/images --password yourpassword
```

List aliases:

```bash
sendclip alias list
sendclip alias ls
```

Remove an alias:

```bash
sendclip alias rm dev
sendclip alias remove dev
```

Aliases are stored in `~/.config/sendclip/config.json`.

## Usage

```bash
sendclip dev
```

Example with a stored alias and a custom filename:

```bash
sendclip dev --name bug-report.png
```

Example with a direct target:

```bash
sendclip 203.0.113.10 ~/images --user user --password yourpassword
```

Use a custom prefix:

```bash
sendclip dev --prefix screenshot
```

Use an explicit filename without creating an alias first:

```bash
sendclip 203.0.113.10 ~/images --user user --name bug-report.png
```

## Output

If the upload succeeds, `sendclip` prints the final remote path, for example:

```text
/home/user/images/clip-20260420-153012.png
```

It also copies that same path to your local clipboard.

## Typical Workflow

1. Copy an image locally
2. Run `sendclip`
3. Paste the remote path into your remote tool or MCP

## Notes

- The clipboard image is read on your local machine
- The file is uploaded to the remote machine you specify
- The final copied path is the remote filesystem path, not a URL
- If your remote machine does not have `python3`, `sendclip` will try `python`
- Alias passwords are stored in plain text in `~/.config/sendclip/config.json`

## License

MIT
