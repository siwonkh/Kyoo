from copy import deepcopy
from datetime import date
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from aiohttp import ClientConnectionError, ClientResponseError, RequestInfo
from langcodes import Language
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from scanner.providers.thetvdb import TVDB


def response_error(path: str, status: int) -> ClientResponseError:
	url = URL(f"https://api4.thetvdb.com/v4/{path}")
	return ClientResponseError(
		RequestInfo(url, "GET", CIMultiDictProxy(CIMultiDict()), url),
		(),
		status=status,
	)


class SeasonTranslationTests(IsolatedAsyncioTestCase):
	def setUp(self):
		# Avoid opening a session: fixtures exercise the provider without TVDB access.
		self.provider = object.__new__(TVDB)
		self.provider._image_map = [
			{"id": 1, "recordType": "season", "slug": "posters"},
			{"id": 2, "recordType": "season", "slug": "backgrounds"},
			{"id": 3, "recordType": "season", "slug": "banners"},
		]
		self.info = {
			"number": 1,
			"seriesId": "371310",
			"nameTranslations": ["kor", "por", "deu"],
			"overviewTranslations": ["kor"],
			"episodes": [
				{"aired": "2021-01-10"},
				{"aired": None},
				{"aired": "2021-12-19"},
			],
			"artwork": [
				{"type": 1, "language": "kor", "image": "https://example.com/kor.jpg"},
			],
		}
		self.translations = {
			"kor": {"name": "시즌 1", "overview": "한국어 설명"},
			"por": {"name": "Temporada 1", "overview": "Descrição"},
			"deu": {"name": "Staffel 1", "overview": "Beschreibung"},
		}
		self.failures: dict[str, Exception] = {}
		self.provider._get = AsyncMock(side_effect=self.get)

	async def get(self, path: str, **kwargs):
		if path == "seasons/123/extended":
			return {"data": deepcopy(self.info)}
		language = path.rsplit("/", 1)[-1]
		if language in self.failures:
			raise self.failures[language]
		return {"data": self.translations[language]}

	async def test_missing_translation_keeps_other_languages_and_season_metadata(self):
		self.failures["deu"] = response_error("seasons/123/translations/deu", 404)
		with self.assertLogs("scanner.providers.thetvdb", level="WARNING") as logs:
			season = await self.provider.get_seasons(123)

		self.assertEqual(
			set(season.translations), {Language.get("ko"), Language.get("pt")}
		)
		self.assertEqual(season.translations[Language.get("ko")].name, "시즌 1")
		self.assertEqual(season.translations[Language.get("pt")].name, "Temporada 1")
		self.assertEqual(
			season.translations[Language.get("ko")].poster,
			"https://example.com/kor.jpg",
		)
		self.assertEqual(season.season_number, 1)
		self.assertEqual(season.start_air, date(2021, 1, 10))
		self.assertEqual(season.end_air, date(2021, 12, 19))
		self.assertEqual(season.external_id["tvdb"][0].serie_id, "371310")
		self.assertEqual(season.external_id["tvdb"][0].season, 1)
		self.assertIn("season=123, language=deu", logs.output[0])

	async def test_all_missing_translations_still_returns_season(self):
		self.failures = {
			language: response_error(f"seasons/123/translations/{language}", 404)
			for language in self.translations
		}
		with self.assertLogs("scanner.providers.thetvdb", level="WARNING"):
			season = await self.provider.get_seasons(123)
		self.assertEqual(season.translations, {})
		self.assertEqual(season.season_number, 1)

	async def test_no_translation_languages_returns_season(self):
		self.info["nameTranslations"] = []
		self.info["overviewTranslations"] = []
		season = await self.provider.get_seasons(123)
		self.assertEqual(season.translations, {})
		self.provider._get.assert_awaited_once_with("seasons/123/extended")

	async def test_overview_only_translations_work_without_english_or_names(self):
		self.info["nameTranslations"] = []
		self.info["overviewTranslations"] = ["pt,kor,deu"]
		self.translations["pt"] = self.translations.pop("por")
		self.translations["pt"]["name"] = None
		self.translations["kor"]["name"] = None
		self.failures["deu"] = response_error("seasons/123/translations/deu", 404)
		with self.assertLogs("scanner.providers.thetvdb", level="WARNING"):
			season = await self.provider.get_seasons(123)
		self.assertEqual(
			set(season.translations), {Language.get("ko"), Language.get("pt")}
		)
		self.assertIsNone(season.translations[Language.get("ko")].name)
		self.assertEqual(
			season.translations[Language.get("ko")].description, "한국어 설명"
		)
		self.assertEqual(
			season.translations[Language.get("pt")].description, "Descrição"
		)

	async def test_comma_separated_and_overview_only_languages_keep_correct_pairs(self):
		self.info["nameTranslations"] = ["kor,por", "kor"]
		self.info["overviewTranslations"] = ["deu,por"]
		season = await self.provider.get_seasons(123)
		for language, translation in self.translations.items():
			self.assertEqual(
				season.translations[Language.get(language)].name, translation["name"]
			)
		self.assertEqual(self.provider._get.await_count, 4)

	async def test_other_http_errors_are_not_skipped(self):
		for status in (401, 403, 429, 500):
			with self.subTest(status=status):
				error = response_error("seasons/123/translations/deu", status)
				self.failures["deu"] = error
				with self.assertRaises(ClientResponseError) as raised:
					await self.provider.get_seasons(123)
				self.assertIs(raised.exception, error)

	async def test_connection_errors_are_not_skipped(self):
		error = ClientConnectionError("TVDB unavailable")
		self.failures["deu"] = error
		with self.assertRaises(ClientConnectionError) as raised:
			await self.provider.get_seasons(123)
		self.assertIs(raised.exception, error)

	async def test_missing_season_is_not_skipped(self):
		error = response_error("seasons/123/extended", 404)
		self.provider._get.side_effect = error
		with self.assertRaises(ClientResponseError) as raised:
			await self.provider.get_seasons(123)
		self.assertIs(raised.exception, error)

	async def test_invalid_translation_response_is_not_skipped(self):
		async def get_invalid(path: str, **kwargs):
			return await self.get(path, **kwargs) if path.endswith("extended") else {}

		self.provider._get.side_effect = get_invalid
		with self.assertRaises(KeyError):
			await self.provider.get_seasons(123)
