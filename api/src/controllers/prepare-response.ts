// The transcoder returns 202 with no body after scheduling playback preparation.
// Keep the existing public response envelope without parsing an empty body.
export const readPreparationResponse = async (response: Response) => {
	const text = await response.text();
	return {
		status: response.status,
		body: text ? JSON.parse(text) : null,
	};
};
