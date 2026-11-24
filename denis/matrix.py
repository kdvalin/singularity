#!/usr/bin/env python3
import asyncio
import json
import sys
import os
import argparse
import types

from nio import AsyncClient, LoginResponse

CONFIG_FILE = "/tmp/matrix_creds"


def login() -> AsyncClient | None:
    if not os.path.exists(CONFIG_FILE):
        print(f"Credential file {CONFIG_FILE} does not exist", file=sys.stderr)
        print("Run the \"login\" command first", file=sys.stderr)
        return None

    with open(CONFIG_FILE, 'r') as file:
        config = json.load(file)

    client = AsyncClient(config['homeserver'], ssl=False)
    client.access_token = config["access_token"]
    client.user_id = config["user_id"]
    client.device_id = config["device_id"]

    return client


async def login_cmd(args: types.SimpleNamespace) -> int:
    if os.path.exists(CONFIG_FILE):
        print(f"Credential file {CONFIG_FILE} is present", file=sys.stderr)
        print("Run logout to clean it up before logging in", file=sys.stderr)
        return 1

    device_name = "denis_nio_client"
    client = AsyncClient(args.homeserver, args.uname, ssl=False)
    resp = await client.login(args.password, device_name)

    if not isinstance(resp, LoginResponse):
        print(f"Could not login to {args.homeserver} as {args.uname}", file=sys.stderr)
        print(f"{resp}", file=sys.stderr)
        await client.close()
        return 1

    with open(CONFIG_FILE, 'w') as file:
        json.dump({
            "homeserver": args.homeserver,
            "user_id": resp.user_id,
            "device_id": resp.device_id,
            "access_token": resp.access_token,
        }, file)
    await client.close()
    print("Logged in!")

    return 0

async def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    login_parser = subparsers.add_parser("login", help="Login to the matrix server")
    login_parser.add_argument("homeserver", type=str, help="The URL to the homeserver to login to")
    login_parser.add_argument("uname", type=str, help="The user to login as")
    login_parser.add_argument("password", type=str, help="Password for the user")
    login_parser.set_defaults(func=login_cmd)

    args = parser.parse_args()
    await args.func(args)


asyncio.run(main())
