"""The command line."""

from __future__ import annotations

import pytest

from spokenid import Scheme
from spokenid.cli import main


def test_new_prints_a_valid_identifier(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["new"]) == 0
    printed = capsys.readouterr().out.strip()
    assert Scheme().validate(printed)


def test_new_can_print_several(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["new", "-n", "5"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 5
    assert len(set(lines)) == 5


def test_new_honours_length(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["new", "--length", "12"]) == 0
    printed = capsys.readouterr().out.strip()
    assert len(printed.replace("-", "")) == 12


def test_check_accepts_a_good_one(capsys: pytest.CaptureFixture[str]) -> None:
    identifier = Scheme().random()
    assert main(["check", identifier]) == 0
    assert capsys.readouterr().out.strip() == identifier


def test_check_reports_repairs_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", "OOOO-OOOO"]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "0000-0000"
    assert "read 'O' as '0'" in captured.err


def test_check_fails_loudly(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", "AAAA-AAAA"]) == 1
    assert "vowel" in capsys.readouterr().err


def test_next_counts(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["next", "0000-0000"]) == 0
    assert capsys.readouterr().out.strip() == "0000-001X"


def test_next_takes_a_step(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["next", "0000-0000", "--step", "26"]) == 0
    assert Scheme().validate(capsys.readouterr().out.strip())


def test_next_on_nonsense_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["next", "nonsense"]) == 1
    assert capsys.readouterr().err


def test_say(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["say", "4KM7-PC2M"]) == 0
    assert capsys.readouterr().out.strip() == "4 Kilo Mike 7, Papa Charlie 2 Mike"


def test_describe(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["describe", "--members", "100000"]) == 0
    out = capsys.readouterr().out
    assert "8,031,810,176" in out
    assert "100,000" in out


def test_alphabet(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["alphabet"]) == 0
    out = capsys.readouterr().out
    assert "0123456789CDFHJKMNPQRTVWXY" in out
    assert "no vowels" in out
    assert "looks like '5'" in out


def test_no_check_flag(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["new", "--no-check", "--length", "4"]) == 0
    assert len(capsys.readouterr().out.strip()) == 4


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--version"])
    assert caught.value.code == 0
    assert "spokenid" in capsys.readouterr().out


def test_no_command_is_an_error() -> None:
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2


def test_python_dash_m_works() -> None:
    """`python -m spokenid` has to run, and nothing else covers __main__."""
    import subprocess
    import sys

    finished = subprocess.run(
        [sys.executable, "-m", "spokenid", "new"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert Scheme().validate(finished.stdout.strip())
