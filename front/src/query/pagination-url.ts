// Older responses can leave HTTP pagination links in the query cache even after
// the reverse proxy is fixed. Upgrade only links to the current HTTPS host.
export const normalizePaginationUrl = (url: string, browserUrl?: string) => {
	if (!browserUrl) return url;
	try {
		const current = new URL(browserUrl);
		const next = new URL(url, current);
		if (
			current.protocol === "https:" &&
			next.protocol === "http:" &&
			next.host === current.host
		) {
			next.protocol = "https:";
			return next.toString();
		}
	} catch {
		// Preserve the existing fetch error for malformed URLs.
	}
	return url;
};
