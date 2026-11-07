// Keep playable titles visible even when providers attach them to collections.
// The explicit collection filter still opens the collection-only browse view.
export const showListParams = (filter?: string) => ({
	ignoreInCollection: false,
	filter: /\bkind\s+eq\s+collection\b/.test(filter ?? "")
		? filter
		: filter
			? `kind ne collection and (${filter})`
			: "kind ne collection",
});
