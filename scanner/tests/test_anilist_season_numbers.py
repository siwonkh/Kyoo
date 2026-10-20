from datetime import datetime
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from scanner.identifiers.anilist import (
	AnimeListData,
	AnimeListDb,
	identify_anilist,
	normalize_title,
)
from scanner.models.videos import Guess


class AbsoluteAnimeSeasonTest(IsolatedAsyncioTestCase):
	async def test_explicit_tvdb_seasons_and_absolute_numbers(self):
		anime = AnimeListDb.AnimeEntry.from_xml(
			b'<anime anidbid="8550" tvdbid="252322" defaulttvdbseason="a" '
			b'tmdbtv="46298"><name>Hunter x Hunter (2011)</name><mapping-list>'
			b'<mapping anidbseason="1" tvdbseason="1" start="1" end="58"/>'
			b'<mapping anidbseason="1" tvdbseason="2" start="59" end="136" offset="-58"/>'
			b'<mapping anidbseason="1" tvdbseason="3" start="137" end="148" offset="-136"/>'
			b'</mapping-list></anime>'
		)
		data = AnimeListData(
			fetched_at=datetime.now(),
			titles={normalize_title("Hunter x Hunter 2011"): "8550"},
			animes={"8550": anime},
			tvdb_anidb={"252322": ["8550"]},
		)
		cases = [
			((1, 1), (1, 1)),
			((2, 1), (2, 1)),
			((2, 78), (2, 78)),
			((3, 12), (3, 12)),
			((None, 59), (2, 1)),
			((2, 85), (2, 27)),
		]
		with patch(
			"scanner.identifiers.anilist.get_anilist_data",
			new=AsyncMock(return_value=data),
		):
			for (season, episode), expected in cases:
				with self.subTest(season=season, episode=episode):
					guess = Guess(
						title="Hunter x Hunter 2011",
						kind="episode",
						extra_kind=None,
						years=[2011],
						episodes=[Guess.Episode(season=season, episode=episode)],
						external_id={},
						from_="guessit",
					)
					result = await identify_anilist("", guess)
					self.assertEqual(
						(result.episodes[0].season, result.episodes[0].episode),
						expected,
					)
