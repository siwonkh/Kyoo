import assert from "node:assert/strict";
import test from "node:test";
import { readPreparationResponse } from "../src/controllers/prepare-response.ts";

test("empty 202 preparation response is accepted without JSON parsing", async () => {
	assert.deepEqual(
		await readPreparationResponse(new Response(null, { status: 202 })),
		{ status: 202, body: null },
	);
});

test("upstream JSON error remains visible in the preparation envelope", async () => {
	const response = new Response(
		JSON.stringify({ message: "File does not exist" }),
		{ status: 404 },
	);
	assert.deepEqual(await readPreparationResponse(response), {
		status: 404,
		body: { message: "File does not exist" },
	});
});
