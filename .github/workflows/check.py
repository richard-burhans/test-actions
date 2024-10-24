#!/usr/bin/env python

import json
import jsonschema
import requests
import sys
import typing
import whenever

EARLIEST_EPOCH: typing.Final = 1721928468


def load_json_schema(pathname: str) -> jsonschema.validators.Draft202012Validator:
    try:
        with open(pathname) as f:
            schema = json.load(f)
    except FileNotFoundError:
        sys.exit(f"ERROR: can't find schema file: {pathname}")
    except json.JSONDecodeError:
        sys.exit(f"ERROR: error decoding schema file: {pathname}")

    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.exceptions.SchemaError:
        sys.exit(f"ERROR: invalid json schema: {pathname}")

    return jsonschema.Draft202012Validator(schema)


dockerhub_tags_validator = load_json_schema("dockerhub-tags.schema")
dockerhub_error_validator = load_json_schema("dockerhub-error.schema")


def get_dockerhub_tags_page(repo: str, page: int = 1, page_size: int = 10) -> tuple[bool, dict[str, int]]:
    tag_dict: dict[str, int] = {}
    finished = False

    url = f"https://hub.docker.com/v2/repositories/{repo}/tags?page={page}&page_size={page_size}"
    response = requests.get(url)

    try:
        tags_json = json.loads(response.text)
    except json.JSONDecodeError:
        sys.exit(f"ERROR: error decoding json: {response.text}")

    if response.status_code == 200:
        if dockerhub_tags_validator.is_valid(tags_json):
            finished = tags_json["next"] is None
            results = tags_json["results"]

            for result in results:
                name = result["name"]
                last_updated = result["last_updated"]
                last_updated_dt = whenever.Instant.parse_rfc3339(last_updated)
                last_updated_ts = last_updated_dt.timestamp()
                if name != "latest" and last_updated_ts >= EARLIEST_EPOCH:
                    tag_dict[name] = last_updated_dt.timestamp()
        else:
            sys.exit("ERROR: unknown tags json format")
    else:
        if not dockerhub_error_validator.is_valid(tags_json):
            sys.exit("ERROR: unknown error json format")

    return finished, tag_dict


def get_dockerhub_tags(repo: str) -> dict[str, int]:
    tag_dict: dict[str, int] = {}

    page = 0
    finished = False
    while not finished:
        page += 1
        finished, page_dict = get_dockerhub_tags_page(repo, page)
        tag_dict.update(page_dict)

    return tag_dict


quay_tags_validator = load_json_schema("quay-tags.schema")
quay_error_validator = load_json_schema("quay-error.schema")


def get_quay_tags(repo: str) -> dict[str, int]:
    tag_dict: dict[str, int] = {}

    url = f"https://quay.io/api/v1/repository/{repo}"
    response = requests.get(url)

    try:
        tags_json = json.loads(response.text)
    except json.JSONDecodeError:
        sys.exit(f"ERROR: error decoding json: {response.text}")

    if response.status_code == 200:
        if quay_tags_validator.is_valid(tags_json):
            for key, key_dict in tags_json["tags"].items():
                name = key_dict["name"]
                last_modified = key_dict["last_modified"]
                last_modified_dt = whenever.Instant.parse_rfc2822(last_modified)
                if name != "latest":
                    tag_dict[name] = last_modified_dt.timestamp()
        else:
            sys.exit("ERROR: unknown tags json format")
    else:
        if not quay_error_validator.is_valid(tags_json):
            sys.exit("ERROR: unknown error json format")

    return tag_dict


src_dict = get_dockerhub_tags("ncbi/egapx")
dst_dict = get_quay_tags("galaxy/egapx")

build_tag_list = []

for src_tag, src_epoch in src_dict.items():
    if src_tag in dst_dict:
        dst_epoch = dst_dict[src_tag]
        if src_epoch >= dst_epoch:
            build_tag_list.append(src_tag)
    else:
        build_tag_list.append(src_tag)

tag_line = ":".join([str(x) for x in build_tag_list])

print(f"tags_to_build={tag_line}")
