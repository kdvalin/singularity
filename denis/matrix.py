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


class MatrixError(RuntimeError):
    what: str
    rtc: int

    def __init__(self, what: str, rtc: int):
        self.rtc = rtc
        self.what = what

class MatrixNamespace(types.SimpleNamespace):
    client: nio.AsyncClient

async def get_spaces(client: AsyncClient) -> list[dict[str, str]]:
    output = []
    await client.sync()
    for i in client.rooms.values():
        if i.room_type == "m.space":
            output.append({
                "name": i.name,
                "id": i.room_id
            })

    return output

async def get_rooms(client: AsyncClient) -> list[dict[str, str]]:
    output = []
    await client.sync()
    for i in client.rooms.values():
        if i.room_type != "m.space":
            output.append({
                "name": i.name,
                "id": i.room_id
            })

    return output

async def get_room_by_name(client: AsyncClient, name: str) -> dict[str, str] | None:
    rooms = await get_rooms(client)
    for i in rooms:
        if i['name'] == name:
            return i
    return None

def login() -> AsyncClient:
    if not os.path.exists(CONFIG_FILE):
        raise MatrixError(f"Credential file {CONFIG_FILE} does not exist\nRun the \"login\" command first", 1)

    with open(CONFIG_FILE, 'r') as file:
        config = json.load(file)

    client = AsyncClient(config['homeserver'], ssl=False)
    client.access_token = config["access_token"]
    client.user_id = config["user_id"]
    client.device_id = config["device_id"]

    return client


async def login_cmd(args: MatrixNamespace) -> int:
    if os.path.exists(CONFIG_FILE):
        raise MatrixError(f"Credential file {CONFIG_FILE} is present\nRun logout to clean it up before logging in", 1)

    device_name = "denis_nio_client"
    client = AsyncClient(args.homeserver, args.uname, ssl=False)
    resp = await client.login(args.password, device_name)

    if isinstance(resp, nio.LoginError):
        raise MatrixError(f"Could not login to {args.homeserver} as {args.uname}\n{resp}", 1)

    with open(CONFIG_FILE, 'w') as file:
        json.dump({
            "homeserver": args.homeserver,
            "user_id": resp.user_id,
            "device_id": resp.device_id,
            "access_token": resp.access_token,
        }, file)
    await client.close()
    print("Logged in!")


async def logout_cmd(_: types.SimpleNamespace) -> int:  
    resp = await args.client.logout()
    if isinstance(resp, nio.LogoutError):
        raise MatrixError(f"Could not logout!\n{resp}", 1)

    os.remove(CONFIG_FILE)
    print("Logged out!")


async def space_create_cmd(args: types.SimpleNamespace) -> int:    
    resp = await args.client.room_create(
        nio.RoomVisibility.public,
        name=args.name,
        space=True
    )

    if isinstance(resp, nio.RoomCreateError):
        raise MatrixError(f"Could not create space \"{args.name}\"\n{resp}", 1)

    print("Space created successfully!")


async def space_list_cmd(args: types.SimpleNamespace):
    spaces = await get_spaces(args.client)

    print("Name\tID")
    for space in spaces:    
        print(f"{space['name']}\t{space['id']}")


async def room_create_cmd(args: types.SimpleNamespace):
    resp: nio.RoomCreateResponse = await args.client.room_create(
        nio.RoomVisibility.public,
        name=args.name
    )

    if isinstance(resp, nio.RoomCreateError):
        raise MatrixError(f'Could not create room "{args.name}"\n{resp}', 1)

    print("Room created!")

    if args.space is None:
        return
    
    space_id = None
    spaces = await get_spaces(args.client)
    for i in spaces:
        if i['name'] == args.space:
            space_id = i['id']
            break
    
    if space_id is None:
        raise MatrixError(f'Could not associate room "{args.name}" with space "{args.space}"\nCould not find space "{args.space}"', 1)

    put_resp = await args.client.room_put_state(
        room_id=space_id,
        event_type="m.space.child",
        state_key=resp.room_id,
        content={
            "via": [args.client.homeserver],
            "suggested": True
        }
    )

    if isinstance(put_resp, nio.RoomPutStateError):
        raise MatrixError(f'Could not associate room "{args.name}" with space "{args.space}\n{put_resp}', 1)


async def room_list_cmd(args: types.SimpleNamespace) -> int:
    print("Name\tID")
    for i in await get_rooms(args.client):
        print(f"{i['name']}\t{i['id']}")
    return 0

async def room_invite_cmd(args: types.SimpleNamespace) -> int:  
    room = await get_room_by_name(args.client, args.name)
    if room is None:
        raise MatrixError(f'Could not find room named "{args.name}"', 1)
    
    resp = await args.client.room_invite(
        room['id'],
        args.user
    )

    if isinstance(resp, nio.RoomInviteError):
        raise MatrixError(f'Could not invite "{args.user}" to "{args.name}"\n{resp}', 1)
    
    print('User invited!')
    return 0
    

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

    space_list_parser = space_subparsers.add_parser("list", help="Lists the spaces within the matrix server")
    space_list_parser.set_defaults(func=space_list_cmd)

    room_parser = subparsers.add_parser("room", help="Manage spaces within the matrix server")
    room_subparsers = room_parser.add_subparsers(dest="room_cmd", required=True)
    
    room_create_parser = room_subparsers.add_parser("create", help="Creates a room on the matrix server")
    room_create_parser.add_argument("name", help="Name of the room", type=str)
    room_create_parser.add_argument("-s", "--space", help="The space to place the room under", type=str, dest="space", default=None)
    room_create_parser.set_defaults(func=room_create_cmd)

    room_list_parser = room_subparsers.add_parser("list", help="Invites a user to a room")
    room_list_parser.set_defaults(func=room_list_cmd)

    room_invite_parser = room_subparsers.add_parser("invite", help="Invites a user to a room")
    room_invite_parser.add_argument("name", help="Name of the room", type=str)
    room_invite_parser.add_argument("user", help="User ID to be added to the room", type=str)
    room_invite_parser.set_defaults(func=room_invite_cmd)

    args = parser.parse_args()

    rtc = 0
    try:
        if args.command != "login":
            args.client = login()
        else:
            args.client = None
        await args.func(args)
    except MatrixError as e:
        print(e.what, file=sys.stderr)
        rtc = e.rtc
    finally:
        if args.client is not None:
            await args.client.close()
        sys.exit(rtc)

asyncio.run(main())
