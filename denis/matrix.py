#!/usr/bin/env python3
import asyncio
import json
import sys
import os
import argparse
import types

import nio
from nio import AsyncClient

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

    if isinstance(resp, nio.LoginError):
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

async def logout_cmd(_: types.SimpleNamespace) -> int:
    retval = 0
    client = login()
    if client is None:
        print("Nothing to log out!", file=sys.stderr)
        return 0
    
    resp = await client.logout()
    if isinstance(resp, nio.LogoutError):
        print("Could not logout!", file=sys.stderr)
        print(f"{resp}", file=sys.stderr)
        retval = 1
    await client.close()
    os.remove(CONFIG_FILE)
    print("Logged out!")
    return retval


async def space_create_cmd(args: types.SimpleNamespace) -> int:
    retval = 0
    client = login()
    if client is None:
        return 1
    
    resp = await client.room_create(
        nio.RoomVisibility.public,
        name=args.name,
        space=True
    )

    if isinstance(resp, nio.RoomCreateError):
        retval = 1
        print(f"Could not create space \"{args.name}\"", file=sys.stderr)
        print(resp)
    else:
        print("Space created successfully!")

    await client.close()
    return retval
    

async def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    login_parser = subparsers.add_parser("login", help="Login to the matrix server")
    login_parser.add_argument("homeserver", type=str, help="The URL to the homeserver to login to")
    login_parser.add_argument("uname", type=str, help="The user to login as")
    login_parser.add_argument("password", type=str, help="Password for the user")
    login_parser.set_defaults(func=login_cmd)

    logout_parser = subparsers.add_parser("logout", help="Login to the matrix server")
    logout_parser.set_defaults(func=logout_cmd)

    space_parser = subparsers.add_parser("space", help="Manage spaces within the matrix server")
    space_subparsers = space_parser.add_subparsers(dest="spaces_cmd", required=True)
    
    space_create_parser = space_subparsers.add_parser("create", help="Creates a space on the matrix server")
    space_create_parser.add_argument("name", help="Name of the space", type=str)
    space_create_parser.set_defaults(func=space_create_cmd)

    args = parser.parse_args()
    await args.func(args)


asyncio.run(main())
