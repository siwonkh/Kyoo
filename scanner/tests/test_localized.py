import unicodedata
import unittest
from collections.abc import Sequence
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from scanner.identifiers.anilist import AnimeListData, AnimeListDb, normalize_title
from scanner.identifiers.guess.guess import guessit
from scanner.identifiers.guess.localized import MARKERS, Markers, localized
from scanner.identifiers.identify import identify


def values(name: str, *, titles: Sequence[str] = ()) -> dict:
	return {
		key: [match.value for match in matches]
		for key, matches in guessit(
			name, expected_titles=[normalize_title(title) for title in titles]
		).items()
	}


class LocalizedFilenameTests(unittest.TestCase):
	def test_season_and_episode_markers(self):
		for name, season, episode in (
			("작품 2기 - 9화.mkv", 2, 9),
			("작품 시즌 2 - 제9화.mkv", 2, 9),
			("작품 시즌2 에피소드9.mkv", 2, 9),
			("작품 제2기 - 제09회.mkv", 2, 9),
			("작품_2기_009화.mkv", 2, 9),
			("作品 2期 - 第14話.mkv", 2, 14),
			("作品 シーズン2 - 14話.mkv", 2, 14),
			("Example Staffel 2 Folge 14.mkv", 2, 14),
			("Example.staffel.2.folge.14.mkv", 2, 14),
			("Example Saison 2 Episode 14.mkv", 2, 14),
			("Example Temporada 2 Episodio 14.mkv", 2, 14),
			("Example Stagione 2 Episodio 14.mkv", 2, 14),
			("Example - S02E14.mkv", 2, 14),
		):
			with self.subTest(name=name):
				ret = values(name)
				self.assertEqual(ret["season"], [season])
				self.assertEqual(ret["episode"], [episode])
				self.assertEqual(ret["type"], ["episode"])

	def test_episode_without_season(self):
		for label in ("9화", "9회", "제9화", "第9話", "Folge 9"):
			with self.subTest(label=label):
				ret = values(f"Example - {label}.mkv")
				self.assertEqual(ret["title"], ["Example"])
				self.assertEqual(ret["episode"], [9])
				self.assertNotIn("season", ret)

	def test_composed_and_decomposed_filenames_keep_match_offsets(self):
		for form in ("NFC", "NFD"):
			name = unicodedata.normalize(form, "작품 시즌 2 - 제9화.mkv")
			ret = guessit(name)
			self.assertEqual(ret["season"][0].value, 2)
			self.assertEqual(ret["episode"][0].value, 9)
			for key in ("season", "episode"):
				match = ret[key][0]
				self.assertEqual(name[match.start : match.end], match.raw)

	def test_filename_season_overrides_directory(self):
		ret = values("/video/Example/시즌 1/Example 2기 - 9화.mkv")
		self.assertEqual(ret["season"], [2])
		self.assertEqual(ret["episode"], [9])

	def test_directory_season_is_used_when_filename_has_only_episode(self):
		ret = values("/video/Example/시즌 2/Example - 9화.mkv")
		self.assertEqual(ret["season"], [2])
		self.assertEqual(ret["episode"], [9])

	def test_marker_fragments_in_title_words_are_untouched(self):
		for title in ("9화의 비밀", "2기의 기억", "Folge14er", "Staffel2er"):
			with self.subTest(title=title):
				ret = values(f"{title} (2021).mkv")
				self.assertNotIn("season", ret)
				self.assertNotIn("episode", ret)
				self.assertEqual(ret["type"], ["movie"])
				self.assertEqual(ret["title"], [title])

	def test_known_titles_retain_localized_markers(self):
		for title in ("Example 2기", "Example 2期", "Example Staffel 2", "Example 9화"):
			with self.subTest(title=title):
				ret = values(f"{title} - 10화.mkv", titles=[title])
				self.assertEqual(ret["title"], [title])
				self.assertEqual(ret["episode"], [10])
				self.assertNotIn("season", ret)

	def test_existing_expected_titles_and_season_fixups(self):
		for name, title, titles, season, episode in (
			(
				"Owarimonogatari S2 E15.mkv",
				"Owarimonogatari S2",
				["Owarimonogatari S2"],
				None,
				15,
			),
			(
				"JoJo's Bizarre Adventure - Diamond is Unbreakable - 12.mkv",
				"JoJo's Bizarre Adventure - Diamond is Unbreakable",
				["JoJo's Bizarre Adventure - Diamond is Unbreakable"],
				None,
				12,
			),
			("Example 2nd Season - 12.mkv", "Example", [], 2, 12),
			("Example Season 2 - 08.mkv", "Example", [], 2, 8),
		):
			with self.subTest(name=name):
				ret = values(name, titles=titles)
				self.assertEqual(ret["title"], [title])
				self.assertEqual(ret.get("season"), [season] if season else None)
				self.assertEqual(ret["episode"], [episode])

	def test_excluded_properties_disable_localized_markers(self):
		ret = guessit(
			"Example 2기 - 9화.mkv", extra_flags={"excludes": ["season", "episode"]}
		)
		self.assertNotIn("season", ret)
		self.assertNotIn("episode", ret)
		self.assertEqual(ret["type"][0].value, "movie")

	def test_language_can_be_added_through_marker_data(self):
		with patch.dict(
			MARKERS,
			{
				"test": Markers(
					season_suffix=("testseason",), episode_suffix=("testepisode",)
				)
			},
		):
			ret = localized().matches("Example 3testseason - 7testepisode.mkv")
			self.assertEqual([m.value for m in ret.named("season")], [3])
			self.assertEqual([m.value for m in ret.named("episode")], [7])


class AnimeMappingTests(unittest.IsolatedAsyncioTestCase):
	async def asyncSetUp(self):
		# A small offline fixture using the real Re:Zero season/cour mapping.
		self.base = "Re: 제로부터 시작하는 이세계 생활"
		self.cour = f"{self.base} 2기 Part2"
		self.data = AnimeListData(
			fetched_at=datetime(2021, 1, 1, tzinfo=UTC),
			titles={
				normalize_title(self.base): "11370",
				normalize_title(self.cour): "15593",
			},
			animes={
				"11370": AnimeListDb.AnimeEntry(
					anidbid="11370",
					tvdbid="305089",
					defaulttvdbseason=1,
					name="Re:Zero",
				),
				"15593": AnimeListDb.AnimeEntry(
					anidbid="15593",
					tvdbid="305089",
					defaulttvdbseason=2,
					episodeoffset=13,
					name="Re:Zero Part2",
				),
			},
			tvdb_anidb={"305089": ["11370", "15593"]},
		)
		for module in ("scanner.identifiers.identify", "scanner.identifiers.anilist"):
			mock = patch(
				f"{module}.get_anilist_data", new=AsyncMock(return_value=self.data)
			)
			mock.start()
			self.addCleanup(mock.stop)

	async def test_korean_cour_alias_uses_database_offset(self):
		for label in ("2쿨", "Part2", "Part 2", "Cour 2"):
			with self.subTest(label=label):
				video = await identify(
					f"Re_제로부터 시작하는 이세계 생활 2기 {label} (2021) - 9화.mkv"
				)
				self.assertEqual(video.guess.title, "Re:Zero")
				self.assertEqual(video.guess.from_, "anilist")
				self.assertEqual(video.guess.external_id["anidb"], "15593")
				self.assertEqual(
					[(e.season, e.episode) for e in video.guess.episodes], [(2, 22)]
				)
				self.assertIsNone(video.part)

	async def test_explicit_episode_number_is_preserved(self):
		video = await identify("Re_제로부터 시작하는 이세계 생활 - S02E14.mkv")
		self.assertEqual(video.guess.external_id["anidb"], "11370")
		self.assertEqual(
			[(e.season, e.episode) for e in video.guess.episodes], [(2, 14)]
		)

	async def test_cour_labels_do_not_assume_a_fixed_offset(self):
		self.data.animes["15593"].episodeoffset = 7
		video = await identify("Re_제로부터 시작하는 이세계 생활 2기 2쿨 - 9화.mkv")
		self.assertEqual(
			[(e.season, e.episode) for e in video.guess.episodes], [(2, 16)]
		)

	async def test_missing_title_database_still_parses_korean(self):
		self.data.titles.clear()
		with (
			patch(
				"scanner.identifiers.identify.get_anilist_data",
				new=AsyncMock(side_effect=RuntimeError("offline")),
			),
			self.assertLogs("scanner.identifiers.identify", level="ERROR"),
		):
			video = await identify("알려지지 않은 작품 2기 - 9화.mkv")
		self.assertEqual(video.guess.kind, "episode")
		self.assertEqual(
			[(e.season, e.episode) for e in video.guess.episodes], [(2, 9)]
		)

	async def test_video_parts_and_versions_keep_the_same_rendering(self):
		first = await identify("Example 2기 - 9화 part1 v2.mkv")
		second = await identify("Example 2기 - 9화 part2 v3.mkv")
		self.assertEqual((first.part, first.version), (1, 2))
		self.assertEqual((second.part, second.version), (2, 3))
		self.assertEqual(first.rendering, second.rendering)
		self.assertEqual(first.path, "Example 2기 - 9화 part1 v2.mkv")


class CourAliasTests(unittest.TestCase):
	def test_equivalent_cour_labels(self):
		for label in ("2쿨", "2 쿨", "Part2", "Part 2", "Cour 2", "第2クール"):
			with self.subTest(label=label):
				self.assertEqual(
					normalize_title(f"Example {label}"),
					normalize_title("Example Part2"),
				)

	def test_unrelated_title_words_survive(self):
		for title in ("Part2way", "2쿨한 이야기", "2クールな物語"):
			self.assertNotEqual(normalize_title(title), normalize_title("Part2"))


if __name__ == "__main__":
	unittest.main()
