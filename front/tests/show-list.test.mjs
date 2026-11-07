import assert from "node:assert/strict";
import test from "node:test";
import { showListParams } from "../src/query/show-list.ts";

test("default browse includes collection members as individual titles", () => {
	assert.deepEqual(showListParams(), {
		ignoreInCollection: false,
		filter: "kind ne collection",
	});
});

test("genre and OR filters cannot bring collection cards back", () => {
	assert.deepEqual(showListParams("genres has action or genres has fantasy"), {
		ignoreInCollection: false,
		filter: "kind ne collection and (genres has action or genres has fantasy)",
	});
});

test("explicit collection browse preserves its filters", () => {
	const filter = "kind eq collection and genres has animation";
	assert.equal(showListParams(filter).filter, filter);
});

test("movie and series filters keep collection members visible", () => {
	for (const kind of ["movie", "serie"]) {
		assert.deepEqual(showListParams(`kind eq ${kind}`), {
			ignoreInCollection: false,
			filter: `kind ne collection and (kind eq ${kind})`,
		});
	}
});
