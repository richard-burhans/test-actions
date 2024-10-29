#!/usr/bin/env python

import abc
import json
import jsonschema
import requests
import sys
import typing
import whenever

EARLIEST_EPOCH: typing.Final = 1721928468


class ImageTags(metaclass=abc.ABCMeta):
    def __init__(self, repo: str, tags_schema_pathname: str, error_schema_pathname: str,  earliest_epoch: int = EARLIEST_EPOCH):
        self.repo = repo
        self.tags_validator: jsonschema.validators.Draft202012Validator = self._load_json_schema(tags_schema_pathname)
        self.error_validator: jsonschema.validators.Draft202012Validator = self._load_json_schema(error_schema_pathname)
        self.earliest_epoch = earliest_epoch
        self.tag_dict: dict[str, list[tuple[int, str, str]]] = {}

    def _load_json_schema(self, pathname: str) -> jsonschema.validators.Draft202012Validator:
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

    def _load_json_page(self, url: str) -> dict[str, typing.Any]:
        tags_json = {}

        try:
            response = requests.get(url)
        except requests.exceptions.RequestException:
            sys.exit(f"ERROR: error getting url: {url}")

        try:
            tags_json = json.loads(response.text)
        except json.JSONDecodeError:
            sys.exit(f"ERROR: error decoding json: {response.text}")

        if response.status_code == 200:
            if not self.tags_validator.is_valid(tags_json):
                sys.exit(f"ERROR: unknown tags json format: {response.text}")
        else:
            if not self.error_validator.is_valid(tags_json):
                sys.exit("ERROR: unknown error json format: response.text")

        return tags_json

    @abc.abstractmethod
    def load_tags(self, page: int = 1, page_size: int = 10) -> None:
        """Load all image tags pages"""
        raise NotImplementedError


class DockerhubTags(ImageTags):
    def load_tags(self, page: int = 1, page_size: int = 10) -> None:
        """Load all image tags pages from dockerhub"""
        finished = False

        while not finished:
            url = f"https://hub.docker.com/v2/repositories/{self.repo}/tags?page={page}&page_size={page_size}"
            tags_json = self._load_json_page(url)

            finished = tags_json["next"] is None
            results = tags_json["results"]

            for result in results:
                name = result["name"]
                platform_tuples = set()

                for image in result["images"]:
                    architecture = image["architecture"]
                    os = image["os"]
                    platform_tuples.add((os, architecture))

                last_updated = result["last_updated"]
                last_updated_dt = whenever.Instant.parse_rfc3339(last_updated)
                last_updated_ts = last_updated_dt.timestamp()

                if name != "latest" and last_updated_ts >= self.earliest_epoch:
                    if len(platform_tuples) > 0:
                        tag_list = self.tag_dict.setdefault(name, [])
                        for os, architecture in platform_tuples:
                            tag_list.append((last_updated_dt.timestamp(), os, architecture))

            page += 1


class QuayTags(ImageTags):
    def load_tags(self, page: int = 1, page_size: int = 10) -> None:
        """Load all image tags pages from Quay"""
        finished = False

        while not finished:
            url = f"https://quay.io/api/v1/repository/{self.repo}/tag?page={page}&limit={page_size}"
            tags_json = self._load_json_page(url)

            finished = tags_json.get("has_additional", False) is False
            results = tags_json.get("tags", [])

            for result in results:
                name = result["name"]
                last_modified = result["last_modified"]
                last_modified_dt = whenever.Instant.parse_rfc2822(last_modified)
                last_modified_ts = last_modified_dt.timestamp()

                if name != "latest" and last_modified_ts >= self.earliest_epoch:
                    tag_list = self.tag_dict.setdefault(name, [])
                    tag_list.append((last_modified_ts, "", ""))

            page += 1

tags_to_build: list[str] = []

dockerhub_tags = DockerhubTags("ncbi/egapx", ".github/workflows/dockerhub-tags.schema", ".github/workflows/dockerhub-error.schema")
dockerhub_tags.load_tags()

quay_tags = QuayTags("galaxy/egpax", ".github/workflows/quay-tags.schema", ".github/workflows/quay-error.schema")
quay_tags.load_tags()

for tag in dockerhub_tags.tag_dict.keys():
    for dockerhub_ts, os, arch in dockerhub_tags.tag_dict[tag]:
        if tag not in quay_tags.tag_dict:
            tags_to_build.append(tag)
        else:
            for quay_ts, _, _ in  quay_tags.tag_dict[tag]:
                if dockerhub_ts > quay_ts:
                    tags_to_build.append(tag)


print (tags_to_build)
