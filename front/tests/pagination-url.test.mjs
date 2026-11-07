import assert from "node:assert/strict";
import { test } from "node:test";
import { normalizePaginationUrl } from "../src/query/pagination-url.ts";

const browserUrl =
	"https://media.zevky.com/series/that-time-i-got-reincarnated-as-a-slime";
const reportedUrl =
	"http://media.zevky.com/api/series/that-time-i-got-reincarnated-as-a-slime/entries?query=&filter=%28kind+eq+episode+or+isAvailable+eq+true+or+content+eq+story%29&includeSeasons=true&after=WzQxLDQyOV0";

test("upgrades the reported season cursor without changing path or filters", () => {
	assert.equal(
		normalizePaginationUrl(reportedUrl, browserUrl),
		reportedUrl.replace(/^http:/, "https:"),
	);
});

test("also upgrades pagination on the emergency origin", () => {
	assert.equal(
		normalizePaginationUrl(
			"http://media2.zevky.com/api/videos?after=abc",
			"https://media2.zevky.com/admin/unmatched",
		),
		"https://media2.zevky.com/api/videos?after=abc",
	);
});

test("preserves relative first-page requests", () => {
	const url = "/api/series/slime/entries?includeSeasons=true";
	assert.equal(normalizePaginationUrl(url, browserUrl), url);
});

test("preserves HTTPS pagination", () => {
	const url = reportedUrl.replace(/^http:/, "https:");
	assert.equal(normalizePaginationUrl(url, browserUrl), url);
});

test("does not redirect an API on another host", () => {
	const url = "http://another-server.example/api/entries?after=abc";
	assert.equal(normalizePaginationUrl(url, browserUrl), url);
});

test("does not change a different API port", () => {
	const url = "http://media.zevky.com:8901/api/entries?after=abc";
	assert.equal(normalizePaginationUrl(url, browserUrl), url);
});

test("supports HTTPS pages and HTTP links using the same explicit port", () => {
	assert.equal(
		normalizePaginationUrl(
			"http://media.zevky.com:8443/api/entries?after=abc",
			"https://media.zevky.com:8443/series/slime",
		),
		"https://media.zevky.com:8443/api/entries?after=abc",
	);
});

test("preserves HTTP development environments", () => {
	const url = "http://localhost:8901/api/entries?after=abc";
	assert.equal(normalizePaginationUrl(url, "http://localhost:8901/"), url);
});

test("preserves native and server-side requests without a browser URL", () => {
	assert.equal(normalizePaginationUrl(reportedUrl), reportedUrl);
});

test("leaves malformed URLs to the existing fetch error handling", () => {
	assert.equal(normalizePaginationUrl("http://[", browserUrl), "http://[");
});
