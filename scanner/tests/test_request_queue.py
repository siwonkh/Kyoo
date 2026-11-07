import json
import os
from asyncio import CancelledError
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, skipUnless
from unittest.mock import AsyncMock, Mock, patch

import asyncpg

from scanner.models.request import Request
from scanner.requests import RequestCreator, RequestProcessor


class RequestRecoveryTests(IsolatedAsyncioTestCase):
	async def test_listener_checks_on_startup_and_without_notification(self):
		db = SimpleNamespace(
			add_termination_listener=Mock(),
			remove_termination_listener=Mock(),
			add_listener=AsyncMock(),
			remove_listener=AsyncMock(),
		)

		@asynccontextmanager
		async def database():
			yield db

		processor = RequestProcessor(None, None)
		processor.process_all = AsyncMock(side_effect=[None, CancelledError()])
		with (
			patch("scanner.requests.get_db", database),
			patch("scanner.requests.REQUEST_POLL_INTERVAL", 0.01),
		):
			with self.assertRaises(CancelledError):
				await processor.listen(Mock())
		self.assertEqual(processor.process_all.await_count, 2)
		db.remove_listener.assert_awaited_once()

	async def test_database_failure_yields_instead_of_busy_looping(self):
		processor = RequestProcessor(None, None)
		processor.process_request = AsyncMock(side_effect=[RuntimeError("DB unavailable"), False])
		with self.assertLogs("scanner.requests", level="ERROR"):
			await processor.process_all()
		self.assertEqual(processor.process_request.await_count, 1)
		self.assertFalse(processor._processing)
		await processor.process_all()
		self.assertEqual(processor.process_request.await_count, 2)


class TemporaryQueue:
	"""Run the production methods against a transaction-local temporary table."""

	def __init__(self, db):
		self.db = db
		self.claimed = None

	async def fetchrow(self, sql, *args):
		self.claimed = await self.db.fetchrow(sql.replace("scanner.requests", "pg_temp.request_queue_test"), *args)
		# Stop process_request before contacting a metadata provider or Kyoo API.
		return None

	async def fetchmany(self, sql, args):
		return await self.db.fetchmany(sql.replace("scanner.requests", "pg_temp.request_queue_test").replace("requests.videos", "request_queue_test.videos"), args)

	async def execute(self, sql, *args):
		if sql.lower().startswith("notify "):
			return "NOTIFY"  # Do not wake the production worker from this test.
		return await self.db.execute(sql.replace("scanner.requests", "pg_temp.request_queue_test"), *args)


@skipUnless(os.environ.get("KYOO_SCANNER_TEST_DB_FROM_ENV") == "1", "enable temporary-table PostgreSQL tests explicitly")
class RequestQueuePostgresTests(IsolatedAsyncioTestCase):
	async def asyncSetUp(self):
		self.db = await asyncpg.connect(
			host=os.environ.get("PGHOST", "postgres"),
			user=os.environ.get("PGUSER", "kyoo"),
			password=os.environ.get("PGPASSWORD", "password"),
			database=os.environ.get("PGDATABASE", "kyoo"),
		)
		self.transaction = self.db.transaction()
		await self.db.set_type_codec("jsonb", schema="pg_catalog", encoder=json.dumps, decoder=json.loads)
		await self.transaction.start()
		await self.db.execute("""
			create temporary table request_queue_test (
				pk serial primary key, kind text not null, title text not null, year integer,
				external_id jsonb not null default '{}', videos jsonb not null default '[]',
				status text not null default 'pending', started_at timestamptz,
				error jsonb, created_at timestamptz not null default now(),
				unique nulls not distinct (kind,title,year)
			);
			insert into request_queue_test (kind,title,status) values ('movie','old failure','failed');
			analyze request_queue_test;
			insert into request_queue_test (kind,title) values
				('movie','movie 1'),('movie','movie 2'),('movie','movie 3'),('movie','movie 4');
		""")
		self.queue = TemporaryQueue(self.db)

	async def asyncTearDown(self):
		await self.transaction.rollback()
		await self.db.close()

	async def test_stale_statistics_claim_exactly_one_and_preserve_other_work(self):
		# The old IN (... LIMIT 1 FOR UPDATE) query marked all four rows running
		# with the small-queue statistics above. Exercise the actual fixed method.
		processor = RequestProcessor(None, None)
		processor._database = self.queue
		for expected in range(1, 5):
			await processor.process_request()
			self.assertEqual(self.queue.claimed["pk"], expected + 1)
			self.assertEqual(await self.db.fetchval("select count(*) from request_queue_test where status='running'"), expected)
		await processor.process_request()
		self.assertIsNone(self.queue.claimed)

	async def test_reclaims_expired_but_leaves_recent_running_work_alone(self):
		await self.db.execute("""
			update request_queue_test set status='running',started_at=now() where pk>1;
			update request_queue_test set started_at=now()-interval '31 minutes' where pk=3;
		""")
		processor = RequestProcessor(None, None)
		processor._database = self.queue
		await processor.process_request()
		self.assertEqual(self.queue.claimed["pk"], 3)
		await processor.process_request()
		self.assertIsNone(self.queue.claimed)

	async def test_reenqueue_deduplicates_identical_videos_and_keeps_running_state(self):
		creator = RequestCreator(self.queue)
		request = Request(kind="movie", title="movie 1", year=None, external_id={}, videos=[Request.Video(id="test-video", episodes=[])])
		await creator.enqueue([request])
		await self.db.execute("update request_queue_test set status='running',started_at=now() where title='movie 1'")
		await creator.enqueue([request])
		row = await self.db.fetchrow("select status,jsonb_array_length(videos) as videos from request_queue_test where title='movie 1'")
		self.assertEqual(row["status"], "running")
		self.assertEqual(row["videos"], 1)
