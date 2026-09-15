"""Localized filename markers shared by parsing and anime title lookup."""

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass

from guessit.rules.common.pattern import is_disabled
from rebulk import Rebulk


@dataclass(frozen=True)
class Markers:
	season_prefix: tuple[str, ...] = ()
	season_suffix: tuple[str, ...] = ()
	episode_prefix: tuple[str, ...] = ()
	episode_suffix: tuple[str, ...] = ()
	number_prefix: tuple[str, ...] = ()
	cour_prefix: tuple[str, ...] = ()
	cour_suffix: tuple[str, ...] = ()


# Add a language's words here and filename examples in tests/test_localized.py.
# Existing GuessIt markers do not need to be repeated.
MARKERS = {
	"ko": Markers(
		season_prefix=("시즌",),
		season_suffix=("기",),
		episode_prefix=("에피소드",),
		episode_suffix=("화", "회"),
		number_prefix=("제",),
		cour_suffix=("쿨",),
	),
	"ja": Markers(
		season_prefix=("シーズン",),
		season_suffix=("期",),
		episode_suffix=("話",),
		number_prefix=("第",),
		cour_suffix=("クール",),
	),
	"de": Markers(season_prefix=("Staffel",), episode_prefix=("Folge",)),
	"en": Markers(cour_prefix=("part", "cour")),
}


def _words(words: tuple[str, ...]) -> str:
	# Match both composed and decomposed filenames without rewriting the path:
	# GuessIt match offsets are also used to group versions and multi-file videos.
	variants = {
		unicodedata.normalize(form, word) for word in words for form in ("NFC", "NFD")
	}
	return (
		"(?:"
		+ "|".join(
			re.escape(word)
			for word in sorted(variants, key=lambda word: (-len(word), word))
		)
		+ ")"
	)


def _patterns(
	prefix: tuple[str, ...],
	suffix: tuple[str, ...],
	number_prefix: tuple[str, ...],
	digits: int,
) -> Iterator[str]:
	separator = r"[\s._-]*"
	number = rf"\d{{1,{digits}}}"
	if number_prefix:
		number = rf"(?:{_words(number_prefix)}{separator})?{number}"
	# Require a separate filename token so title words containing markers survive.
	before, after = r"(?<![^\W_])", r"(?![^\W_])"
	if prefix:
		yield before + _words(prefix) + separator + number + after
	if suffix:
		yield before + number + separator + _words(suffix) + after


def _number(value: str) -> int:
	match = re.search(r"\d+", value)
	assert match is not None
	return int(match[0])


def localized() -> Rebulk:
	rebulk = Rebulk().regex_defaults(flags=re.IGNORECASE)
	for markers in MARKERS.values():
		for name, digits in (("season", 2), ("episode", 4)):
			for pattern in _patterns(
				getattr(markers, f"{name}_prefix"),
				getattr(markers, f"{name}_suffix"),
				markers.number_prefix,
				digits,
			):
				rebulk.regex(
					pattern,
					name=name,
					formatter=_number,
					tags=["SxxExx", "localized"],
					disabled=lambda context, name=name: is_disabled(context, name),
				)
	return rebulk


_COUR_PATTERNS = tuple(
	re.compile(pattern, re.IGNORECASE)
	for markers in MARKERS.values()
	for pattern in _patterns(
		markers.cour_prefix, markers.cour_suffix, markers.number_prefix, 2
	)
)


def normalize_cour(title: str) -> str:
	"""Treat cour labels as anime title aliases, never as multi-file `part`s."""
	for pattern in _COUR_PATTERNS:
		title = pattern.sub(lambda match: f"Part{_number(match[0])}", title)
	return title
