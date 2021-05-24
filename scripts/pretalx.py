#!/usr/bin/env python
import os
from pathlib import Path

import click
import httpx
import yaml

from slugify import slugify

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

PRETALX_EVENT_ID = "pyohio-2021"
DATA_DIR = Path("./data")

@click.group()
@click.pass_context
def pretalx(ctx):
    """Utilities for getting data from Pretalx"""

    ctx.obj = {}
    try:
        ctx.obj["api_key"] = os.environ["PRETALX_API_KEY"]
    except KeyError:
        click.echo("Environment variable must be set to interact with Pretalx: PRETALX_API_KEY")
        raise click.Abort()

    if not Path(".projectroot").is_file():
        click.echo("File not found: .projectroot\nMake sure this command is run from the project root and not ./scripts!")
        raise click.Abort()

@pretalx.command()
@click.pass_context
def get_event_data(ctx):
    """Get session and speaker data from Pretalx"""
    sessions_url = f"https://pretalx.com/api/events/{PRETALX_EVENT_ID}/submissions?state=confirmed"
    headers = {
        "Authorization": f"Token {ctx.obj['api_key']}"
    }
    click.echo('Getting talks...', err=True)
    results = get_all_json_results(sessions_url, headers)

    click.echo('Writing talk files...', err=True)
    talk_codes = []
    for talk in results:
        speakers = [{
            "name": s["name"],
            "avatar": s["avatar"],
            "code": s["code"],
            "slug": slugify(s["name"]),
        } for s in talk["speakers"]]
        data = {
            "code": talk["code"],
            "title": talk["title"],
            "slug": slugify(talk["title"]),
            "description": f"md//{talk['description']}",
            "speakers": speakers,
            "type": talk["submission_type"]["en"],
        }
        talk_codes.append(talk["code"])
        save_filename = Path(f"{DATA_DIR}/talks/").joinpath(f"{data['slug']}.yaml")
        with open(save_filename, "w") as save_file:
            yaml.dump(data, save_file, allow_unicode=True)

    click.echo('Getting speaker info...', err=True)
    speaker_codes = []
    for talk in results:
        for speaker in talk["speakers"]:
            speaker_codes.append(speaker["code"])
    speaker_data = []
    for speaker_code in speaker_codes:
        speaker_url = f"https://pretalx.com/api/events/{PRETALX_EVENT_ID}/speakers/{speaker_code}"
        response = httpx.get(speaker_url, headers=headers)
        response.raise_for_status()
        speaker_data.append(response.json())

    click.echo("Writing speaker files...", err=True)
    for speaker in speaker_data:
        data = {
            "name": speaker["name"],
            "slug": slugify(speaker["name"]),
            "code": speaker["code"],
            "avatar": speaker["avatar"],
            "biography": f"md//{speaker['biography']}",
            "submissions": [s for s in speaker["submissions"] if s in talk_codes],
        }
        save_filename = Path(f"{DATA_DIR}/speakers/").joinpath(f"{data['slug']}.yaml")
        with open(save_filename, "w") as save_file:
            yaml.dump(data, save_file, allow_unicode=True)


def get_all_json_results(url, headers):
    results = []
    response = httpx.get(url, headers=headers)
    response.raise_for_status()
    response_json = response.json()
    results.extend(response_json["results"])
    if (url:= response_json["next"]):
        sub_results = get_all_json_results(url, headers=headers)
        results.extend(sub_results)
    return results


def write_yaml_document(document, filename, path="."):
    outfile_name = str(Path(path, filename).resolve())
    with open(outfile_name, "w") as outfile:
        yaml.dump(document, outfile, default_flow_style=False, Dumper=Dumper)


if __name__ == "__main__":
    pretalx()