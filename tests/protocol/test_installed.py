"""mypal_protocol comes from the engine repo as a dependency, not a local copy.

The canonical package and its full test suite live in mypal-engine. This
checks only that the client gets it from there and can build the register
message it needs.
"""

import pathlib

import mypal_protocol

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_protocol_is_installed_not_vendored():
    location = pathlib.Path(mypal_protocol.__file__).resolve()
    assert REPO_ROOT not in location.parents, (
        f"mypal_protocol imported from inside this repo ({location}). It must come from the "
        "mypal-protocol dependency on the engine repo; delete the local copy."
    )
    assert not (REPO_ROOT / "mypal_protocol").exists(), "a vendored mypal_protocol/ directory reappeared"


def test_protocol_exposes_what_the_client_needs():
    from mypal_protocol import PROTOCOL_VERSION, RegisterMessage

    msg = RegisterMessage(node_id="n", platform="cli", protocol_version=PROTOCOL_VERSION)
    assert msg.protocol_version == PROTOCOL_VERSION
