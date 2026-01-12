// api/token.js
import { generateClientToken } from '@vercel/blob';

export default async function handler(request, response) {
    // 1. Only allow POST requests
    if (request.method !== 'POST') {
        return response.status(405).json({ error: 'Method not allowed' });
    }

    try {
        // 2. Parse the body. The client sends a JSON with a 'payload' field.
        const body = typeof request.body === 'string' ? JSON.parse(request.body) : request.body;

        // Extract the pathname from the specific payload structure you saw:
        // { type: "blob.generate-client-token", payload: { pathname: "...", ... } }
        const pathname = body?.payload?.pathname;

        if (!pathname) {
            return response.status(400).json({ error: 'No pathname found in request payload' });
        }

        // 3. Generate the token using your BLOB_READ_WRITE_TOKEN
        const token = await generateClientToken({
            pathname,
            access: 'public',
        });

        return response.status(200).json(token);
    } catch (error) {
        console.error("Token generation error:", error.message);
        return response.status(500).json({ error: error.message });
    }
}
