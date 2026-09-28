from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, Mock, call

from scanner.fsscan import FsScanner
from scanner.models.videos import VideoInfo


class TargetedScanTest(IsolatedAsyncioTestCase):
	async def test_only_target_directory_is_deleted_and_reidentified(self):
		root = "/video/Hunter x Hunter (2011)"
		current = f"{root}/S02E01.mp4"
		stale = f"{root}/old.mp4"
		other_show = "/video/Another Show/S01E01.mp4"
		client = MagicMock()
		client.get_videos_info = AsyncMock(
			return_value=VideoInfo(
				paths={current, stale, other_show}, unmatched=set(), guesses={}
			)
		)
		client.delete_videos = AsyncMock()
		scanner = FsScanner(client, MagicMock())
		scanner.walk_fs = Mock(return_value={current})
		scanner._register = AsyncMock()

		await scanner.scan(path=root, remove_deleted=True, reidentify_existing=True)

		client.delete_videos.assert_awaited_once_with({stale})
		scanner._register.assert_has_awaits(
			[call({current}, replace_links=True)]
		)
		self.assertEqual(scanner._register.await_count, 1)
