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
        print(resp, file=sys.stderr)
    else:
        print("Space created successfully!")

    await client.close()
    return retval

async def space_list_cmd(args: types.SimpleNamespace) -> int:
    client = login()
    if client is None:
        return 1

    spaces = await get_spaces(client)

    print("Name\tID")
    for space in spaces:    
        print(f"{space['name']}\t{space['id']}")
    await client.close()
    return 0

async def room_create_cmd(args: types.SimpleNamespace) -> int:
    client = login()
    if client is None:
        return 1

    resp: nio.RoomCreateResponse = await client.room_create(
        nio.RoomVisibility.public,
        name=args.name
    )

    if isinstance(resp, nio.RoomCreateError):
        print(f'Could not create room "{args.name}"', file=sys.stderr)
        print(f'{resp}')
        await client.close()
        return 1
    print("Room created!")

    if args.space is None:
        return 0
    
    space_id = None
    spaces = await get_spaces(client)
    for i in spaces:
        if i['name'] == args.space:
            space_id = i['id']
            break
    
    if space_id is None:
        print(f'Could not associate room "{args.name}" with space "{args.space}', file=sys.stder)
        print(f'Could not find space "{args.space}"')
        await client.close()
        return 1

    put_resp = await client.room_put_state(
        room_id=space_id,
        event_type="m.space.child",
        state_key=resp.room_id,
        content={
            "via": [client.homeserver],
            "suggested": True
        }
    )

    if isinstance(put_resp, nio.RoomPutStateError):
        print(f'Could not associate room "{args.name}" with space "{args.space}', file=sys.stder)
        print(f'{put_resp}')
        await client.close()
        return 1
    
    await client.close()
    return 0

async def room_list_cmd(args: types.SimpleNamespace) -> int:
    client = login()
    if client is None:
        return 1
    print("Name\tID")
    for i in await get_rooms(client):
        print(f"{i['name']}\t{i['id']}")
    await client.close()
    return 0

async def room_invite_cmd(args: types.SimpleNamespace) -> int:
    client = login()
    if client is None:
        return 1
    
    room = await get_room_by_name(client, args.name)
    if room is None:
        print(f'Could not find room named "{args.name}"')
        await client.close()
        return 1
    
    resp = await client.room_invite(
        room['id'],
        args.user
    )

    if isinstance(resp, nio.RoomInviteError):
        print(f'Could not invite "{args.user}" to "{args.name}"')
        print(f'{resp}')
        await client.close()
        return 1
    
    print('User invited!')
    await client.close()
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
    await args.func(args)


asyncio.run(main())
