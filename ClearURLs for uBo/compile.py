# Original license:
# Copyright © 2021 rusty-snake
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# this code has been modified by https://github.com/iam-py-test, as to improve compatibility and fix issues

import json
import sys
from datetime import date
from typing import IO

import requests  # type: ignore

HEAD = """\
! Title: ClearURLs for uBo - List extension
! Homepage: https://github.com/DandelionSprout/adfilt/discussions/163
! Last updated: {date}
! Expires: 1 day
! Note: This was based off of https://gist.github.com/rusty-snake/5cd83a87d680ecbd03e79a1a06758207, which is based off of https://github.com/ClearURLs/Rules. The maintainers of Adfilt (DandelionSprout and iam-py-test, and contributors) have made some modifications as to keep it up-to-date with the source and to fix issues

"""
KNOWN_BAD_FILTERS = [
    "$removeparam=/^ref_?=/",
    "$removeparam=sa,domain=google.*",
    "$removeparam=usg,domain=google.*",
    "$removeparam=referrer",
]


def normalize_url_pattern(url_pattern: str) -> str:
    # No need for protocol and subdomain
    url_pattern = url_pattern.replace(r"^https?:\/\/(?:[a-z0-9-]+\.)*?", "", 1)
    url_pattern = url_pattern.replace(r"https?:\/\/([a-z0-9-.]*\.)", "", 1)
    url_pattern = url_pattern.replace(r"^https?:\/\/", "", 1)
    # domain= style TLD globbing
    url_pattern = url_pattern.replace(r"(?:\.[a-z]{2,}){1,}", ".*", 1)
    # Remove backslashes
    url_pattern = url_pattern.replace("\\", "")

    # Specific fixups
    url_pattern = url_pattern.replace("(?:accounts.)?", "", 1)
    url_pattern = url_pattern.replace("(?:support.)?", "", 1)
    url_pattern = url_pattern.replace("(?:yandex.*|ya.ru)", "yandex.*", 1)

    return url_pattern


def normalize_exception(exception: str) -> tuple[str, str]:
    orig_exception = exception

    exception = exception.replace(r"^https?:\/\/(?:[a-z0-9-]+\.)*?", "||", 1)
    exception = exception.replace(r"^https?:\/\/", "||", 1)
    # FIXME: |ws://
    exception = exception.replace(r"^wss?:\/\/(?:[a-z0-9-]+\.)*?", "|wss://", 1)
    exception = exception.replace(r"(?:\.[a-z]{2,}){1,}", "TLD_WILDCARD", 1)

    exception = exception.replace("=[^/?&]*", "=")
    exception = exception.replace("=.*?", "=")
    exception = exception.replace("=.", "=")
    exception = exception.replace("[^?]*\\?.*?", "*?*")
    exception = exception.replace("[^?]+.*?&?", "*?*")
    exception = exception.replace("\\?.*?", "?")
    exception = exception.replace(".*?&?", "*")
    exception = exception.replace(".*?", "*")

    exception = exception.replace("\\", "")

    if any(c in "([" for c in exception):
        exception = orig_exception
        exception = exception.replace("(?:", "(")
        return "regex", exception
    elif any(c in "/?" for c in exception):
        exception = exception.replace("TLD_WILDCARD", ".*", 1)
        exception = exception.replace("|wss://zoom.us", "|wss://zoom.us^", 1)
        return "path", exception
    else:
        exception = exception.replace("TLD_WILDCARD", ".*", 1)
        exception = exception.replace("||", "", 1)
        return "domain", exception


def expand_se(rule: str) -> list[str]:
    # https://stackoverflow.com/questions/20061268/python-regex-string-expansion
    # Is there a lib for that?
    #
    # 1. foo_(1|2)_bar -> foo_1_bar + foo_2_bar
    # 2. foo_[12]_bar -> foo_1_bar + foo_2_bar
    # 3. foo_?bar -> foobar + foo_bar
    # But foo_[a-z]*_bar -> foo_[a-z]*_bar
    raise NotImplementedError


def is_regex(rule: str) -> bool:
    return any(c in r".^$*+?{}[]\|()" for c in rule)


def write_rules(
    url_pattern: str,
    rules: list[str],
    regex_fromat: str,
    plain_format: str,
    filterlist: IO[str],
) -> None:
    for rule in rules:
        filter_ = (regex_fromat if is_regex(rule) else plain_format).format(
            rule, url_pattern
        )
        if filter_ not in KNOWN_BAD_FILTERS:
            filterlist.write(filter_ + "\n")


def getrules() -> str:
    RULES = "https://raw.githubusercontent.com/ClearURLs/Rules/master/data.min.json"
    return requests.get(RULES).text


def main() -> int:
    data_min_json = json.loads(getrules())
    filterlist = open("clear_urls_uboified.txt", "w")
    filterlist.write(HEAD.format(date=date.today().strftime("%d/%m/%Y")))

    # TODO: referralMarketing
    providers = {
        provider["urlPattern"]: provider["rules"]
        for provider in data_min_json["providers"].values()
        if provider["rules"]
    }

    # TODO:
    # - Dollars
    # $removeparam=\$original_url,domain=reddit.co
    # - URL encoded
    # $removeparam=%24deep_link,domain=reddit.com
    # - Better is_regex
    # $removeparam=/^p\[\]=/,domain=flipkart.com
    for url_pattern, rules in providers.items():
        url_pattern = normalize_url_pattern(url_pattern)
        rules = [rule.replace("(?:%3F)?", "", 1).replace("(?:", "(") for rule in rules]
        if url_pattern == ".*":
            write_rules(
                url_pattern,
                rules,
                "$removeparam=/^{0}=/",
                "$removeparam={0}",
                filterlist,
            )
        elif "/" in url_pattern:
            write_rules(
                url_pattern,
                rules,
                "||{1}$removeparam=/^{0}=/",
                "||{1}$removeparam={0}",
                filterlist,
            )
        else:
            write_rules(
                url_pattern,
                rules,
                "$removeparam=/^{0}=/,domain={1}",
                "$removeparam={0},domain={1}",
                filterlist,
            )

    exceptions = [
        exception
        for provider in data_min_json["providers"].values()
        for exception in provider["exceptions"]
    ]
    for exception in exceptions:
        kind, exception = normalize_exception(exception.replace("\\\\", "\\"))
        if kind == "regex":
            filterlist.write("@@/{0}/$removeparam".format(exception) + "\n")
        elif kind == "path":
            filterlist.write("@@{0}$removeparam".format(exception) + "\n")
        elif kind == "domain":
            filterlist.write("@@$removeparam,domain={0}".format(exception) + "\n")
        else:
            raise ValueError

    return 0


if __name__ == "__main__":
    sys.exit(main())